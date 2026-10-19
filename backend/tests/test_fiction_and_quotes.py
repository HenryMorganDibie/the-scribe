"""Phase 3 (unit level): fiction pack, scene plans, style signals, quote verification."""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.routes.projects import ChapterUpdate
from app.api.routes.voice import VoiceProfileUpdate
from app.models import BookEntry, VoiceProfile
from app.services import packs
from app.services.ai import generation
from app.services.book_bible import format_timeline
from app.services.quote_check import extract_quotes, match_quote
from app.services.style_signals import fiction_signals
from tests.test_packs import CHRISTIAN_TERMS, FakeLLM


# ── Fiction pack ────────────────────────────────────────────────────

def test_fiction_pack_is_registered_and_selectable():
    assert packs.get_pack("fiction").is_fiction
    assert VoiceProfileUpdate(pack="fiction").pack == "fiction"
    assert not packs.GENERAL.is_fiction and packs.GENERAL.verifies_quotes
    assert not packs.FICTION.verifies_quotes and not packs.CHRISTIAN.verifies_quotes


async def test_fiction_voice_brief_speaks_to_a_novelist():
    brief = await generation.build_voice_brief(VoiceProfile(user_id="u1", pack="fiction", theological_lens="Fantasy"))
    assert "ghostwriting for a novelist" in brief
    assert "GENRE: Fantasy" in brief
    assert "never contradict established story facts" in brief.lower()
    assert not CHRISTIAN_TERMS.search(brief)


def test_scene_plan_lists_scenes_in_order_with_pov_and_setting():
    plan = generation.format_scene_plan([
        {"title": "The storm", "summary": "Ada loses the lamp.", "pov": "Ada", "setting": "Lighthouse"},
        {"title": "  ", "summary": "blank titles are skipped"},
        {"title": "Morning after", "summary": "", "pov": "", "setting": ""},
        "not a scene",
    ], "scene")
    assert plan.splitlines() == [
        "Scene Plan (write these scenes, in this order):",
        "  1. The storm [POV: Ada; Setting: Lighthouse] — Ada loses the lamp.",
        "  2. Morning after",
    ]
    assert generation.format_scene_plan(None, "scene") == ""


async def test_fiction_chapter_prompt_follows_scene_plan(monkeypatch):
    llm = FakeLLM()

    async def empty(*_args, **_kwargs):
        return {"samples": [], "testimonies": []} if _kwargs.get("query") else ""

    monkeypatch.setattr(generation, "get_llm_client", lambda: llm)
    monkeypatch.setattr(generation, "retrieve_relevant_context", empty)
    monkeypatch.setattr(generation, "get_chapter_memory", empty)
    monkeypatch.setattr(generation, "book_context", empty)

    chapter = SimpleNamespace(
        id="c1", title="Landfall", intent="Ada reaches the island", key_points=[], anchor_scriptures=[],
        chapter_number=3, scenes=[{"title": "The crossing", "pov": "Ada"}],
    )
    project = SimpleNamespace(id="p1", title="Salt", theme=None, genre=None,
                              target_audience=None, style_rules=None, style_notes=None)

    _ = [c async for c in generation.generate_chapter_stream(
        VoiceProfile(user_id="u1", pack="fiction"), chapter, project, db=None)]

    prompt = llm.prompts[0]
    assert "Scene Plan" in prompt and "The crossing [POV: Ada]" in prompt
    assert "separating scenes with a line containing only * * *" in prompt
    assert "Write in scenes: show, don't tell" in prompt
    assert "End on a hook" in prompt
    assert not CHRISTIAN_TERMS.search(prompt)


def test_scene_items_are_validated():
    update = ChapterUpdate(scenes=[{"title": "Opening", "pov": "Ada"}])
    assert update.scenes[0].model_dump() == {"title": "Opening", "summary": "", "pov": "Ada", "setting": ""}
    with pytest.raises(ValidationError):
        ChapterUpdate(scenes=[{"title": ""}])
    with pytest.raises(ValidationError):
        ChapterUpdate(scenes=[{"title": "x"}] * 41)


def test_timeline_is_numbered_in_order_with_when_labels():
    text = format_timeline([
        BookEntry(kind="event", title="Ada is born", when_label="1990", body=""),
        BookEntry(kind="event", title="The flood", when_label=None, body="Village lost."),
    ])
    assert text.splitlines() == [
        "TIMELINE (events in story order — never reorder or contradict them):",
        "  1. Ada is born (1990)",
        "  2. The flood — Village lost.",
    ]


# ── Style signals ───────────────────────────────────────────────────

def test_first_person_past_with_dialogue():
    text = ('I walked to the harbour and I looked for her boat. "Where did you go?" I asked. '
            'She turned away. I waited and I watched the water until it was dark.')
    signals = fiction_signals(text)
    assert signals["pov"] == "first person"
    assert signals["tense"] == "past"
    assert 0.05 < signals["dialogue_ratio"] < 0.3


def test_third_person_present():
    text = ("She walks to the harbour. He is waiting. She looks at him and says nothing. "
            "He takes her hand. They are quiet. She knows what comes next.")
    signals = fiction_signals(text)
    assert signals["pov"] == "third person"
    assert signals["tense"] == "present"
    assert signals["dialogue_ratio"] == 0.0


def test_signals_on_too_little_text_are_unclear():
    assert fiction_signals("Rain.") == {"pov": "unclear", "tense": "unclear", "dialogue_ratio": 0.0}


# ── Quote verification ──────────────────────────────────────────────

SOURCES = [
    ("Interview with Dr. Lee", "We found that teams who wrote things down shipped faster and argued less, every single quarter."),
    ("Keynote 2024", "Pricing is a story you tell about value, not a number you pick from a spreadsheet."),
]


def test_extract_quotes_skips_short_phrases_and_duplicates():
    text = ('She called it "good enough". As Lee put it, “teams who wrote things down shipped faster and argued less.” '
            'Later: "Teams who wrote things down shipped faster and argued less."')
    assert extract_quotes(text) == ["teams who wrote things down shipped faster and argued less."]


def test_verbatim_quote_is_verified_despite_case_and_punctuation():
    result = match_quote("Pricing is a story you tell about value — not a number you pick", SOURCES)
    assert result["status"] == "verified" and result["source_title"] == "Keynote 2024"


def test_misquote_is_close_and_returns_the_sources_wording():
    result = match_quote("teams who wrote everything down shipped much faster and argued less", SOURCES)
    assert result["status"] == "close"
    assert result["source_title"] == "Interview with Dr. Lee"
    assert "wrote things down shipped faster and argued less" in result["source_excerpt"]


def test_unsourced_quote_is_not_found():
    result = match_quote("the best way to predict the future is to invent it", SOURCES)
    assert result == {**result, "status": "not_found", "source_title": None, "source_excerpt": None}
