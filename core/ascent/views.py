import asyncio
import random

import discord
from discord import ButtonStyle, Interaction, ui

from core.ascent.mechanics import AscentMechanics, PINNACLE_REWARDS
from core.combat import engine
from core.combat import ui as combat_ui
from core.combat.drops import DropManager
from core.combat.gen_mob import generate_ascent_monster
from core.combat.loot import (
    generate_accessory,
    generate_armor,
    generate_boot,
    generate_glove,
    generate_helmet,
    generate_weapon,
)
from core.models import Monster, Player


# ---------------------------------------------------------------------------
# Milestone reward helpers (every 5 floors)
# ---------------------------------------------------------------------------

_EQUIP_SLOTS = ["weapon", "armor", "accessory", "glove", "boot", "helmet"]
_EQUIP_WEIGHTS = [35, 10, 25, 10, 10, 10]
_RUNE_POOL = ["refinement_runes", "potential_runes"]
_KEY_POOL = ["dragon_key", "angel_key", "soul_cores", "balance_fragment"]


async def _grant_milestone_rewards(bot, user_id: str, server_id: str, player: Player, floor: int) -> list[str]:
    """Grants curio + rune cache + equip cache + boss key cache. Returns display strings."""
    log = []

    # Curio
    await bot.database.users.modify_currency(user_id, "curios", 1)
    log.append("🎁 Curio")

    # Rune cache (base Black Market values, no settlement multiplier)
    rune_qty = random.randint(1, 5)
    rune_names = []
    for _ in range(rune_qty):
        rtype = random.choice(_RUNE_POOL)
        await bot.database.users.modify_currency(user_id, rtype, 1)
        rune_names.append("Refinement" if rtype == "refinement_runes" else "Potential")
    log.append(f"💎 Runes ×{rune_qty} ({', '.join(rune_names)})")

    # Equipment cache (1 item, weighted slot)
    slot = random.choices(_EQUIP_SLOTS, weights=_EQUIP_WEIGHTS, k=1)[0]
    generators = {
        "weapon": lambda: generate_weapon(user_id, player.level, False),
        "armor": lambda: generate_armor(user_id, player.level, False),
        "accessory": lambda: generate_accessory(user_id, player.level, False),
        "glove": lambda: generate_glove(user_id, player.level),
        "boot": lambda: generate_boot(user_id, player.level),
        "helmet": lambda: generate_helmet(user_id, player.level),
    }
    item = await generators[slot]()
    if item:
        creators = {
            "weapon": bot.database.equipment.create_weapon,
            "armor": bot.database.equipment.create_armor,
            "accessory": bot.database.equipment.create_accessory,
            "glove": bot.database.equipment.create_glove,
            "boot": bot.database.equipment.create_boot,
            "helmet": bot.database.equipment.create_helmet,
        }
        await creators[slot](item)
        log.append(f"⚔️ {item.name}")

    # Boss key cache
    key_qty = random.randint(1, 5)
    key_names = []
    for _ in range(key_qty):
        ktype = random.choice(_KEY_POOL)
        await bot.database.users.modify_currency(user_id, ktype, 1)
        key_names.append(ktype.replace("_", " ").title())
    log.append(f"🗝️ Keys ×{key_qty} ({', '.join(key_names)})")

    return log


# ---------------------------------------------------------------------------
# AscentView
# ---------------------------------------------------------------------------


