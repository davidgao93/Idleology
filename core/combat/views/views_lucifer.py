# core/combat/views_lucifer.py
import random

import discord
from discord import ButtonStyle, Interaction

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.combat.views.post_combat_view import PostCombatView
from core.images import BOSS_LUCIFER
from core.combat.views.views_uber_hub import UberReturnView


class LuciferChoiceRow(discord.ui.ActionRow["LuciferChoiceView"]):
    @discord.ui.button(label="Enraged", emoji="❤️‍🔥", style=ButtonStyle.danger)
    async def enraged(self, interaction: Interaction, button: discord.ui.Button):
        await self.view._on_enraged(interaction)

    @discord.ui.button(label="Solidified", emoji="💙", style=ButtonStyle.primary)
    async def solidified(self, interaction: Interaction, button: discord.ui.Button):
        await self.view._on_solidified(interaction)

    @discord.ui.button(label="Unstable", emoji="💔", style=ButtonStyle.secondary)
    async def unstable(self, interaction: Interaction, button: discord.ui.Button):
        await self.view._on_unstable(interaction)

    @discord.ui.button(label="Inverse", emoji="💞", style=ButtonStyle.secondary)
    async def inverse(self, interaction: Interaction, button: discord.ui.Button):
        await self.view._on_inverse(interaction)

    @discord.ui.button(label="Original", emoji="🖤", style=ButtonStyle.success)
    async def original(self, interaction: Interaction, button: discord.ui.Button):
        await self.view._on_original(interaction)


class LuciferChoiceView(BaseLayoutView):
    """Soul Core selection after defeating Lucifer."""

    def __init__(
        self, bot, user_id, player, server_id: str = None, rematch_callback=None
    ):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.rematch_callback = rematch_callback
        self.message = None  # Set by caller after send
        self._processing = False  # Re-entry guard (fix 1)
        self._embed: discord.Embed | None = None
        self.row = LuciferChoiceRow()

    def set_content(self, embed: discord.Embed) -> None:
        """Renders `embed` (the victory embed + Soul Core prompt) as this
        view's Components V2 content, followed by the choice buttons."""
        self._embed = embed
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(self.row)

    async def on_timeout(self):
        if self.message:
            try:
                embed = discord.Embed(
                    title="Core Expired",
                    description="*You hesitated too long. The Soul Core crumbles to ash.*",
                    color=discord.Color.dark_grey(),
                )
                self.clear_items()
                self.add_item(combat_ui.embed_to_container(embed))
                await self.message.edit(view=self)
            except Exception:
                pass
        await super().on_timeout()

    async def _conclude(self, interaction, msg):
        # Fix 1: guard against double-click before the first await.
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        await interaction.response.defer()
        embed = self._embed
        embed.add_field(name="Choice", value=msg, inline=False)

        stamina_data = await self.bot.database.users.get_stamina(self.user_id)
        stamina = stamina_data["combat_stamina"]

        post_view = (
            PostCombatView(
                self.bot,
                self.user_id,
                self.server_id,
                self.player,
                stamina,
                self.rematch_callback,
            )
            if self.rematch_callback
            else None
        )

        if post_view is not None:
            post_view.set_content(embed)
            msg_obj = await interaction.edit_original_response(view=post_view)
            post_view.message = msg_obj
        else:
            self.clear_items()
            self.add_item(combat_ui.embed_to_container(embed))
            await interaction.edit_original_response(view=self)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def _on_enraged(self, interaction: Interaction):
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

    async def _on_solidified(self, interaction: Interaction):
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

    async def _on_unstable(self, interaction: Interaction):
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

    async def _on_inverse(self, interaction: Interaction):
        diff = self.player.base_defence - self.player.base_attack
        await self.bot.database.users.modify_stat(self.user_id, "attack", diff)
        await self.bot.database.users.modify_stat(self.user_id, "defence", -diff)
        await self._conclude(
            interaction,
            f"Stats Swapped! (Atk: {self.player.base_defence}, Def: {self.player.base_attack})",
        )

    async def _on_original(self, interaction: Interaction):
        await self.bot.database.users.modify_currency(self.user_id, "soul_cores", 1)
        await self._conclude(interaction, "You pocket a Soul Core.")


class InfernalContractRow(discord.ui.ActionRow["InfernalContractView"]):
    @discord.ui.button(
        label="Accept Contract", style=discord.ButtonStyle.danger, emoji="🩸"
    )
    async def accept(self, interaction: Interaction, button: discord.ui.Button):
        await self.view._on_accept(interaction)

    @discord.ui.button(
        label="Reject Contract", style=discord.ButtonStyle.secondary, emoji="🖤"
    )
    async def reject(self, interaction: Interaction, button: discord.ui.Button):
        await self.view._on_reject(interaction)


class InfernalContractView(BaseLayoutView):
    """Randomly-generated stat contract presented after killing Uber Lucifer."""

    STAT_LABELS = {"attack": "⚔️ ATK", "defence": "🛡️ DEF", "hp": "❤️ HP"}

    def __init__(self, bot, user_id: str, player, server_id: str, message):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.user_id = user_id
        self.player = player
        self.server_id = server_id
        self.message = message
        self._processing = False  # Re-entry guard (fix 2)
        self.row = InfernalContractRow()

        self.contract = self._roll_contract()

    def set_content(self, embed: discord.Embed) -> None:
        """Renders `embed` (the victory embed + contract offer) as this
        view's Components V2 content, followed by the accept/reject row."""
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(self.row)

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

    async def _on_accept(self, interaction: Interaction):
        # Fix 2: guard against double-click before the first await.
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

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
        return_view = UberReturnView(
            self.bot, self.user_id, self.server_id, self.player
        )
        return_view.set_content(embed)
        await interaction.edit_original_response(view=return_view)
        return_view.message = await interaction.original_response()
        self.stop()

    async def _on_reject(self, interaction: Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="🖤 Contract Rejected",
            description="Lucifer watches you walk away. *He will remember.*",
            color=discord.Color.dark_grey(),
        )
        embed.set_thumbnail(url=BOSS_LUCIFER)
        self.bot.state_manager.clear_active(self.user_id)
        return_view = UberReturnView(
            self.bot, self.user_id, self.server_id, self.player
        )
        return_view.set_content(embed)
        await interaction.edit_original_response(view=return_view)
        return_view.message = await interaction.original_response()
        self.stop()
