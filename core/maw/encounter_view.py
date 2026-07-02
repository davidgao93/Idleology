"""
core/maw/encounter_view.py — Maw of Infinity 10-turn DPS encounter.

Modelled after ElementalEncounterView. The Maw has 99,999 HP for damage
calculation purposes but never dies — HP is reset to max after each turn so
instakills and overkill cannot end the fight early.

On completion, damage is added to the player's cycle total and the view
transitions back to MawView (lobby) showing the updated contribution.
"""

from __future__ import annotations

import asyncio
import copy
import time

import discord
from discord import ButtonStyle, Interaction

from core.base_view import BaseView
from core.combat.turns import engine
from core.images import MAW_MAIN
from core.maw import mechanics
from core.models import Monster, Player


_MAW_MONSTER = Monster(
    name="The Infinite Maw",
    level=100,
    hp=99_999,
    max_hp=99_999,
    xp=0,
    attack=1,
    defence=1,
    modifiers=[],
    image=MAW_MAIN,
    flavor="tears at the fabric of reality",
    species="Maw",
    is_boss=True,
)


class MawEncounterView(BaseView):
    # Auto-battle loop runs inside a button callback; buttons stay live.
    concurrent_dispatch = True

    MAX_TURNS = mechanics.MAW_TURNS

    def __init__(
        self,
        bot,
        player: Player,
        user_id: str,
        server_id: str,
        cycle_id: int,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.cycle_id = cycle_id
        self.message = None

        self.monster = copy.copy(_MAW_MONSTER)
        self.turn = 0
        self.total_damage = 0
        self.last_log = ""
        self._running = False

        self.weakness = mechanics.get_weekly_weakness()
        self._ward_at_start = (
            player.combat_ward
        )  # track ward baseline for ward_to_damage

        # Apply stat effects first (modifiers reduce player stats), then
        # start passives (weapon/armor round-1 effects). Correct order per
        # the main combat system in cogs/combat.py.
        engine.apply_stat_effects(self.player, self.monster)
        engine.apply_combat_start_passives(self.player, self.monster)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        hp_pct = max(0.0, self.monster.hp / self.monster.max_hp)
        filled = int(hp_pct * 20)
        bar = "█" * filled + "░" * (20 - filled)

        desc = (
            f"`[{bar}]`\n"
            f"**HP:** {self.monster.hp:,} / {self.monster.max_hp:,}\n\n"
            f"**Turn:** {self.turn} / {self.MAX_TURNS}\n"
            f"**Damage This Run:** {self.total_damage:,}"
        )
        if self.last_log:
            desc += f"\n\n{self.last_log}"

        embed = discord.Embed(
            title="🌑 The Infinite Maw",
            description=desc,
            color=0x1A0033,
        )
        embed.set_image(url=MAW_MAIN)

        w = self.weakness
        embed.add_field(
            name=f"{w['emoji']} Weekly Weakness — {w['name']}",
            value=w["description"],
            inline=False,
        )
        return embed

    # ------------------------------------------------------------------
    # Auto-Battle
    # ------------------------------------------------------------------

    @discord.ui.button(label="Auto-Battle", style=ButtonStyle.danger, emoji="⚔️")
    async def auto_battle(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self._running:
            return
        self._running = True
        button.disabled = True
        message = interaction.message

        weakness_key = self.weakness["key"]
        while self.turn < self.MAX_TURNS:
            self.turn += 1
            result = engine.process_player_turn(self.player, self.monster)
            turn_damage = result.damage

            # Apply weekly weakness bonus
            if weakness_key == "hit_damage" and result.is_hit and not result.is_crit:
                turn_damage = int(turn_damage * 1.5)
            elif weakness_key == "crit_damage" and result.is_crit:
                turn_damage = int(turn_damage * 1.5)
            elif weakness_key == "miss_damage" and not result.is_hit:
                # Misses deal 50% of the player's base attack as phantom damage
                turn_damage = int(self.player.get_total_attack() * 0.5)

            self.total_damage += turn_damage
            self.monster.hp = self.monster.max_hp  # Maw never dies
            self.last_log = result.log
            try:
                await message.edit(embed=self.build_embed(), view=self)
            except discord.HTTPException:
                pass
            await asyncio.sleep(1.0)

        # Ward-to-damage: accumulate ward gained during the fight as bonus damage
        if weakness_key == "ward_to_damage":
            ward_generated = max(0, self.player.combat_ward - self._ward_at_start)
            self.total_damage += ward_generated

        await self._finalize(message)

    # ------------------------------------------------------------------
    # Finalize: persist damage, rebuild lobby
    # ------------------------------------------------------------------

    async def _finalize(self, message: discord.Message):
        now_ts = int(time.time())

        # Persist damage and record the fight
        await self.bot.database.maw.add_damage(
            self.user_id, self.cycle_id, self.total_damage, now_ts
        )

        # Fetch updated state for lobby reconstruction
        record = await self.bot.database.maw.get_record(self.user_id, self.cycle_id)
        total_cycle_damage = await self.bot.database.maw.get_cycle_total_damage(
            self.cycle_id
        )
        participant_count = await self.bot.database.maw.count_participants(
            self.cycle_id
        )

        # Check for pending rewards from the previous cycle
        prev_cycle_id = mechanics.get_previous_cycle_id(self.cycle_id)
        pending_record = await self.bot.database.maw.get_record(
            self.user_id, prev_cycle_id
        )
        if pending_record and pending_record["rewards_collected"]:
            pending_record = None

        pending_total = 0
        pending_participants = 0
        if pending_record:
            pending_total = await self.bot.database.maw.get_cycle_total_damage(
                prev_cycle_id
            )
            pending_participants = await self.bot.database.maw.count_participants(
                prev_cycle_id
            )

        self.clear_items()
        self.stop()

        embed = self._build_completion_embed(record, total_cycle_damage)

        from core.maw.views import MawView

        view = MawView(
            bot=self.bot,
            user_id=self.user_id,
            server_id=self.server_id,
            cycle_id=self.cycle_id,
            now_ts=now_ts,
            record=record,
            pending_record=pending_record,
            prev_cycle_id=prev_cycle_id,
            participant_count=participant_count,
            total_cycle_damage=total_cycle_damage,
            pending_total_damage=pending_total,
            pending_participant_count=pending_participants,
        )
        await message.edit(embed=embed, view=view)
        view.message = message

    def _build_completion_embed(
        self, record: dict | None, total_cycle_damage: int
    ) -> discord.Embed:
        cycle_total = record["damage_dealt"] if record else self.total_damage
        pct = mechanics.contribution_pct(cycle_total, total_cycle_damage)
        fights_done = record["fights_this_cycle"] if record else 0
        fights_left = max(0, mechanics.MAX_FIGHTS_PER_CYCLE - fights_done)

        embed = discord.Embed(
            title="🌑 The Infinite Maw — Run Complete",
            description=(
                f"**Damage This Run:** {self.total_damage:,}\n"
                f"**Your Cycle Total:** {cycle_total:,}  ({pct:.1f}% of all damage)\n\n"
                f"**Fights Remaining This Cycle:** {fights_left} / {mechanics.MAX_FIGHTS_PER_CYCLE}"
            ),
            color=0x1A0033,
        )
        embed.set_thumbnail(url=MAW_MAIN)
        return embed
