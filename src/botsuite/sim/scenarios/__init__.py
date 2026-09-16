from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import chat, moderation, raid, tournament

#: name -> (callable returning a summary dict, one-line description)
SCENARIOS: dict[str, tuple[Callable[..., dict[str, Any]], str]] = {
    "raid": (raid.run, "Vague de 30 comptes jetables → scoring de risque et verrouillage"),
    "moderation": (
        moderation.run,
        "Flood, cross-post, mention bomb, scam obfusqué → sanctions graduées",
    ),
    "chat": (chat.run, "Conversation LLM → contexte tronqué, découpage 2000 caractères, quota"),
    "tournament": (
        tournament.run,
        "Tournoi complet → inscriptions, équipes, redémarrage, classement",
    ),
}

__all__ = ["SCENARIOS", "chat", "moderation", "raid", "tournament"]
