"""Scenario: message-level moderation.

Four behaviours, one after the other, against a single account:
flood, cross-posting, mention bomb, and an obfuscated scam. The sanction ladder escalates
across them, which is the point — no single message here deserves a kick, the accumulation
does.
"""

from __future__ import annotations

from typing import Any

from ...clock import FakeClock
from ...models import Action
from ...security import SecurityEngine
from .. import console
from ..world import SimWorld

OBFUSCATED_SCAM = "F​r3​e​  N1TR​O  — сlaim here"
SPACED_SCAM = "f r e e   n i t r o   g i v e a w a y"


def run(verbose: bool = True) -> dict[str, Any]:
    world = SimWorld(seed=7, clock=FakeClock())
    engine = SecurityEngine(world.clock)

    spammer = world.member(name="promo_bot_x", account_age_days=2, has_avatar=False)
    regular = world.member(name="nina_wave", account_age_days=800, has_avatar=True)

    if verbose:
        console.title("Scénario 2 — Modération des messages")

    results: list[tuple[str, Action, str]] = []

    def push(label: str, message) -> None:
        decision = engine.on_message(message)
        rules = ", ".join(v.rule for v in decision.verdicts if v.rule != "sanctions.ladder")
        results.append((label, decision.action, rules))
        if verbose:
            if decision.action is Action.ALLOW:
                console.muted(f"{label:<28} {console.action('allow')}")
            else:
                console.warn(
                    f"{label:<28} {console.action(decision.action.value)} "
                    f"{decision.points:>4.1f} pts  [{rules}]"
                )

    if verbose:
        console.step("Messages normaux d'un membre établi")
    for text in ("salut tout le monde", "quelqu'un a testé la nouvelle map ?"):
        push(f"membre régulier : « {text[:18]}… »", world.message(regular, text))
        world.tick(30)

    if verbose:
        console.step("Flood : 9 messages en 4 secondes (capacité du bucket : 5)")
    for i in range(9):
        push(f"flood #{i + 1}", world.message(spammer, f"achete mes services {i}"))
        world.tick(0.45)

    if verbose:
        console.step("Cross-post : le même message dans 4 salons")
    for channel in world.channels:
        push(
            f"cross-post salon {channel}",
            world.message(spammer, "promo du jour !!", channel_id=channel),
        )
        world.tick(2)

    if verbose:
        console.step("Mention bomb")
    push("mention @everyone", world.message(spammer, "regardez ça", mentions_everyone=True))
    world.tick(2)

    if verbose:
        console.step("Scam obfusqué (zero-width + homoglyphes cyrilliques, puis lettres espacées)")
    push("scam zero-width", world.message(spammer, OBFUSCATED_SCAM))
    world.tick(2)
    push("scam lettres espacées", world.message(spammer, SPACED_SCAM))
    world.tick(2)
    push("lien d'invitation externe", world.message(spammer, "rejoins https://discord.gg/abcd1234"))

    final_points = engine.ladder.points(spammer.id, world.clock.now())
    final_action = engine.ladder.action_for(final_points)

    regular_blocked = sum(1 for r in results[:2] if r[1] is not Action.ALLOW)
    if verbose:
        console.step("Bilan")
        console.info(f"Membre régulier — messages bloqués : {regular_blocked} / 2")
        console.info(f"Spammeur — points cumulés          : {final_points:.1f}")
        console.alert(f"Sanction finale                    : {final_action.value}")
        console.info(f"Entrées d'audit                    : {len(engine.audit)}")

    return {
        "scenario": "moderation",
        "regular_blocked": regular_blocked,
        "spammer_points": round(final_points, 2),
        "final_action": final_action.value,
        "audit_entries": len(engine.audit),
        "rules_fired": sorted({r for _, _, rules in results for r in rules.split(", ") if r}),
    }
