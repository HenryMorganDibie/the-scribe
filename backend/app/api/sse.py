"""Server-sent-event helpers shared by every streaming endpoint.

Every event is JSON (`{"text": ...}`, `{"error": ...}`, or another object),
so newlines in generated text can't break the SSE framing, and every stream
ends with `[DONE]` — including when the AI provider fails mid-way, which now
produces an error event the client can show instead of a silent cut-off.
"""
import json
from typing import AsyncIterator, Optional

import structlog

from app.services.ai.llm_client import get_llm_client

logger = structlog.get_logger()

SSE_DONE = "data: [DONE]\n\n"
USER_FACING_ERROR = "The writing assistant couldn't finish just now. Please try again in a moment."


def sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def sse_text(chunk: str) -> str:
    return sse_event({"text": chunk})


def sse_error(exc: Exception, action: str) -> str:
    # Provider errors can contain request details; log them, show a plain message.
    logger.warning("stream_failed", action=action, error=str(exc)[:500])
    return sse_event({"error": USER_FACING_ERROR})


async def stream_llm(
    messages: list[dict], *, action: str, system: Optional[str] = None, max_tokens: int = 1000,
) -> AsyncIterator[str]:
    """Stream one LLM completion as SSE text events, ending with [DONE] even on failure."""
    try:
        async for chunk in get_llm_client().stream(messages=messages, system=system, max_tokens=max_tokens):
            yield sse_text(chunk)
    except Exception as exc:
        yield sse_error(exc, action)
    yield SSE_DONE
