"""Graduated sanctions.

Infraction points decay exponentially, so a member who slips once a month never climbs
the ladder while someone flooding for ten minutes reaches a timeout quickly. Every step is
reversible until `BAN`, which is deliberately the last one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..clock import Clock
from ..models import Action


@dataclass
class LadderConfig:
    #: Time for accumulated points to fall to 1/e of their value.
    decay_seconds: float = 3600.0
    #: (points threshold, action) — evaluated from the highest threshold down.
    steps: tuple[tuple[float, Action], ...] = (
        (1.0, Action.WARN),
        (3.0, Action.TIMEOUT),
        (5.0, Action.KICK),
        (8.0, Action.BAN),
    )


@dataclass
class _Record:
    points: float = 0.0
    updated_at: float = 0.0


@dataclass
class SanctionLadder:
    clock: Clock
    config: LadderConfig = field(default_factory=LadderConfig)
    _records: dict[int, _Record] = field(default_factory=dict, init=False)

    def points(self, user_id: int, now: float | None = None) -> float:
        record = self._records.get(user_id)
        if record is None:
            return 0.0
        now = self.clock.now() if now is None else now
        elapsed = max(0.0, now - record.updated_at)
        return record.points * math.exp(-elapsed / self.config.decay_seconds)

    def record(
        self, user_id: int, weight: float = 1.0, now: float | None = None
    ) -> tuple[float, Action]:
        """Add `weight` infraction points and return (current points, action to apply)."""
        now = self.clock.now() if now is None else now
        current = self.points(user_id, now) + weight
        self._records[user_id] = _Record(points=current, updated_at=now)
        return current, self.action_for(current)

    def action_for(self, points: float) -> Action:
        action = Action.FLAG
        for threshold, candidate in self.config.steps:
            if points >= threshold:
                action = candidate
        return action

    def forgive(self, user_id: int) -> None:
        self._records.pop(user_id, None)
