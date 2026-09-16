from __future__ import annotations

from botsuite.models import Action
from botsuite.security import SecurityEngine


def test_clean_message_is_allowed_and_not_audited(clock, make_message):
    engine = SecurityEngine(clock)
    decision = engine.on_message(make_message(content="salut tout le monde"))
    assert decision.action is Action.ALLOW
    assert engine.audit == []


def test_offending_message_is_audited(clock, make_message):
    engine = SecurityEngine(clock)
    decision = engine.on_message(make_message(content="FREE NITRO ici discord.gg/abc"))
    assert decision.action is not Action.ALLOW
    assert len(engine.audit) == len(decision.verdicts)
    assert {r.subject_name for r in engine.audit} == {"user1"}


def test_repeated_offences_escalate(clock, make_message):
    engine = SecurityEngine(clock)
    actions = []
    for i in range(6):
        actions.append(engine.on_message(make_message(content=f"free nitro {i}")).action)
        clock.advance(5)
    assert actions[0] is Action.WARN
    assert actions[-1] in (Action.KICK, Action.BAN)


def test_join_of_a_lone_suspicious_account_is_only_flagged(clock, make_member):
    engine = SecurityEngine(clock)
    decision = engine.on_member_join(make_member(name="throwaway", age_days=0.1, avatar=False))
    assert decision.action in (Action.ALLOW, Action.FLAG)
    assert decision.action is not Action.LOCKDOWN
