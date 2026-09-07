"""
Unified LLM client — rotates across Ollama (local + free cloud-hosted
models), Groq (free tier), and Anthropic behind one interface, so the rest
of the codebase (generation.py, companion_chat.py, dna_report.py, etc.)
never needs to know which provider actually answered a given call.

Same design as the Interview Copilot project's multi-provider rotation
(see memory: interview_copilot_project, groq_free_tier_models):
  - An ordered candidate list is tried in order.
  - Each provider is tracked by a shared ProviderHealthTracker; anything
    currently in cooldown (rate-limited or repeatedly failing) is skipped.
  - Failover is silent — on error/429/timeout the router moves to the next
    candidate rather than raising, and only raises once every candidate has
    failed.
  - Default order is cheapest/free first: local Ollama pool -> Groq's best
    free-tier models -> Anthropic last, as a quality fallback (and as the
    sole candidate when LLM_PROVIDER is pinned to "anthropic" for a final
    submission/demo where consistent top quality matters more than cost).

LLM_PROVIDER controls the mode:
  - "rotate" (default): full rotation as described above.
  - "anthropic" / "groq": pin to exactly one provider, no rotation — for
    when you deliberately want guaranteed-consistent output (e.g. final
    manuscript export) or need to isolate one provider while debugging.
"""
from typing import AsyncIterator, Awaitable, Callable, Optional
from dataclasses import dataclass

from app.core.config import settings
from app.services.ai.ollama_pool import LocalModelPool
from app.services.ai.provider_health import ProviderHealthTracker, get_health_tracker, looks_rate_limited


@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class LLMResult:
    text: str
    usage: LLMUsage


# ── Individual provider implementations ─────────────────────────────────
# Each exposes `.id` (used for health tracking + cost lookup + generation
# log attribution) and an async generator `.stream(...)` that sets
# `.last_usage` as a side effect once the stream completes.

class AnthropicProvider:
    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic
        self.id = "anthropic"
        self.model = model
        self.last_usage: Optional[LLMUsage] = None
        self._client = AsyncAnthropic(api_key=api_key)

    async def stream(self, messages: list[dict], system: Optional[str], max_tokens: int) -> AsyncIterator[str]:
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


class GroqProvider:
    def __init__(self, api_key: str, model: str):
        from groq import AsyncGroq
        self.id = f"groq:{model}"
        self.model = model
        self.last_usage: Optional[LLMUsage] = None
        self._client = AsyncGroq(api_key=api_key)

    async def stream(self, messages: list[dict], system: Optional[str], max_tokens: int) -> AsyncIterator[str]:
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
        # approximate using a simple word-based heuristic (~1.3 tokens/word).
        full_text = "".join(output_text)
        input_text = " ".join(m.get("content", "") for m in groq_messages)
        self.last_usage = LLMUsage(
            input_tokens=int(len(input_text.split()) * 1.3),
            output_tokens=int(len(full_text.split()) * 1.3),
        )


class OllamaProvider:
    """Streams a chat completion from a specific already-chosen Ollama model
    (model selection itself is LocalModelPool's job, not this class's).

    Works against either:
      - a local Ollama daemon (`base_url=http://localhost:11434`, no `api_key`)
        — this is what LocalModelPool discovery targets, and what "-cloud"
        suffixed model names proxy through.
      - Ollama's direct cloud API (`base_url=https://ollama.com/api`, with
        `api_key` set) — no local daemon involved at all, so this is the one
        that actually works from a server like Render. Model names here drop
        the "-cloud" suffix (e.g. "gpt-oss:120b", not "gpt-oss:120b-cloud").
        Bearer-token auth per https://docs.ollama.com/api/authentication.

    `supports_thinking` must be known up front (from LocalModelPool's
    discovered capabilities, or hardcoded for the fixed cloud-direct model
    list below) rather than guessed: models like gpt-oss ignore `think: false`
    outright (confirmed live — it burns the entire max_tokens budget on
    hidden chain-of-thought and can return empty content at low budgets),
    but only honor `think: "low"` to actually cut reasoning down; sending
    that same string value to a model without thinking support 400s the
    request. So thinking-capable models get "low", everything else gets no
    `think` field at all.
    """

    def __init__(self, base_url: str, model: str, supports_thinking: bool = False, api_key: str = ""):
        label = "ollama-cloud" if api_key else "ollama"
        self.id = f"{label}:{model}"
        self.model = model
        self.last_usage: Optional[LLMUsage] = None
        self._base_url = base_url.rstrip("/")
        self._supports_thinking = supports_thinking
        self._api_key = api_key

    async def stream(self, messages: list[dict], system: Optional[str], max_tokens: int) -> AsyncIterator[str]:
        import json
        import httpx

        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        ollama_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {"num_predict": max_tokens},
        }
        if self._supports_thinking:
            payload["think"] = "low"

        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self._base_url}/api/chat", json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    obj = json.loads(line)
                    content = (obj.get("message") or {}).get("content")
                    if content:
                        yield content
                    if obj.get("done"):
                        self.last_usage = LLMUsage(
                            input_tokens=obj.get("prompt_eval_count", 0),
                            output_tokens=obj.get("eval_count", 0),
                        )
                        return


