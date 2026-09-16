"""Wiring: raid monitor + spam detector + content filter + sanction ladder.

`SecurityEngine` is the only object the Discord adapter talks to. It returns decisions;
it never performs them. Applying a timeout or a ban is the adapter's job, which keeps the
engine free of side effects and trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..clock import Clock
from ..models import Action, MemberSnapshot, MessageSnapshot, Verdict, harshest
from .content import ContentFilter
from .raid import RaidConfig, RaidMonitor
from .sanctions import LadderConfig, SanctionLadder
from .spam import SpamConfig, SpamDetector


@dataclass
class AuditRecord:
    at: float
    subject_id: int
    subject_name: str
    action: Action
    rule: str
    reason: str
    details: dict = field(default_factory=dict)


@dataclass
class Decision:
    """What the adapter should do, plus everything needed to justify it in the audit log."""

    action: Action
    verdicts: list[Verdict]
    points: float = 0.0

    @property
    def is_noop(self) -> bool:
        return self.action in (Action.ALLOW, Action.FLAG) and not self.verdicts


class SecurityEngine:
    def __init__(
        self,
        clock: Clock,
        *,
        raid_config: RaidConfig | None = None,
        spam_config: SpamConfig | None = None,
        ladder_config: LadderConfig | None = None,
        content_filter: ContentFilter | None = None,
        dry_run: bool = False,
    ) -> None:
        self.clock = clock
        self.raid = RaidMonitor(clock, raid_config)
        self.spam = SpamDetector(clock, spam_config)
        self.content = content_filter or ContentFilter()
        self.ladder = SanctionLadder(clock, ladder_config or LadderConfig())
        #: When True the engine still decides, but the adapter is expected to log only.
        #: Every new rule should run a few days in dry-run before it is allowed to act.
        self.dry_run = dry_run
        self.audit: list[AuditRecord] = []

    # -- audit -------------------------------------------------------------
    def _log(self, subject_id: int, subject_name: str, verdict: Verdict, at: float) -> None:
        self.audit.append(
            AuditRecord(
                at=at,
                subject_id=subject_id,
                subject_name=subject_name,
                action=verdict.action,
                rule=verdict.rule,
                reason=verdict.reason,
                details=dict(verdict.details),
            )
        )

    # -- events ------------------------------------------------------------
    def on_member_join(self, member: MemberSnapshot) -> Decision:
        assessment = self.raid.observe(member)
        verdicts: list[Verdict] = []

        if assessment.lockdown:
            verdicts.append(
                Verdict(
                    action=Action.LOCKDOWN,
                    rule="raid.burst",
                    reason=(
                        f"{assessment.burst_size} arrivées dans la fenêtre, "
                        f"risque moyen {assessment.mean_risk:.2f}"
                    ),
                    score=assessment.mean_risk,
                    details={"factors": assessment.factors},
                )
            )
        elif assessment.risk >= 0.5:
            verdicts.append(
                Verdict(
                    action=Action.FLAG,
                    rule="raid.suspicious_join",
                    reason=f"score de risque {assessment.risk:.2f}",
                    score=assessment.risk,
                    details={"factors": assessment.factors},
                )
            )

        for verdict in verdicts:
            self._log(member.id, member.name, verdict, member.joined_at)

        top = harshest(verdicts)
        return Decision(action=top.action if top else Action.ALLOW, verdicts=verdicts)

    def on_message(self, message: MessageSnapshot) -> Decision:
        verdicts = self.spam.on_message(message) + self.content.check(message.content)
        if not verdicts:
            return Decision(action=Action.ALLOW, verdicts=[])

        points, ladder_action = self.ladder.record(
            message.author_id, weight=float(len(verdicts)), now=message.created_at
        )
        top = harshest(verdicts)
        assert top is not None

        # The message itself is removed; the sanction against the author is whatever the
        # ladder says, which may be harsher than this single message warrants.
        final = ladder_action if ladder_action.value != Action.FLAG.value else top.action
        sanction = Verdict(
            action=final,
            rule="sanctions.ladder",
            reason=f"{points:.1f} points d'infraction cumulés",
            score=points,
            details={"triggered_by": [v.rule for v in verdicts]},
        )

        for verdict in [*verdicts, sanction]:
            self._log(message.author_id, message.author_name, verdict, message.created_at)

        return Decision(action=final, verdicts=[*verdicts, sanction], points=points)
