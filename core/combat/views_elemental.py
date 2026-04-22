import asyncio
import copy

import discord
from discord import ButtonStyle, Interaction

from core.combat import engine
from core.models import Monster, Player
from core.skills.mechanics import SkillMechanics

_ELEMENTAL_MONSTER = Monster(
    name="Elemental of Elements",
    level=100,
    hp=999_999_999,
    max_hp=999_999_999,
    xp=0,
    attack=1,
    defence=1,
    modifiers=[],
    image="",
    flavor="An ancient convergence of elemental forces.",
    species="Elemental",
    is_boss=True,
)


class ElementalEncounterView(discord.ui.View):
    MAX_TURNS = 20

    def __init__(self, bot, player: Player, user_id: str, server_id: str):
        super().__init__(timeout=300)
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

        engine.apply_combat_start_passives(self.player)
        engine.apply_stat_effects(self.player, self.monster)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

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
        embed.set_image(url="https://i.imgur.com/VaiiiND.png")
        return embed

    @discord.ui.button(label="Auto-Battle", style=ButtonStyle.success, emoji="⚔️")
    async def auto_battle(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self._running:
            return
        self._running = True
        button.disabled = True
        message = interaction.message

        while self.turn < self.MAX_TURNS and self.monster.hp > 0:
            self.turn += 1
            result = engine.process_player_turn(self.player, self.monster)
            self.total_damage += result.damage
            self.last_log = result.log
            await message.edit(embed=self.build_embed(), view=self)
            await asyncio.sleep(1.0)

        await self._finalize(message)

    async def _finalize(self, message: discord.Message):
        rewards = await self._calculate_rewards()
        await self._award_rewards(rewards)
        embed = self._build_completion_embed(rewards)
        self.clear_items()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await message.edit(embed=embed, view=None)

    async def _calculate_rewards(self) -> dict:
        multiplier = self.total_damage // 1000
        if multiplier == 0:
            return {"mining": {}, "woodcutting": {}, "fishing": {}}

        rewards = {}
        for skill_type in ("mining", "woodcutting", "fishing"):
            skill_row = await self.bot.database.skills.get_data(
                self.user_id, self.server_id, skill_type
            )
            tool_tier = skill_row[2]
            base = SkillMechanics.calculate_yield(skill_type, tool_tier)
            rewards[skill_type] = {k: v * multiplier for k, v in base.items()}

        return rewards

    async def _award_rewards(self, rewards: dict):
        for skill_type, resources in rewards.items():
            if resources:
                await self.bot.database.skills.update_batch(
                    self.user_id, self.server_id, skill_type, resources
                )

    def _build_completion_embed(self, rewards: dict) -> discord.Embed:
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

        return embed

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            if self.message:
                await self.message.edit(view=None)
        except Exception:
            pass
