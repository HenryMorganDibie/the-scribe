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


def test_docx_html_parser_preserves_formatting():
    import io
    from docx import Document
    
    chapters = [
        {
            "number": 1, 
            "title": "Rich Text Test", 
            "content": "<p>Normal text <strong>bold text</strong> <em>italic text</em> <u>underlined text</u></p><blockquote>Blockquote text</blockquote>"
        }
    ]
    result = create_manuscript_docx(title="Formatting Test", author_name="Formatter", chapters=chapters)
    
    doc = Document(io.BytesIO(result))
    
    non_empty_paras = [p for p in doc.paragraphs if p.text.strip()]
    
    content_para = next(p for p in non_empty_paras if "Normal text" in p.text)
    runs = content_para.runs
    
    bold_run = next(r for r in runs if "bold text" in r.text)
    assert bold_run.bold is True
    
    italic_run = next(r for r in runs if "italic text" in r.text)
    assert italic_run.italic is True
    
    underline_run = next(r for r in runs if "underlined text" in r.text)
    assert underline_run.underline is True
    
    bq_para = next(p for p in non_empty_paras if "Blockquote text" in p.text)
    assert bq_para.paragraph_format.left_indent is not None
    assert any(r.italic for r in bq_para.runs)