# ── Router ────────────────────────────────────────────────────────────
ProviderFactory = Callable[[], Awaitable[Optional[object]]]


class ProviderRouter:
    """Tries candidates in order, skipping anything in cooldown, and fails
    over silently on error. Commits to a candidate only after its first
    chunk arrives successfully, so a mid-request failure never produces
    output stitched together from two different providers."""

    def __init__(self, candidates: list[ProviderFactory], health: ProviderHealthTracker):
        self._candidates = candidates
        self._health = health
        self.last_provider: Optional[object] = None

    async def stream(self, messages: list[dict], system: Optional[str], max_tokens: int) -> AsyncIterator[str]:
        errors: list[str] = []

        for make_candidate in self._candidates:
            provider = await make_candidate()
            if provider is None:
                continue
            if not self._health.is_available(provider.id):
                continue

            gen = provider.stream(messages, system, max_tokens)
            try:
                first_chunk = await gen.__anext__()
            except StopAsyncIteration:
                self._health.record_success(provider.id)
                self.last_provider = provider
                return
            except Exception as exc:
                self._health.record_failure(provider.id, rate_limited=looks_rate_limited(exc))
                errors.append(f"{provider.id}: {exc}")
                continue

            self._health.record_success(provider.id)
            self.last_provider = provider
            yield first_chunk
            async for chunk in gen:
                yield chunk
            return

        detail = "; ".join(errors) if errors else "no providers configured"
        raise RuntimeError(f"All LLM providers failed or are unavailable ({detail}).")


DEFAULT_GROQ_FALLBACKS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]

# Ollama's direct cloud API (https://docs.ollama.com/api/authentication) —
# no local daemon involved, so this is what actually works from a server
# with no Ollama installed (e.g. Render). Model names drop the "-cloud"
# suffix used by the local-daemon proxy path. Both are gpt-oss reasoning
# models (same family already handled locally), hence supports_thinking=True.
OLLAMA_CLOUD_BASE_URL = "https://ollama.com"  # OllamaProvider appends /api/chat itself
DEFAULT_OLLAMA_CLOUD_FALLBACKS: list[tuple[str, bool]] = [("gpt-oss:120b", True), ("gpt-oss:20b", True)]


def _groq_priority_models() -> list[str]:
    models = [settings.GROQ_MODEL] if settings.GROQ_MODEL else []
    for m in DEFAULT_GROQ_FALLBACKS:
        if m not in models:
            models.append(m)
    return models


def _ollama_cloud_priority_models() -> list[tuple[str, bool]]:
    models = [(settings.OLLAMA_CLOUD_MODEL, True)] if settings.OLLAMA_CLOUD_MODEL else []
    seen = {m[0] for m in models}
    for m in DEFAULT_OLLAMA_CLOUD_FALLBACKS:
        if m[0] not in seen:
            models.append(m)
            seen.add(m[0])
    return models


