import asyncio
import random

import discord
from discord import ButtonStyle, Interaction, ui

from core.ascent.mechanics import PINNACLE_REWARDS, AscentMechanics
from core.base_layout_view import BaseLayoutView
from core.combat import jewel_engine as _je
from core.combat import ui as combat_ui
from core.combat.combat_log import CombatLogger
from core.combat.economy.drops import DropManager
from core.combat.economy.loot import (
    generate_accessory,
    generate_armor,
    generate_boot,
    generate_glove,
    generate_helmet,
    generate_weapon,
)
from core.hall_of_firsts import triggers as hof_triggers
from core.combat.mobgen.gen_mob import generate_ascent_monster
from core.combat.turns import engine
from core.images import VALE_PORTRAIT, VALE_THUMBNAIL
from core.npc_voices import get_quip
from core.models import Monster, Player

# ---------------------------------------------------------------------------
# Milestone reward helpers (every 5 floors)
# ---------------------------------------------------------------------------

_EQUIP_SLOTS = ["weapon", "armor", "accessory", "glove", "boot", "helmet"]
_EQUIP_WEIGHTS = [35, 10, 25, 10, 10, 10]
_RUNE_POOL = ["refinement_runes", "potential_runes"]
_KEY_POOL = ["dragon_key", "angel_key", "soul_cores", "balance_fragment"]


