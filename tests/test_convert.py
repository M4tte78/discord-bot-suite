"""The adapter conversion is tested against duck-typed stubs, so the test suite never
needs a gateway connection — or even discord.py — to cover it."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from botsuite.adapters.discord_adapter.convert import to_member_snapshot, to_message_snapshot

CREATED = dt.datetime(2024, 1, 1, tzinfo=dt.UTC)
JOINED = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def test_member_conversion():
    member = SimpleNamespace(
        id=42, name="luca", created_at=CREATED, joined_at=JOINED, avatar=object()
    )
    snapshot = to_member_snapshot(member)
    assert snapshot.id == 42
    assert snapshot.name == "luca"
    assert snapshot.has_avatar is True
    assert snapshot.joined_at == JOINED.timestamp()


def test_member_without_avatar():
    member = SimpleNamespace(id=1, name="x", created_at=CREATED, joined_at=JOINED, avatar=None)
    assert to_member_snapshot(member).has_avatar is False


def test_message_conversion():
    message = SimpleNamespace(
        id=7,
        author=SimpleNamespace(id=42, __str__=lambda self: "luca"),
        channel=SimpleNamespace(id=100),
        content="salut",
        created_at=JOINED,
        mentions=[1, 2, 3],
        mention_everyone=False,
    )
    snapshot = to_message_snapshot(message)
    assert snapshot.author_id == 42
    assert snapshot.channel_id == 100
    assert snapshot.mention_count == 3
    assert snapshot.mentions_everyone is False


def test_message_with_empty_content():
    message = SimpleNamespace(
        id=8,
        author=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=2),
        content=None,
        created_at=JOINED,
        mentions=None,
        mention_everyone=True,
    )
    snapshot = to_message_snapshot(message)
    assert snapshot.content == ""
    assert snapshot.mention_count == 0
    assert snapshot.mentions_everyone is True
