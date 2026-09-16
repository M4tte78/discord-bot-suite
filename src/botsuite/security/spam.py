"""Flood, duplicate and mention-bomb detection.

Rate limiting uses a token bucket per author: a burst is tolerated up to the bucket
capacity, then the allowance refills at a fixed rate. That is far less punishing for
normal chatter than a fixed "N messages per minute" counter.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from ..clock import Clock
from ..models import Action, MessageSnapshot, Verdict
from .content import collapsed

INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord(?:app)?\.com/invite|discord\.gg|dsc\.gg)/[\w-]+",
    re.IGNORECASE,
)


@dataclass
class SpamConfig:
    bucket_capacity: float = 5.0
    refill_per_second: float = 0.5
    duplicate_window_seconds: float = 60.0
    duplicate_channel_threshold: int = 3
    mention_limit: int = 5
    allow_invites: bool = False


class TokenBucket:
    """Classic token bucket. `consume` returns False when the allowance is exhausted."""

    def __init__(self, capacity: float, refill_per_second: float, clock: Clock) -> None:
        self.capacity = float(capacity)
        self.refill_per_second = float(refill_per_second)
        self.clock = clock
        self._tokens = float(capacity)
        self._last = clock.now()

    def _refill(self, now: float) -> None:
        elapsed = max(0.0, now - self._last)
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_second)
        self._last = now

    @property
    def tokens(self) -> float:
        self._refill(self.clock.now())
        return self._tokens

    def consume(self, amount: float = 1.0, now: float | None = None) -> bool:
        self._refill(self.clock.now() if now is None else now)
        if self._tokens >= amount:
            self._tokens -= amount
            return True
        return False


@dataclass
class _DuplicateTrack:
    channels: set[int] = field(default_factory=set)
    first_seen: float = 0.0


class SpamDetector:
    def __init__(self, clock: Clock, config: SpamConfig | None = None) -> None:
        self.clock = clock
        self.config = config or SpamConfig()
        self._buckets: dict[int, TokenBucket] = {}
        self._duplicates: dict[tuple[int, str], _DuplicateTrack] = {}

    def _bucket(self, author_id: int) -> TokenBucket:
        bucket = self._buckets.get(author_id)
        if bucket is None:
            bucket = TokenBucket(
                self.config.bucket_capacity, self.config.refill_per_second, self.clock
            )
            self._buckets[author_id] = bucket
        return bucket

    def _fingerprint(self, content: str) -> str:
        return hashlib.sha1(collapsed(content).encode("utf-8")).hexdigest()[:16]

    def _prune_duplicates(self, now: float) -> None:
        window = self.config.duplicate_window_seconds
        stale = [k for k, v in self._duplicates.items() if now - v.first_seen > window]
        for key in stale:
            del self._duplicates[key]

    def on_message(self, message: MessageSnapshot) -> list[Verdict]:
        cfg = self.config
        now = message.created_at
        verdicts: list[Verdict] = []

        # 1. Flood
        if not self._bucket(message.author_id).consume(now=now):
            verdicts.append(
                Verdict(
                    action=Action.DELETE,
                    rule="spam.flood",
                    reason="débit de messages au-delà de l'allocation du token bucket",
                    score=1.0,
                    details={"capacity": cfg.bucket_capacity, "refill": cfg.refill_per_second},
                )
            )

        # 2. Same payload across several channels
        self._prune_duplicates(now)
        if collapsed(message.content):
            key = (message.author_id, self._fingerprint(message.content))
            track = self._duplicates.setdefault(key, _DuplicateTrack(first_seen=now))
            track.channels.add(message.channel_id)
            if len(track.channels) >= cfg.duplicate_channel_threshold:
                verdicts.append(
                    Verdict(
                        action=Action.DELETE,
                        rule="spam.cross_post",
                        reason=f"message identique dans {len(track.channels)} salons",
                        score=1.0,
                        details={"channels": sorted(track.channels)},
                    )
                )

        # 3. Mention bombing
        if message.mentions_everyone or message.mention_count >= cfg.mention_limit:
            verdicts.append(
                Verdict(
                    action=Action.DELETE,
                    rule="spam.mentions",
                    reason=(
                        "mention @everyone"
                        if message.mentions_everyone
                        else f"{message.mention_count} mentions dans un seul message"
                    ),
                    score=1.0,
                    details={"mention_count": message.mention_count},
                )
            )

        # 4. Third-party invite links
        if not cfg.allow_invites:
            match = INVITE_RE.search(message.content)
            if match:
                verdicts.append(
                    Verdict(
                        action=Action.DELETE,
                        rule="spam.invite",
                        reason="lien d'invitation externe",
                        score=1.0,
                        details={"match": match.group(0)},
                    )
                )

        return verdicts