async def _grant_milestone_rewards(
    bot, user_id: str, server_id: str, player: Player, floor: int
) -> list[str]:
    """Grants 1 curio + randomly one of: rune cache, equip cache, or boss key cache."""
    log = []

    # Curio
    await bot.database.users.modify_currency(user_id, "curios", 1)
    log.append("🎁 Curio")

    cache_choice = random.choice(["runes", "equipment", "keys"])

    if cache_choice == "runes":
        rune_qty = random.randint(1, 5)
        rune_names = []
        for _ in range(rune_qty):
            rtype = random.choice(_RUNE_POOL)
            await bot.database.users.modify_currency(user_id, rtype, 1)
            rune_names.append(
                "Refinement" if rtype == "refinement_runes" else "Potential"
            )
        log.append(f"💎 Runes ×{rune_qty} ({', '.join(rune_names)})")

    elif cache_choice == "equipment":
        slot = random.choices(_EQUIP_SLOTS, weights=_EQUIP_WEIGHTS, k=1)[0]
        generators = {
            "weapon": lambda: generate_weapon(user_id, player.level),
            "armor": lambda: generate_armor(user_id, player.level),
            "accessory": lambda: generate_accessory(user_id, player.level),
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

    else:
        key_qty = random.randint(1, 5)
        key_names = []
        for _ in range(key_qty):
            ktype = random.choice(_KEY_POOL)
            await bot.database.users.modify_currency(user_id, ktype, 1)
            key_names.append(ktype.replace("_", " ").title())
        log.append(f"🗝️ Keys ×{key_qty} ({', '.join(key_names)})")

    return log


# ---------------------------------------------------------------------------
# AscentLobbyView
# ---------------------------------------------------------------------------


class AscentLobbyRow(discord.ui.ActionRow["AscentLobbyView"]):
    @discord.ui.button(label="Begin Run", style=ButtonStyle.danger, emoji="🏔️")
    async def begin_run_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_begin_run(interaction)

    @discord.ui.button(label="Pinnacles", style=ButtonStyle.primary, emoji="✨")
    async def pinnacles_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_view_pinnacles(interaction)

    @discord.ui.button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
    async def close_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_close(interaction)


class AscentLobbyView(BaseLayoutView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        best_floor: int,
        pinnacle_keys: int,
        player_avatar_url: str | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.best_floor = best_floor
        self.pinnacle_keys = pinnacle_keys
        self.player_avatar_url = player_avatar_url
        self._processing = False
        self.row = AscentLobbyRow()
        self._sync_items()

    def _sync_items(self):
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(self.build_embed()))
        self.add_item(self.row)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏔️ The Ascent",
            description=(
                f"*{get_quip('ascent')}*\n\n"
                "Climb an endless tower of escalating floors, each guarded by a fearsome boss.\n"
                "Reach new pinnacle floors to earn permanent stat bonuses."
            ),
            color=discord.Color.from_rgb(180, 120, 60),
        )
        embed.set_author(name="Vale", icon_url=VALE_PORTRAIT)
        embed.set_thumbnail(url=VALE_THUMBNAIL)
        # Floor info
        starting_floor = AscentMechanics.calculate_starting_floor(self.best_floor)
        embed.add_field(
            name="Best Floor",
            value=str(self.best_floor) if self.best_floor > 0 else "None",
            inline=True,
        )
        embed.add_field(name="Starting Floor", value=str(starting_floor), inline=True)
        embed.add_field(
            name="Pinnacle Keys", value=f"🗝️ {self.pinnacle_keys}", inline=True
        )

        # Cumulative bonuses
        bonuses = AscentMechanics.get_cumulative_pinnacle_bonuses(
            self.player.ascension_unlocks
        )
        bonus_parts = []
        if bonuses["atk_pct"]:
            bonus_parts.append(f"+{bonuses['atk_pct']}% ATK")
        if bonuses["def_pct"]:
            bonus_parts.append(f"+{bonuses['def_pct']}% DEF")
        if bonuses["crit"]:
            bonus_parts.append(f"+{bonuses['crit']} Crit")
        if bonuses["hit"]:
            bonus_parts.append(f"+{bonuses['hit']} Hit")
        if bonuses["pdr"]:
            bonus_parts.append(f"+{bonuses['pdr']} PDR")
        if bonuses["fdr"]:
            bonus_parts.append(f"+{bonuses['fdr']} FDR")
        if bonuses["hp"]:
            bonus_parts.append(f"+{bonuses['hp']} Max HP")

        embed.add_field(
            name="Active Pinnacle Bonuses",
            value=", ".join(bonus_parts) if bonus_parts else "None yet",
            inline=False,
        )

        # Next pinnacle floor
        unlocked = self.player.ascension_unlocks
        next_pinnacle = next(
            (f for f in sorted(PINNACLE_REWARDS) if f not in unlocked), None
        )
        if next_pinnacle:
            embed.add_field(
                name="Next Pinnacle",
                value=f"Floor {next_pinnacle} — {AscentMechanics.pinnacle_label(next_pinnacle)}",
                inline=False,
            )
        else:
            embed.add_field(
                name="Next Pinnacle", value="All pinnacles unlocked!", inline=False
            )

        embed.set_footer(text="A Pinnacle Key is consumed when you begin a run.")
        return embed

    async def _on_begin_run(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        current_keys = await self.bot.database.users.get_currency(
            self.user_id, "pinnacle_key"
        )
        if current_keys < 1:
            self._processing = False
            return await interaction.response.send_message(
                "You need a **Pinnacle Key** to begin the Ascent.", ephemeral=True
            )

        await interaction.response.defer()

        await self.bot.database.users.modify_currency(self.user_id, "pinnacle_key", -1)
        self.bot.state_manager.set_active(self.user_id, "ascent")

        _je.reset_jewel_charges(self.player)

        starting_floor = AscentMechanics.calculate_starting_floor(self.best_floor)
        m_level = AscentMechanics.calculate_floor_monster_level(starting_floor)
        n_mods, b_mods = AscentMechanics.get_floor_modifier_counts(starting_floor)

        monster = Monster(
            name="",
            level=0,
            hp=0,
            max_hp=0,
            xp=0,
            attack=0,
            defence=0,
            modifiers=[],
            image="",
            flavor="",
            is_boss=True,
        )
        monster = await generate_ascent_monster(
            self.player, monster, m_level, n_mods, b_mods
        )

        self.player.combat_ward = self.player.get_combat_ward_value()
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        view = AscentView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            monster,
            start_logs,
            starting_floor=starting_floor,
            best_floor=self.best_floor,
            player_avatar_url=self.player_avatar_url,
        )
        self.stop()
        msg = await interaction.edit_original_response(view=view)
        view.message = msg

    async def _on_view_pinnacles(self, interaction: Interaction):
        unlocked = self.player.ascension_unlocks
        lines = []
        for floor, _ in sorted(PINNACLE_REWARDS.items()):
            status = "✅" if floor in unlocked else "⬜"
            lines.append(
                f"{status} **Floor {floor}** — {AscentMechanics.pinnacle_label(floor)}"
            )

        pages = []
        chunk_size = 8
        for i in range(0, len(lines), chunk_size):
            pages.append("\n".join(lines[i : i + chunk_size]))

        view = AscentPinnacleListView(self, pages)
        await interaction.response.edit_message(view=view)

    async def _on_close(self, interaction: Interaction):
        # session-terminating Close for ascent lobby
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()


