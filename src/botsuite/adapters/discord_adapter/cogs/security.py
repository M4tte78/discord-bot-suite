"""Security cog: turns `SecurityEngine` decisions into Discord API calls."""

from __future__ import annotations

import datetime as dt
import logging

import discord
from discord import app_commands
from discord.ext import commands

from ....models import Action
from ..convert import to_member_snapshot, to_message_snapshot

log = logging.getLogger("botsuite.security")

TIMEOUT_DURATION = dt.timedelta(minutes=10)


class Security(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.engine = bot.security

    # -- helpers -----------------------------------------------------------
    async def _audit(self, guild: discord.Guild, text: str) -> None:
        channel = discord.utils.get(guild.text_channels, name="mod-logs")
        if channel is not None:
            await channel.send(text)
        log.info("[%s] %s", guild.id, text)

    # -- listeners ---------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        decision = self.engine.on_member_join(to_member_snapshot(member))
        if decision.action is Action.ALLOW:
            return

        if decision.action is Action.LOCKDOWN and member.guild.default_role:
            perms = member.guild.default_role.permissions
            perms.send_messages = False
            await member.guild.default_role.edit(
                permissions=perms, reason="Raid détecté — verrouillage automatique"
            )
            await self._audit(member.guild, f"🔒 Verrouillage : {decision.verdicts[0].reason}")
        else:
            await self._audit(
                member.guild, f"⚠️ Arrivée suspecte {member} — {decision.verdicts[0].reason}"
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        decision = self.engine.on_message(to_message_snapshot(message))
        if decision.action is Action.ALLOW:
            return

        if self.engine.dry_run:
            await self._audit(
                message.guild, f"[dry-run] {decision.action.value} → {message.author}"
            )
            return

        try:
            await message.delete()
        except discord.NotFound:
            pass

        member = message.author
        if decision.action is Action.TIMEOUT and isinstance(member, discord.Member):
            await member.timeout(TIMEOUT_DURATION, reason="Sanction automatique")
        elif decision.action is Action.KICK and isinstance(member, discord.Member):
            await member.kick(reason="Sanction automatique")
        elif decision.action is Action.BAN and isinstance(member, discord.Member):
            await member.ban(reason="Sanction automatique", delete_message_days=1)

        rules = ", ".join(v.rule for v in decision.verdicts)
        await self._audit(
            message.guild,
            f"🛡️ {decision.action.value} — {member} ({decision.points:.1f} pts) [{rules}]",
        )

    # -- commands ----------------------------------------------------------
    @app_commands.command(name="unlock", description="Lever le verrouillage anti-raid")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def unlock(self, interaction: discord.Interaction) -> None:
        self.engine.raid.release()
        role = interaction.guild.default_role
        perms = role.permissions
        perms.send_messages = True
        await role.edit(permissions=perms, reason="Déverrouillage manuel")
        await interaction.response.send_message("Serveur déverrouillé.", ephemeral=True)

    @app_commands.command(name="forgive", description="Remettre à zéro les points d'un membre")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def forgive(self, interaction: discord.Interaction, member: discord.Member) -> None:
        self.engine.ladder.forgive(member.id)
        await interaction.response.send_message(
            f"Compteur remis à zéro pour {member}.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Security(bot))