def _build_rotating_router() -> ProviderRouter:
    candidates: list[ProviderFactory] = []

    if settings.OLLAMA_ENABLED:
        pool = LocalModelPool(settings.OLLAMA_BASE_URL)

        async def _local_candidate():
            picked = await pool.get_best_model()
            if picked is None:
                return None
            return OllamaProvider(settings.OLLAMA_BASE_URL, picked["name"], picked["supports_thinking"])

        candidates.append(_local_candidate)

    if settings.GROQ_API_KEY:
        for model in _groq_priority_models():
            async def _groq_candidate(model=model):
                return GroqProvider(settings.GROQ_API_KEY, model)
            candidates.append(_groq_candidate)

    if settings.OLLAMA_API_KEY:
        for model, supports_thinking in _ollama_cloud_priority_models():
            async def _ollama_cloud_candidate(model=model, supports_thinking=supports_thinking):
                return OllamaProvider(OLLAMA_CLOUD_BASE_URL, model, supports_thinking, api_key=settings.OLLAMA_API_KEY)
            candidates.append(_ollama_cloud_candidate)

    if settings.ANTHROPIC_API_KEY:
        async def _anthropic_candidate():
            return AnthropicProvider(settings.ANTHROPIC_API_KEY, settings.ANTHROPIC_MODEL)
        candidates.append(_anthropic_candidate)

    return ProviderRouter(candidates, get_health_tracker())


def _build_pinned_router(provider: str) -> ProviderRouter:
    candidates: list[ProviderFactory] = []

    if provider == "anthropic":
        async def _anthropic_only():
            return AnthropicProvider(settings.ANTHROPIC_API_KEY, settings.ANTHROPIC_MODEL)
        candidates.append(_anthropic_only)
    elif provider == "groq":
        async def _groq_only():
            return GroqProvider(settings.GROQ_API_KEY, settings.GROQ_MODEL)
        candidates.append(_groq_only)

    return ProviderRouter(candidates, get_health_tracker())


class LLMClient:
    """
    Facade with a single async streaming method regardless of which
    provider ends up serving the request.

    Usage:
        client = get_llm_client()
        async for chunk in client.stream(system=..., messages=[...], max_tokens=2000):
            yield chunk
        usage = client.last_usage       # populated after stream completes
        served_by = client.provider     # e.g. "groq:openai/gpt-oss-120b" — for cost/logging only
    """

    def __init__(self):
        mode = settings.LLM_PROVIDER
        self._router = _build_rotating_router() if mode == "rotate" else _build_pinned_router(mode)
        self.provider: str = ""
        self.last_usage: Optional[LLMUsage] = None

    async def stream(
        self,
        messages: list[dict],
        system: Optional[str] = None,
        max_tokens: int = 1500,
    ) -> AsyncIterator[str]:
        async for chunk in self._router.stream(messages, system, max_tokens):
            yield chunk

        served = self._router.last_provider
        if served is not None:
            self.provider = served.id
            self.last_usage = served.last_usage

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
    """Factory — returns a fresh client wired to the configured provider mode."""
    return LLMClient()


# Cost tables (USD per token) — used for generation_logs.cost_usd. Looked up
# by the provider id's prefix before the first ":" (e.g. "groq:openai/gpt-oss-120b" -> "groq").
COST_PER_TOKEN = {
    "anthropic": {"input": 0.000003, "output": 0.000015},   # claude-sonnet-4
    # GPT-OSS 120B on Groq: $0.15 input / $0.60 output per million tokens.
    "groq": {"input": 0.00000015, "output": 0.00000060},
    "ollama": {"input": 0.0, "output": 0.0},  # local daemon (incl. "-cloud" proxy) — free
    # Ollama's direct cloud API is credit-metered, not published per-token —
    # logged as 0 same as the free tier above since no real per-token rate exists to apply.
    "ollama-cloud": {"input": 0.0, "output": 0.0},
}


def estimate_cost(provider: str, usage: LLMUsage) -> float:
    prefix = provider.split(":", 1)[0]
    rates = COST_PER_TOKEN.get(prefix, COST_PER_TOKEN["anthropic"])
    return (usage.input_tokens * rates["input"]) + (usage.output_tokens * rates["output"])
