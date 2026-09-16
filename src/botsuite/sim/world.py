"""A deterministic fake Discord server.

Everything is generated from a seeded `random.Random`, so two runs of the same scenario
produce byte-identical output. That is what lets the scenarios double as tests.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import count

from ..clock import FakeClock
from ..models import MemberSnapshot, MessageSnapshot

DAY = 86_400.0

FIRST = [
    "luca",
    "nina",
    "theo",
    "maya",
    "adam",
    "lea",
    "hugo",
    "jade",
    "noah",
    "iris",
    "eliot",
    "sara",
    "kais",
    "romy",
    "milo",
    "alba",
    "yanis",
    "zoe",
    "gabin",
    "nour",
]
LAST = [
    "fox",
    "wave",
    "storm",
    "pixel",
    "koda",
    "ember",
    "nova",
    "flux",
    "rune",
    "vega",
]


@dataclass
class SimWorld:
    seed: int = 1337
    guild_id: int = 900_000_001
    clock: FakeClock = field(default_factory=FakeClock)
    channels: tuple[int, ...] = (100, 101, 102, 103)
    _ids: count[int] = field(default_factory=lambda: count(1_000), init=False)
    _msg_ids: count[int] = field(default_factory=lambda: count(50_000), init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self._used_names: set[str] = set()

    def _unique_name(self) -> str:
        for _ in range(64):
            candidate = f"{self.rng.choice(FIRST)}_{self.rng.choice(LAST)}"
            if candidate not in self._used_names:
                self._used_names.add(candidate)
                return candidate
        candidate = f"member_{len(self._used_names) + 1}"
        self._used_names.add(candidate)
        return candidate

    # -- members -----------------------------------------------------------
    def member(
        self,
        *,
        name: str | None = None,
        account_age_days: float | None = None,
        has_avatar: bool | None = None,
    ) -> MemberSnapshot:
        now = self.clock.now()
        if name is None:
            name = self._unique_name()
        if account_age_days is None:
            account_age_days = self.rng.uniform(60.0, 1200.0)
        if has_avatar is None:
            has_avatar = self.rng.random() > 0.15
        return MemberSnapshot(
            id=next(self._ids),
            name=name,
            account_created_at=now - account_age_days * DAY,
            has_avatar=has_avatar,
            joined_at=now,
        )

    def raid_wave(self, size: int, template: str = "free_nitro_{i:02d}") -> list[MemberSnapshot]:
        """Accounts created the same day, no avatar, names from one template."""
        now = self.clock.now()
        return [
            MemberSnapshot(
                id=next(self._ids),
                name=template.format(i=i),
                account_created_at=now - self.rng.uniform(0.2, 2.0) * DAY,
                has_avatar=False,
                joined_at=now,
            )
            for i in range(1, size + 1)
        ]

    # -- messages ----------------------------------------------------------
    def message(
        self,
        author: MemberSnapshot,
        content: str,
        *,
        channel_id: int | None = None,
        mention_count: int = 0,
        mentions_everyone: bool = False,
    ) -> MessageSnapshot:
        return MessageSnapshot(
            id=next(self._msg_ids),
            author_id=author.id,
            author_name=author.name,
            channel_id=channel_id if channel_id is not None else self.channels[0],
            content=content,
            created_at=self.clock.now(),
            mention_count=mention_count,
            mentions_everyone=mentions_everyone,
        )

    # -- time --------------------------------------------------------------
    def tick(self, seconds: float) -> float:
        return self.clock.advance(seconds)
