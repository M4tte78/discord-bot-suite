from __future__ import annotations

import pytest

from botsuite.security.raid import RaidConfig, RaidMonitor, name_similarity


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        RaidConfig(weight_account_age=0.9)


def test_legitimate_joins_are_low_risk(clock, make_member):
    monitor = RaidMonitor(clock)
    for _ in range(5):
        member = make_member(name="regular_user", age_days=400, avatar=True)
        assessment = monitor.observe(member)
        clock.advance(600)
        assert assessment.risk < 0.3
        assert not assessment.lockdown


def test_burst_of_fresh_lookalike_accounts_triggers_lockdown(clock, make_member):
    monitor = RaidMonitor(clock, RaidConfig(join_threshold=8, window_seconds=30))
    lockdown_at = None
    for i in range(12):
        member = make_member(name=f"free_nitro_{i:02d}", age_days=0.5, avatar=False)
        assessment = monitor.observe(member)
        if assessment.lockdown and lockdown_at is None:
            lockdown_at = i + 1
        clock.advance(1)
    assert lockdown_at == 8
    assert monitor.locked_down


def test_burst_of_legitimate_accounts_does_not_lock_down(clock, make_member):
    """A popular server can get 12 real joins in 12 seconds — that is not a raid."""
    monitor = RaidMonitor(clock, RaidConfig(join_threshold=8, window_seconds=30))
    names = [
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
        "milo",
        "zoe",
    ]
    for name in names:
        assessment = monitor.observe(make_member(name=name, age_days=500, avatar=True))
        clock.advance(1)
        assert not assessment.lockdown


def test_window_expiry_resets_the_burst(clock, make_member):
    monitor = RaidMonitor(clock, RaidConfig(join_threshold=8, window_seconds=30))
    for i in range(6):
        monitor.observe(make_member(name=f"x_{i}", age_days=0.5, avatar=False))
        clock.advance(1)
    clock.advance(120)
    assessment = monitor.observe(make_member(name="later", age_days=0.5, avatar=False))
    assert assessment.burst_size == 1


def test_name_similarity_is_symmetric_and_bounded():
    assert name_similarity("free_nitro_01", "free_nitro_02") > 0.85
    assert name_similarity("luca_fox", "zzzzzzzz") < 0.4
    assert 0.0 <= name_similarity("a", "b") <= 1.0


def test_release_lifts_lockdown(clock, make_member):
    monitor = RaidMonitor(clock, RaidConfig(join_threshold=2, window_seconds=30))
    for i in range(3):
        monitor.observe(make_member(name=f"raid_{i}", age_days=0.1, avatar=False))
    assert monitor.locked_down
    monitor.release()
    assert not monitor.locked_down
