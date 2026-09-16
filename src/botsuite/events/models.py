"""Event lifecycle as an explicit state machine.

Every transition is validated, so a double click on "Rejoindre" after the event has been
locked raises instead of silently corrupting the roster. The whole object is JSON
round-trippable — that is what lets the state live in the store rather than in memory.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class EventState(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    LOCKED = "locked"
    RUNNING = "running"
    FINISHED = "finished"
    CANCELLED = "cancelled"


ALLOWED: dict[EventState, set[EventState]] = {
    EventState.DRAFT: {EventState.OPEN, EventState.CANCELLED},
    EventState.OPEN: {EventState.LOCKED, EventState.CANCELLED},
    EventState.LOCKED: {EventState.RUNNING, EventState.OPEN, EventState.CANCELLED},
    EventState.RUNNING: {EventState.FINISHED, EventState.CANCELLED},
    EventState.FINISHED: set(),
    EventState.CANCELLED: set(),
}


class InvalidTransition(RuntimeError):
    pass


class EventFull(RuntimeError):
    pass


@dataclass
class Participant:
    user_id: int
    name: str
    rating: float = 1000.0
    signed_up_at: float = 0.0


@dataclass
class Event:
    id: str
    title: str
    guild_id: int
    capacity: int = 16
    team_count: int = 2
    state: EventState = EventState.DRAFT
    opens_at: float = 0.0
    starts_at: float = 0.0
    participants: dict[int, Participant] = field(default_factory=dict)
    teams: list[list[int]] = field(default_factory=list)
    standings: list[int] = field(default_factory=list)
    channel_ids: list[int] = field(default_factory=list)
    role_ids: list[int] = field(default_factory=list)
    reminded_at: float | None = None

    # -- transitions -------------------------------------------------------
    def _transition(self, target: EventState) -> None:
        if target not in ALLOWED[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {target.value} interdit")
        self.state = target

    def open(self) -> None:
        self._transition(EventState.OPEN)

    def lock(self) -> None:
        self._transition(EventState.LOCKED)

    def reopen(self) -> None:
        self._transition(EventState.OPEN)

    def start(self) -> None:
        self._transition(EventState.RUNNING)

    def finish(self, standings: list[int]) -> None:
        self._transition(EventState.FINISHED)
        self.standings = list(standings)

    def cancel(self) -> None:
        self._transition(EventState.CANCELLED)

    # -- roster ------------------------------------------------------------
    @property
    def is_full(self) -> bool:
        return len(self.participants) >= self.capacity

    def signup(self, participant: Participant) -> bool:
        """Returns False when the member was already registered (idempotent click)."""
        if self.state is not EventState.OPEN:
            raise InvalidTransition("les inscriptions ne sont pas ouvertes")
        if participant.user_id in self.participants:
            return False
        if self.is_full:
            raise EventFull(f"{self.title} est complet ({self.capacity} places)")
        self.participants[participant.user_id] = participant
        return True

    def withdraw(self, user_id: int) -> bool:
        if self.state not in (EventState.OPEN, EventState.LOCKED):
            raise InvalidTransition("désinscription impossible à ce stade")
        return self.participants.pop(user_id, None) is not None

    # -- serialisation -----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        data["participants"] = {str(k): asdict(v) for k, v in self.participants.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        payload = dict(data)
        payload["state"] = EventState(payload["state"])
        payload["participants"] = {
            int(k): Participant(**v) for k, v in payload.get("participants", {}).items()
        }
        return cls(**payload)
