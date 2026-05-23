# cogs/apex.py

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from core.apex.mechanics import ApexMechanics
from core.apex.models import profile_from_db
from core.apex.views.lobby_view import ApexLobbyView, _build_lobby_embed


class Apex(commands.Cog, name="apex"):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # /apex — Main entry point
    # ------------------------------------------------------------------

    @app_commands.command(
        name="apex",
        description="Enter the Apex Hunt lobby. Dangerous zones, powerful rewards.",
    )
    async def apex(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Standard gate checks
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # Level gate — Apex Hunts are endgame content (unlocked at 90)
        if existing_user["level"] < 90:
            return await interaction.response.send_message(
                "⚠️ Apex Hunts unlock at **Level 90**.",
                ephemeral=True,
            )

        # Load profile and apply charge regen
        profile_row = await self.bot.database.apex.get_or_create_profile(
            user_id, server_id
        )
        profile = profile_from_db(profile_row)
        charges, new_ts = ApexMechanics.calculate_charges(profile)
        if new_ts != profile.last_charge_time:
            await self.bot.database.apex.restore_charges(
                user_id, server_id, charges, new_ts
            )
            profile.hunt_charges = charges
            profile.last_charge_time = new_ts

        secs_to_next = ApexMechanics.seconds_until_next_charge(profile)

        # Player name
        player_name = existing_user["name"]

        # Mark active so the player can't open two lobbies simultaneously
        self.bot.state_manager.set_active(user_id, "apex")

        embed = _build_lobby_embed(player_name, profile, charges, secs_to_next)
        view = ApexLobbyView(
            self.bot, user_id, server_id,
            player_name, profile, charges,
        )
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    # ------------------------------------------------------------------
    # /give_meta_shard — Player-to-player meta shard transfer
    # ------------------------------------------------------------------

    @app_commands.command(
        name="give_meta_shard",
        description="Give a meta shard to another player.",
    )
    @app_commands.describe(
        recipient="The player to send the shard to",
        shard="Which meta shard to give",
        amount="How many to give (default 1)",
    )
    @app_commands.choices(shard=[
        app_commands.Choice(name="Sharpened Fang",   value="sharpened_fang"),
        app_commands.Choice(name="Engorged Heart",   value="engorged_heart"),
        app_commands.Choice(name="Condensed Blood",  value="condensed_blood"),
        app_commands.Choice(name="Primal Essence",   value="primal_essence"),
        app_commands.Choice(name="Soul Vessel",      value="soul_vessel"),
    ])
    async def give_meta_shard(
        self,
        interaction: Interaction,
        recipient: discord.Member,
        shard: str,
        amount: int = 1,
    ):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        to_id = str(recipient.id)

        if recipient.id == interaction.user.id:
            return await interaction.response.send_message(
                "You cannot give a shard to yourself.", ephemeral=True
            )
        if recipient.bot:
            return await interaction.response.send_message(
                "Bots have no use for meta shards.", ephemeral=True
            )
        if amount < 1:
            return await interaction.response.send_message(
                "Amount must be at least 1.", ephemeral=True
            )

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        recip_user = await self.bot.database.users.get(to_id, server_id)
        if not recip_user:
            return await interaction.response.send_message(
                f"{recipient.display_name} is not registered on this server.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        success = await self.bot.database.apex.transfer_meta_shard(
            user_id, to_id, server_id, shard, amount
        )

        shard_display = shard.replace("_", " ").title()
        if not success:
            await interaction.followup.send(
                f"⚠️ You don't have enough **{shard_display}** to give.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"✅ Gave **{amount}x {shard_display}** to {recipient.mention}.",
            ephemeral=True,
        )

        # DM the recipient if possible
        try:
            await recipient.send(
                f"🎁 **{interaction.user.display_name}** sent you "
                f"**{amount}x {shard_display}** in **{interaction.guild.name}**!"
            )
        except Exception:
            pass


async def setup(bot):
    await bot.add_cog(Apex(bot))
