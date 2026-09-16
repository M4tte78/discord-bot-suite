"""Bounded concurrency and per-user quotas.

Two different problems, often confused:

* **Quota** protects the budget — one user cannot burn the monthly allowance alone.
* **Queue** protects the provider and the event loop — however many users ask at once,
  only `concurrency` requests are in flight, the rest wait.

Without the queue, a busy server produces a burst of concurrent HTTP calls, the provider
answers 429, and every user sees an error. With it, they just wait a little longer.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field

from ..clock import Clock
from .provider import Provider


class QuotaExceeded(RuntimeError):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"quota atteint, réessaye dans {retry_after:.0f} s")
        self.retry_after = retry_after


@dataclass
class QuotaConfig:
    max_calls: int = 5
    window_seconds: float = 60.0


@dataclass
class UserQuota:
    clock: Clock
    config: QuotaConfig = field(default_factory=QuotaConfig)
    _hits: dict[int, deque[float]] = field(default_factory=dict, init=False)

    def _window(self, user_id: int, now: float) -> deque[float]:
        hits = self._hits.setdefault(user_id, deque())
        while hits and now - hits[0] > self.config.window_seconds:
            hits.popleft()
        return hits

    def remaining(self, user_id: int, now: float | None = None) -> int:
        now = self.clock.now() if now is None else now
        return max(0, self.config.max_calls - len(self._window(user_id, now)))

    def consume(self, user_id: int, now: float | None = None) -> None:
        now = self.clock.now() if now is None else now
        hits = self._window(user_id, now)
        if len(hits) >= self.config.max_calls:
            retry_after = self.config.window_seconds - (now - hits[0])
            raise QuotaExceeded(max(0.0, retry_after))
        hits.append(now)


class RequestQueue:
    """Serialises provider calls through a bounded pool of workers."""

    def __init__(self, provider: Provider, concurrency: int = 2) -> None:
        self.provider = provider
        self.concurrency = max(1, concurrency)
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self.in_flight = 0
        self.peak_in_flight = 0
        self.waited = 0

    async def submit(self, messages: list[dict[str, str]]) -> str:
        if self._semaphore.locked():
            self.waited += 1
        async with self._semaphore:
            self.in_flight += 1
            self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
            try:
                return await self.provider.complete(messages)
            finally:
                self.in_flight -= 1
