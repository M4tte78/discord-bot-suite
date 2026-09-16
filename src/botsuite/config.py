"""Configuration loaded from the environment.

No secret is ever hard-coded; `.env.example` documents every key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    return int(raw) if raw else default


def _env_float(key: str, default: float) -> float:
    raw = _env(key)
    return float(raw) if raw else default


@dataclass
class LLMSettings:
    provider: str = "mock"
    base_url: str = ""
    model: str = "gpt-4o-mini"
    api_key: str = ""
    context_budget_tokens: int = 2048
    max_concurrency: int = 2
    quota_calls: int = 5
    quota_window_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> LLMSettings:
        return cls(
            provider=_env("LLM_PROVIDER", "mock"),
            base_url=_env("LLM_BASE_URL"),
            model=_env("LLM_MODEL", "gpt-4o-mini"),
            api_key=_env("LLM_API_KEY"),
            context_budget_tokens=_env_int("LLM_CONTEXT_BUDGET_TOKENS", 2048),
            max_concurrency=_env_int("LLM_MAX_CONCURRENCY", 2),
            quota_calls=_env_int("LLM_QUOTA_CALLS", 5),
            quota_window_seconds=_env_float("LLM_QUOTA_WINDOW_SECONDS", 60.0),
        )


@dataclass
class Settings:
    discord_token: str = ""
    discord_guild_id: int | None = None
    storage_url: str = "memory://"
    llm: LLMSettings = field(default_factory=LLMSettings)

    @classmethod
    def from_env(cls) -> Settings:
        guild = _env("DISCORD_GUILD_ID")
        return cls(
            discord_token=_env("DISCORD_TOKEN"),
            discord_guild_id=int(guild) if guild else None,
            storage_url=_env("STORAGE_URL", "memory://"),
            llm=LLMSettings.from_env(),
        )
