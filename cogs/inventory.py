import asyncio

from discord import Interaction, app_commands
from discord.ext import commands

from core.character.profile_hub import ProfileHubView
from core.character.profile_ui import ProfileBuilder
from core.first_use import TutorialGateView
from core.inventory.views import SLOT_ORDER, GearView, LoadoutView

# Core
from core.items.factory import (
    create_accessory,
    create_armor,
    create_boot,
    create_glove,
    create_helmet,
    create_weapon,
)


async def _fetch_all_slots(bot, user_id: str) -> dict:
    """Fetch and factory-create all six equipment slots concurrently."""
    factories = {
        "weapon": create_weapon,
        "armor": create_armor,
        "helmet": create_helmet,
        "glove": create_glove,
        "boot": create_boot,
        "accessory": create_accessory,
    }
    raw_results = await asyncio.gather(
        *[bot.database.equipment.get_all(user_id, slot) for slot in SLOT_ORDER]
    )
    all_items = {}
    for slot, rows in zip(SLOT_ORDER, raw_results):
        items = [factories[slot](row) for row in rows]
        items.sort(
            key=lambda x: (getattr(x, "is_equipped", False), x.level), reverse=True
        )
        all_items[slot] = items
    return all_items


class Inventory(commands.Cog, name="inventory"):
    def __init__(self, bot):
        self.bot = bot

    async def _generic_gear_command(self, interaction: Interaction, initial_slot: str):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "inventory")

        async def _build():
            all_items = await _fetch_all_slots(self.bot, user_id)
            view = GearView(
                self.bot,
                user_id,
                all_items,
                initial_slot=initial_slot,
                player_name=existing_user["name"],
            )
            return view.build_embed(), view

        if not await self.bot.database.tutorials.has_seen(user_id, "inventory"):
            await self.bot.database.tutorials.mark_seen(user_id, "inventory")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "inventory", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    # --- Commands ---

    @app_commands.command(
        name="gear", description="Manage all your equipped gear in one place."
    )
    async def gear(self, interaction: Interaction):
        await self._generic_gear_command(interaction, initial_slot="weapon")

    @app_commands.command(name="inventory", description="Check your inventory summary.")
    async def inventory_summary(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        view = ProfileHubView(self.bot, user_id, server_id, "inventory")
        embed = await ProfileBuilder.build_inventory(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="resources", description="View refined materials and settlement resources."
    )
    async def resources(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        view = ProfileHubView(self.bot, user_id, server_id, "resources")
        embed = await ProfileBuilder.build_resources(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="weapons", description="Manage your weapons.")
    async def weapons(self, interaction: Interaction):
        await self._generic_gear_command(interaction, initial_slot="weapon")

    @app_commands.command(name="armor", description="Manage your armor.")
    async def armor(self, interaction: Interaction):
        await self._generic_gear_command(interaction, initial_slot="armor")

    @app_commands.command(name="accessory", description="Manage your accessories.")
    async def accessory(self, interaction: Interaction):
        await self._generic_gear_command(interaction, initial_slot="accessory")

    @app_commands.command(name="gloves", description="Manage your gloves.")
    async def gloves(self, interaction: Interaction):
        await self._generic_gear_command(interaction, initial_slot="glove")

    @app_commands.command(name="boots", description="Manage your boots.")
    async def boots(self, interaction: Interaction):
        await self._generic_gear_command(interaction, initial_slot="boot")

    @app_commands.command(name="helmets", description="Manage your helmets.")
    async def helmets(self, interaction: Interaction):
        await self._generic_gear_command(interaction, initial_slot="helmet")

    @app_commands.command(name="loadouts", description="Manage your gear loadouts.")
    async def loadouts(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "inventory")

        try:
            view = await LoadoutView.create(
                self.bot,
                user_id,
                server_id,
                mode="standalone",
                player_name=existing_user["name"],
            )
        except Exception:
            self.bot.state_manager.clear_active(user_id)
            raise

        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Inventory(bot))
