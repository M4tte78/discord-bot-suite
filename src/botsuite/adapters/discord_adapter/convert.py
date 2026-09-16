"""discord.py objects → domain snapshots.

Kept in its own module with no `discord` import at module scope, so the conversion logic
can be unit-tested against duck-typed stubs.
"""

from __future__ import annotations

from typing import Any

from ...models import MemberSnapshot, MessageSnapshot


def _timestamp(value: Any) -> float:
    return value.timestamp() if hasattr(value, "timestamp") else float(value)


def to_member_snapshot(member: Any, *, joined_at: Any = None) -> MemberSnapshot:
    joined = joined_at if joined_at is not None else member.joined_at
    return MemberSnapshot(
        id=int(member.id),
        name=str(getattr(member, "name", member)),
        account_created_at=_timestamp(member.created_at),
        has_avatar=getattr(member, "avatar", None) is not None,
        joined_at=_timestamp(joined),
    )


def to_message_snapshot(message: Any) -> MessageSnapshot:
    return MessageSnapshot(
        id=int(message.id),
        author_id=int(message.author.id),
        author_name=str(message.author),
        channel_id=int(message.channel.id),
        content=message.content or "",
        created_at=_timestamp(message.created_at),
        mention_count=len(getattr(message, "mentions", []) or []),
        mentions_everyone=bool(getattr(message, "mention_everyone", False)),
    )
