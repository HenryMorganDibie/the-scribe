"""
Unified LLM client — supports Anthropic (Claude) and Groq as interchangeable
providers behind one interface.

Why: Anthropic gives the best quality (and is the production target), but Groq's
free tier (Llama 3.3 70B / 70B versatile, etc.) is fast and free, which is useful
for development iteration and live demos without burning API credits.

Switch providers via LLM_PROVIDER env var: "anthropic" (default) or "groq".
Both providers are exposed through the same async streaming interface, so the
rest of the codebase (generation.py, routes/generate.py) doesn't need to know
which one is active.
"""
from typing import AsyncIterator, Optional
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class LLMResult:
    text: str
    usage: LLMUsage


class LLMClient:
    """
    Thin wrapper exposing a single async streaming method regardless of provider.

    Usage:
        client = get_llm_client()
        async for chunk in client.stream(system=..., messages=[...], max_tokens=2000):
            yield chunk
        usage = client.last_usage  # populated after stream completes
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.last_usage: Optional[LLMUsage] = None

        if self.provider == "groq":
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            self.model = settings.GROQ_MODEL
        else:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            self.model = settings.ANTHROPIC_MODEL

    async def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1500,
    ) -> AsyncIterator[str]:
        """
        Stream text chunks from the active provider.
        Populates self.last_usage after the stream completes.
        """
        if self.provider == "groq":
            async for chunk in self._stream_groq(messages, system, max_tokens):
                yield chunk
        else:
            async for chunk in self._stream_anthropic(messages, system, max_tokens):
                yield chunk

    async def _stream_anthropic(self, messages, system, max_tokens):
        kwargs = {"model": self.model, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = system

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
            self.last_usage = LLMUsage(
                input_tokens=final.usage.input_tokens,
                output_tokens=final.usage.output_tokens,
            )

    async def _stream_groq(self, messages, system, max_tokens):
        groq_messages = []
        if system:
            groq_messages.append({"role": "system", "content": system})
        groq_messages.extend(messages)

        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=groq_messages,
            max_tokens=max_tokens,
            stream=True,
        )

        output_text = []
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                output_text.append(delta)
                yield delta

        # Groq doesn't return usage on the stream itself in all SDK versions —
        # approximate using a simple word-based heuristic (~1.3 tokens/word)
        full_text = "".join(output_text)
        input_text = " ".join(m.get("content", "") for m in groq_messages)
        self.last_usage = LLMUsage(
            input_tokens=int(len(input_text.split()) * 1.3),
            output_tokens=int(len(full_text.split()) * 1.3),
        )

    async def complete(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1500,
    ) -> LLMResult:
        """Non-streaming completion — collects the full stream and returns it."""
        chunks = []
        async for chunk in self.stream(messages, system, max_tokens):
            chunks.append(chunk)
        return LLMResult(text="".join(chunks), usage=self.last_usage or LLMUsage(0, 0))


def get_llm_client() -> LLMClient:
    """Factory — returns a fresh client configured for the active provider."""
    return LLMClient()


# Cost tables (USD per token) — used for generation_logs.cost_usd
COST_PER_TOKEN = {
    "anthropic": {"input": 0.000003, "output": 0.000015},   # claude-sonnet-4
    "groq": {"input": 0.0, "output": 0.0},                  # free tier
}


def estimate_cost(provider: str, usage: LLMUsage) -> float:
    rates = COST_PER_TOKEN.get(provider, COST_PER_TOKEN["anthropic"])
    return (usage.input_tokens * rates["input"]) + (usage.output_tokens * rates["output"])
