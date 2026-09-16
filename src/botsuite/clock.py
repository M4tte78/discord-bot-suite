"""Injectable clock.

Every component that reasons about time takes a `Clock` instead of calling `time.time()`.
Tests and the simulator inject `FakeClock`, so a 30-second raid window can be exercised in
microseconds and the results are byte-for-byte reproducible.
"""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float:
        """Seconds since the epoch."""
        ...


class RealClock:
    def now(self) -> float:
        return time.time()


class FakeClock:
    """Manually advanced clock."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self._t = float(start)

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> float:
        self._t += float(seconds)
        return self._t
