"""
Tests for the Voice Brief builder — the architectural core of generation.
Run with: pytest backend/tests/test_voice_brief.py
"""
import pytest
from app.services.ai.generation import build_voice_brief, _cadence_description
from app.models import VoiceProfile


def test_cadence_description_ranges():
    assert "punchy" in _cadence_description(0.1)
    assert "Balanced" in _cadence_description(0.45) or "balanced" in _cadence_description(0.45)
    assert "flowing" in _cadence_description(0.9)


@pytest.mark.asyncio
async def test_build_voice_brief_includes_core_sections():
    profile = VoiceProfile(
        user_id="test-user",
        theological_lens="Prophetic",
        ministry_background="Pastors a discipleship-focused church.",
        target_audience="Believers seeking purpose",
        tone_preferences=["Teaching", "Exhortation"],
        signature_phrases=["This is your set time", "Let that sink in"],
        anchor_scriptures=[{"ref": "Isaiah 61:1-3", "themes": ["calling"]}],
        cadence_score=0.4,
        style_tags=["rhetorical_questions", "direct_address"],
        voice_summary="A direct, exhortative voice that favors short declarations.",
        preferred_translation="NKJV",
        writing_samples=["Sample sermon text for voice matching."],
    )

    brief = await build_voice_brief(profile)

    assert "Prophetic" in brief
    assert "This is your set time" in brief
    assert "Isaiah 61:1-3" in brief
    assert "NKJV" in brief
    assert "rhetorical_questions" in brief
    assert "Never break voice" in brief


@pytest.mark.asyncio
async def test_build_voice_brief_handles_empty_profile():
    """A freshly-created profile (pre-onboarding) shouldn't crash the brief builder."""
    profile = VoiceProfile(user_id="new-user")
    brief = await build_voice_brief(profile)
    assert "VOICE BRIEF" in brief
    assert "Spirit-filled" in brief  # default theological lens fallback
