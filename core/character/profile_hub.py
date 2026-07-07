"""
core/character/profile_hub.py
ProfileHubView — tabbed profile UI. Embed building lives in profile_ui.py.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.character.profile_ui import ProfileBuilder
from core.combat import ui as combat_ui

# Row 0: Profile | Cooldowns | Inventory | Crafting | Resources
_ROW0 = [
    ("profile", "Profile", "👤", 0),
    ("cooldowns", "Cooldowns", "⏰", 0),
    ("inventory", "Inventory", "🎒", 0),
    ("crafting", "Crafting", "⚗️", 0),
    ("resources", "Resources", "📦", 0),
]

# Row 1: Stats | Gear Passives | Misc Passives | Uber | Close
_ROW1 = [
    ("stats", "Stats", "📊", 1),
    ("gear_passives", "Gear Passives", "⚡", 1),
    ("misc_passives", "Misc Passives", "🔮", 1),
    ("uber", "Uber", "⚔️", 1),
]


class ProfileHubView(BaseLayoutView):
    def __init__(self, bot, user_id: str, server_id: str, active_tab: str):
        super().__init__(bot, user_id, server_id)
        self.active_tab = active_tab
        self._processing = False

    async def on_timeout(self):
        # Overrides BaseLayoutView default: no clear_active since this view
        # never sets it, and the whole message is deleted rather than
        # stripped (read-only view, nothing worth leaving behind).
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass
        self.stop()

    def _build_rows(self) -> list[discord.ui.ActionRow]:
        row0 = discord.ui.ActionRow()
        row1 = discord.ui.ActionRow()

        for tab_id, label, emoji, row_idx in [*_ROW0, *_ROW1]:
            style = (
                ButtonStyle.primary
                if self.active_tab == tab_id
                else ButtonStyle.secondary
            )
            btn = ui.Button(label=label, emoji=emoji, style=style, custom_id=tab_id)
            btn.callback = self.handle_tab_switch
            (row0 if row_idx == 0 else row1).add_item(btn)

        close_btn = ui.Button(
            label="Close", emoji="✖️", style=ButtonStyle.secondary, custom_id="close"
        )
        close_btn.callback = self.handle_close
        row1.add_item(close_btn)

        return [row0, row1]

    def set_content(self, embed: discord.Embed) -> None:
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(embed))
        for row in self._build_rows():
            self.add_item(row)

    async def handle_close(self, interaction: Interaction):
        # No clear_active: ProfileHubView is never set_active (read-only, can be
        # opened alongside another active session) — clearing here would wipe
        # whatever other feature the user has genuinely active.
        # session-terminating Close (special: no guard)
        await interaction.response.defer()
        self.stop()
        try:
            await interaction.delete_original_response()
        except Exception:
            pass

    async def handle_tab_switch(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        tab_id = interaction.data["custom_id"]
        if tab_id == self.active_tab:
            return await interaction.response.defer()
        self._processing = True
        self.active_tab = tab_id
        await interaction.response.defer()

        embed = None
        if tab_id == "profile":
            embed = await ProfileBuilder.build_card(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "stats":
            embed = await ProfileBuilder.build_stats(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "gear_passives":
            embed = await ProfileBuilder.build_gear_passives(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "misc_passives":
            embed = await ProfileBuilder.build_misc_passives(
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

        self._processing = False
        self.set_content(embed)
        await interaction.edit_original_response(view=self)
