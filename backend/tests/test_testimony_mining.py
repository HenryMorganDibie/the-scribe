from app.services.ai.testimony_mining import _parse_testimonies


def test_parse_testimonies_valid_array():
    raw = '[{"title": "Healed at the altar", "story": "One night...", "themes": ["healing"]}]'
    out = _parse_testimonies(raw)
    assert len(out) == 1
    assert out[0]["title"] == "Healed at the altar"
    assert out[0]["themes"] == ["healing"]


def test_parse_testimonies_strips_fences():
    raw = '```json\n[{"title": "T", "story": "S", "themes": []}]\n```'
    assert _parse_testimonies(raw)[0]["title"] == "T"


def test_parse_testimonies_bad_returns_empty():
    assert _parse_testimonies("nonsense") == []


def test_parse_testimonies_drops_incomplete_entries():
    raw = '[{"title": "ok", "story": "s", "themes": []}, {"title": "no story"}]'
    out = _parse_testimonies(raw)
    assert len(out) == 1
