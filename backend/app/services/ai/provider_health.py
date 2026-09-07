"""
Per-provider cooldown tracking so the LLM router skips providers it knows are
currently exhausted (rate-limited, erroring) instead of retrying them blind
on every request.

Mirrors the health/backoff design used in the Interview Copilot project's
`ProviderHealthTracker` (TS) — flat 60s cooldown on rate-limit signals
(matches Groq's per-minute reset window), exponential backoff (capped) on
repeated non-rate-limit failures.
"""
import time


class ProviderHealthTracker:
    def __init__(self):
        self._cooldown_until: dict[str, float] = {}
        self._fail_streak: dict[str, int] = {}

    def is_available(self, provider_id: str) -> bool:
        until = self._cooldown_until.get(provider_id)
        return until is None or time.monotonic() >= until

    def record_success(self, provider_id: str) -> None:
        self._fail_streak.pop(provider_id, None)
        self._cooldown_until.pop(provider_id, None)

    def record_failure(self, provider_id: str, rate_limited: bool = False) -> None:
        streak = self._fail_streak.get(provider_id, 0) + 1
        self._fail_streak[provider_id] = streak
        cooldown = 60.0 if rate_limited else min(2 ** streak, 300.0)
        self._cooldown_until[provider_id] = time.monotonic() + cooldown


# Process-wide singleton. A fresh LLMClient/router is built per request, but
# cooldown state has to persist across requests for "skip what's currently
# exhausted" to mean anything.
_shared_tracker = ProviderHealthTracker()


def get_health_tracker() -> ProviderHealthTracker:
    return _shared_tracker


def looks_rate_limited(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None) == 429:
        return True
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "rate_limit" in text
