"""Event service: persistence, scheduling decisions, teams and results.

Every mutation is written back to the store immediately. The service holds no cached
state, so constructing a second `EventService` over the same store — which is exactly what
a process restart looks like — sees the identical world. The `tournament` scenario relies
on that to demonstrate crash-safety.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..clock import Clock
from ..storage.base import KeyValueStore
from .matchmaking import balanced_teams, spread
from .models import Event, EventState, Participant
from .scoring import Leaderboard

NAMESPACE = "events"


@dataclass
class DueTasks:
    to_open: list[Event]
    to_remind: list[Event]
    to_start: list[Event]

    @property
    def is_empty(self) -> bool:
        return not (self.to_open or self.to_remind or self.to_start)


class EventService:
    def __init__(self, store: KeyValueStore, clock: Clock, reminder_lead: float = 900.0) -> None:
        self.store = store
        self.clock = clock
        self.reminder_lead = reminder_lead

    # -- persistence -------------------------------------------------------
    def save(self, event: Event) -> Event:
        self.store.put(NAMESPACE, event.id, event.to_dict())
        return event

    def load(self, event_id: str) -> Event | None:
        payload = self.store.get(NAMESPACE, event_id)
        return Event.from_dict(payload) if payload else None

    def all(self) -> list[Event]:
        return [Event.from_dict(payload) for _, payload in self.store.items(NAMESPACE)]

    # -- commands ----------------------------------------------------------
    def create(
        self,
        event_id: str,
        title: str,
        guild_id: int,
        *,
        capacity: int = 16,
        team_count: int = 2,
        opens_at: float = 0.0,
        starts_at: float = 0.0,
    ) -> Event:
        event = Event(
            id=event_id,
            title=title,
            guild_id=guild_id,
            capacity=capacity,
            team_count=team_count,
            opens_at=opens_at,
            starts_at=starts_at,
        )
        return self.save(event)

    def signup(self, event_id: str, participant: Participant) -> tuple[Event, bool]:
        event = self._require(event_id)
        added = event.signup(participant)
        self.save(event)
        return event, added

    def withdraw(self, event_id: str, user_id: int) -> tuple[Event, bool]:
        event = self._require(event_id)
        removed = event.withdraw(user_id)
        self.save(event)
        return event, removed

    def lock_and_build_teams(self, event_id: str) -> tuple[Event, float]:
        event = self._require(event_id)
        event.lock()
        teams = balanced_teams(list(event.participants.values()), event.team_count)
        event.teams = [[p.user_id for p in team] for team in teams]
        self.save(event)
        return event, spread(teams)

    def start(self, event_id: str) -> Event:
        event = self._require(event_id)
        event.start()
        return self.save(event)

    def finish(self, event_id: str, standings: list[int]) -> Event:
        event = self._require(event_id)
        event.finish(standings)
        return self.save(event)

    def publish_results(self, event_id: str, leaderboard: Leaderboard) -> Event:
        event = self._require(event_id)
        ranking = [
            (user_id, event.participants[user_id].name)
            for user_id in event.standings
            if user_id in event.participants
        ]
        leaderboard.record_results(ranking)
        return event

    # -- scheduler ---------------------------------------------------------
    def due(self, now: float | None = None) -> DueTasks:
        """What the periodic task should act on right now."""
        now = self.clock.now() if now is None else now
        to_open, to_remind, to_start = [], [], []
        for event in self.all():
            if event.state is EventState.DRAFT and event.opens_at and now >= event.opens_at:
                to_open.append(event)
            elif event.state is EventState.OPEN:
                if event.starts_at and now >= event.starts_at:
                    to_start.append(event)
                elif (
                    event.starts_at
                    and event.reminded_at is None
                    and now >= event.starts_at - self.reminder_lead
                ):
                    to_remind.append(event)
        return DueTasks(to_open=to_open, to_remind=to_remind, to_start=to_start)

    def mark_reminded(self, event_id: str, at: float | None = None) -> Event:
        event = self._require(event_id)
        event.reminded_at = self.clock.now() if at is None else at
        return self.save(event)

    # -- internals ---------------------------------------------------------
    def _require(self, event_id: str) -> Event:
        event = self.load(event_id)
        if event is None:
            raise KeyError(f"événement inconnu : {event_id}")
        return event