class AscentPinnacleRow(discord.ui.ActionRow["AscentPinnacleListView"]):
    @discord.ui.button(label="◀", style=ButtonStyle.secondary)
    async def prev_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_prev(interaction)

    @discord.ui.button(label="▶", style=ButtonStyle.secondary)
    async def next_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_next(interaction)

    @discord.ui.button(label="Back", style=ButtonStyle.secondary)
    async def back_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_back(interaction)


class AscentPinnacleListView(BaseLayoutView):
    def __init__(self, lobby_view: "AscentLobbyView", pages: list[str]):
        super().__init__(lobby_view.bot, parent=lobby_view)
        self.lobby_view = lobby_view
        self.pages = pages
        self.page = 0
        self.row = AscentPinnacleRow()
        self._sync_items()

    def _update_buttons(self):
        self.row.prev_btn.disabled = self.page == 0
        self.row.next_btn.disabled = self.page >= len(self.pages) - 1

    def _sync_items(self):
        self._update_buttons()
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(self.build_embed()))
        self.add_item(self.row)

    def build_embed(self) -> discord.Embed:
        unlocked_count = len(self.lobby_view.player.ascension_unlocks)
        total = len(PINNACLE_REWARDS)
        embed = discord.Embed(
            title="✨ Pinnacle Floors",
            description=(
                self.pages[self.page] if self.pages else "No pinnacle floors defined."
            ),
            color=discord.Color.from_rgb(180, 120, 60),
        )
        embed.set_footer(
            text=f"Unlocked: {unlocked_count}/{total} | Page {self.page + 1}/{len(self.pages)}"
        )
        return embed

    async def _on_prev(self, interaction: Interaction):
        self.page -= 1
        self._sync_items()
        await interaction.response.edit_message(view=self)

    async def _on_next(self, interaction: Interaction):
        self.page += 1
        self._sync_items()
        await interaction.response.edit_message(view=self)

    async def _on_back(self, interaction: Interaction):
        self.stop()
        self.lobby_view._sync_items()
        await interaction.response.edit_message(view=self.lobby_view)


# ---------------------------------------------------------------------------
# AscentView
# ---------------------------------------------------------------------------


class AscentCombatRow(discord.ui.ActionRow["AscentView"]):
    @discord.ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️")
    async def attack_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_attack(interaction)

    @discord.ui.button(label="Heal", style=ButtonStyle.success, emoji="🩹")
    async def heal_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_heal(interaction)

    @discord.ui.button(label="Auto", style=ButtonStyle.primary, emoji="⏩")
    async def auto_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_auto(interaction)

    @discord.ui.button(
        label="Full Send", style=ButtonStyle.danger, emoji="💀", disabled=True
    )
    async def full_send_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_full_send(interaction)

    @discord.ui.button(label="Retreat", style=ButtonStyle.secondary, emoji="🏃")
    async def retreat_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_retreat(interaction)


