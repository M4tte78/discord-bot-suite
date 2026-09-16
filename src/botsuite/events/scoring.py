"""Persistent leaderboard."""

from __future__ import annotations

from dataclasses import dataclass

from ..storage.base import KeyValueStore

NAMESPACE = "leaderboard"
DEFAULT_POINTS = (10, 6, 4, 2, 1)


@dataclass
class Standing:
    user_id: int
    name: str
    points: int
    events: int


class Leaderboard:
    def __init__(self, store: KeyValueStore, guild_id: int, points=DEFAULT_POINTS) -> None:
        self.store = store
        self.guild_id = guild_id
        self.points = tuple(points)

    def _key(self, user_id: int) -> str:
        return f"{self.guild_id}:{user_id}"

    def award(self, user_id: int, name: str, points: int) -> Standing:
        current = self.store.get(NAMESPACE, self._key(user_id)) or {
            "user_id": user_id,
            "name": name,
            "points": 0,
            "events": 0,
        }
        current["points"] += points
        current["events"] += 1
        current["name"] = name
        self.store.put(NAMESPACE, self._key(user_id), current)
        return Standing(**current)

    def record_results(self, ranking: list[tuple[int, str]]) -> list[Standing]:
        """`ranking` is ordered best-first."""
        out = []
        for position, (user_id, name) in enumerate(ranking):
            points = self.points[position] if position < len(self.points) else 0
            out.append(self.award(user_id, name, points))
        return out

    def top(self, limit: int = 10) -> list[Standing]:
        rows = [
            Standing(**payload)
            for key, payload in self.store.items(NAMESPACE)
            if key.startswith(f"{self.guild_id}:")
        ]
        rows.sort(key=lambda s: (-s.points, s.name))
        return rows[:limit]
