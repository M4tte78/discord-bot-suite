"""The simulator scenarios double as end-to-end regression tests.

Because the world is seeded and the clock is fake, these assertions are exact.
"""

from __future__ import annotations

from botsuite.sim.scenarios import SCENARIOS, chat, moderation, raid, tournament


def test_every_scenario_is_registered():
    assert set(SCENARIOS) == {"raid", "moderation", "chat", "tournament"}


def test_raid_scenario():
    summary = raid.run(verbose=False)
    assert summary["legit_flagged"] == 0, "aucun membre légitime ne doit être signalé"
    assert summary["lockdown_at"] is not None
    assert summary["lockdown_at"] <= 10, "le verrouillage doit arriver tôt dans la vague"
    assert summary["raid_flagged"] >= summary["raid_size"] - 2


def test_moderation_scenario():
    summary = moderation.run(verbose=False)
    assert summary["regular_blocked"] == 0
    assert summary["final_action"] == "ban"
    assert {"spam.flood", "spam.cross_post", "spam.mentions", "spam.invite"} <= set(
        summary["rules_fired"]
    )
    assert "content.scam.free_nitro" in summary["rules_fired"]


def test_chat_scenario():
    summary = chat.run(verbose=False)
    assert summary["max_chunk"] <= 2000
    assert summary["chunks"] > 1
    assert summary["code_fence_preserved"]
    assert summary["quota_refusals"] == 1
    assert summary["peak_in_flight"] <= 2


def test_tournament_scenario():
    summary = tournament.run(verbose=False)
    assert summary["signed_up"] == summary["capacity"]
    assert summary["rejected"] == 1
    assert summary["duplicates_ignored"] == 1
    assert summary["state_survived_restart"]
    assert summary["final_state"] == "finished"
    assert summary["reminders_sent"] == 1


def test_scenarios_are_reproducible():
    assert raid.run(verbose=False) == raid.run(verbose=False)
    assert tournament.run(verbose=False) == tournament.run(verbose=False)
