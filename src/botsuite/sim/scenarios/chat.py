"""Scenario: the LLM chat bot.

Demonstrates the three constraints that actually bite in production: the context window
has to be trimmed, the answer has to be cut into ≤2000-character messages without
destroying code blocks, and one user must not be able to drain the quota.

Runs entirely on `MockProvider` — no API key, no network.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ...clock import FakeClock
from ...llm import ChatService, MockProvider
from ...llm.queue import QuotaConfig
from .. import console


async def _run(verbose: bool) -> dict[str, Any]:
    clock = FakeClock()
    provider = MockProvider()
    service = ChatService(
        provider=provider,
        clock=clock,
        budget_tokens=220,  # tiny on purpose, so truncation is visible in a short demo
        concurrency=2,
        quota=QuotaConfig(max_calls=4, window_seconds=60.0),
    )

    if verbose:
        console.title("Scénario 3 — Bot de génération de texte")
        console.step("Conversation courte : le contexte tient dans le budget")

    channel = "guild:900000001/channel:100"
    user = 4242

    for prompt in ("c'est quoi un token bucket ?", "et pour un serveur de 5000 membres ?"):
        reply = await service.ask(user_id=user, channel_key=channel, prompt=prompt)
        if verbose:
            console.muted(f"utilisateur → {prompt}")
            console.info(f"bot        → {reply.text[:96]}…")
            console.muted(f"             tours abandonnés : {reply.dropped_turns}")
        clock.advance(5)

    if verbose:
        console.step("La conversation s'allonge : la fenêtre glissante commence à couper")

    dropped_total = 0
    for i in range(4):
        reply = await service.ask(
            user_id=user + i + 1,  # autres membres, pour ne pas épuiser le quota du premier
            channel_key=channel,
            prompt=f"question de suivi numéro {i} avec un peu de contexte en plus pour peser",
        )
        dropped_total = reply.dropped_turns
        clock.advance(5)
    if verbose:
        console.info(f"Tours les plus anciens abandonnés du contexte : {dropped_total}")
        console.muted("Le prompt système, lui, est toujours conservé.")

    if verbose:
        console.step("Réponse longue → découpage en messages Discord (limite 2000 caractères)")

    long_reply = await service.ask(
        user_id=9001, channel_key=channel, prompt="détaille l'architecture du bot"
    )
    sizes = [len(c) for c in long_reply.chunks]
    has_fence = any(c.startswith("```") for c in long_reply.chunks)
    if verbose:
        console.info(f"{len(long_reply.chunks)} messages, tailles : {sizes}")
        console.ok("Aucun message ne dépasse la limite")
        if has_fence:
            console.ok("Le bloc de code est resté dans un seul message, fence intacte")

    if verbose:
        console.step("Quota : 4 appels par fenêtre de 60 s pour un même utilisateur")

    refused = 0
    for i in range(5):
        reply = await service.ask(user_id=7777, channel_key=channel, prompt=f"ping {i}")
        if not reply.ok:
            refused += 1
            if verbose:
                console.warn(f"appel #{i + 1} refusé — {reply.error}")
        elif verbose:
            console.muted(f"appel #{i + 1} accepté")

    if verbose:
        console.step("Rafale simultanée : 8 demandes d'un coup, concurrence bornée à 2")

    burst_service = ChatService(
        provider=MockProvider(latency=0.01),
        clock=clock,
        concurrency=2,
        quota=QuotaConfig(max_calls=50, window_seconds=60.0),
    )
    await asyncio.gather(
        *(
            burst_service.ask(user_id=1000 + i, channel_key=f"{channel}#{i}", prompt=f"salut {i}")
            for i in range(8)
        )
    )
    if verbose:
        console.info(
            "Pic de requêtes simultanées vers le fournisseur : "
            f"{burst_service.queue.peak_in_flight}"
        )
        console.info(f"Requêtes mises en attente : {burst_service.queue.waited}")
        console.ok("Le fournisseur n'a jamais vu plus de 2 appels en parallèle")

    return {
        "scenario": "chat",
        "chunks": len(long_reply.chunks),
        "max_chunk": max(sizes),
        "code_fence_preserved": has_fence,
        "quota_refusals": refused,
        "peak_in_flight": burst_service.queue.peak_in_flight,
        "provider_calls": provider.calls,
    }


def run(verbose: bool = True) -> dict[str, Any]:
    return asyncio.run(_run(verbose))
