"""
Tests for DOCX export — verifies manuscript generation doesn't crash
and produces a valid docx file.
"""
from app.services.export.docx_export import create_manuscript_docx, html_to_plain


def test_html_to_plain_strips_tags():
    html = "<p>Hello <strong>world</strong></p><p>Second paragraph</p>"
    plain = html_to_plain(html)
    assert "<" not in plain
    assert "Hello" in plain
    assert "Second paragraph" in plain


def test_create_manuscript_docx_returns_bytes():
    chapters = [
        {"number": 1, "title": "The Wilderness Season", "content": "<p>It begins in silence.</p>"},
        {"number": 2, "title": "The Turning", "content": "<p>Isaiah 61:1<br>The Spirit of the Lord is upon me.</p>"},
    ]
    result = create_manuscript_docx(title="Called", author_name="Test Author", chapters=chapters)

    assert isinstance(result, bytes)
    assert len(result) > 0
    # docx files are zip archives — check for the PK signature
    assert result[:2] == b"PK"
