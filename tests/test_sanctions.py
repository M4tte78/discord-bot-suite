from __future__ import annotations

from botsuite.models import Action
from botsuite.security.sanctions import LadderConfig, SanctionLadder


def test_ladder_escalates(clock):
    ladder = SanctionLadder(clock)
    actions = [ladder.record(1)[1] for _ in range(8)]
    assert actions[0] is Action.WARN
    assert Action.TIMEOUT in actions
    assert Action.KICK in actions
    assert actions[-1] is Action.BAN


def test_points_decay(clock):
    ladder = SanctionLadder(clock, LadderConfig(decay_seconds=60.0))
    ladder.record(1, weight=4.0)
    assert ladder.points(1) == 4.0
    clock.advance(600)  # ten half-lives worth
    assert ladder.points(1) < 0.1


def test_decay_prevents_escalation_for_occasional_offenders(clock):
    ladder = SanctionLadder(clock, LadderConfig(decay_seconds=60.0))
    for _ in range(5):
        _, action = ladder.record(1, weight=1.0)
        assert action is Action.WARN
        clock.advance(3600)


def test_forgive_resets(clock):
    ladder = SanctionLadder(clock)
    ladder.record(1, weight=5.0)
    ladder.forgive(1)
    assert ladder.points(1) == 0.0
