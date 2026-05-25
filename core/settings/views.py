import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView

_HARD_MODE_DESC = (
    "**☠️ Hard Combat Mode** — {status}\n"
    "Monster ATK and DEF are doubled. Corrupted encounter rate +2%. "
    "On death, your current-level EXP is wiped. "
    "Victories grant an additional **+50% EXP & Gold** (additive with other bonuses). "
    "Requires level 100."
)


class SettingsView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        doors_status: bool,
        exp_protection: bool,
        hard_mode: bool = False,
        player_level: int = 1,
    ):
        super().__init__(bot, user_id)
        self.doors_status = doors_status
        self.exp_protection = exp_protection
        self.hard_mode = hard_mode
        self.player_level = player_level
        self.rebuild_buttons()

    def rebuild_buttons(self):
        self.clear_items()

        doors_lbl = "Disable Boss Doors" if self.doors_status else "Enable Boss Doors"
        doors_style = ButtonStyle.danger if self.doors_status else ButtonStyle.success
        doors_btn = ui.Button(label=doors_lbl, style=doors_style, emoji="🚪", row=0)
        doors_btn.callback = self.toggle_doors
        self.add_item(doors_btn)

        exp_lbl = (
            "Disable EXP Protection" if self.exp_protection else "Enable EXP Protection"
        )
        exp_style = ButtonStyle.danger if self.exp_protection else ButtonStyle.success
        exp_btn = ui.Button(label=exp_lbl, style=exp_style, emoji="🛡️", row=1)
        exp_btn.callback = self.toggle_exp_protection
        self.add_item(exp_btn)

        if self.player_level >= 100:
            hard_lbl = "Disable Hard Mode" if self.hard_mode else "Enable Hard Mode"
            hard_style = ButtonStyle.danger if self.hard_mode else ButtonStyle.blurple
            hard_btn = ui.Button(label=hard_lbl, style=hard_style, emoji="☠️", row=2)
            hard_btn.callback = self.toggle_hard_mode
            self.add_item(hard_btn)

        close_btn = ui.Button(label="Close", style=ButtonStyle.secondary, emoji="✖️", row=3)
        close_btn.callback = self._close
        self.add_item(close_btn)

    def build_embed(self) -> discord.Embed:
        doors_str = "🟢 ENABLED" if self.doors_status else "🔴 DISABLED"
        exp_str = "🟢 ENABLED" if self.exp_protection else "🔴 DISABLED"
        hard_str = "🟢 ENABLED" if self.hard_mode else "🔴 DISABLED"

        desc = (
            "**🚪 Boss Doors** — {doors}\n"
            "When enabled, your keys and fragments will resonate, giving you a chance to "
            "encounter Boss Doors during regular `/combat`. Disable to bypass all boss "
            "encounters and fight only standard monsters (useful for Slayer tasks or general grinding).\n\n"
            "**🛡️ EXP Protection** — {exp}\n"
            "When enabled, you will still see experience rewards but will not actually gain it. "
            "Useful for staying at your current level."
        ).format(doors=doors_str, exp=exp_str)

        if self.player_level >= 100:
            desc += "\n\n" + _HARD_MODE_DESC.format(status=hard_str)

        embed = discord.Embed(
            title="Settings", description=desc, color=discord.Color.blue()
        )
        return embed

    async def toggle_doors(self, interaction: Interaction):
        self.doors_status = not self.doors_status
        await self.bot.database.users.toggle_doors(self.user_id, self.doors_status)
        self.rebuild_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_exp_protection(self, interaction: Interaction):
        self.exp_protection = not self.exp_protection
        await self.bot.database.users.toggle_exp_protection(
            self.user_id, self.exp_protection
        )
        self.rebuild_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_hard_mode(self, interaction: Interaction):
        self.hard_mode = not self.hard_mode
        await self.bot.database.users.toggle_hard_mode(self.user_id, self.hard_mode)
        self.rebuild_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _close(self, interaction: Interaction):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()
