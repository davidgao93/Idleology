import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.companions.mechanics import CompanionMechanics
from core.images import (
    UPGRADE_GEMINI_ENGRAM,
)


class BalancedEngramView(BaseView):
    """Allows consuming a Gemini Engram to awaken or reroll a companion's balanced (secondary) passive."""

    def __init__(self, bot, user_id, companion, parent_view):
        super().__init__(bot, user_id=user_id, parent=parent_view)
        self.comp = companion
        self.parent_view = parent_view

    def add_back_button(self):
        """Helper to re-add the back button after clearing items."""
        btn_back = Button(label="Back", style=ButtonStyle.secondary, row=4)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def render(self, interaction: Interaction):
        server_id = str(interaction.guild.id)

        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        self.engrams = uber_prog.get("gemini_engrams", 0)

        current_passive = self.comp.balanced_passive
        display_passive = (
            current_passive.replace("_", " ").title()
            if current_passive != "none"
            else "Not Awakened"
        )
        tier_display = (
            f"T{self.comp.balanced_passive_tier} "
            if self.comp.balanced_passive_tier > 0
            else ""
        )

        desc = (
            f"**Current Balanced Passive:** {tier_display}{display_passive}\n"
            f"**Gemini Engrams Owned:** {self.engrams}\n\n"
            f"Consuming an Engram awakens your companion's hidden potential, granting a secondary passive "
            f"at T{max(1, self.comp.passive_tier - 2)} (Primary Tier − 2, minimum T1).\n"
            f"Re-rolling always changes the secondary passive type."
        )

        self.embed = discord.Embed(
            title=f"♊ Balanced Awakening: {self.comp.name}",
            description=desc,
            color=discord.Color.blurple(),
        )
        self.embed.set_thumbnail(url=UPGRADE_GEMINI_ENGRAM)

        self.clear_items()
        btn_consume = Button(
            label="Consume Engram",
            style=ButtonStyle.blurple,
            emoji="♊",
            disabled=(self.engrams < 1),
        )
        btn_consume.callback = self.confirm_engram
        self.add_item(btn_consume)
        self.add_back_button()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)
        self.message = await interaction.original_response()

    async def go_back(self, interaction: Interaction):
        """Returns to the companion detail view."""
        embed = self.parent_view.get_embed()
        self.parent_view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
        self.stop()

    async def confirm_engram(self, interaction: Interaction):
        server_id = str(interaction.guild.id)
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, server_id
        )
        if uber_prog.get("gemini_engrams", 0) < 1:
            return await interaction.response.send_message(
                "You do not have any Gemini Engrams!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < 25_000_000:
            return await interaction.response.send_message(
                "You need **25,000,000 gold** to use a Balanced Engram.", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_gold(self.user_id, -25_000_000)
        await self.bot.database.uber.increment_gemini_engrams(
            self.user_id, server_id, -1
        )

        new_type, new_tier = CompanionMechanics.roll_balanced_passive(
            self.comp.passive_type, self.comp.passive_tier, self.comp.balanced_passive
        )

        await self.bot.database.companions.update_balanced_passive(
            self.comp.id, new_type, new_tier
        )
        self.comp.balanced_passive = new_type
        self.comp.balanced_passive_tier = new_tier

        display_new = new_type.replace("_", " ").title()
        res_embed = discord.Embed(
            title="♊ Balanced Awakening!",
            description=(
                f"The twins' constellation realigns, awakening a new potential.\n\n"
                f"**New Balanced Passive:** T{new_tier} {display_new}"
            ),
            color=discord.Color.blurple(),
        )
        res_embed.set_thumbnail(url=UPGRADE_GEMINI_ENGRAM)

        self.clear_items()
        remaining = uber_prog.get("gemini_engrams", 0) - 1
        if remaining > 0:
            btn_again = Button(label="Roll Again", style=ButtonStyle.primary)
            btn_again.callback = self.render
            self.add_item(btn_again)

        self.add_back_button()
        await interaction.edit_original_response(embed=res_embed, view=self)
        self.message = await interaction.original_response()
