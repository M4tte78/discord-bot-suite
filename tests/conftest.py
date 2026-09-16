from __future__ import annotations

import pytest

from botsuite.clock import FakeClock
from botsuite.models import MemberSnapshot, MessageSnapshot

DAY = 86_400.0


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_member(clock: FakeClock):
    counter = {"n": 0}

    def _make(name="member", age_days=365.0, avatar=True, joined_at=None):
        counter["n"] += 1
        at = clock.now() if joined_at is None else joined_at
        return MemberSnapshot(
            id=counter["n"],
            name=name,
            account_created_at=at - age_days * DAY,
            has_avatar=avatar,
            joined_at=at,
        )

    return _make


@pytest.fixture
def make_message(clock: FakeClock):
    counter = {"n": 0}

    def _make(content="hello", author_id=1, channel_id=100, at=None, mentions=0, everyone=False):
        counter["n"] += 1
        return MessageSnapshot(
            id=1000 + counter["n"],
            author_id=author_id,
            author_name=f"user{author_id}",
            channel_id=channel_id,
            content=content,
            created_at=clock.now() if at is None else at,
            mention_count=mentions,
            mentions_everyone=everyone,
        )

    return _make
