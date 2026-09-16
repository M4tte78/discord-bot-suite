"""Model providers behind one Protocol.

`MockProvider` is the default: the whole suite runs, and the test suite passes, with no
API key and no network. `OpenAICompatibleProvider` targets any `/chat/completions`
endpoint (OpenAI, Mistral, Groq, a local vLLM…).
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Protocol, runtime_checkable


class ProviderError(RuntimeError):
    pass


@runtime_checkable
class Provider(Protocol):
    name: str

    async def complete(self, messages: list[dict[str, str]]) -> str: ...


CANNED = [
    "Voici ce que je comprends de ta demande : {topic}. En résumé, trois points comptent — "
    "le contexte, la contrainte principale, et la prochaine action concrète.",
    "Bonne question sur {topic}. La réponse courte est « ça dépend du volume » ; la réponse "
    "longue tient en deux paragraphes que je peux détailler si tu veux.",
    "Pour {topic}, je partirais sur l'option la plus simple d'abord, quitte à la remplacer "
    "quand le besoin réel sera mesuré.",
]


class MockProvider:
    """Deterministic, offline provider.

    The answer is picked from `CANNED` by hashing the last user message, so the same
    conversation always produces the same transcript — which is what makes the simulator
    scenarios reproducible and assertable in tests.
    """

    name = "mock"

    def __init__(self, latency: float = 0.0, long_answer_trigger: str = "détaille") -> None:
        self.latency = latency
        self.long_answer_trigger = long_answer_trigger
        self.calls = 0

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        if self.latency:
            await asyncio.sleep(self.latency)

        user_messages = [m for m in messages if m["role"] == "user"]
        if not user_messages:
            raise ProviderError("aucun message utilisateur dans le contexte")
        last = user_messages[-1]["content"]

        if self.long_answer_trigger in last.lower():
            return self._long_answer(last)

        index = int(hashlib.sha1(last.encode("utf-8")).hexdigest(), 16) % len(CANNED)
        topic = last.strip().rstrip("?").strip()
        return CANNED[index].format(topic=topic[:60])

    def _long_answer(self, prompt: str) -> str:
        paragraph = (
            "Le point important ici est que la logique métier ne dépend pas de la couche "
            "transport : elle reçoit des instantanés, elle renvoie des décisions, et c'est "
            "l'adaptateur qui applique ces décisions sur la plateforme. "
        )
        body = "\n\n".join(f"{i + 1}. {paragraph}" for i in range(9))
        code = (
            "```python\n"
            "async def on_message(self, message):\n"
            "    decision = self.engine.on_message(to_snapshot(message))\n"
            "    if decision.action is Action.DELETE:\n"
            "        await message.delete()\n"
            "```"
        )
        return f"Réponse détaillée sur « {prompt[:40]} » :\n\n{body}\n\n{code}\n\nFin."


class OpenAICompatibleProvider:
    """Any endpoint exposing POST {base_url}/chat/completions."""

    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ProviderError("clé d'API manquante (LLM_API_KEY)")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def complete(self, messages: list[dict[str, str]]) -> str:
        import httpx  # imported lazily so the mock path needs no dependency at runtime

        payload = {"model": self.model, "messages": messages}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            if response.status_code == 429:
                raise ProviderError("limite de débit du fournisseur atteinte (429)")
            response.raise_for_status()
            data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:  # pragma: no cover - provider contract break
            raise ProviderError(f"réponse inattendue du fournisseur : {data}") from exc


def build_provider(settings) -> Provider:
    """Factory driven by `botsuite.config.LLMSettings`."""
    if settings.provider == "mock":
        return MockProvider()
    if settings.provider == "openai-compatible":
        return OpenAICompatibleProvider(
            base_url=settings.base_url, api_key=settings.api_key, model=settings.model
        )
    raise ProviderError(f"fournisseur inconnu : {settings.provider}")
