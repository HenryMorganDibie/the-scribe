"""Tests for deterministic sermon-to-book blueprint validation."""
from app.services.ai.sermon_book import _clean_chapters


def test_clean_chapters_keeps_only_valid_and_bounded_outline_data():
    chapters = _clean_chapters([
        {"title": "A Call to Hope", "intent": "Help the reader trust God.", "key_points": ["God is faithful"] * 7, "anchor_scriptures": ["Romans 5:5"] * 6},
        {"intent": "Missing a title"},
        "not an object",
    ], 3)

    assert chapters == [{
        "title": "A Call to Hope",
        "intent": "Help the reader trust God.",
        "key_points": ["God is faithful"] * 5,
        "anchor_scriptures": ["Romans 5:5"] * 4,
    }]


def test_clean_chapters_returns_empty_for_non_list_model_output():
    assert _clean_chapters({"title": "not a list"}, 8) == []
