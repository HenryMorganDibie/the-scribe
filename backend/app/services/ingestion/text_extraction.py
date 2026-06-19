"""Extract plain text from an uploaded sermon source (PDF, DOCX, or pasted text)."""
import io


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def _extract_docx(data: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs).strip()


def extract_text(source_type: str, *, file_bytes: bytes | None = None, text_value: str | None = None) -> str:
    """
    Return plain text for the given source type.
    - source_type 'text' uses text_value; 'pdf'/'docx' use file_bytes.
    Raises ValueError if the result is empty/unreadable.
    """
    if source_type == "text":
        result = (text_value or "").strip()
    elif source_type == "pdf":
        result = _extract_pdf(file_bytes or b"")
    elif source_type == "docx":
        result = _extract_docx(file_bytes or b"")
    else:
        raise ValueError(f"Unsupported source_type for text extraction: {source_type!r}")

    if not result:
        raise ValueError("No readable text could be extracted from the source.")
    return result
