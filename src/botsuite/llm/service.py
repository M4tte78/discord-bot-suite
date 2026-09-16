"""The chat bot's business logic, with no Discord import in sight."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..clock import Clock
from .chunking import LIMIT, split_message
from .context import ContextWindow, Conversation
from .provider import Provider, ProviderError
from .queue import QuotaConfig, QuotaExceeded, RequestQueue, UserQuota

DEFAULT_SYSTEM_PROMPT = (
    "Tu es l'assistant d'un serveur Discord communautaire. Réponds en français, de manière "
    "concise et factuelle. Si tu ne sais pas, dis-le."
)


@dataclass
class ChatReply:
    chunks: list[str]
    dropped_turns: int = 0
    error: str | None = None
    conversation_key: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def text(self) -> str:
        return "\n".join(self.chunks)


@dataclass
class ChatService:
    provider: Provider
    clock: Clock
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    budget_tokens: int = 2048
    concurrency: int = 2
    quota: QuotaConfig = field(default_factory=QuotaConfig)
    message_limit: int = LIMIT

    def __post_init__(self) -> None:
        self.window = ContextWindow(self.system_prompt, budget_tokens=self.budget_tokens)
        self.queue = RequestQueue(self.provider, concurrency=self.concurrency)
        self.quotas = UserQuota(self.clock, self.quota)
        self._conversations: dict[str, Conversation] = {}

    def conversation(self, key: str) -> Conversation:
        return self._conversations.setdefault(key, Conversation(key=key))

    def reset(self, key: str) -> None:
        self.conversation(key).reset()

    async def ask(self, *, user_id: int, channel_key: str, prompt: str) -> ChatReply:
        now = self.clock.now()
        try:
            self.quotas.consume(user_id, now)
        except QuotaExceeded as exc:
            return ChatReply(chunks=[], error=str(exc), conversation_key=channel_key)

        conversation = self.conversation(channel_key)
        conversation.add("user", prompt, at=now)
        dropped = self.window.dropped(conversation)
        messages = self.window.build(conversation)

        try:
            answer = await self.queue.submit(messages)
        except ProviderError as exc:
            return ChatReply(chunks=[], error=str(exc), conversation_key=channel_key)

        conversation.add("assistant", answer, at=self.clock.now())
        return ChatReply(
            chunks=split_message(answer, self.message_limit),
            dropped_turns=dropped,
            conversation_key=channel_key,
        )
