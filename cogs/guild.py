import json

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from core.character.tutorial import TutorialView
from core.images import AMARA_AUTHOR
from core.character.views import RegistrationView, UnregisterView
from core.images import GUILD_UNREGISTER


class Guild(commands.Cog, name="adventurer's guild"):
    def __init__(self, bot):
        self.bot = bot

    def load_exp_table(self):
        with open("assets/exp.json") as file:
            return json.load(file)

    @app_commands.command(name="register", description="Start your journey.")
    async def register(self, interaction: Interaction, name: str):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing = await self.bot.database.users.get(user_id, server_id)
        if existing:
            return await interaction.response.send_message(
                "You are already registered! Use `/card`.", ephemeral=True
            )

        self.bot.state_manager.set_active(user_id, "register")

        embed = discord.Embed(
            title="Adventurers' Guild — Intake",
            description=(
                f"So, **{name}** — you want to make it official.\n\n"
                "I don't turn people away without good reason, but I do need you on "
                "record before you walk out those doors carrying a guild mark. "
                "We'll start simple: pick a face that suits you. "
                "Everything else comes after.\n\n"
                "*Select your gender below to begin.*"
            ),
            color=0x3D2B1F,
        )
        embed.set_author(name="Guildmaster Amara", icon_url=AMARA_AUTHOR)
        embed.set_thumbnail(url=AMARA_PORTRAIT)
        embed.set_image(url=AMARA_PORTRAIT)

        view = RegistrationView(self.bot, user_id, name)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="tutorial",
        description="Replay Guildmaster Amara's introduction to the guild.",
    )
    async def tutorial(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "tutorial")
        view = TutorialView(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="unregister", description="Unregister as an adventurer.")
    async def unregister_adventurer(self, interaction: Interaction) -> None:
        """
        Unregisters the command sender as an adventurer.
        """
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # 2. State Lock
        self.bot.state_manager.set_active(user_id, "unregister")
        embed = discord.Embed(
            title="Confirm Unregistration",
            description=(
                "Are you sure you want to unregister as an adventurer? \n"
                "**This action is permanent and deletes all progress.**"
            ),
            color=0xFFCC00,
        )
        embed.set_thumbnail(url=GUILD_UNREGISTER)  # 3. View Instantiation
        view = UnregisterView(
            self.bot, user_id, existing_user["ideology"]
        )
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Guild(bot))
