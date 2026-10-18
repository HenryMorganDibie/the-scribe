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
