import asyncio
import copy
import random

import discord
from discord import ButtonStyle, Interaction

from core.base_view import BaseView
from core.combat.turns import engine
from core.emojis import QUEST_COMPLETE, RUNE_NATURE
from core.images import COMBAT_ELEMENTAL
from core.items.factory import load_player
from core.models import Monster, Player
from core.skills.mastery import (
    get_attunement_rune_bonus,
    get_insight_rune_bonus,
    get_mastery_insight,
)
from core.skills.mechanics import SkillMechanics


class _ElementalCompletionView(BaseView):
    """Shown after the Elemental of Elements fight ends — allows repeat or exit."""

    def __init__(self, bot, user_id: str, server_id: str):
        super().__init__(bot, user_id, server_id)
        self._processing = False

    @discord.ui.button(label="Repeat", style=ButtonStyle.success, emoji="🔄")
    async def repeat(self, interaction: Interaction, button: discord.ui.Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        mastery_row = await self.bot.database.skills.get_mastery(
            self.user_id, self.server_id
        )
        has_keys = all(
            mastery_row.get(k, 0) >= 1
            for k in ("blessed_bismuth", "sparkling_sprig", "capricious_carp")
        )
        if not has_keys:
            self._processing = False
            return await interaction.followup.send(
                "You need 1 Blessed Bismuth, 1 Sparkling Sprig, and 1 Capricious Carp to fight again.",
                ephemeral=True,
            )

        await self.bot.database.skills.consume_elemental_keys(
            self.user_id, self.server_id
        )
        self.bot.state_manager.set_active(self.user_id, "elemental_boss")
        self.stop()

        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        player = await load_player(self.user_id, user_row, self.bot.database)

        new_view = ElementalEncounterView(
            self.bot, player, self.user_id, self.server_id
        )
        await interaction.edit_original_response(
            embed=new_view.build_embed(), view=new_view
        )
        new_view.message = await interaction.original_response()

    @discord.ui.button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
    async def exit(self, interaction: Interaction, button: discord.ui.Button):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.message.delete()


_ELEMENTAL_MONSTER = Monster(
    name="Elemental of Elements",
    level=100,
    hp=99_999,
    max_hp=99_999,
    xp=0,
    attack=1,
    defence=1,
    modifiers=[],
    image="",
    flavor="An ancient convergence of elemental forces.",
    species="Elemental",
    is_boss=True,
)


class ElementalEncounterView(BaseView):
    # Auto-battle loop runs inside a button callback; buttons stay live.
    concurrent_dispatch = True

    MAX_TURNS = 20

    def __init__(self, bot, player: Player, user_id: str, server_id: str):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.player = player
        self.user_id = user_id
        self.server_id = server_id
        self.message = None

        self.monster = copy.copy(_ELEMENTAL_MONSTER)
        self.turn = 0
        self.total_damage = 0
        self.last_log = ""
        self._running = False

        engine.apply_combat_start_passives(self.player, self.monster)
        engine.apply_stat_effects(self.player, self.monster)

    def build_embed(self) -> discord.Embed:
        hp_pct = max(0.0, self.monster.hp / self.monster.max_hp)
        filled = int(hp_pct * 20)
        bar = "█" * filled + "░" * (20 - filled)

        desc = (
            f"`[{bar}]`\n"
            f"**HP:** {self.monster.hp:,} / {self.monster.max_hp:,}\n\n"
            f"**Turn:** {self.turn} / {self.MAX_TURNS}\n"
            f"**Total Damage:** {self.total_damage:,}"
        )
        if self.last_log:
            desc += f"\n\n{self.last_log}"

        embed = discord.Embed(
            title="⚗️ Elemental of Elements",
            description=desc,
            color=0x9B59B6,
        )
        embed.set_image(url=COMBAT_ELEMENTAL)
        return embed

    @discord.ui.button(label="Auto-Battle", style=ButtonStyle.success, emoji="⚔️")
    async def auto_battle(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self._running:
            return
        self._running = True
        button.disabled = True
        message = interaction.message

        while self.turn < self.MAX_TURNS:
            self.turn += 1
            result = engine.process_player_turn(self.player, self.monster)
            self.total_damage += result.damage
            self.monster.hp = (
                self.monster.max_hp
            )  # reset so instakills/overkill can't end the fight early
            self.last_log = result.log
            await message.edit(embed=self.build_embed(), view=self)
            await asyncio.sleep(1.0)

        await self._finalize(message)

    async def _finalize(self, message: discord.Message):
        rewards = await self._calculate_rewards()
        await self._award_rewards(rewards)

        rune_gained = False
        try:
            rune_gained = await self._roll_nature_rune()
        except Exception:
            pass

        quest_msgs = []
        try:
            from core.quests.mechanics import tick_quest_progress

            quest_msgs = await tick_quest_progress(
                self.bot, self.user_id, self.server_id, "elemental_defeat"
            )
        except Exception as e:
            print(f"[Quest tick error in elemental]: {e}")

        embed = self._build_completion_embed(
            rewards, rune_gained=rune_gained, quest_msgs=quest_msgs
        )
        self.clear_items()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        completion_view = _ElementalCompletionView(
            self.bot, self.user_id, self.server_id
        )
        await message.edit(embed=embed, view=completion_view)
        completion_view.message = message

    async def _calculate_rewards(self) -> dict:
        multiplier = self.total_damage // 1000
        if multiplier == 0:
            return {"mining": {}, "woodcutting": {}, "fishing": {}}

        rewards = {}
        for skill_type in ("mining", "woodcutting", "fishing"):
            skill_row = await self.bot.database.skills.get_data(
                self.user_id, self.server_id, skill_type
            )
            tool_tier = SkillMechanics.get_tool_tier(skill_type, skill_row)
            base = SkillMechanics.calculate_yield(skill_type, tool_tier)
            rewards[skill_type] = {k: v * multiplier for k, v in base.items()}

        return rewards

    async def _award_rewards(self, rewards: dict):
        for skill_type, resources in rewards.items():
            if resources:
                await self.bot.database.skills.update_batch(
                    self.user_id, self.server_id, skill_type, resources
                )

    async def _roll_nature_rune(self) -> bool:
        """Roll for a Rune of Nature using base 3% + Nature's Attunement + Insight."""
        mrow = await self.bot.database.skills.get_mastery(self.user_id, self.server_id)
        base_chance = 0.03
        att_bonus = get_attunement_rune_bonus(mrow)
        insight = get_mastery_insight(mrow)
        insight_bonus = get_insight_rune_bonus(insight)
        total_chance = base_chance + att_bonus + insight_bonus

        if random.random() < total_chance:
            await self.bot.database.skills.add_runes_of_nature(self.user_id, 1)
            return True
        return False

    def _build_completion_embed(
        self,
        rewards: dict,
        rune_gained: bool = False,
        quest_msgs: list | None = None,
    ) -> discord.Embed:
        multiplier = self.total_damage // 1000
        embed = discord.Embed(
            title="⚗️ Elemental of Elements — Complete!",
            description=(
                f"**Total Damage Dealt:** {self.total_damage:,}\n"
                f"**Reward Multiplier:** ×{multiplier:,}"
            ),
            color=0x2ECC71,
        )

        if multiplier == 0:
            embed.description += (
                "\n\nNo materials awarded — deal at least 1,000 damage next time!"
            )
            if quest_msgs:
                embed.add_field(
                    name=f"{QUEST_COMPLETE} Quest Progress",
                    value="\n".join(quest_msgs),
                    inline=False,
                )
            return embed

        for skill_type, resources in rewards.items():
            if not resources:
                continue
            info = SkillMechanics.get_skill_info(skill_type)
            lines = [
                f"**{name.replace('_', ' ').title()}:** {amt:,}"
                for name, amt in resources.items()
            ]
            embed.add_field(
                name=f"{info['emoji']} {info['display_name']}",
                value="\n".join(lines),
                inline=True,
            )

        if rune_gained:
            embed.add_field(
                name=f"{RUNE_NATURE}",
                value="**You received a Rune of Nature!**",
                inline=False,
            )

        if quest_msgs:
            embed.add_field(
                name="📋 Quest Progress", value="\n".join(quest_msgs), inline=False
            )

        return embed
