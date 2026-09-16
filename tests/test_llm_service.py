from __future__ import annotations

import asyncio

import pytest

from botsuite.llm import ChatService, MockProvider
from botsuite.llm.queue import QuotaConfig, QuotaExceeded, RequestQueue, UserQuota


def test_quota_blocks_after_the_limit(clock):
    quota = UserQuota(clock, QuotaConfig(max_calls=3, window_seconds=60))
    for _ in range(3):
        quota.consume(1)
    with pytest.raises(QuotaExceeded):
        quota.consume(1)


def test_quota_window_slides(clock):
    quota = UserQuota(clock, QuotaConfig(max_calls=2, window_seconds=10))
    quota.consume(1)
    quota.consume(1)
    clock.advance(11)
    quota.consume(1)
    assert quota.remaining(1) == 1


def test_quota_is_per_user(clock):
    quota = UserQuota(clock, QuotaConfig(max_calls=1, window_seconds=60))
    quota.consume(1)
    quota.consume(2)


async def test_queue_bounds_concurrency():
    queue = RequestQueue(MockProvider(latency=0.01), concurrency=2)
    await asyncio.gather(*(queue.submit([{"role": "user", "content": f"q{i}"}]) for i in range(10)))
    assert queue.peak_in_flight <= 2
    assert queue.waited > 0


async def test_service_returns_chunked_reply(clock):
    service = ChatService(provider=MockProvider(), clock=clock)
    reply = await service.ask(user_id=1, channel_key="c", prompt="détaille l'architecture")
    assert reply.ok
    assert len(reply.chunks) > 1
    assert all(len(c) <= 2000 for c in reply.chunks)


async def test_service_keeps_history(clock):
    service = ChatService(provider=MockProvider(), clock=clock)
    await service.ask(user_id=1, channel_key="c", prompt="première question")
    await service.ask(user_id=1, channel_key="c", prompt="deuxième question")
    assert len(service.conversation("c").turns) == 4  # 2 user + 2 assistant


async def test_service_reports_quota_error_instead_of_raising(clock):
    service = ChatService(
        provider=MockProvider(), clock=clock, quota=QuotaConfig(max_calls=1, window_seconds=60)
    )
    assert (await service.ask(user_id=1, channel_key="c", prompt="a")).ok
    second = await service.ask(user_id=1, channel_key="c", prompt="b")
    assert not second.ok
    assert "quota" in second.error


async def test_conversations_are_isolated_per_channel(clock):
    service = ChatService(provider=MockProvider(), clock=clock)
    await service.ask(user_id=1, channel_key="a", prompt="question A")
    await service.ask(user_id=1, channel_key="b", prompt="question B")
    assert len(service.conversation("a").turns) == 2
    assert len(service.conversation("b").turns) == 2
