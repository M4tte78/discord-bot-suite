from __future__ import annotations

import pytest

from botsuite.events import EventService, Leaderboard, Participant
from botsuite.events.matchmaking import balanced_teams, spread
from botsuite.events.models import Event, EventFull, EventState, InvalidTransition
from botsuite.storage import MemoryStore


@pytest.fixture
def service(clock):
    return EventService(MemoryStore(), clock)


def _participants(n, rating=1000):
    return [Participant(user_id=i, name=f"p{i}", rating=rating + i * 10) for i in range(1, n + 1)]


def test_signup_requires_open_state(service):
    event = service.create("e1", "Tournoi", 1)
    with pytest.raises(InvalidTransition):
        service.signup("e1", Participant(user_id=1, name="a"))
    event.open()
    service.save(event)
    _, added = service.signup("e1", Participant(user_id=1, name="a"))
    assert added


def test_double_signup_is_idempotent(service):
    event = service.create("e1", "Tournoi", 1)
    event.open()
    service.save(event)
    participant = Participant(user_id=1, name="a")
    assert service.signup("e1", participant)[1] is True
    assert service.signup("e1", participant)[1] is False
    assert len(service.load("e1").participants) == 1


def test_capacity_is_enforced(service):
    event = service.create("e1", "Tournoi", 1, capacity=2)
    event.open()
    service.save(event)
    for participant in _participants(2):
        service.signup("e1", participant)
    with pytest.raises(EventFull):
        service.signup("e1", Participant(user_id=99, name="late"))


def test_invalid_transitions_are_rejected():
    event = Event(id="e", title="t", guild_id=1)
    with pytest.raises(InvalidTransition):
        event.start()
    event.open()
    event.lock()
    event.start()
    event.finish([])
    with pytest.raises(InvalidTransition):
        event.open()


def test_state_survives_a_restart(service, clock):
    event = service.create("e1", "Tournoi", 1, capacity=8, team_count=2)
    event.open()
    service.save(event)
    for participant in _participants(8):
        service.signup("e1", participant)
    service.lock_and_build_teams("e1")

    rebooted = EventService(service.store, clock)
    recovered = rebooted.load("e1")
    assert recovered.state is EventState.LOCKED
    assert len(recovered.participants) == 8
    assert sum(len(team) for team in recovered.teams) == 8


def test_scheduler_returns_due_work(service, clock):
    now = clock.now()
    service.create("e1", "T", 1, opens_at=now + 10, starts_at=now + 1000)
    assert service.due().is_empty
    clock.advance(11)
    due = service.due()
    assert [e.id for e in due.to_open] == ["e1"]


def test_reminder_is_sent_once(service, clock):
    now = clock.now()
    event = service.create("e1", "T", 1, starts_at=now + 1000)
    event.open()
    service.save(event)
    clock.advance(200)  # reminder_lead defaults to 900 s
    assert len(service.due().to_remind) == 1
    service.mark_reminded("e1")
    assert len(service.due().to_remind) == 0


def test_balanced_teams_are_balanced():
    teams = balanced_teams(_participants(12), 3)
    assert [len(t) for t in teams] == [4, 4, 4]
    assert spread(teams) < 100


def test_balanced_teams_are_deterministic():
    players = _participants(9)
    assert balanced_teams(players, 3) == balanced_teams(list(reversed(players)), 3)


def test_leaderboard_accumulates(clock):
    store = MemoryStore()
    board = Leaderboard(store, guild_id=1)
    board.record_results([(1, "a"), (2, "b")])
    board.record_results([(2, "b"), (1, "a")])
    top = board.top()
    assert top[0].name in ("a", "b")
    assert top[0].points == 16
    assert top[0].events == 2


def test_leaderboards_are_scoped_per_guild():
    store = MemoryStore()
    Leaderboard(store, guild_id=1).record_results([(1, "a")])
    assert Leaderboard(store, guild_id=2).top() == []
