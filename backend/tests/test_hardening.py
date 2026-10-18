"""Hardening: onboarding input limits and AI quotas on onboarding / voice endpoints."""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.routes import onboarding, voice
from app.models import VoiceProfile


# ── Input validation ────────────────────────────────────────────────

def test_known_answers_are_accepted():
    onboarding.StepUpdate(step=0, field="pack", value="fiction")
    onboarding.StepUpdate(step=3, field="tone_preferences", value=["Lyrical", "Dark"])
    onboarding.OnboardingComplete(data={
        "pack": "general", "writing_samples": ["x" * 40_000], "style_rules": ["Present tense"], "pov_tense": "First person",
    })


@pytest.mark.parametrize("field,value", [
    ("is_admin", True),                                   # unknown field
    ("ministry_background", "x" * 5_001),                 # text too long
    ("ministry_background", {"nested": "object"}),        # wrong type
    ("signature_phrases", "not a list"),
    ("signature_phrases", ["x"] * 51),                    # too many items
    ("signature_phrases", ["x" * 501]),                   # item too long
    ("writing_samples", ["x" * 50_001]),                  # sample too long
    ("writing_samples", ["x"] * 11),                      # too many samples
])
def test_bad_answers_are_rejected(field, value):
    with pytest.raises(ValidationError):
        onboarding.StepUpdate(step=0, field=field, value=value)
    with pytest.raises(ValidationError):
        onboarding.OnboardingComplete(data={field: value})


# ── Quotas ──────────────────────────────────────────────────────────

class ProfileDB:
    def __init__(self, profile):
        self.profile = profile
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)
        return SimpleNamespace(scalar_one_or_none=lambda: self.profile)

    async def commit(self):
        return None


@pytest.fixture
def quota(monkeypatch):
    calls = []

    async def fake_quota(_db, user_id, action, _limit):
        calls.append((user_id, action))

    for module in (onboarding, voice):
        monkeypatch.setattr(module, "consume_user_quota", fake_quota)
    return calls


async def test_voice_preview_counts_against_the_daily_ai_limit(quota):
    db = ProfileDB(VoiceProfile(user_id="u1", pack="general", onboarding_data={}))
    await onboarding.voice_preview(current_user=SimpleNamespace(id="u1"), db=db)
    assert quota == [("u1", "ai_request")]


