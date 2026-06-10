import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.images import SYLAS_AUTHOR, UPGRADE_INFERNAL_ENGRAM
from core.inventory.upgrades.base import BaseUpgradeView
from core.items.equipment_mechanics import EquipmentMechanics
from core.models import Weapon


class InfernalEngramView(BaseUpgradeView):
    """Allows consuming an Infernal Engram to unlock or reroll an infernal weapon passive."""

    def __init__(self, bot, user_id, item: Weapon, parent_view):
        super().__init__(bot, user_id, item, parent_view)
        self._processing = False

    async def render(self, interaction: Interaction):
        self._processing = False
        server_id = str(interaction.guild.id)

        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        self.engrams = uber_prog["infernal_engrams"]

        current_passive = getattr(self.item, "infernal_passive", "none")
        display_passive = (
            current_passive.replace("_", " ").title()
            if current_passive != "none"
            else "None"
        )

        desc = (
            f"**Current Infernal Passive:** {display_passive}\n"
            f"**Infernal Engrams Owned:** {self.engrams}\n"
            f"**Gold Cost:** 25,000,000\n\n"
            "Consuming an Engram will imbue your weapon with a powerful Infernal passive, or reroll your existing one."
        )

        self.embed = discord.Embed(
            title=f"🔥 Infernal Imbue: {self.item.name}",
            description=desc,
            color=discord.Color.dark_red(),
        )
        self.embed.set_author(name="Artificer Sylas", icon_url=SYLAS_AUTHOR)
        self.embed.set_thumbnail(url=UPGRADE_INFERNAL_ENGRAM)

        self.clear_items()
        btn_consume = Button(
            label="Consume Engram",
            style=ButtonStyle.danger,
            emoji="🔥",
            disabled=(self.engrams < 1),
        )
        btn_consume.callback = self.confirm_engram
        self.add_item(btn_consume)
        self.add_back_button()

        await self._send_render(interaction, self.embed)

    async def confirm_engram(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        server_id = str(interaction.guild.id)
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        if uber_prog["infernal_engrams"] < 1:
            self._processing = False
            return await interaction.response.send_message(
                "You do not have any Infernal Engrams!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 25_000_000:
            self._processing = False
            return await interaction.response.send_message(
                "You need **25,000,000 gold** to use an Infernal Engram.",
                ephemeral=True,
            )

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        await self.bot.database.users.modify_gold(self.user_id, -25_000_000)
        await self.bot.database.uber.increment_infernal_engrams(
            self.user_id, server_id, -1
        )

        current_p = getattr(self.item, "infernal_passive", "none")
        new_passive = EquipmentMechanics.roll_infernal_passive(current_p)

        await self.bot.database.equipment.update_passive(
            self.item.item_id, "weapon", new_passive, "infernal_passive"
        )
        self.item.infernal_passive = new_passive

        display_new = new_passive.replace("_", " ").title()
        res_embed = discord.Embed(
            title="🔥 Engram Ignited!",
            description=f"The Engram shatters in hellfire, branding your weapon.\n\n**New Passive:** {display_new}",
            color=discord.Color.red(),
        )
        res_embed.set_author(name="Artificer Sylas", icon_url=SYLAS_AUTHOR)
        res_embed.set_thumbnail(url=UPGRADE_INFERNAL_ENGRAM)

        self.clear_items()
        if uber_prog["infernal_engrams"] - 1 > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)
        self.message = await interaction.original_response()
