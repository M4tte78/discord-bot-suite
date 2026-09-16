"""Scenario: a raid wave against a server that also receives legitimate joins.

What it demonstrates: the risk score separates the two populations, and lockdown only
fires on the burst — the legitimate members that join just before are never flagged.
"""

from __future__ import annotations

from typing import Any

from ...clock import FakeClock
from ...models import Action
from ...security import SecurityEngine
from ...security.raid import RaidConfig
from .. import console
from ..world import SimWorld

RAID_SIZE = 30


def run(verbose: bool = True) -> dict[str, Any]:
    world = SimWorld(seed=42, clock=FakeClock())
    engine = SecurityEngine(
        world.clock, raid_config=RaidConfig(window_seconds=30.0, join_threshold=8)
    )

    if verbose:
        console.title("Scénario 1 — Détection de raid")
        console.step("Trafic normal : 5 arrivées légitimes réparties sur 10 minutes")

    legit_flags = 0
    for _ in range(5):
        member = world.member()
        decision = engine.on_member_join(member)
        if decision.action is not Action.ALLOW:
            legit_flags += 1
        if verbose:
            console.muted(
                f"{member.name:<18} compte de "
                f"{(member.joined_at - member.account_created_at) / 86400:>6.0f} j  "
                f"→ {decision.action.value}"
            )
        world.tick(120)

    if verbose:
        console.step(f"Raid : {RAID_SIZE} comptes créés cette semaine, sans avatar, noms générés")

    lockdown_at = None
    flagged = 0
    wave = []
    for i in range(RAID_SIZE):
        world.tick(0.8)  # ~1.25 arrivée par seconde
        member = world.raid_wave(1, template=f"free_nitro_{i + 1:02d}")[0]
        wave.append(member)
        decision = engine.on_member_join(member)
        assessment = engine.raid._recent[-1][1]
        if decision.action is not Action.ALLOW:
            flagged += 1
        if decision.action is Action.LOCKDOWN and lockdown_at is None:
            lockdown_at = i + 1

        if verbose and (i < 10 or lockdown_at == i + 1):
            label = console.action(decision.action.value)
            line = f"{member.name:<18} risque {assessment:.2f}  → {label}"
            if decision.action is Action.LOCKDOWN:
                console.alert(line + f" (déclenché au {i + 1}e compte de la vague)")
            elif decision.action is Action.FLAG:
                console.warn(line)
            else:
                console.muted(line)

    if verbose and lockdown_at:
        console.muted(f"… {RAID_SIZE - lockdown_at} arrivées suivantes traitées serveur verrouillé")

    if verbose:
        console.step("Bilan")
        console.info(f"Comptes légitimes signalés  : {legit_flags} / 5")
        console.info(f"Comptes du raid signalés     : {flagged} / {RAID_SIZE}")
        if lockdown_at:
            console.ok(f"Verrouillage automatique après {lockdown_at} arrivées de la vague")
        else:
            console.alert("Aucun verrouillage déclenché")
        console.info(f"Entrées d'audit écrites      : {len(engine.audit)}")

    return {
        "scenario": "raid",
        "legit_flagged": legit_flags,
        "raid_flagged": flagged,
        "raid_size": RAID_SIZE,
        "lockdown_at": lockdown_at,
        "audit_entries": len(engine.audit),
    }
