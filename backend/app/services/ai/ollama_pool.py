"""
Local/free Ollama model pool for The Scribe's LLM rotation.

Discovers whatever chat-capable models are actually pulled on the Ollama
server at runtime (no hardcoded model list — same "dynamic, not just one
fixed model" approach used in the Interview Copilot project's
`LocalModelPool`), benchmarks them with a tiny prompt, and picks the fastest
currently-healthy one that clears a quality floor.

Quality scoring here is tuned for THIS app's job — long-form devotional /
theological prose (chapters, testimonies, voice DNA), not code — which is a
different bar than a coding assistant:
  - Ollama's free cloud-hosted models (name ends in "-cloud", e.g.
    `gpt-oss:120b-cloud`) proxy through the local daemon to ollama.com, so
    they're network-bound rather than limited by this machine's CPU/RAM —
    scored highest and benchmarked first.
  - General local instruct/chat models score in the middle.
  - Coder-tuned models (name contains "coder") are deprioritized — they
    weren't trained for narrative/expository prose and it shows.
"""
import time
from typing import Optional

import httpx

QUALITY_FLOOR = 0.5
BENCHMARK_TIMEOUT_S = 20.0
GOOD_ENOUGH_LATENCY_S = 6.0
CACHE_TTL_S = 600.0


def _quality_score(name: str) -> float:
    n = name.lower()
    if "coder" in n:
        return 0.3
    if "-cloud" in n:
        return 0.85
    return 0.65


class LocalModelPool:
    """Picks the best currently-available local/cloud-Ollama model for a call.

    One instance is shared for the process; `get_best_model()` re-discovers
    and re-benchmarks at most once per CACHE_TTL_S.
    """

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")
        self._cache: Optional[list[dict]] = None
        self._cache_at: float = 0.0

    async def get_best_model(self) -> Optional[dict]:
        now = time.monotonic()
        if self._cache is None or (now - self._cache_at) >= CACHE_TTL_S:
            async with httpx.AsyncClient() as client:
                self._cache = await self._discover_and_benchmark(client)
                self._cache_at = now
        return self._pick_from_cache()

    def _pick_from_cache(self) -> Optional[dict]:
        healthy = [r for r in (self._cache or []) if r["ok"] and r["score"] >= QUALITY_FLOOR]
        if not healthy:
            return None
        return min(healthy, key=lambda r: r["latency"])

    async def _discover_and_benchmark(self, client: httpx.AsyncClient) -> list[dict]:
        try:
            resp = await client.get(f"{self._base_url}/api/tags", timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return []

        models = [
            (m["model"], "thinking" in (m.get("capabilities") or []))
            for m in data.get("models", [])
            if "completion" in (m.get("capabilities") or [])
        ]
        # Cloud-hosted models first (network-bound, unaffected by local
        # CPU/RAM limits), then alphabetical among the rest.
        ordered = sorted(models, key=lambda m: (0 if "-cloud" in m[0] else 1, m[0]))

        results: list[dict] = []
        for name, supports_thinking in ordered:
            score = _quality_score(name)
            if score < QUALITY_FLOOR:
                results.append({"name": name, "score": score, "latency": None, "ok": False, "supports_thinking": supports_thinking})
                continue
            latency = await self._benchmark(client, name)
            results.append({
                "name": name,
                "score": score,
                "latency": latency,
                "ok": latency is not None,
                "supports_thinking": supports_thinking,
            })
            if latency is not None and latency <= GOOD_ENOUGH_LATENCY_S:
                break  # good enough — stop trialing further candidates
        return results

    async def _benchmark(self, client: httpx.AsyncClient, name: str) -> Optional[float]:
        start = time.monotonic()
        try:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": name,
                    "messages": [{"role": "user", "content": "Say OK."}],
                    "stream": False,
                    "think": False,
                },
                timeout=BENCHMARK_TIMEOUT_S,
            )
            resp.raise_for_status()
            return time.monotonic() - start
        except Exception:
            return None
