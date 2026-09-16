"""Conversation memory under a token budget.

A Discord channel can hold months of history; a model context cannot. The window keeps
the system prompt (always), then walks backwards through the turns and keeps as many as
fit in the budget. Dropping *oldest first* is what makes the assistant feel like it
remembers the current exchange without paying for the whole channel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: ~4 characters per token is the usual rule of thumb for Latin-script text.
#: Swap for a real tokenizer (tiktoken) if exact accounting matters.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


@dataclass(frozen=True)
class Turn:
    role: str  # "user" | "assistant"
    content: str
    at: float = 0.0

    def as_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class Conversation:
    key: str
    turns: list[Turn] = field(default_factory=list)

    def add(self, role: str, content: str, at: float = 0.0) -> Turn:
        turn = Turn(role=role, content=content, at=at)
        self.turns.append(turn)
        return turn

    def reset(self) -> None:
        self.turns.clear()


@dataclass
class ContextWindow:
    system_prompt: str
    budget_tokens: int = 2048
    max_turns: int = 40

    def build(self, conversation: Conversation) -> list[dict[str, str]]:
        system = {"role": "system", "content": self.system_prompt}
        remaining = self.budget_tokens - estimate_tokens(self.system_prompt)

        kept: list[Turn] = []
        for turn in reversed(conversation.turns[-self.max_turns :]):
            cost = estimate_tokens(turn.content)
            if cost > remaining:
                break
            remaining -= cost
            kept.append(turn)

        kept.reverse()
        return [system, *(t.as_message() for t in kept)]

    def dropped(self, conversation: Conversation) -> int:
        """Number of turns the budget forced out — surfaced in the simulator output."""
        return max(0, len(conversation.turns) - (len(self.build(conversation)) - 1))
