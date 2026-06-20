from types import SimpleNamespace
from app.models import VoiceProfile
from app.services.ai.dna_report import compute_dna_metrics


def _sermon(transcript):
    return SimpleNamespace(transcript=transcript)


def test_compute_dna_metrics_basic():
    profile = VoiceProfile(
        user_id="u1",
        theological_lens="Prophetic",
        signature_phrases=["set time", "let that sink in"],
        anchor_scriptures=[
            {"ref": "Isaiah 61:1", "themes": ["calling", "healing"]},
            {"ref": "Joel 2:28", "themes": ["prophecy", "calling"]},
        ],
    )
    sermons = [
        _sermon("This is your set time. Isaiah 61:1 says... set time again."),
        _sermon("Joel 2:28 and Isaiah 61:1. Let that sink in."),
    ]
    versions = [
        SimpleNamespace(version_number=1, cadence_score=0.4, phrase_count=2, scripture_count=1),
        SimpleNamespace(version_number=2, cadence_score=0.5, phrase_count=4, scripture_count=2),
    ]
    m = compute_dna_metrics(profile, sermons, versions)

    # "calling" appears in both scriptures -> top theme
    assert m["top_themes"][0]["theme"] == "calling"
    assert m["top_themes"][0]["count"] == 2
    # "set time" appears 2x across transcripts, more than "let that sink in" (1x)
    assert m["top_phrases"][0]["phrase"] == "set time"
    assert m["top_phrases"][0]["count"] == 2
    # Isaiah 61:1 referenced twice
    refs = {s["ref"]: s["count"] for s in m["top_scriptures"]}
    assert refs["Isaiah 61:1"] == 2
    assert "Prophetic" in m["ministry_focus"]
    assert m["timeline"][0]["version"] == 1 and m["timeline"][-1]["version"] == 2


def test_compute_dna_metrics_empty_profile():
    profile = VoiceProfile(user_id="u1")
    m = compute_dna_metrics(profile, [], [])
    assert m["top_scriptures"] == []
    assert m["top_phrases"] == []
    assert m["top_themes"] == []
    assert m["timeline"] == []
