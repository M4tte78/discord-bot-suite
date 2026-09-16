"""Raid detection.

Two signals are combined:

* **Join burst** — how many accounts joined inside a sliding window.
* **Per-account risk** — account age, missing avatar, and pseudonym similarity with the
  other accounts of the current burst (raid tooling tends to generate names from one
  template, e.g. `free_nitro_01` … `free_nitro_40`).

A single risky account is not a raid, and a burst of legitimate accounts is not a raid
either. Lockdown is only proposed when the burst is large *and* its mean risk is high.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..clock import Clock
from ..models import MemberSnapshot

DAY = 86_400.0


@dataclass
class RaidConfig:
    window_seconds: float = 30.0
    join_threshold: int = 8
    young_account_days: float = 7.0
    similarity_threshold: float = 0.75
    lockdown_mean_risk: float = 0.6
    history: int = 100
    #: Weights must sum to 1.0 — checked in __post_init__.
    weight_account_age: float = 0.35
    weight_no_avatar: float = 0.15
    weight_name_similarity: float = 0.25
    weight_burst: float = 0.25

    def __post_init__(self) -> None:
        total = (
            self.weight_account_age
            + self.weight_no_avatar
            + self.weight_name_similarity
            + self.weight_burst
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"risk weights must sum to 1.0, got {total}")


@dataclass(frozen=True)
class JoinAssessment:
    member_id: int
    member_name: str
    risk: float
    burst_size: int
    mean_risk: float
    lockdown: bool
    factors: dict[str, float]


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class RaidMonitor:
    """Stateful, single-guild join monitor."""

    def __init__(self, clock: Clock, config: RaidConfig | None = None) -> None:
        self.clock = clock
        self.config = config or RaidConfig()
        self._recent: deque[tuple[MemberSnapshot, float]] = deque(maxlen=self.config.history)
        self.locked_down = False

    # -- internals ---------------------------------------------------------
    def _prune(self, now: float) -> None:
        window = self.config.window_seconds
        while self._recent and now - self._recent[0][0].joined_at > window:
            self._recent.popleft()

    def _factors(self, member: MemberSnapshot, burst_size: int) -> dict[str, float]:
        cfg = self.config
        age_days = (member.joined_at - member.account_created_at) / DAY
        age_factor = _clamp(1.0 - age_days / cfg.young_account_days)

        similarity = max(
            (name_similarity(member.name, other.name) for other, _ in self._recent),
            default=0.0,
        )
        similarity_factor = similarity if similarity >= cfg.similarity_threshold else 0.0

        burst_factor = _clamp((burst_size - 1) / max(cfg.join_threshold - 1, 1))

        return {
            "account_age": round(age_factor, 4),
            "no_avatar": 0.0 if member.has_avatar else 1.0,
            "name_similarity": round(similarity_factor, 4),
            "burst": round(burst_factor, 4),
        }

    # -- public API --------------------------------------------------------
    def observe(self, member: MemberSnapshot) -> JoinAssessment:
        cfg = self.config
        self._prune(member.joined_at)

        burst_size = len(self._recent) + 1
        factors = self._factors(member, burst_size)
        risk = (
            factors["account_age"] * cfg.weight_account_age
            + factors["no_avatar"] * cfg.weight_no_avatar
            + factors["name_similarity"] * cfg.weight_name_similarity
            + factors["burst"] * cfg.weight_burst
        )
        risk = round(_clamp(risk), 4)

        self._recent.append((member, risk))
        risks = [r for _, r in self._recent]
        mean_risk = round(sum(risks) / len(risks), 4)

        lockdown = burst_size >= cfg.join_threshold and mean_risk >= cfg.lockdown_mean_risk
        if lockdown:
            self.locked_down = True

        return JoinAssessment(
            member_id=member.id,
            member_name=member.name,
            risk=risk,
            burst_size=burst_size,
            mean_risk=mean_risk,
            lockdown=lockdown,
            factors=factors,
        )

    def release(self) -> None:
        """Lift the lockdown (moderator command / cooldown expiry)."""
        self.locked_down = False
