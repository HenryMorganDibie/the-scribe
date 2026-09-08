"""
Export service. Generates .pdf manuscripts from chapter HTML content.

Mirrors docx_export.py's structure (title page, table of contents, chapters,
same scripture-detection heuristic) and the same HTML subset (p/h1-h3/
blockquote/ul/ol/li, inline strong/b/em/i/u/br). Reportlab's Paragraph
understands a small HTML-like markup natively for inline tags, so unlike
docx_export.py's full HTMLParser state machine, only block-level splitting
is done by hand here.
"""
import re
from io import BytesIO
from typing import List

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus.tableofcontents import TableOfContents

_BLOCK_RE = re.compile(r"<(p|h1|h2|h3|blockquote|li)(?:\s[^>]*)?>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
_SCRIPTURE_RE = re.compile(r"^[A-Z][a-zA-Z\s]+ \d+:\d+")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ManuscriptTitle", fontName="Times-Bold", fontSize=20, alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name="ManuscriptAuthor", fontName="Times-Roman", fontSize=14, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="TOCHeading", fontName="Times-Bold", fontSize=16, alignment=TA_CENTER, spaceAfter=18))
    styles.add(ParagraphStyle(name="TOCEntryStyle", fontName="Times-Roman", fontSize=12, leading=18))
    styles.add(ParagraphStyle(name="ChapterLabel", fontName="Times-Bold", fontSize=11, spaceAfter=4))
    # Named "ChapterTitle", not "Heading1", to avoid colliding with
    # getSampleStyleSheet()'s own built-in "Heading1". Kept distinct so
    # ManuscriptDocTemplate.afterFlowable can key off it unambiguously.
    styles.add(ParagraphStyle(name="ChapterTitle", fontName="Times-Bold", fontSize=16, alignment=TA_CENTER, spaceAfter=18))
    styles.add(ParagraphStyle(name="Body", fontName="Times-Roman", fontSize=12, leading=16, firstLineIndent=24, spaceAfter=8, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle(name="Scripture", fontName="Times-Italic", fontSize=11, leading=15, leftIndent=36, spaceAfter=8))
    styles.add(ParagraphStyle(name="Blockquote", fontName="Times-Italic", fontSize=11, leading=15, leftIndent=36, spaceAfter=8))
    styles.add(ParagraphStyle(name="ListItemStyle", fontName="Times-Roman", fontSize=12, leading=16))
    return styles


def _normalize_inline(html: str) -> str:
    """Reportlab's Paragraph mini-markup wants <b>/<i>, not <strong>/<em>."""
    html = re.sub(r"<(/?)strong>", r"<\1b>", html, flags=re.IGNORECASE)
    html = re.sub(r"<(/?)em>", r"<\1i>", html, flags=re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "<br/>", html, flags=re.IGNORECASE)
    return html


def _html_to_flowables(html: str, styles) -> list:
    flowables = []
    list_items: list = []
    in_list = False

    for tag, inner in _BLOCK_RE.findall(html):
        inner = _normalize_inline(inner.strip())
        if not inner:
            continue

        if tag == "li":
            list_items.append(ListItem(Paragraph(inner, styles["ListItemStyle"])))
            in_list = True
            continue
        elif in_list:
            flowables.append(ListFlowable(list_items, bulletType="bullet"))
            list_items = []
            in_list = False

        if tag in ("h1", "h2", "h3"):
            flowables.append(Paragraph(inner, styles["ChapterLabel"]))
        elif tag == "blockquote":
            flowables.append(Paragraph(inner, styles["Blockquote"]))
        else:
            plain = re.sub(r"<[^>]+>", "", inner)
            style = styles["Scripture"] if _SCRIPTURE_RE.match(plain.strip()) else styles["Body"]
            flowables.append(Paragraph(inner, style))

    if in_list and list_items:
        flowables.append(ListFlowable(list_items, bulletType="bullet"))

    return flowables


class ManuscriptDocTemplate(SimpleDocTemplate):
    """Notifies the TableOfContents flowable of each chapter title's real
    page number as the document is laid out. reportlab resolves this with
    a second build pass (doc.multiBuild), unlike Word's field-code approach,
    which defers resolution to whoever opens the file."""

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "ChapterTitle":
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))


def create_manuscript_pdf(
    title: str,
    author_name: str,
    chapters: List[dict],  # [{number, title, content}]
) -> bytes:
    """Generate a publisher-ready .pdf manuscript with a real table of
    contents (page numbers resolved via reportlab's two-pass build).
    Skipped for a single-chapter export, where a TOC is meaningless."""
    buffer = BytesIO()
    doc = ManuscriptDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        leftMargin=1.25 * inch,
        rightMargin=1.25 * inch,
    )
    styles = _styles()
    story = []

    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph(title.upper(), styles["ManuscriptTitle"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"by {author_name}", styles["ManuscriptAuthor"]))
    story.append(PageBreak())

    if len(chapters) > 1:
        toc = TableOfContents()
        toc.levelStyles = [styles["TOCEntryStyle"]]
        story.append(Paragraph("Table of Contents", styles["TOCHeading"]))
        story.append(toc)
        story.append(PageBreak())

    for chapter in chapters:
        story.append(Paragraph(f"Chapter {chapter['number']}", styles["ChapterLabel"]))
        story.append(Paragraph(chapter["title"].upper(), styles["ChapterTitle"]))
        story.append(Spacer(1, 12))

        content_html = chapter.get("content") or ""
        if not content_html.strip().startswith("<"):
            content_html = "\n\n".join(f"<p>{p}</p>" for p in content_html.split("\n\n"))

        story.extend(_html_to_flowables(content_html, styles))
        story.append(PageBreak())

    doc.multiBuild(story)
    return buffer.getvalue()
