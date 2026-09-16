"""Scenario: a full tournament, including a simulated process restart.

The interesting part is at the end: a second `EventService` is built over the same store,
which is exactly what the bot sees after a crash or a deployment. The roster, the teams
and the state are all still there.
"""

from __future__ import annotations

from typing import Any

from ...clock import FakeClock
from ...events import EventService, Leaderboard, Participant
from ...storage import MemoryStore
from .. import console
from ..world import SimWorld

CAPACITY = 12
TEAM_COUNT = 3


def run(verbose: bool = True) -> dict[str, Any]:
    world = SimWorld(seed=99, clock=FakeClock())
    store = MemoryStore()
    service = EventService(store, world.clock, reminder_lead=900.0)
    leaderboard = Leaderboard(store, guild_id=world.guild_id)

    if verbose:
        console.title("Scénario 4 — Tournoi")

    now = world.clock.now()
    event = service.create(
        "cup-2026-03",
        "Coupe interne #3",
        world.guild_id,
        capacity=CAPACITY,
        team_count=TEAM_COUNT,
        opens_at=now + 60,
        starts_at=now + 3600,
    )
    if verbose:
        console.step("Événement créé à l'état DRAFT, ouverture programmée dans 60 s")

    # -- scheduler opens the event -----------------------------------------
    world.tick(61)
    due = service.due()
    for pending in due.to_open:
        pending.open()
        service.save(pending)
    if verbose:
        console.ok(f"Tâche planifiée : {len(due.to_open)} événement ouvert automatiquement")

    # -- signups ------------------------------------------------------------
    if verbose:
        console.step(f"Inscriptions par bouton — {CAPACITY + 2} clics pour {CAPACITY} places")

    members = [world.member() for _ in range(CAPACITY + 1)]
    duplicates = 0
    rejected = 0
    for index, member in enumerate(members):
        participant = Participant(
            user_id=member.id,
            name=member.name,
            rating=1000 + world.rng.randint(-250, 250),
            signed_up_at=world.clock.now(),
        )
        try:
            _, added = service.signup(event.id, participant)
            if not added:
                duplicates += 1
        except Exception as exc:  # EventFull
            rejected += 1
            if verbose:
                console.warn(f"{member.name:<18} refusé — {exc}")
        world.tick(3)
        if index == 3:  # double click on the same button
            _, added = service.signup(event.id, participant)
            if not added:
                duplicates += 1
                if verbose:
                    console.muted(f"{member.name:<18} double clic ignoré (idempotent)")

    event = service.load(event.id)
    if verbose:
        console.info(f"Inscrits : {len(event.participants)} / {CAPACITY}")

    # -- reminder -----------------------------------------------------------
    world.clock.advance(3600 - 900 - world.clock.now() + now)
    due = service.due()
    reminded = len(due.to_remind)
    for pending in due.to_remind:
        service.mark_reminded(pending.id)
    if verbose:
        console.step("15 minutes avant le début")
        console.ok(f"Rappel envoyé pour {reminded} événement (une seule fois)")
        console.muted(
            f"Re-passage du planificateur : {len(service.due().to_remind)} rappel à envoyer"
        )

    # -- teams --------------------------------------------------------------
    event, team_spread = service.lock_and_build_teams(event.id)
    teams = [[event.participants[uid] for uid in team] for team in event.teams]
    if verbose:
        console.step("Verrouillage et constitution des équipes")
        for i, team in enumerate(teams, start=1):
            total = sum(p.rating for p in team)
            console.info(f"Équipe {i} — total {total:>6.0f} — " + ", ".join(p.name for p in team))
        console.ok(f"Écart entre la meilleure et la moins bonne équipe : {team_spread:.0f} points")

    # -- restart ------------------------------------------------------------
    if verbose:
        console.step("Redémarrage du bot simulé (nouveau service sur le même stockage)")
    rebooted = EventService(store, world.clock)
    recovered = rebooted.load(event.id)
    intact = (
        recovered is not None
        and recovered.state is event.state
        and len(recovered.participants) == len(event.participants)
        and recovered.teams == event.teams
    )
    if verbose:
        if intact:
            console.ok(
                f"État retrouvé : {recovered.state.value}, {len(recovered.participants)} inscrits, "
                f"{len(recovered.teams)} équipes"
            )
        else:
            console.alert("État perdu au redémarrage")

    # -- run and finish -----------------------------------------------------
    rebooted.start(event.id)
    standings = [team[0].user_id for team in teams]  # meilleur joueur de chaque équipe
    finished = rebooted.finish(event.id, standings)
    rebooted.publish_results(event.id, leaderboard)

    if verbose:
        console.step("Classement après publication des résultats")
        for rank, standing in enumerate(leaderboard.top(5), start=1):
            console.info(f"{rank}. {standing.name:<18} {standing.points:>3} pts")

    return {
        "scenario": "tournament",
        "signed_up": len(event.participants),
        "capacity": CAPACITY,
        "rejected": rejected,
        "duplicates_ignored": duplicates,
        "team_spread": round(team_spread, 2),
        "reminders_sent": reminded,
        "state_survived_restart": intact,
        "final_state": finished.state.value,
        "leaderboard_size": len(leaderboard.top(50)),
    }