class AscentView(BaseLayoutView):
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
        player_avatar_url: str | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.monster = initial_monster
        self.logs = start_logs or {}
        self.player_avatar_url = player_avatar_url

        self.current_floor = starting_floor
        self.best_floor = best_floor

        # Rewards accumulated this session for the summary embed
        self.milestone_log: list[str] = []
        self.pinnacle_log: list[str] = []

        self.combat_logger = CombatLogger(player, initial_monster)
        self.combat_logger.log_combat_start(player, initial_monster)

        self.row = AscentCombatRow()
        self._update_heal_btn()
        self._update_full_send_state()
        self._sync_items(self._combat_layout())

    async def on_timeout(self):
        if self.player.current_hp > 0:
            await self._end_run(
                self.message if hasattr(self, "message") else None, retreated=True
            )
        else:
            self.bot.state_manager.clear_active(self.user_id)

    def _floor_title(self) -> str:
        return f"Ascent Floor {self.current_floor} | {self.player.name}"

    def _update_heal_btn(self):
        self.row.heal_btn.label = f"Heal ({self.player.potions}/20)"
        self.row.heal_btn.disabled = self.player.potions <= 0

    def _update_full_send_state(self):
        """Full Send unlocks once HP is at/below Auto's low-HP protection threshold (20%)."""
        self.row.full_send_btn.disabled = not (
            0 < self.player.current_hp <= self.player.total_max_hp * 0.2
        )

    def _update_buttons(self):
        """Re-enables every combat button, then re-applies Heal's potion-gated
        lock and Full Send's HP-gated lock. Called after any state change that
        might have left buttons disabled mid-loop (Auto/Full Send) or stale
        from a previous floor."""
        for child in self.row.children:
            child.disabled = False
        self._update_heal_btn()
        self._update_full_send_state()

    def _combat_layout(self) -> discord.ui.Container:
        return combat_ui.create_combat_layout(
            self.player,
            self.monster,
            self.logs,
            title_override=self._floor_title(),
            player_avatar_url=self.player_avatar_url,
        )

    def _sync_items(self, container=None, *, interactive: bool = True):
        container = container if container is not None else self._combat_layout()
        self.clear_items()
        self.add_item(container)
        if interactive:
            self.add_item(self.row)

    async def _refresh(
        self,
        interaction: Interaction = None,
        message: discord.Message = None,
        *,
        update_heal: bool = True,
    ):
        if update_heal:
            self._update_heal_btn()
        self._sync_items(self._combat_layout())
        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(view=self)
        elif message:
            await message.edit(view=self)
        elif interaction:
            await interaction.edit_original_response(view=self)

    # --- Buttons ---

    async def _on_attack(self, interaction: Interaction):
        p_log = engine.process_player_turn(self.player, self.monster)
        self.combat_logger.log_player_turn(p_log, self.monster)
        self.logs = {self.player.name: p_log}
        if self.monster.hp > 0:
            m_log = engine.process_monster_turn(self.player, self.monster)
            self.combat_logger.log_monster_turn(m_log, self.player)
            self.logs[self.monster.name] = m_log
        await self._check_state(interaction)

    async def _on_heal(self, interaction: Interaction):
        self.logs = {"Heal": engine.process_heal(self.player, self.monster)}
        if self.monster.hp > 0:
            m_log = engine.process_monster_turn(self.player, self.monster)
            self.combat_logger.log_monster_turn(m_log, self.player)
            self.logs[self.monster.name] = m_log
        await self._check_state(interaction)

    async def _on_auto(self, interaction: Interaction):
        await interaction.response.defer()
        message = interaction.message

        # Disable all buttons for the duration of the auto loop
        for child in self.row.children:
            child.disabled = True
        await message.edit(view=self)

        while (
            self.player.current_hp > (self.player.total_max_hp * 0.2)
            and self.monster.hp > 0
        ):
            for _ in range(10):
                if (
                    self.player.current_hp <= (self.player.total_max_hp * 0.2)
                    or self.monster.hp <= 0
                ):
                    break
                p_log = engine.process_player_turn(self.player, self.monster)
                self.combat_logger.log_player_turn(p_log, self.monster)
                m_log = (
                    engine.process_monster_turn(self.player, self.monster)
                    if self.monster.hp > 0
                    else ""
                )
                if m_log:
                    self.combat_logger.log_monster_turn(m_log, self.player)
                self.logs = {self.player.name: p_log, self.monster.name: m_log}

            if self.monster.hp > 0 and self.player.current_hp > (
                self.player.total_max_hp * 0.2
            ):
                await self._refresh(message=message, update_heal=False)
                await asyncio.sleep(1.0)
            else:
                break

        if (
            0 < self.player.current_hp <= (self.player.total_max_hp * 0.2)
            and self.monster.hp > 0
        ):
            # Low HP pause — re-enable buttons so the player can act
            self._update_buttons()
            self.logs["Auto-Battle"] = "🛑 Paused: Low HP protection!"
            await self._refresh(message=message)
            await message.channel.send(
                f"<@{self.user_id}> ⚠️ Low HP Protection triggered — auto paused! "
                "**Full Send** is now available if you want to gamble on finishing the fight.",
                delete_after=15,
            )
        else:
            await self._check_state(interaction, message)

    async def _on_full_send(self, interaction: Interaction):
        """Unlocked at low HP (same threshold Auto warns on). Repeats attacks with
        no HP floor until the monster is defeated or the player dies."""
        await interaction.response.defer()
        message = interaction.message

        for child in self.row.children:
            child.disabled = True
        await message.edit(view=self)

        while self.player.current_hp > 0 and self.monster.hp > 0:
            for _ in range(10):
                if self.player.current_hp <= 0 or self.monster.hp <= 0:
                    break
                p_log = engine.process_player_turn(self.player, self.monster)
                self.combat_logger.log_player_turn(p_log, self.monster)
                m_log = (
                    engine.process_monster_turn(self.player, self.monster)
                    if self.monster.hp > 0
                    else ""
                )
                if m_log:
                    self.combat_logger.log_monster_turn(m_log, self.player)
                self.logs = {self.player.name: p_log, self.monster.name: m_log}

            if self.player.current_hp > 0 and self.monster.hp > 0:
                await self._refresh(message=message, update_heal=False)
                await asyncio.sleep(1.0)

        await self._check_state(message=message)

    async def _on_retreat(self, interaction: Interaction):
        await self._end_run(interaction, retreated=True)

    # --- Logic ---

    async def _check_state(
        self, interaction: Interaction = None, message: discord.Message = None
    ):
        if self.player.current_hp <= 0:
            await self._handle_defeat(interaction, message)
        elif self.monster.hp <= 0:
            await self._handle_floor_clear(interaction, message)
        else:
            self._update_full_send_state()
            await self._refresh(interaction, message)

    async def _handle_floor_clear(
        self, interaction: Interaction, message: discord.Message
    ):
        self.combat_logger.log_combat_end(self.player, self.monster, "victory")
        floor = self.current_floor

        # Update best floor
        if floor > self.best_floor:
            self.best_floor = floor
            await self.bot.database.ascension.update_highest_floor(self.user_id, floor)
            await hof_triggers.check_peak(self.bot, self.user_id, floor)

        # Milestone rewards (every 5 floors)
        milestone_rewards = None
        if floor % 5 == 0:
            milestone_rewards = await _grant_milestone_rewards(
                self.bot, self.user_id, self.server_id, self.player, floor
            )
            self.milestone_log.append(
                f"**Floor {floor}:\n** " + "\n".join(milestone_rewards)
            )

        # Pinnacle unlock
        pinnacle_gained = None
        if floor in PINNACLE_REWARDS and floor not in self.player.ascension_unlocks:
            await self.bot.database.ascension.unlock_floor(self.user_id, floor)
            self.player.ascension_unlocks.add(floor)
            self.player.compute_flat_stats()  # refresh flat cache so new bonuses apply immediately
            label = AscentMechanics.pinnacle_label(floor)
            self.pinnacle_log.append(f"**Floor {floor}:** {label}")
            pinnacle_gained = label

        from core.combat.turns.boundary import fire_on_victory_effects

        fire_on_victory_effects(self.player)

        # Skiller boot passive
        skiller_msg = await DropManager.proc_skiller(
            self.bot, self.user_id, self.server_id, self.player
        )

        quest_msgs = []
        try:
            from core.quests.mechanics import tick_quest_progress

            quest_msgs = await tick_quest_progress(
                self.bot, self.user_id, self.server_id, "ascent_floor"
            )
        except Exception as e:
            print(f"[Quest tick error in ascent]: {e}")

        # Build clear embed
        embed = discord.Embed(
            title=f"Floor {floor} Cleared!",
            color=discord.Color.green(),
        )
        lines = []
        if milestone_rewards:
            lines.append("📦 **Milestone Rewards:**\n" + "\n".join(milestone_rewards))
        if pinnacle_gained:
            lines.append(f"✨ **Pinnacle Unlock:** {pinnacle_gained}")
        if skiller_msg:
            lines.append(skiller_msg)
        lines.extend(quest_msgs)
        embed.description = "\n".join(lines) if lines else "Onwards..."
        embed.set_footer(
            text=f"HP: {self.player.current_hp}/{self.player.total_max_hp} | Next floor in 3s..."
        )

        self._sync_items(combat_ui.embed_to_container(embed), interactive=False)
        target = (
            interaction.edit_original_response
            if interaction and interaction.response.is_done()
            else (interaction.response.edit_message if interaction else message.edit)
        )
        await target(view=self)

        await asyncio.sleep(3)
        await self._next_floor(interaction, message)

    async def _next_floor(self, interaction, message):
        from core.combat.turns.boundary import reset_combat_transients

        self.current_floor += 1
        self.player.reset_combat_bonus()
        self.player.combat_ward = self.player.get_combat_ward_value()
        reset_combat_transients(self.player)

        m_level = AscentMechanics.calculate_floor_monster_level(self.current_floor)
        n_mods, b_mods = AscentMechanics.get_floor_modifier_counts(self.current_floor)

        next_monster = Monster(
            name="",
            level=0,
            hp=0,
            max_hp=0,
            xp=0,
            attack=0,
            defence=0,
            modifiers=[],
            image="",
            flavor="",
            is_boss=True,
        )
        next_monster = await generate_ascent_monster(
            self.player, next_monster, m_level, n_mods, b_mods
        )
        self.monster = next_monster

        engine.apply_stat_effects(self.player, self.monster)
        self.logs = engine.apply_combat_start_passives(self.player, self.monster)

        self.combat_logger = CombatLogger(self.player, self.monster)
        self.combat_logger.log_combat_start(self.player, self.monster)

        self._update_buttons()
        self._sync_items(self._combat_layout())

        msg_obj = message if message else (await interaction.original_response())
        await msg_obj.edit(view=self)

    async def _handle_defeat(self, interaction, message):
        self.combat_logger.log_combat_end(self.player, self.monster, "defeat")
        self.player.current_hp = 1
        embed = combat_ui.create_defeat_embed(
            self.player,
            self.monster,
            0,
            title=f"Defeated on Floor {self.current_floor}",
            description_extra=f"\nBest floor this session: **{self.best_floor}**",
        )

        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        self.stop()

        lobby_view = AscentRunCompleteView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            embed,
            player_avatar_url=self.player_avatar_url,
        )
        target = (
            interaction.response.edit_message
            if interaction and not interaction.response.is_done()
            else (interaction.edit_original_response if interaction else message.edit)
        )
        await target(view=lobby_view)

    async def _end_run(self, interaction_or_msg, retreated: bool = True):
        embed = discord.Embed(
            title="Ascent Complete" if not retreated else "Ascent Ended",
            color=(
                discord.Color.blurple() if not retreated else discord.Color.light_grey()
            ),
        )
        embed.add_field(name="Best Floor", value=str(self.best_floor), inline=True)
        embed.add_field(
            name="Floors Cleared", value=str(self.current_floor - 1), inline=True
        )

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

        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        self.stop()

        lobby_view = AscentRunCompleteView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            embed,
            player_avatar_url=self.player_avatar_url,
        )
        if isinstance(interaction_or_msg, Interaction):
            if not interaction_or_msg.response.is_done():
                await interaction_or_msg.response.edit_message(view=lobby_view)
            else:
                await interaction_or_msg.edit_original_response(view=lobby_view)
        elif interaction_or_msg:
            await interaction_or_msg.edit(view=lobby_view)


class AscentLobbyReturnRow(discord.ui.ActionRow["AscentRunCompleteView"]):
    @discord.ui.button(label="Back to Lobby", style=ButtonStyle.primary, emoji="🏔️")
    async def back_to_lobby_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_back_to_lobby(interaction)


class AscentRunCompleteView(BaseLayoutView):
    """Shown after an Ascent run ends (defeat or retreat) — lets the player
    jump back to the lobby on the same message."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        header_embed: discord.Embed,
        player_avatar_url: str | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.player_avatar_url = player_avatar_url
        self._processing = False
        self.row = AscentLobbyReturnRow()
        self.add_item(combat_ui.embed_to_container(header_embed))
        self.add_item(self.row)

    async def _on_back_to_lobby(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        self.bot.state_manager.set_active(self.user_id, "ascent")
        pinnacle_keys = await self.bot.database.users.get_currency(
            self.user_id, "pinnacle_key"
        )
        best_floor = await self.bot.database.ascension.get_highest_floor(self.user_id)

        lobby = AscentLobbyView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            best_floor,
            pinnacle_keys,
            player_avatar_url=self.player_avatar_url,
        )
        self.stop()
        await interaction.edit_original_response(view=lobby)
