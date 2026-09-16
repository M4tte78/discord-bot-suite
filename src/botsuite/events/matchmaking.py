"""Balanced team building.

Greedy assignment: sort players by rating descending, then repeatedly place the next
player on the team with the lowest total. Simple, deterministic, and it keeps the spread
between team totals small — good enough for a community tournament, and easy to explain,
which matters more than optimality here.
"""

from __future__ import annotations

from .models import Participant


def balanced_teams(players: list[Participant], team_count: int) -> list[list[Participant]]:
    if team_count < 1:
        raise ValueError("team_count doit être >= 1")
    teams: list[list[Participant]] = [[] for _ in range(team_count)]
    totals = [0.0] * team_count

    # Sort by rating, then by id so ties are resolved deterministically.
    for player in sorted(players, key=lambda p: (-p.rating, p.user_id)):
        target = min(range(team_count), key=lambda i: (totals[i], len(teams[i]), i))
        teams[target].append(player)
        totals[target] += player.rating

    return teams


def spread(teams: list[list[Participant]]) -> float:
    """Difference between the strongest and the weakest team — the quality metric."""
    if not teams:
        return 0.0
    totals = [sum(p.rating for p in team) for team in teams]
    return max(totals) - min(totals)
