"""LLM router failover: hung providers time out and the next provider answers."""
import asyncio

import pytest

from app.services.ai.llm_client import ProviderRouter
from app.services.ai.provider_health import ProviderHealthTracker


class HungProvider:
    id = "hung"
    last_usage = None

    def __init__(self):
        self.closed = False

    async def stream(self, messages, system, max_tokens):
        try:
            await asyncio.sleep(3600)  # accepts the request, never answers
            yield "never"
        finally:
            self.closed = True


class WorkingProvider:
    id = "working"
    last_usage = None

    async def stream(self, messages, system, max_tokens):
        yield "Hello "
        yield "world"


def _router(*providers, timeout=0.05):
    async def factory_for(p):
        return p

    factories = [lambda p=p: factory_for(p) for p in providers]
    return ProviderRouter(factories, ProviderHealthTracker(), first_chunk_timeout=timeout)


async def _collect(router):
    return "".join([c async for c in router.stream([{"role": "user", "content": "hi"}], None, 10)])


async def test_hung_provider_times_out_and_next_provider_answers():
    hung, working = HungProvider(), WorkingProvider()
    router = _router(hung, working)

    assert await asyncio.wait_for(_collect(router), timeout=5) == "Hello world"
    assert router.last_provider is working
    assert hung.closed  # its stream was cleaned up, not left running


async def test_timed_out_provider_is_put_in_cooldown():
    hung = HungProvider()
    router = _router(hung, WorkingProvider())
    await _collect(router)
    assert not router._health.is_available("hung")


async def test_all_providers_hung_raises_with_reason():
    with pytest.raises(RuntimeError, match="no response within"):
        await asyncio.wait_for(_collect(_router(HungProvider())), timeout=5)


# ── Anthropic provider (anthropic 1.x) ──────────────────────────────

class _FakeStream:
    def __init__(self, texts, stop_reason="end_turn", category=None):
        from types import SimpleNamespace

        self._texts = texts
        self._final = SimpleNamespace(
            stop_reason=stop_reason,
            stop_details=SimpleNamespace(category=category) if stop_reason == "refusal" else None,
            usage=SimpleNamespace(input_tokens=11, output_tokens=22),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            for t in self._texts:
                yield t
        return gen()

    async def get_final_message(self):
        return self._final


def _anthropic_with(stream, captured):
    from types import SimpleNamespace
    from app.services.ai.llm_client import AnthropicProvider

    provider = AnthropicProvider(api_key="sk-test", model="claude-opus-5-5")

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return stream

    provider._client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=fake_stream)))
    return provider


async def test_anthropic_request_adds_thinking_headroom_effort_and_fallback(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_THINKING_HEADROOM_TOKENS", 8000)
    monkeypatch.setattr(settings, "ANTHROPIC_EFFORT", "medium")
    captured = {}
    provider = _anthropic_with(_FakeStream(["Hello ", "there"]), captured)

    text = "".join([c async for c in provider.stream([{"role": "user", "content": "hi"}], "Be brief.", 300)])

    assert text == "Hello there"
    assert captured["model"] == "claude-opus-5-5"
    assert captured["max_tokens"] == 8300          # reply budget + thinking headroom
    assert captured["output_config"] == {"effort": "medium"}
    assert captured["betas"] == ["server-side-fallback-2026-07-01"]
    assert captured["fallbacks"] == "default"
    assert captured["system"] == "Be brief."
    assert "temperature" not in captured
    assert (provider.last_usage.input_tokens, provider.last_usage.output_tokens) == (11, 22)


async def test_refusal_fails_over_without_putting_anthropic_in_cooldown():
    from app.services.ai.llm_client import LLMRefusal

    refusing = _anthropic_with(_FakeStream([], stop_reason="refusal", category="cyber"), {})
    with pytest.raises(LLMRefusal, match="cyber"):
        _ = [c async for c in refusing.stream([{"role": "user", "content": "x"}], None, 10)]

    refusing = _anthropic_with(_FakeStream([], stop_reason="refusal", category="cyber"), {})
    router = _router(refusing, WorkingProvider())
    assert await _collect(router) == "Hello world"
    assert router._health.is_available("anthropic")  # a decline is not an outage


async def test_anthropic_gets_its_own_longer_first_chunk_timeout():
    provider = _anthropic_with(_FakeStream(["x"]), {})
    assert provider.first_chunk_timeout >= 60
