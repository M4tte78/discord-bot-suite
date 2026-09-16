"""Bot entry point.

Cogs are loaded dynamically and can be reloaded at runtime with `/reload <cog>`, so a
rule change ships without dropping the gateway connection.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from ...clock import RealClock
from ...config import Settings
from ...events import EventService
from ...llm import ChatService
from ...llm.provider import build_provider
from ...llm.queue import QuotaConfig
from ...security import SecurityEngine
from ...storage import build_store

log = logging.getLogger("botsuite")

COGS = (
    "botsuite.adapters.discord_adapter.cogs.security",
    "botsuite.adapters.discord_adapter.cogs.chat",
    "botsuite.adapters.discord_adapter.cogs.events",
)


class BotSuite(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.members = True  # required for join events
        intents.message_content = True  # privileged intent, enable it in the dev portal
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.clock = RealClock()
        self.store = build_store(settings.storage_url)
        self.security = SecurityEngine(self.clock)
        self.chat = ChatService(
            provider=build_provider(settings.llm),
            clock=self.clock,
            budget_tokens=settings.llm.context_budget_tokens,
            concurrency=settings.llm.max_concurrency,
            quota=QuotaConfig(
                max_calls=settings.llm.quota_calls,
                window_seconds=settings.llm.quota_window_seconds,
            ),
        )
        self.events = EventService(self.store, self.clock)

    async def setup_hook(self) -> None:
        for cog in COGS:
            await self.load_extension(cog)
            log.info("cog chargé : %s", cog)
        if self.settings.discord_guild_id:
            guild = discord.Object(id=self.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def close(self) -> None:
        self.store.close()
        await super().close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s %(message)s"
    )
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # pragma: no cover
        pass

    settings = Settings.from_env()
    if not settings.discord_token:
        print(
            "DISCORD_TOKEN est vide. Pour explorer le projet sans serveur Discord :\n"
            "    python -m botsuite.sim all"
        )
        return 1

    BotSuite(settings).run(settings.discord_token, log_handler=None)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
