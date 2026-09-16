"""Platform-neutral domain models.

These are deliberately *not* discord.py objects. The adapter layer converts
`discord.Member` / `discord.Message` into these snapshots, which keeps the engines
testable and makes the suite portable to another chat platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Action(StrEnum):
    ALLOW = "allow"
    FLAG = "flag"
    DELETE = "delete"
    WARN = "warn"
    TIMEOUT = "timeout"
    KICK = "kick"
    BAN = "ban"
    LOCKDOWN = "lockdown"


#: Ordering used when several rules fire on the same event: the harshest wins.
SEVERITY: dict[Action, int] = {
    Action.ALLOW: 0,
    Action.FLAG: 1,
    Action.DELETE: 2,
    Action.WARN: 3,
    Action.TIMEOUT: 4,
    Action.KICK: 5,
    Action.BAN: 6,
    Action.LOCKDOWN: 7,
}


@dataclass(frozen=True)
class MemberSnapshot:
    id: int
    name: str
    account_created_at: float
    has_avatar: bool
    joined_at: float


@dataclass(frozen=True)
class MessageSnapshot:
    id: int
    author_id: int
    author_name: str
    channel_id: int
    content: str
    created_at: float
    mention_count: int = 0
    mentions_everyone: bool = False


@dataclass
class Verdict:
    action: Action
    rule: str
    reason: str
    score: float = 0.0
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"[{self.action.value}] {self.rule}: {self.reason}"


def harshest(verdicts: list[Verdict]) -> Verdict | None:
    """Return the verdict with the highest severity, or None for an empty list."""
    if not verdicts:
        return None
    return max(verdicts, key=lambda v: SEVERITY[v.action])
