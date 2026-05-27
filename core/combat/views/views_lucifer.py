# core/combat/views_lucifer.py
import random

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.images import BOSS_LUCIFER
from core.combat.views.views_uber_hub import UberReturnView


class LuciferChoiceView(BaseView):
    """Soul Core selection after defeating Lucifer."""

    def __init__(self, bot, user_id, player):
        super().__init__(bot, user_id)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        self.message = None  # Set by caller after send

    async def on_timeout(self):
        if self.message:
            try:
                embed = discord.Embed(
                    title="Core Expired",
                    description="*You hesitated too long. The Soul Core crumbles to ash.*",
                    color=discord.Color.dark_grey(),
                )
                await self.message.edit(embed=embed, view=None)
            except Exception:
                pass
        await super().on_timeout()

    async def _conclude(self, interaction, msg):
        embed = interaction.message.embeds[0]
        embed.add_field(name="Choice", value=msg, inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    @ui.button(label="Enraged", emoji="❤️‍🔥", style=ButtonStyle.danger)
    async def enraged(self, interaction: Interaction, button: ui.Button):
        adj = random.randint(-1, 2)
        await self.bot.database.users.modify_stat(self.user_id, "attack", adj)

        if adj == -1:
            flavor = "The core backfires violently."
        elif adj == 0:
            flavor = "The soul core fades and its power fails to bind."
        elif adj == 1:
            flavor = "A fierce anger surges through you."
        else:  # +2
            flavor = "Unbridled wrath consumes you!"

        msg = f"{flavor}"
        if adj != 0:
            msg += f" (Attack changed by {adj:+})"

        await self._conclude(interaction, msg)

    @ui.button(label="Solidified", emoji="💙", style=ButtonStyle.primary)
    async def solidified(self, interaction: Interaction, button: ui.Button):
        adj = random.randint(-1, 2)
        await self.bot.database.users.modify_stat(self.user_id, "defence", adj)

        if adj == -1:
            flavor = "The core falters, making you more vulnerable."
        elif adj == 0:
            flavor = "The soul core fades and its power fails to bind."
        elif adj == 1:
            flavor = "Your body hardens with newfound resilience."
        else:  # +2
            flavor = "The core forms an impenetrable shield!"

        msg = f"{flavor}"
        if adj != 0:
            msg += f" (Defence changed by {adj:+})"

        await self._conclude(interaction, msg)

    @ui.button(label="Unstable", emoji="💔", style=ButtonStyle.secondary)
    async def unstable(self, interaction: Interaction, button: ui.Button):
        total = self.player.base_attack + self.player.base_defence
        # Randomize towards equilibrium (49-51% split)
        new_atk = int(total * random.uniform(0.49, 0.51))
        new_def = total - new_atk
        atk_diff = new_atk - self.player.base_attack
        def_diff = new_def - self.player.base_defence
        await self.bot.database.users.modify_stat(self.user_id, "attack", atk_diff)
        await self.bot.database.users.modify_stat(self.user_id, "defence", def_diff)
        await self._conclude(
            interaction, f"Chaos ensues! (Atk: {new_atk}, Def: {new_def})"
        )

    @ui.button(label="Inverse", emoji="💞", style=ButtonStyle.secondary)
    async def inverse(self, interaction: Interaction, button: ui.Button):
        diff = self.player.base_defence - self.player.base_attack
        await self.bot.database.users.modify_stat(self.user_id, "attack", diff)
        await self.bot.database.users.modify_stat(self.user_id, "defence", -diff)
        await self._conclude(
            interaction,
            f"Stats Swapped! (Atk: {self.player.base_defence}, Def: {self.player.base_attack})",
        )

    @ui.button(label="Original", emoji="🖤", style=ButtonStyle.success)
    async def original(self, interaction: Interaction, button: ui.Button):
        await self.bot.database.users.modify_currency(self.user_id, "soul_cores", 1)
        await self._conclude(interaction, "You pocket a Soul Core.")


class InfernalContractView(BaseView):
    """Randomly-generated stat contract presented after killing Uber Lucifer."""

    STAT_LABELS = {"attack": "⚔️ ATK", "defence": "🛡️ DEF", "hp": "❤️ HP"}

    def __init__(self, bot, user_id: str, player, server_id: str, message):
        super().__init__(bot, user_id)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        self.server_id = server_id
        self.message = message

        self.contract = self._roll_contract()

    def _roll_contract(self) -> dict:
        roll = random.random()
        if roll < 0.05:  # 5%  — all positive
            signs = [1, 1, 1]
        elif roll < 0.25:  # 20% — 2 positive 1 negative
            signs = [1, 1, -1]
        else:  # 75% — 1 positive 2 negative
            signs = [1, -1, -1]

        random.shuffle(signs)
        stats = ["attack", "defence", "hp"]
        random.shuffle(stats)

        return {stat: signs[i] * random.randint(5, 20) for i, stat in enumerate(stats)}

    def contract_summary(self) -> str:
        parts = []
        for stat, delta in self.contract.items():
            sign = "+" if delta > 0 else ""
            parts.append(f"{self.STAT_LABELS[stat]}: **{sign}{delta}**")
        return (
            "\n".join(parts)
            + "\n\n*Lucifer offers a deal. Most deals are poor. This may be too.*"
        )

    @ui.button(label="Accept Contract", style=discord.ButtonStyle.danger, emoji="🩸")
    async def accept(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()

        atk_delta = self.contract.get("attack", 0)
        def_delta = self.contract.get("defence", 0)
        hp_delta = self.contract.get("hp", 0)

        # Clamp to minimums first, then derive actual deltas applied
        new_atk = max(1, self.player.base_attack + atk_delta)
        new_def = max(1, self.player.base_defence + def_delta)
        new_hp = max(10, self.player.max_hp + hp_delta)

        actual_atk_delta = new_atk - self.player.base_attack
        actual_def_delta = new_def - self.player.base_defence
        actual_hp_delta = new_hp - self.player.max_hp

        self.player.base_attack = new_atk
        self.player.base_defence = new_def
        self.player.max_hp = new_hp
        self.player.current_hp = min(self.player.current_hp, self.player.total_max_hp)
        self.player.compute_flat_stats()  # Refresh flat cache with new base values

        # update_from_player_object does not write attack/defence/max_hp,
        # so we must persist those via modify_stat directly.
        if actual_atk_delta:
            await self.bot.database.users.modify_stat(
                self.user_id, "attack", actual_atk_delta
            )
        if actual_def_delta:
            await self.bot.database.users.modify_stat(
                self.user_id, "defence", actual_def_delta
            )
        if actual_hp_delta:
            await self.bot.database.users.modify_stat(
                self.user_id, "max_hp", actual_hp_delta
            )
        await self.bot.database.users.update_from_player_object(self.player)

        parts = []
        for stat, delta in self.contract.items():
            sign = "+" if delta > 0 else ""
            parts.append(f"{self.STAT_LABELS[stat]}: **{sign}{delta}**")

        embed = discord.Embed(
            title="🩸 Contract Signed",
            description="The ink dries in flame. Your soul bears the mark.\n\n"
            + "\n".join(parts),
            color=discord.Color.dark_red(),
        )
        embed.set_thumbnail(url=BOSS_LUCIFER)
        embed.set_footer(text="There is no going back.")
        self.bot.state_manager.clear_active(self.user_id)
        return_view = UberReturnView(self.bot, self.user_id, self.server_id, self.player)
        await interaction.edit_original_response(embed=embed, view=return_view)
        self.stop()

    @ui.button(label="Reject Contract", style=discord.ButtonStyle.secondary, emoji="🖤")
    async def reject(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(
            title="🖤 Contract Rejected",
            description="Lucifer watches you walk away. *He will remember.*",
            color=discord.Color.dark_grey(),
        )
        embed.set_thumbnail(url=BOSS_LUCIFER)
        self.bot.state_manager.clear_active(self.user_id)
        return_view = UberReturnView(self.bot, self.user_id, self.server_id, self.player)
        await interaction.edit_original_response(embed=embed, view=return_view)
        self.stop()
