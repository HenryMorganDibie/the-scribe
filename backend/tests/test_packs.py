"""Genre packs: prompts stay Christian for Christian authors and neutral for everyone else."""
import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import generate, onboarding
from app.models import VoiceProfile
from app.services import packs
from app.services.ai import generation, sermon_book, testimony_mining
from app.services.ai.voice_enrichment import finalize_dna, voice_dna_prompt

# Words that should never leak into a general-pack prompt.
CHRISTIAN_TERMS = re.compile(r"christian|scripture|bible|theolog|ministr|sermon|testimon|prophetic|god\b", re.I)


class FakeLLM:
    """Captures prompts; returns canned text from both complete() and stream()."""

    def __init__(self, text="ok"):
        self.text = text
        self.prompts = []
        self.provider = "fake"
        self.last_usage = None

    def _record(self, messages, system):
        self.prompts.append("\n".join(filter(None, [system, *[m["content"] for m in messages]])))

    async def complete(self, messages, system=None, max_tokens=0):
        self._record(messages, system)
        return SimpleNamespace(text=self.text)

    async def stream(self, messages, system=None, max_tokens=0):
        self._record(messages, system)
        yield self.text


def _profile(pack: str, **kwargs) -> VoiceProfile:
    return VoiceProfile(user_id="u1", pack=pack, **kwargs)


# ── Pack resolution ─────────────────────────────────────────────────

def test_get_pack_falls_back_to_general():
    assert packs.get_pack("christian").id == "christian"
    assert packs.get_pack("general").id == "general"
    for bad in (None, "", "unknown", object()):
        assert packs.get_pack(bad).id == "general"


# ── Voice brief ─────────────────────────────────────────────────────

async def test_general_voice_brief_has_no_christian_wording():
    profile = _profile(
        "general",
        theological_lens="Memoir",
        target_audience="Early-career engineers",
        theological_guardrails=["No jargon without a definition"],
        anchor_scriptures=[{"ref": "Isaiah 61:1"}],  # ignored for this pack
    )
    brief = await generation.build_voice_brief(profile)

    assert "GENRE / BOOK TYPE: Memoir" in brief
    assert "STYLE RULES" in brief and "No jargon without a definition" in brief
    assert "Isaiah" not in brief
    assert not CHRISTIAN_TERMS.search(brief), CHRISTIAN_TERMS.search(brief)


async def test_christian_voice_brief_keeps_scripture_and_translation():
    profile = _profile("christian", anchor_scriptures=[{"ref": "Isaiah 61:1"}], preferred_translation="KJV")
    brief = await generation.build_voice_brief(profile)

    assert "a Christian author" in brief
    assert "THEOLOGICAL LENS: Spirit-filled" in brief
    assert "PREFERRED BIBLE TRANSLATION: KJV" in brief
    assert "Isaiah 61:1" in brief


# ── Voice DNA extraction ────────────────────────────────────────────

def test_voice_dna_prompt_only_asks_christian_pack_for_scriptures():
    assert "anchor_scriptures" in voice_dna_prompt(packs.CHRISTIAN, "TRANSCRIPT", "text")
    general = voice_dna_prompt(packs.GENERAL, "TRANSCRIPT", "text")
    assert "anchor_scriptures" not in general
    assert not CHRISTIAN_TERMS.search(general)


async def test_finalize_dna_drops_scriptures_for_general_pack():
    dna = await finalize_dna({"voice_summary": "x", "anchor_scriptures": [{"ref": "John 3:16"}]}, packs.GENERAL, db=None)
    assert "anchor_scriptures" not in dna


# ── Chapter generation, preview, mining, book planning ─────────────

async def test_general_chapter_prompt_is_neutral(monkeypatch):
    llm = FakeLLM()

    async def fake_context(**_kwargs):
        return {"samples": [], "testimonies": []}

    async def fake_memory(*_args):
        return ""

    async def fake_book_context(*_args, **_kwargs):
        return ""

    monkeypatch.setattr(generation, "get_llm_client", lambda: llm)
    monkeypatch.setattr(generation, "retrieve_relevant_context", fake_context)
    monkeypatch.setattr(generation, "get_chapter_memory", fake_memory)
    monkeypatch.setattr(generation, "book_context", fake_book_context)

    profile = _profile("general", theological_lens="Business")
    chapter = SimpleNamespace(
        id="c1", title="Pricing", intent="Teach value pricing", key_points=["Anchor on outcomes"],
        anchor_scriptures=["Ries, Positioning (1981)"], chapter_number=2,
    )
    project = SimpleNamespace(
        id="p1", title="Charge More", theme=None, genre=None,
        target_audience=None, style_rules=None, style_notes=None,
    )

    chunks = [c async for c in generation.generate_chapter_stream(profile, chapter, project, db=None)]

    prompt = llm.prompts[0]
    assert chunks[0] == "ok"
    assert "Genre: Business" in prompt
    assert "Key References for This Chapter" in prompt and "Ries, Positioning (1981)" in prompt
    assert not CHRISTIAN_TERMS.search(prompt), CHRISTIAN_TERMS.search(prompt)


