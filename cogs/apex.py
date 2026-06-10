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
    # /soul — Direct entry to Soul Stone view
    # ------------------------------------------------------------------

    @app_commands.command(
        name="soul",
        description="Open your Soul Stone directly.",
    )
    async def soul(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        if existing_user["level"] < 90:
            return await interaction.response.send_message(
                "⚠️ The Soul Stone unlocks at **Level 90**.",
                ephemeral=True,
            )

        from core.items.factory import load_player
        from core.apex.models import soul_stone_from_db, shards_from_db, meta_shards_from_db
        from core.apex.views.soul_stone_view import SoulStoneView, _build_soul_stone_embed

        player = await load_player(user_id, existing_user, self.bot.database)

        ss_row = await self.bot.database.apex.get_or_create_soul_stone(user_id, server_id)
        shards_row = await self.bot.database.apex.get_or_create_shards(user_id, server_id)
        meta_row = await self.bot.database.apex.get_or_create_meta_shards(user_id, server_id)
        soul_stone = soul_stone_from_db(ss_row)
        shards = shards_from_db(shards_row)
        meta = meta_shards_from_db(meta_row)

        self.bot.state_manager.set_active(user_id, "soul_stone")

        embed = _build_soul_stone_embed(soul_stone, shards, meta, player.name)
        view = SoulStoneView(self.bot, user_id, server_id, player)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()



async def setup(bot):
    await bot.add_cog(Apex(bot))
