"""
core/character/profile_hub.py
ProfileHubView — tabbed profile UI. Embed building lives in profile_ui.py.
"""

from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.character.profile_ui import ProfileBuilder


class ProfileHubView(BaseView):
    def __init__(self, bot, user_id: str, server_id: str, active_tab: str):
        super().__init__(bot, user_id, server_id)
        self.active_tab = active_tab
        self.update_buttons()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass

    def update_buttons(self):
        self.clear_items()

        tabs = [
            ("card", "Card", "👤"),
            ("cooldowns", "Cooldowns", "⏰"),
            ("stats", "Stats", "📊"),
            ("passives", "Passives", "⚡"),
            ("inventory", "Inventory", "🎒"),
            ("crafting", "Crafting", "⚗️"),
            ("resources", "Resources", "📦"),
            ("uber", "Uber", "⚔️"),
        ]

        for tab_id, label, emoji in tabs:
            style = (
                ButtonStyle.primary
                if self.active_tab == tab_id
                else ButtonStyle.secondary
            )
            btn = ui.Button(label=label, emoji=emoji, style=style, custom_id=tab_id)
            btn.callback = self.handle_tab_switch
            self.add_item(btn)

    async def handle_tab_switch(self, interaction: Interaction):
        tab_id = interaction.data["custom_id"]
        if tab_id == self.active_tab:
            return await interaction.response.defer()

        self.active_tab = tab_id
        self.update_buttons()
        await interaction.response.defer()

        embed = None
        if tab_id == "card":
            embed = await ProfileBuilder.build_card(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "stats":
            embed = await ProfileBuilder.build_stats(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "passives":
            embed = await ProfileBuilder.build_passives(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "inventory":
            embed = await ProfileBuilder.build_inventory(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "cooldowns":
            embed = await ProfileBuilder.build_cooldowns(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "crafting":
            embed = await ProfileBuilder.build_crafting(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "resources":
            embed = await ProfileBuilder.build_resources(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "uber":
            embed = await ProfileBuilder.build_uber(
                self.bot, self.user_id, self.server_id
            )

        await interaction.edit_original_response(embed=embed, view=self)
