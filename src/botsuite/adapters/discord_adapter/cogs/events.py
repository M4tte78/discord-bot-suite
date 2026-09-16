"""Events cog: persistent signup buttons + a scheduler loop.

`SignupView(timeout=None)` with a fixed `custom_id` is what makes the button survive a
restart: the view is re-registered in `cog_load`, so an old message still routes to a live
handler instead of failing silently.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ....events import Leaderboard, Participant
from ....events.models import EventFull, InvalidTransition

log = logging.getLogger("botsuite.events")


class SignupView(discord.ui.View):
    def __init__(self, service, event_id: str) -> None:
        super().__init__(timeout=None)
        self.service = service
        self.event_id = event_id
        self.join.custom_id = f"signup:{event_id}"
        self.leave.custom_id = f"withdraw:{event_id}"

    @discord.ui.button(label="Rejoindre", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        participant = Participant(
            user_id=interaction.user.id,
            name=interaction.user.display_name,
            signed_up_at=interaction.created_at.timestamp(),
        )
        try:
            event, added = self.service.signup(self.event_id, participant)
        except (EventFull, InvalidTransition) as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        message = "Inscription enregistrée." if added else "Tu es déjà inscrit."
        await interaction.response.send_message(
            f"{message} ({len(event.participants)}/{event.capacity})", ephemeral=True
        )

    @discord.ui.button(label="Se retirer", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        try:
            event, removed = self.service.withdraw(self.event_id, interaction.user.id)
        except InvalidTransition as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        text = "Désinscrit." if removed else "Tu n'étais pas inscrit."
        await interaction.response.send_message(
            f"{text} ({len(event.participants)}/{event.capacity})", ephemeral=True
        )


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = bot.events

    async def cog_load(self) -> None:
        # Re-register a persistent view per known event so old messages keep working.
        for event in self.service.all():
            self.bot.add_view(SignupView(self.service, event.id))
        self.scheduler.start()

    async def cog_unload(self) -> None:
        self.scheduler.cancel()

    @tasks.loop(seconds=60)
    async def scheduler(self) -> None:
        due = self.service.due()
        for event in due.to_open:
            event.open()
            self.service.save(event)
            log.info("inscriptions ouvertes : %s", event.id)
        for event in due.to_remind:
            self.service.mark_reminded(event.id)
            log.info("rappel envoyé : %s", event.id)
        for event in due.to_start:
            self.service.lock_and_build_teams(event.id)
            self.service.start(event.id)
            log.info("événement démarré : %s", event.id)

    @scheduler.before_loop
    async def before_scheduler(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="event-create", description="Créer un événement")
    @app_commands.checks.has_permissions(manage_events=True)
    async def create(
        self,
        interaction: discord.Interaction,
        event_id: str,
        title: str,
        capacity: int = 16,
        teams: int = 2,
    ) -> None:
        event = self.service.create(
            event_id, title, interaction.guild_id, capacity=capacity, team_count=teams
        )
        event.open()
        self.service.save(event)
        view = SignupView(self.service, event.id)
        self.bot.add_view(view)
        await interaction.response.send_message(
            f"**{title}** — {capacity} places, {teams} équipes.", view=view
        )

    @app_commands.command(name="leaderboard", description="Afficher le classement")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        board = Leaderboard(self.bot.store, interaction.guild_id)
        rows = board.top(10)
        if not rows:
            await interaction.response.send_message("Classement vide.", ephemeral=True)
            return
        lines = [f"{i}. **{s.name}** — {s.points} pts" for i, s in enumerate(rows, start=1)]
        await interaction.response.send_message("\n".join(lines))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Events(bot))
