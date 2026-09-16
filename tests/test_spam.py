from __future__ import annotations

from botsuite.models import Action
from botsuite.security.spam import SpamConfig, SpamDetector, TokenBucket


def test_token_bucket_allows_a_burst_then_throttles(clock):
    bucket = TokenBucket(capacity=5, refill_per_second=0.5, clock=clock)
    assert all(bucket.consume() for _ in range(5))
    assert not bucket.consume()


def test_token_bucket_refills_over_time(clock):
    bucket = TokenBucket(capacity=2, refill_per_second=1.0, clock=clock)
    assert bucket.consume() and bucket.consume()
    assert not bucket.consume()
    clock.advance(1.0)
    assert bucket.consume()


def test_flood_is_detected(clock, make_message):
    detector = SpamDetector(clock, SpamConfig(bucket_capacity=3, refill_per_second=0.1))
    verdicts = []
    for i in range(6):
        verdicts.append(detector.on_message(make_message(content=f"m{i}")))
        clock.advance(0.1)
    assert verdicts[0] == []
    assert any(v.rule == "spam.flood" for v in verdicts[-1])


def test_cross_posting_is_detected(clock, make_message):
    detector = SpamDetector(clock, SpamConfig(duplicate_channel_threshold=3))
    results = [
        detector.on_message(make_message(content="promo !", channel_id=c)) for c in (1, 2, 3)
    ]
    assert not any(v.rule == "spam.cross_post" for v in results[0])
    assert any(v.rule == "spam.cross_post" for v in results[2])


def test_cross_post_window_expires(clock, make_message):
    detector = SpamDetector(
        clock, SpamConfig(duplicate_window_seconds=10, duplicate_channel_threshold=2)
    )
    detector.on_message(make_message(content="promo !", channel_id=1))
    clock.advance(30)
    verdicts = detector.on_message(make_message(content="promo !", channel_id=2, at=clock.now()))
    assert not any(v.rule == "spam.cross_post" for v in verdicts)


def test_mention_bomb_and_everyone(clock, make_message):
    detector = SpamDetector(clock)
    assert any(v.rule == "spam.mentions" for v in detector.on_message(make_message(mentions=7)))
    assert any(v.rule == "spam.mentions" for v in detector.on_message(make_message(everyone=True)))


def test_invite_links(clock, make_message):
    detector = SpamDetector(clock)
    for text in (
        "viens sur discord.gg/abc123",
        "https://discord.com/invite/xyz",
        "http://dsc.gg/zz",
    ):
        verdicts = detector.on_message(make_message(content=text))
        assert any(v.rule == "spam.invite" for v in verdicts), text
    assert not any(
        v.rule == "spam.invite" for v in detector.on_message(make_message(content="rien à voir"))
    )


def test_all_spam_verdicts_are_delete(clock, make_message):
    detector = SpamDetector(clock)
    verdicts = detector.on_message(make_message(content="discord.gg/abc", everyone=True))
    assert {v.action for v in verdicts} == {Action.DELETE}