async def test_completing_onboarding_counts_only_when_it_calls_the_ai(quota, monkeypatch):
    import app.services.ai.generation as generation

    async def no_dna(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(generation, "extract_voice_dna", no_dna)
    user = SimpleNamespace(id="u1", onboarded=False)

    await onboarding.complete_onboarding(
        onboarding.OnboardingComplete(data={"pack": "general"}), user, ProfileDB(VoiceProfile(user_id="u1", onboarding_step=0)),
    )
    assert quota == []  # no samples → no AI call → free

    await onboarding.complete_onboarding(
        onboarding.OnboardingComplete(data={"pack": "general", "writing_samples": ["A sample."]}),
        user, ProfileDB(VoiceProfile(user_id="u1", onboarding_step=0)),
    )
    assert quota == [("u1", "ai_request")]


async def test_dna_report_charges_only_for_a_fresh_narrative(quota, monkeypatch):
    import app.services.ai.dna_report as dna_report
    import app.api.routes.voice as voice_routes

    async def fake_narrative(*_args):
        return "A narrative."

    async def no_timeline(*_args):
        return []

    monkeypatch.setattr(dna_report, "generate_dna_narrative", fake_narrative)
    monkeypatch.setattr(voice_routes, "get_timeline", no_timeline)

    class DB(ProfileDB):
        async def execute(self, statement):
            self.executed.append(statement)
            return SimpleNamespace(
                scalar_one_or_none=lambda: self.profile,
                scalars=lambda: SimpleNamespace(all=lambda: []),
            )

    cached = VoiceProfile(user_id="u1", pack="general", dna_narrative="Already written.")
    await voice.dna_report(current_user=SimpleNamespace(id="u1"), db=DB(cached))
    assert quota == []

    fresh = VoiceProfile(user_id="u1", pack="general", dna_narrative=None)
    result = await voice.dna_report(current_user=SimpleNamespace(id="u1"), db=DB(fresh))
    assert quota == [("u1", "ai_request")] and result["narrative"] == "A narrative."


# ── Streams ─────────────────────────────────────────────────────────

async def _drain(response):
    return [chunk async for chunk in response.body_iterator]


async def test_stream_llm_turns_a_provider_failure_into_an_error_event(monkeypatch):
    import json
    from app.api import sse

    class Failing:
        async def stream(self, **_kwargs):
            yield "Half a sent"
            raise RuntimeError("groq: 500 internal secret detail")

    monkeypatch.setattr(sse, "get_llm_client", lambda: Failing())
    events = [e async for e in sse.stream_llm([{"role": "user", "content": "hi"}], action="test")]

    assert json.loads(events[0][6:]) == {"text": "Half a sent"}
    assert json.loads(events[1][6:]) == {"error": sse.USER_FACING_ERROR}  # no provider internals leaked
    assert events[-1] == sse.SSE_DONE


async def test_chapter_stream_uses_its_own_session_and_logs_failures(monkeypatch):
    import json
    from app.api.routes import generate

    sessions = []

    class StreamSession:
        def __init__(self):
            self.added, self.executed, self.commits = [], [], 0
            sessions.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        def add(self, obj):
            self.added.append(obj)

        async def execute(self, statement):
            self.executed.append(statement)

        async def commit(self):
            self.commits += 1

    async def failing_stream(_profile, _chapter, _project, db):
        assert isinstance(db, StreamSession)  # not the (closed) request session
        yield "Opening line. "
        raise RuntimeError("provider exploded")

    async def owned(*_args, **_kwargs):
        return SimpleNamespace(id="c1", project_id="p1", content="", user_id="u1", word_count=0)

    async def profile(*_args):
        return VoiceProfile(user_id="u1", pack="general")

    async def nothing(*_args, **_kwargs):
        return None

    class RequestDB:
        async def commit(self):
            return None

    monkeypatch.setattr(generate, "AsyncSessionLocal", StreamSession)
    monkeypatch.setattr(generate, "generate_chapter_stream", failing_stream)
    monkeypatch.setattr(generate, "get_owned_chapter", owned)
    monkeypatch.setattr(generate, "get_owned_project", owned)
    monkeypatch.setattr(generate, "_get_profile", profile)
    monkeypatch.setattr(generate, "_consume_ai_request", nothing)
    monkeypatch.setattr(generate, "snapshot_chapter", nothing)

    response = await generate.generate_chapter(
        generate.GenerateChapterRequest(chapter_id="c1"), current_user=SimpleNamespace(id="u1"), db=RequestDB(),
    )
    events = await _drain(response)

    assert json.loads(events[0][6:]) == {"text": "Opening line. "}
    assert "error" in json.loads(events[1][6:])
    assert events[-1] == "data: [DONE]\n\n"
    stream_db = sessions[0]
    log = stream_db.added[0]
    assert log.success is False and "provider exploded" in log.error_message
    assert stream_db.commits == 1 and len(stream_db.executed) == 1  # status → Drafted (some text arrived)


# ── Client IP for rate limits ───────────────────────────────────────

def _ip_request(xff=None, peer="10.0.0.9", extra=()):
    from fastapi import Request

    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    headers += [(k.encode(), v.encode()) for k, v in extra]
    return Request({"type": "http", "method": "POST", "headers": headers, "client": (peer, 1234)})


@pytest.mark.parametrize("hops,xff,expected", [
    (0, "6.6.6.6", "10.0.0.9"),                      # no trusted proxy: ignore the header entirely
    (1, "6.6.6.6, 203.0.113.7", "203.0.113.7"),       # one proxy appended the real peer
    (2, "6.6.6.6, 198.51.100.1, 76.76.21.9", "198.51.100.1"),  # client-forged entry on the left is ignored
    (2, "198.51.100.1", "10.0.0.9"),                  # fewer entries than proxies: fall back to the peer
])
def test_client_ip_counts_trusted_proxies_from_the_right(monkeypatch, hops, xff, expected):
    from app.core.config import settings
    from app.services.security.rate_limits import _client_ip

    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", hops)
    assert _client_ip(_ip_request(xff)) == expected


def test_client_ip_ignores_spoofable_cloudflare_header(monkeypatch):
    from app.core.config import settings
    from app.services.security.rate_limits import _client_ip

    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)
    assert _client_ip(_ip_request(extra=[("cf-connecting-ip", "6.6.6.6")])) == "10.0.0.9"
