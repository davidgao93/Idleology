import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView

# ---------------------------------------------------------------------------
# Difficulty tier definitions
# ---------------------------------------------------------------------------

_DIFFICULTY_NAMES = ["Off", "Hard", "Extreme", "Nightmarish", "Delirious"]
_DIFFICULTY_EMOJIS = ["⬜", "☠️", "💀", "👁️", "🌀"]

_DIFFICULTY_DESCRIPTIONS = {
    0: ("Standard encounters — no penalties or bonuses."),
    1: (
        "**☠️ Hard** — Monster ATK & DEF ×2, +15% hit & crit chance, ×1.2 surge multiplier. "
        "Corrupted rate +2%. Victories grant **+50% EXP & Gold**. "
        "On death, current-level EXP is wiped."
    ),
    2: (
        "**💀 Extreme** — Monster ATK & DEF ×2.5, +20% hit & crit chance, ×1.3 surge multiplier. "
        "Corrupted rate +5%. Victories grant **+75% EXP & Gold**. "
        "On death, current-level EXP is wiped."
    ),
    3: (
        "**👁️ Nightmarish** — Monster ATK & DEF ×3, +30% hit & crit chance, ×1.4 surge multiplier, "
        "+10% monster DR. Corrupted rate +8%. Victories grant **+100% EXP & Gold**. "
        "On death, current-level EXP is wiped."
    ),
    4: (
        "**🌀 Delirious** — Monster ATK & DEF ×4, +50% hit & crit chance, ×1.5 surge multiplier, "
        "+25% monster DR. Corrupted rate +10%. Victories grant **+150% EXP & Gold**. "
        "On death, current-level EXP is wiped."
    ),
}


class SettingsView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        doors_status: bool,
        exp_protection: bool,
        auto_rest_pay: bool = False,
        difficulty: int = 0,
        player_level: int = 1,
    ):
        super().__init__(bot, user_id)
        self.doors_status = doors_status
        self.exp_protection = exp_protection
        self.auto_rest_pay = auto_rest_pay
        self.difficulty = max(0, min(4, difficulty))
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

        rest_lbl = (
            "Disable Auto-Pay Rest" if self.auto_rest_pay else "Enable Auto-Pay Rest"
        )
        rest_style = ButtonStyle.danger if self.auto_rest_pay else ButtonStyle.success
        rest_btn = ui.Button(label=rest_lbl, style=rest_style, emoji="💰", row=2)
        rest_btn.callback = self.toggle_auto_rest_pay
        self.add_item(rest_btn)

        if self.player_level >= 100:
            select = ui.Select(
                placeholder=f"⚔️ Combat Difficulty: {_DIFFICULTY_EMOJIS[self.difficulty]} {_DIFFICULTY_NAMES[self.difficulty]}",
                options=[
                    discord.SelectOption(
                        label="⬜ Off",
                        value="0",
                        description="Standard encounters.",
                        default=(self.difficulty == 0),
                    ),
                    discord.SelectOption(
                        label="☠️ Hard",
                        value="1",
                        description="ATK & DEF ×2 | +50% EXP & Gold | Corrupted +2%",
                        default=(self.difficulty == 1),
                    ),
                    discord.SelectOption(
                        label="💀 Extreme",
                        value="2",
                        description="ATK & DEF ×2.5 | +75% EXP & Gold | Corrupted +5%",
                        default=(self.difficulty == 2),
                    ),
                    discord.SelectOption(
                        label="👁️ Nightmarish",
                        value="3",
                        description="ATK & DEF ×3 | +100% EXP & Gold | Corrupted +8%",
                        default=(self.difficulty == 3),
                    ),
                    discord.SelectOption(
                        label="🌀 Delirious",
                        value="4",
                        description="ATK & DEF ×4 | +150% EXP & Gold | Corrupted +10%",
                        default=(self.difficulty == 4),
                    ),
                ],
                row=3,
            )

            async def _difficulty_callback(interaction: Interaction, s=select):
                self.difficulty = int(s.values[0])
                await self.bot.database.users.set_difficulty(
                    self.user_id, self.difficulty
                )
                self.rebuild_buttons()
                await interaction.response.edit_message(
                    embed=self.build_embed(), view=self
                )

            select.callback = _difficulty_callback
            self.add_item(select)

        close_btn = ui.Button(
            label="Close", style=ButtonStyle.secondary, emoji="✖️", row=4
        )
        close_btn.callback = self._close
        self.add_item(close_btn)

    def build_embed(self) -> discord.Embed:
        doors_str = "🟢 ENABLED" if self.doors_status else "🔴 DISABLED"
        exp_str = "🟢 ENABLED" if self.exp_protection else "🔴 DISABLED"

        desc = (
            "**🚪 Boss Doors** — {doors}\n"
            "When enabled, your keys and fragments will resonate, giving you a chance to "
            "encounter Boss Doors during regular `/combat`. Disable to bypass all boss "
            "encounters and fight only standard monsters (useful for Slayer tasks or general grinding).\n\n"
            "**🛡️ EXP Protection** — {exp}\n"
            "When enabled, you will no longer gain any experience. "
            "Useful for staying at your current level.\n\n"
            "**💰 Auto-Pay for Rest** — {rest}\n"
            "When enabled, using `/rest` while on cooldown will automatically pay the gold cost "
            "to instantly rest (if you have enough gold), skipping the confirmation prompt."
        ).format(
            doors=doors_str,
            exp=exp_str,
            rest=("🟢 ENABLED" if self.auto_rest_pay else "🔴 DISABLED"),
        )

        if self.player_level >= 100:
            diff_name = f"{_DIFFICULTY_EMOJIS[self.difficulty]} {_DIFFICULTY_NAMES[self.difficulty]}"
            desc += (
                f"\n\n**⚔️ Combat Difficulty** — {diff_name}\n"
                + _DIFFICULTY_DESCRIPTIONS[self.difficulty]
                + "\n*Requires level 100. Applies to all `/combat` encounters.*"
            )

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

    async def toggle_auto_rest_pay(self, interaction: Interaction):
        self.auto_rest_pay = not self.auto_rest_pay
        await self.bot.database.users.toggle_auto_rest_pay(
            self.user_id, self.auto_rest_pay
        )
        self.rebuild_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _close(self, interaction: Interaction):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()