async def test_voice_preview_uses_pack_chosen_during_onboarding(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr(generation, "get_llm_client", lambda: llm)
    profile = _profile("christian")  # stale column value; onboarding answer wins

    _ = [c async for c in generation.generate_voice_preview_stream({"pack": "general", "theological_lens": "Fiction"}, profile)]

    assert "voice of an author" in llm.prompts[0]
    assert not CHRISTIAN_TERMS.search(llm.prompts[0])


async def test_story_mining_prompt_follows_pack(monkeypatch):
    llm = FakeLLM("[]")
    monkeypatch.setattr(testimony_mining, "get_llm_client", lambda: llm)

    await testimony_mining.mine_testimonies("transcript", packs.GENERAL)
    await testimony_mining.mine_testimonies("transcript", packs.CHRISTIAN)

    assert not CHRISTIAN_TERMS.search(llm.prompts[0])
    assert "sermon transcript" in llm.prompts[1] and "testimonies" in llm.prompts[1]


async def test_general_book_plan_prompt_is_neutral(monkeypatch):
    llm = FakeLLM('{"theme": "t", "chapters": [{"title": "One"}]}')
    monkeypatch.setattr(sermon_book, "get_llm_client", lambda: llm)

    plan = await sermon_book.build_sermon_book_plan(
        title="Charge More", target_reader="", target_chapters=3, theological_lens="Business",
        preferred_translation="NKJV", guardrails=None,
        sermons=[SimpleNamespace(title="Pricing talk", transcript="...")], pack=packs.GENERAL,
    )

    assert plan["chapters"][0]["title"] == "One"
    assert "SOURCE SOURCE" not in llm.prompts[0]
    assert not CHRISTIAN_TERMS.search(llm.prompts[0]), CHRISTIAN_TERMS.search(llm.prompts[0])


# ── Routes ──────────────────────────────────────────────────────────

async def test_scripture_suggest_rejected_for_general_pack_before_quota(monkeypatch):
    quota_calls = []

    async def fake_owned_chapter(*_args, **_kwargs):
        return SimpleNamespace()

    async def fake_profile(*_args):
        return _profile("general")

    async def fake_quota(*args):
        quota_calls.append(args)

    monkeypatch.setattr(generate, "get_owned_chapter", fake_owned_chapter)
    monkeypatch.setattr(generate, "_get_profile", fake_profile)
    monkeypatch.setattr(generate, "_consume_ai_request", fake_quota)

    with pytest.raises(HTTPException) as exc_info:
        await generate.scripture_suggest(
            generate.ScriptureSuggestRequest(chapter_id="c1", context="x"),
            current_user=SimpleNamespace(id="u1"), db=None,
        )
    assert exc_info.value.status_code == 400
    assert quota_calls == []


class ProfileSession:
    def __init__(self, profile):
        self.profile = profile
        self.commits = 0

    async def execute(self, _statement):
        return SimpleNamespace(scalar_one_or_none=lambda: self.profile)

    async def commit(self):
        self.commits += 1


async def test_onboarding_steps_accumulate_and_set_pack():
    profile = _profile("general", onboarding_step=0, onboarding_data=None)
    db = ProfileSession(profile)
    user = SimpleNamespace(id="u1")

    await onboarding.save_step(onboarding.StepUpdate(step=0, field="pack", value="christian"), user, db)
    first = profile.onboarding_data
    await onboarding.save_step(onboarding.StepUpdate(step=1, field="target_audience", value="Leaders"), user, db)

    assert profile.pack == "christian"
    assert profile.onboarding_data == {"pack": "christian", "target_audience": "Leaders"}
    # A new dict each time, so SQLAlchemy sees the change and saves it.
    assert profile.onboarding_data is not first


async def test_onboarding_rejects_unknown_pack():
    db = ProfileSession(_profile("general", onboarding_step=0))
    with pytest.raises(HTTPException):
        await onboarding.save_step(
            onboarding.StepUpdate(step=0, field="pack", value="astrology"), SimpleNamespace(id="u1"), db,
        )


async def test_fiction_onboarding_turns_pov_and_tense_into_the_first_style_rule():
    profile = _profile("general", onboarding_step=0)
    await onboarding.complete_onboarding(
        onboarding.OnboardingComplete(data={
            "pack": "fiction", "pov_tense": "Third person limited, past tense", "style_rules": ["No adverbs"],
        }),
        SimpleNamespace(id="u1", onboarded=False), ProfileSession(profile),
    )
    assert profile.pack == "fiction"
    assert profile.theological_guardrails == ["Point of view and tense: Third person limited, past tense", "No adverbs"]


async def test_onboarding_complete_stores_pack_and_style_rules():
    profile = _profile("general", onboarding_step=0)
    db = ProfileSession(profile)
    user = SimpleNamespace(id="u1", onboarded=False)

    await onboarding.complete_onboarding(
        onboarding.OnboardingComplete(data={
            "pack": "general", "theological_lens": "Fiction", "style_rules": ["Present tense", " "],
        }),
        user, db,
    )

    assert profile.pack == "general"
    assert profile.theological_lens == "Fiction"
    assert profile.theological_guardrails == ["Present tense"]
    assert user.onboarded is True
