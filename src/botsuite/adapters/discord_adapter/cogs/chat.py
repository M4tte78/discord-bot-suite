"""Chat cog: `/ask` and `/reset`.

The answer is sent as several messages when needed — `ChatService` already returned it
pre-split to the Discord limit.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class Chat(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = bot.chat

    @staticmethod
    def _key(interaction: discord.Interaction) -> str:
        return f"guild:{interaction.guild_id}/channel:{interaction.channel_id}"

    @app_commands.command(name="ask", description="Poser une question à l'assistant")
    @app_commands.describe(question="Ta question")
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        # The model call can take several seconds; Discord expects an ack within 3.
        await interaction.response.defer(thinking=True)

        reply = await self.service.ask(
            user_id=interaction.user.id, channel_key=self._key(interaction), prompt=question
        )
        if not reply.ok:
            await interaction.followup.send(f"⏳ {reply.error}", ephemeral=True)
            return

        first, *rest = reply.chunks
        await interaction.followup.send(first)
        for chunk in rest:
            await interaction.followup.send(chunk)

    @app_commands.command(name="reset", description="Oublier la conversation de ce salon")
    async def reset(self, interaction: discord.Interaction) -> None:
        self.service.reset(self._key(interaction))
        await interaction.response.send_message("Contexte réinitialisé.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Chat(bot))
