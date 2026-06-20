"""Shared helper for stripping Markdown code fences around model JSON output."""


def strip_json_fences(raw: str) -> str:
    """Remove a leading ```/```json fence and trailing ``` fence, if present."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text[3:]                  # drop opening ```
        text = text.removeprefix("json")  # drop optional language tag
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()
