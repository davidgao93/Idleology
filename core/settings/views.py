import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.emojis import DIFFICULTY_TIER_EMOJI, GOLD_COIN, POTION

# ---------------------------------------------------------------------------
# Difficulty tier definitions
# ---------------------------------------------------------------------------

_DIFFICULTY_NAMES = ["Off", "Hard", "Extreme", "Nightmarish", "Delirious"]

_DIFFICULTY_DESCRIPTIONS = {
    0: ("Standard encounters — no penalties or bonuses."),
    1: (
        f"**{DIFFICULTY_TIER_EMOJI[1]} Hard** — Monster ATK & DEF ×2, +15% hit & crit chance, ×1.2 surge multiplier. "
        "Corrupted rate +2%. Victories grant **+50% EXP & Gold**. "
        "On death, current-level EXP is wiped."
    ),
    2: (
        f"**{DIFFICULTY_TIER_EMOJI[2]} Extreme** — Monster ATK & DEF ×2.5, +20% hit & crit chance, ×1.3 surge multiplier. "
        "Corrupted rate +5%. Victories grant **+75% EXP & Gold**. "
        "On death, current-level EXP is wiped."
    ),
    3: (
        f"**{DIFFICULTY_TIER_EMOJI[3]} Nightmarish** — Monster ATK & DEF ×3, +30% hit & crit chance, ×1.4 surge multiplier, "
        "+10% monster DR. Corrupted rate +8%. Victories grant **+100% EXP & Gold**. "
        "On death, current-level EXP is wiped."
    ),
    4: (
        f"**{DIFFICULTY_TIER_EMOJI[4]} Delirious** — Monster ATK & DEF ×4, +50% hit & crit chance, ×1.5 surge multiplier, "
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
        corrupted_status: bool = True,
        auto_potion_reload: bool = False,
        auto_rest_unlocked: bool = False,
        auto_reload_unlocked: bool = False,
        nsfw_enabled: bool = False,
    ):
        super().__init__(bot, user_id)
        self.doors_status = doors_status
        self.exp_protection = exp_protection
        self.auto_rest_pay = auto_rest_pay
        self.difficulty = max(0, min(4, difficulty))
        self.player_level = player_level
        self.corrupted_status = corrupted_status
        self.auto_potion_reload = auto_potion_reload
        self.auto_rest_unlocked = auto_rest_unlocked
        self.auto_reload_unlocked = auto_reload_unlocked
        self.nsfw_enabled = nsfw_enabled
        self._processing = False
        self.rebuild_buttons()

    def rebuild_buttons(self):
        self.clear_items()

        doors_lbl = "Disable Boss Doors" if self.doors_status else "Enable Boss Doors"
        doors_style = ButtonStyle.danger if self.doors_status else ButtonStyle.success
        doors_btn = ui.Button(label=doors_lbl, style=doors_style, emoji="🚪", row=0)
        doors_btn.callback = self.toggle_doors
        self.add_item(doors_btn)

        corrupted_lbl = (
            "Disable Corrupted Encounters"
            if self.corrupted_status
            else "Enable Corrupted Encounters"
        )
        corrupted_style = (
            ButtonStyle.danger if self.corrupted_status else ButtonStyle.success
        )
        corrupted_btn = ui.Button(
            label=corrupted_lbl, style=corrupted_style, emoji="☠️", row=0
        )
        corrupted_btn.callback = self.toggle_corrupted_encounters
        self.add_item(corrupted_btn)

        exp_lbl = (
            "Disable EXP Protection" if self.exp_protection else "Enable EXP Protection"
        )
        exp_style = ButtonStyle.danger if self.exp_protection else ButtonStyle.success
        exp_btn = ui.Button(label=exp_lbl, style=exp_style, emoji="🛡️", row=1)
        exp_btn.callback = self.toggle_exp_protection
        self.add_item(exp_btn)

        if self.auto_rest_unlocked:
            rest_lbl = (
                "Disable Auto-Pay Rest"
                if self.auto_rest_pay
                else "Enable Auto-Pay Rest"
            )
            rest_style = (
                ButtonStyle.danger if self.auto_rest_pay else ButtonStyle.success
            )
            rest_btn = ui.Button(
                label=rest_lbl, style=rest_style, emoji=GOLD_COIN, row=1
            )
            rest_btn.callback = self.toggle_auto_rest_pay
        else:
            rest_btn = ui.Button(
                label="Auto-Pay Rest (Unlock: Quest Shop, 10🎫)",
                style=ButtonStyle.secondary,
                emoji="🔒",
                row=1,
                disabled=True,
            )
        self.add_item(rest_btn)

        if self.auto_reload_unlocked:
            reload_lbl = (
                "Disable Auto-Reload Potions"
                if self.auto_potion_reload
                else "Enable Auto-Reload Potions"
            )
            reload_style = (
                ButtonStyle.danger if self.auto_potion_reload else ButtonStyle.success
            )
            reload_btn = ui.Button(
                label=reload_lbl, style=reload_style, emoji="🧪", row=1
            )
            reload_btn.callback = self.toggle_auto_potion_reload
        else:
            reload_btn = ui.Button(
                label="Auto-Reload Potions (Unlock: Quest Shop, 25🎫)",
                style=ButtonStyle.secondary,
                emoji="🔒",
                row=1,
                disabled=True,
            )
        self.add_item(reload_btn)

        nsfw_lbl = "Disable NSFW Monsters" if self.nsfw_enabled else "Enable NSFW Monsters"
        nsfw_style = ButtonStyle.danger if self.nsfw_enabled else ButtonStyle.success
        nsfw_btn = ui.Button(label=nsfw_lbl, style=nsfw_style, emoji="🔞", row=2)
        nsfw_btn.callback = self.toggle_nsfw
        self.add_item(nsfw_btn)

        if self.player_level >= 100:
            select = ui.Select(
                placeholder=f"⚔️ Combat Difficulty: {_DIFFICULTY_NAMES[self.difficulty]}",
                options=[
                    discord.SelectOption(
                        label="Off",
                        value="0",
                        description="Standard encounters.",
                        emoji=DIFFICULTY_TIER_EMOJI[0],
                        default=(self.difficulty == 0),
                    ),
                    discord.SelectOption(
                        label="Hard",
                        value="1",
                        description="ATK & DEF ×2 | +50% EXP & Gold | Corrupted +2%",
                        emoji=DIFFICULTY_TIER_EMOJI[1],
                        default=(self.difficulty == 1),
                    ),
                    discord.SelectOption(
                        label="Extreme",
                        value="2",
                        description="ATK & DEF ×2.5 | +75% EXP & Gold | Corrupted +5%",
                        emoji=DIFFICULTY_TIER_EMOJI[2],
                        default=(self.difficulty == 2),
                    ),
                    discord.SelectOption(
                        label="Nightmarish",
                        value="3",
                        description="ATK & DEF ×3 | +100% EXP & Gold | Corrupted +8%",
                        emoji=DIFFICULTY_TIER_EMOJI[3],
                        default=(self.difficulty == 3),
                    ),
                    discord.SelectOption(
                        label="Delirious",
                        value="4",
                        description="ATK & DEF ×4 | +150% EXP & Gold | Corrupted +10%",
                        emoji=DIFFICULTY_TIER_EMOJI[4],
                        default=(self.difficulty == 4),
                    ),
                ],
                row=3,
            )

            async def _difficulty_callback(interaction: Interaction, s=select):
                if self._processing:
                    await interaction.response.defer()
                    return
                self._processing = True
                self.difficulty = int(s.values[0])
                await self.bot.database.users.set_difficulty(
                    self.user_id, self.difficulty
                )
                self.rebuild_buttons()
                self._processing = False
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
            "**☠️ Corrupted Encounters** — {corrupted}\n"
            "When enabled, Corrupted monsters can appear during regular `/combat` from level 70+. "
            "Disable to skip all Corrupted encounters.\n\n"
            "**🛡️ EXP Protection** — {exp}\n"
            "When enabled, you will no longer gain any experience. "
            "Useful for staying at your current level.\n\n"
            "**{gold} Auto-Pay for Rest** — {rest}\n"
            "When enabled, using `/rest` while on cooldown will automatically pay the gold cost "
            "to instantly rest (if you have enough gold), skipping the confirmation prompt.\n\n"
            "**{potion} Auto-Reload Potions** — {reload}\n"
            "When enabled, winning a normal `/combat` fight will automatically buy enough potions "
            "to top off your stock (if you have enough gold).\n\n"
            "**🔞 NSFW Monsters** — {nsfw}\n"
            "When enabled, monsters with NSFW artwork can appear in your `/combat` encounters."
        ).format(
            doors=doors_str,
            corrupted=("🟢 ENABLED" if self.corrupted_status else "🔴 DISABLED"),
            exp=exp_str,
            gold=GOLD_COIN,
            rest=(
                ("🟢 ENABLED" if self.auto_rest_pay else "🔴 DISABLED")
                if self.auto_rest_unlocked
                else "🔒 LOCKED — unlock for 10🎫 in the Quest Shop (`/quests`)"
            ),
            potion=POTION,
            reload=(
                ("🟢 ENABLED" if self.auto_potion_reload else "🔴 DISABLED")
                if self.auto_reload_unlocked
                else "🔒 LOCKED — unlock for 25🎫 in the Quest Shop (`/quests`)"
            ),
            nsfw=("🟢 ENABLED" if self.nsfw_enabled else "🔴 DISABLED"),
        )

        if self.player_level >= 100:
            diff_name = f"{DIFFICULTY_TIER_EMOJI[self.difficulty]} {_DIFFICULTY_NAMES[self.difficulty]}"
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
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        self.doors_status = not self.doors_status
        await self.bot.database.users.toggle_doors(self.user_id, self.doors_status)
        self.rebuild_buttons()
        self._processing = False
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_exp_protection(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        self.exp_protection = not self.exp_protection
        await self.bot.database.users.toggle_exp_protection(
            self.user_id, self.exp_protection
        )
        self.rebuild_buttons()
        self._processing = False
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_auto_rest_pay(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        self.auto_rest_pay = not self.auto_rest_pay
        await self.bot.database.users.toggle_auto_rest_pay(
            self.user_id, self.auto_rest_pay
        )
        self.rebuild_buttons()
        self._processing = False
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_corrupted_encounters(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        self.corrupted_status = not self.corrupted_status
        await self.bot.database.users.toggle_corrupted_encounters(
            self.user_id, self.corrupted_status
        )
        self.rebuild_buttons()
        self._processing = False
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_auto_potion_reload(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        self.auto_potion_reload = not self.auto_potion_reload
        await self.bot.database.users.toggle_auto_potion_reload(
            self.user_id, self.auto_potion_reload
        )
        self.rebuild_buttons()
        self._processing = False
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_nsfw(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        self.nsfw_enabled = not self.nsfw_enabled
        await self.bot.database.users.toggle_nsfw_enabled(
            self.user_id, self.nsfw_enabled
        )
        self.rebuild_buttons()
        self._processing = False
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _close(self, interaction: Interaction):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()
