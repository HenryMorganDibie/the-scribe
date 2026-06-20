from app.models import VoiceProfile
from app.services.ai.voice_enrichment import _parse_dna_json, merge_voice_dna


def test_parse_dna_json_strips_fences():
    raw = '```json\n{"signature_phrases": ["set time"], "cadence_score": 0.4}\n```'
    out = _parse_dna_json(raw)
    assert out["signature_phrases"] == ["set time"]
    assert out["cadence_score"] == 0.4


def test_parse_dna_json_bad_returns_empty():
    assert _parse_dna_json("not json at all") == {}


def test_merge_voice_dna_is_additive():
    profile = VoiceProfile(
        user_id="u1",
        signature_phrases=["this is your set time"],
        anchor_scriptures=[{"ref": "Isaiah 61:1", "themes": ["calling"]}],
        style_tags=["direct_address"],
        cadence_score=0.4,
        voice_summary="Old summary.",
    )
    new_dna = {
        "signature_phrases": ["this is your set time", "let that sink in"],
        "anchor_scriptures": [{"ref": "Isaiah 61:1"}, {"ref": "Joel 2:28", "themes": ["prophecy"]}],
        "style_tags": ["rhetorical_questions"],
        "cadence_score": 0.6,
        "voice_summary": "New summary.",
    }
    result = merge_voice_dna(profile, new_dna)

    assert profile.signature_phrases == ["this is your set time", "let that sink in"]
    refs = {s["ref"] for s in profile.anchor_scriptures}
    assert refs == {"Isaiah 61:1", "Joel 2:28"}
    assert set(profile.style_tags) == {"direct_address", "rhetorical_questions"}
    assert profile.cadence_score == 0.5  # average of 0.4 and 0.6
    assert profile.voice_summary == "New summary."
    assert result == {"phrases_added": 1, "scriptures_added": 1}


def test_merge_voice_dna_cadence_zero_baseline():
    profile = VoiceProfile(user_id="u1", cadence_score=0.0)
    merge_voice_dna(profile, {"cadence_score": 0.6})
    assert profile.cadence_score == 0.3  # average of 0.0 and 0.6, not 0.6


def test_parse_dna_json_non_dict_returns_empty():
    assert _parse_dna_json("[1, 2, 3]") == {}