class AscentView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        initial_monster: Monster,
        start_logs: dict,
        starting_floor: int,
        best_floor: int,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.monster = initial_monster
        self.logs = start_logs or {}

        self.current_floor = starting_floor
        self.best_floor = best_floor

        # Rewards accumulated this session for the summary embed
        self.milestone_log: list[str] = []
        self.pinnacle_log: list[str] = []

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        if self.player.current_hp > 0:
            await self._end_run(self.message if hasattr(self, "message") else None, retreated=True)
        else:
            self.bot.state_manager.clear_active(self.user_id)

    def _floor_title(self) -> str:
        return f"Ascent Floor {self.current_floor} | {self.player.name}"

    async def _refresh(self, interaction: Interaction = None, message: discord.Message = None):
        embed = combat_ui.create_combat_embed(
            self.player, self.monster, self.logs, title_override=self._floor_title()
        )
        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        elif message:
            await message.edit(embed=embed, view=self)
        elif interaction:
            await interaction.edit_original_response(embed=embed, view=self)

    # --- Buttons ---

    @ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️")
    async def attack(self, interaction: Interaction, button: ui.Button):
        p_log = engine.process_player_turn(self.player, self.monster)
        self.logs = {self.player.name: p_log}
        if self.monster.hp > 0:
            self.logs[self.monster.name] = engine.process_monster_turn(self.player, self.monster)
        await self._check_state(interaction)

    @ui.button(label="Heal", style=ButtonStyle.success, emoji="🩹")
    async def heal(self, interaction: Interaction, button: ui.Button):
        self.logs = {"Heal": engine.process_heal(self.player, self.monster)}
        if self.monster.hp > 0:
            self.logs[self.monster.name] = engine.process_monster_turn(self.player, self.monster)
        await self._check_state(interaction)

    @ui.button(label="Auto Floor", style=ButtonStyle.primary, emoji="⏩")
    async def auto(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        message = interaction.message

        while self.player.current_hp > (self.player.total_max_hp * 0.2) and self.monster.hp > 0:
            for _ in range(10):
                if self.player.current_hp <= (self.player.total_max_hp * 0.2) or self.monster.hp <= 0:
                    break
                p_log = engine.process_player_turn(self.player, self.monster)
                m_log = engine.process_monster_turn(self.player, self.monster) if self.monster.hp > 0 else ""
                self.logs = {self.player.name: p_log, self.monster.name: m_log}

            if self.monster.hp > 0 and self.player.current_hp > (self.player.total_max_hp * 0.2):
                await self._refresh(message=message)
                await asyncio.sleep(1.0)
            else:
                break

        if 0 < self.player.current_hp <= (self.player.total_max_hp * 0.2) and self.monster.hp > 0:
            self.logs["Auto-Battle"] = "Paused: Low HP protection!"
            await self._refresh(message=message)
        else:
            await self._check_state(interaction, message)

    @ui.button(label="Retreat", style=ButtonStyle.secondary, emoji="🏃")
    async def retreat(self, interaction: Interaction, button: ui.Button):
        await self._end_run(interaction, retreated=True)

    # --- Logic ---

    async def _check_state(self, interaction: Interaction = None, message: discord.Message = None):
        if self.player.current_hp <= 0:
            await self._handle_defeat(interaction, message)
        elif self.monster.hp <= 0:
            await self._handle_floor_clear(interaction, message)
        else:
            await self._refresh(interaction, message)

    async def _handle_floor_clear(self, interaction: Interaction, message: discord.Message):
        floor = self.current_floor

        # Update best floor
        if floor > self.best_floor:
            self.best_floor = floor
            await self.bot.database.ascension.update_highest_floor(self.user_id, floor)

        # Milestone rewards (every 5 floors)
        if floor % 5 == 0:
            rewards = await _grant_milestone_rewards(
                self.bot, self.user_id, self.server_id, self.player, floor
            )
            self.milestone_log.append(f"**Floor {floor}:** " + " | ".join(rewards))

        # Pinnacle unlock
        pinnacle_gained = None
        if floor in PINNACLE_REWARDS and floor not in self.player.ascension_unlocks:
            await self.bot.database.ascension.unlock_floor(self.user_id, floor)
            self.player.ascension_unlocks.add(floor)
            self.player.compute_flat_stats()  # refresh flat cache so new bonuses apply immediately
            label = AscentMechanics.pinnacle_label(floor)
            self.pinnacle_log.append(f"**Floor {floor}:** {label}")
            pinnacle_gained = label

        # Skiller boot passive
        skiller_msg = await DropManager.proc_skiller(
            self.bot, self.user_id, self.server_id, self.player
        )

        # Build clear embed
        embed = discord.Embed(
            title=f"Floor {floor} Cleared!",
            color=discord.Color.green(),
        )
        lines = []
        if floor % 5 == 0 and self.milestone_log:
            lines.append(f"📦 Milestone rewards granted!")
        if pinnacle_gained:
            lines.append(f"✨ **Pinnacle Unlock:** {pinnacle_gained}")
        if skiller_msg:
            lines.append(skiller_msg)
        embed.description = "\n".join(lines) if lines else "Onwards..."
        embed.set_footer(text=f"HP: {self.player.current_hp}/{self.player.total_max_hp} | Next floor in 3s...")

        target = (
            interaction.edit_original_response
            if interaction and interaction.response.is_done()
            else (interaction.response.edit_message if interaction else message.edit)
        )
        await target(embed=embed, view=None)

        await asyncio.sleep(3)
        await self._next_floor(interaction, message)

    async def _next_floor(self, interaction, message):
        self.current_floor += 1
        self.player.reset_combat_bonus()
        self.player.combat_ward = self.player.get_combat_ward_value()
        self.player.is_invulnerable_this_combat = False

        m_level = AscentMechanics.calculate_floor_monster_level(self.current_floor)
        n_mods, b_mods = AscentMechanics.get_floor_modifier_counts(self.current_floor)

        next_monster = Monster(
            name="", level=0, hp=0, max_hp=0, xp=0,
            attack=0, defence=0, modifiers=[], image="", flavor="", is_boss=True,
        )
        next_monster = await generate_ascent_monster(self.player, next_monster, m_level, n_mods, b_mods)
        self.monster = next_monster

        engine.apply_stat_effects(self.player, self.monster)
        self.logs = engine.apply_combat_start_passives(self.player, self.monster)

        msg_obj = message if message else (await interaction.original_response())
        embed = combat_ui.create_combat_embed(
            self.player, self.monster, self.logs,
            title_override=self._floor_title(),
        )
        await msg_obj.edit(embed=embed, view=self)

    async def _handle_defeat(self, interaction, message):
        self.player.current_hp = 1
        embed = combat_ui.create_defeat_embed(self.player, self.monster, 0)
        embed.title = f"Defeated on Floor {self.current_floor}"
        embed.description = (embed.description or "") + f"\nBest floor this session: **{self.best_floor}**"

        target = (
            interaction.response.edit_message
            if interaction and not interaction.response.is_done()
            else (interaction.edit_original_response if interaction else message.edit)
        )
        await target(embed=embed, view=None)

        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        self.stop()

    async def _end_run(self, interaction_or_msg, retreated: bool = True):
        embed = discord.Embed(
            title="Ascent Complete" if not retreated else "Ascent Ended",
            color=discord.Color.blurple() if not retreated else discord.Color.light_grey(),
        )
        embed.add_field(name="Best Floor", value=str(self.best_floor), inline=True)
        embed.add_field(name="Floors Cleared", value=str(self.current_floor - 1), inline=True)

        if self.milestone_log:
            embed.add_field(
                name="📦 Milestone Rewards",
                value="\n".join(self.milestone_log[-5:]),  # cap to avoid embed overflow
                inline=False,
            )
        if self.pinnacle_log:
            embed.add_field(
                name="✨ Pinnacle Unlocks",
                value="\n".join(self.pinnacle_log),
                inline=False,
            )

        if isinstance(interaction_or_msg, Interaction):
            if not interaction_or_msg.response.is_done():
                await interaction_or_msg.response.edit_message(embed=embed, view=None)
            else:
                await interaction_or_msg.edit_original_response(embed=embed, view=None)
        elif interaction_or_msg:
            await interaction_or_msg.edit(embed=embed, view=None)

        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        self.stop()
