"""
Export service — generates .docx manuscripts from chapter HTML content.
"""
import io
import re
from typing import List, Optional
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def html_to_plain(html: str) -> str:
    """Strip HTML tags to plain text for docx export."""
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'</p>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def create_manuscript_docx(
    title: str,
    author_name: str,
    chapters: List[dict],  # [{number, title, content}]
) -> bytes:
    """
    Generate a publisher-ready .docx manuscript.
    """
    doc = Document()

    # Page setup: 1-inch margins, 12pt Times New Roman
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1.25)
    section.right_margin = Inches(1.25)

    # Styles
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(12)

    # Title page
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run(title.upper())
    title_run.bold = True
    title_run.font.size = Pt(18)
    title_run.font.name = 'Times New Roman'

    doc.add_paragraph()
    author_para = doc.add_paragraph()
    author_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    author_run = author_para.add_run(f"by {author_name}")
    author_run.font.size = Pt(14)
    author_run.font.name = 'Times New Roman'

    doc.add_page_break()

    # Chapters
    for chapter in chapters:
        # Chapter heading
        ch_para = doc.add_paragraph()
        ch_run = ch_para.add_run(f"Chapter {chapter['number']}")
        ch_run.bold = True
        ch_run.font.size = Pt(11)
        ch_run.font.name = 'Times New Roman'

        title_p = doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        t_run = title_p.add_run(chapter['title'].upper())
        t_run.bold = True
        t_run.font.size = Pt(14)
        t_run.font.name = 'Times New Roman'

        doc.add_paragraph()

        # Content
        content = html_to_plain(chapter.get('content') or '')
        paragraphs = content.split('\n\n')

        for para_text in paragraphs:
            para_text = para_text.strip()
            if not para_text:
                continue

            para = doc.add_paragraph()
            para.paragraph_format.first_line_indent = Inches(0.5)
            para.paragraph_format.space_after = Pt(0)

            # Detect scripture block (lines starting with book:chapter)
            if re.match(r'^[A-Z][a-z]+ \d+:\d+', para_text):
                run = para.add_run(para_text)
                run.italic = True
                run.font.size = Pt(11)
            else:
                run = para.add_run(para_text)
                run.font.size = Pt(12)
            run.font.name = 'Times New Roman'

        doc.add_page_break()

    # Save to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
