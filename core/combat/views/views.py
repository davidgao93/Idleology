"""Main CombatView and post-combat / phase / auto-battle orchestration.

Extends BaseLayoutView (Components V2). Delegates embeds to core.combat.ui,
victory rewards to economy.victory, and turn processing to
core.combat.turns.engine + player_turn/monster_turn.
"""

import asyncio
import random
from datetime import datetime, timedelta

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import jewel_engine as _je
from core.combat import ui as combat_ui
from core.combat.combat_log import CombatLogger
from core.combat.economy import uber_rewards
from core.combat.economy.config import (
    NEET_VOID_KEY_CHANCE,
    XP_LOSS_ON_DEFEAT,
)
from core.combat.economy.experience import ExperienceManager
from core.combat.economy.victory import apply_victory_rewards
from core.combat.mobgen.gen_mob import generate_boss
from core.combat.turns import engine
from core.combat.turns.boundary import (
    fire_on_victory_effects,
    reset_for_phase_transition,
)
from core.combat.views.views_lucifer import LuciferChoiceView
from core.combat.views.views_prestige_boss import PrestigeBossHarvestView
from core.emojis import WIN_STREAK
from core.images import (
    VICTORY_APHRODITE_GEMINI,
    VICTORY_LUCIFER,
    VICTORY_NEET,
)
from core.models import Monster, Player
from core.tavern.mechanics import TavernMechanics

# ---------------------------------------------------------------------------
# Boss-specific victory embed configuration
# Drives thumbnail and extra field injection for named boss encounters.
# NEET and Lucifer still need procedural handling (DB writes / view swap),
# but their embed appearance is fully determined by this table.
# ---------------------------------------------------------------------------
_BOSS_VICTORY_CFG: dict[str, dict] = {
    "Aphrodite": {"thumbnail_url": VICTORY_APHRODITE_GEMINI},
    "Gemini": {"thumbnail_url": VICTORY_APHRODITE_GEMINI},
    "NEET": {"thumbnail_url": VICTORY_NEET},
    "Lucifer": {
        "thumbnail_url": VICTORY_LUCIFER,
        "extra_fields": [
            {
                "name": "❤️‍🔥 A Soul Core manifests...",
                "value": (
                    "**Choose how to absorb its power:**\n"
                    "❤️‍🔥 **Enraged:** Modifies Attack (-1 to +2)\n"
                    "💙 **Solidified:** Modifies Defence (-1 to +2)\n"
                    "💔 **Unstable:** Shuffles Stats towards equilibrium\n"
                    "💞 **Inverse:** Swaps Attack and Defence values\n"
                    "🖤 **Keep:** Store a singular Soul Core"
                ),
                "inline": False,
            }
        ],
    },
}


def _boss_victory_cfg(monster_name: str) -> dict:
    for key, cfg in _BOSS_VICTORY_CFG.items():
        if key in monster_name:
            return cfg
    return {}


_COMBAT_COOLDOWN = timedelta(minutes=10)

from core.combat.views.post_combat_view import PostCombatView  # noqa: E402


class StatPackagePicker(BaseLayoutView):
    """Post-combat view that presents 3 stat-package options for the player to pick.

    One instance handles all pending level-up packages for a single fight: after
    the player chooses a package it pops it from the queue and either presents the
    next one or fires the ``on_done`` callback so the caller can show the
    post-combat view.

    ``on_done`` is an async callable that receives ``(message)`` — the Discord
    message object — and is responsible for the final transition.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player,
        pending_packages: list,
        *,
        on_done,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.pending = pending_packages  # list of package-sets (list of 3 dicts each)
        self.on_done = on_done
        self._processing = False
        self._sync_items()

    def _build_row(self) -> discord.ui.ActionRow:
        row = discord.ui.ActionRow()
        current_set = self.pending[0]  # 3 packages for the current level-up
        styles = [
            discord.ButtonStyle.blurple,
            discord.ButtonStyle.green,
            discord.ButtonStyle.secondary,
        ]
        for i, pkg in enumerate(current_set):
            label = f"⚔️ +{pkg['atk']}  🛡️ +{pkg['def']}  ❤️ +{pkg['hp']}"
            btn = discord.ui.Button(label=label, style=styles[i % len(styles)])
            btn.callback = self._make_callback(pkg)
            row.add_item(btn)
        return row

    def _sync_items(self):
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(self.build_embed()))
        self.add_item(self._build_row())

    def _make_callback(self, pkg):
        async def callback(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            # Apply selected package to DB
            await self.bot.database.users.modify_stat(
                self.user_id, "attack", pkg["atk"]
            )
            await self.bot.database.users.modify_stat(
                self.user_id, "defence", pkg["def"]
            )
            await self.bot.database.users.modify_stat(self.user_id, "max_hp", pkg["hp"])

            # Apply to player object in memory
            self.player.base_attack += pkg["atk"]
            self.player.base_defence += pkg["def"]
            self.player.max_hp += pkg["hp"]
            self.player.current_hp = self.player.total_max_hp  # Full heal
            self.player.compute_flat_stats()

            # Pop the chosen package set and update DB
            self.pending.pop(0)
            await self.bot.database.users.set_pending_packages(
                self.user_id, self.server_id, self.pending or None
            )
            # Persist updated stats (level was already saved; we need max_hp etc.)
            await self.bot.database.users.update_from_player_object(self.player)

            if self.pending:
                # Another level-up package remains — show it
                self._processing = False
                self._sync_items()
                await interaction.edit_original_response(view=self)
            else:
                self.stop()
                await self.on_done(interaction.message)

        return callback

    def build_embed(self) -> discord.Embed:
        remaining = len(self.pending)
        current_set = self.pending[0]

        suffix = (
            f" *({remaining} level-up{'s' if remaining != 1 else ''} remaining)*"
            if remaining > 1
            else ""
        )

        cur_atk = self.player.base_attack
        cur_def = self.player.base_defence
        cur_hp = self.player.max_hp

        embed = discord.Embed(
            title="🎉 Level Up! Choose a Stat Package",
            description=(
                f"Select one of the packages below to permanently apply to your character.{suffix}\n\n"
                f"**Current base stats:** ⚔️ {cur_atk} ATK  🛡️ {cur_def} DEF  ❤️ {cur_hp} HP\n\n"
                "Each package has **15 points** distributed across ATK, DEF, and HP. "
                "Packages are weighted toward whichever stat is furthest behind."
            ),
            color=discord.Color.gold(),
        )
        for i, pkg in enumerate(current_set):
            embed.add_field(
                name=f"Option {i + 1}",
                value=(
                    f"⚔️ **+{pkg['atk']}** ATK → {cur_atk + pkg['atk']}\n"
                    f"🛡️ **+{pkg['def']}** DEF → {cur_def + pkg['def']}\n"
                    f"❤️ **+{pkg['hp']}** HP → {cur_hp + pkg['hp']}"
                ),
                inline=True,
            )
        return embed


class CombatActionRow(discord.ui.ActionRow["CombatView"]):
    """Row 0: primary combat actions. Thin dispatchers — logic lives on
    CombatView so it stays easy to follow and share with the auto-battle
    loop, which drives the same methods directly."""

    @discord.ui.button(label="Attack", style=ButtonStyle.danger, emoji="⚔️")
    async def attack_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_attack(interaction)

    @discord.ui.button(label="Heal", style=ButtonStyle.success, emoji="🩹")
    async def heal_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_heal(interaction)

    @discord.ui.button(label="Auto", style=ButtonStyle.primary, emoji="⏩")
    async def auto_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_auto(interaction)

    @discord.ui.button(label="Flee", style=ButtonStyle.secondary, emoji="🏃")
    async def flee_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_flee(interaction)


class CombatActionRow2(discord.ui.ActionRow["CombatView"]):
    """Row 1: Free Yourself (Verdant Colossus only) + 10 Turns."""

    @discord.ui.button(label="Free Yourself", style=ButtonStyle.secondary, emoji="🌿")
    async def free_yourself_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_free_yourself(interaction)

    @discord.ui.button(label="10 Turns", style=ButtonStyle.secondary, emoji="⚡")
    async def fast_auto_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_fast_auto(interaction)


class CombatView(BaseLayoutView):
    # Flee must stay clickable while the auto-battle loop runs inside a
    # button callback; this view manages its own re-entry flags.
    concurrent_dispatch = True

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        monster: Monster,
        initial_logs: dict,
        combat_phases=None,
        post_combat_view=None,
        rematch_callback=None,
        hard_mode: int = 0,
        combat_streak: int = 0,
        crisis_callback=None,
        rite_callback=None,
        disable_potions: bool = False,
        player_avatar_url: str | None = None,
        title_override: str | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.monster = monster
        self.logs = initial_logs or {}
        self.post_combat_view = post_combat_view
        self.rematch_callback = rematch_callback
        self.crisis_callback = crisis_callback
        # The Rite of Convergence: when set, handle_end_state() hands victory/defeat
        # entirely to this callback instead of the standard reward pipeline (which
        # is keyed by boss-name substrings — e.g. "Lucifer", "NEET" — that Rite's
        # own "Lucifer Reborn"/"NEET Reborn" wing monsters would otherwise collide
        # with) and the Uber-specific reward path. Signature: async fn(view, message,
        # interaction) -> None; the callback owns the entire end-of-fight flow.
        self.rite_callback = rite_callback
        # The Rite of Convergence's Trial's Drought writ: forces the Heal button
        # off for the whole fight regardless of potion count.
        self.disable_potions = disable_potions
        self.hard_mode = (
            hard_mode  # int: 0=off, 1=hard, 2=extreme, 3=nightmarish, 4=delirious
        )
        self.combat_streak = combat_streak  # streak at start of this fight
        self.player_avatar_url = player_avatar_url

        _je.reset_jewel_charges(player)

        # Per-encounter reset for Verdant Snare flag (rematch paths reuse the Player object;
        # fresh load_player paths get a default False via dataclass anyway).
        # Prestige phase chains use lighter reset_combat_bonus for other transients.
        player.cs.is_snared = False

        # Boss / Chain Handling
        self.combat_phases = combat_phases or []  # List of dicts
        self.current_phase_index = 0
        self._auto_running = False
        self._was_auto = False
        self.killing_blow = 0
        self._processing = (
            False  # Re-entry guard for mutating actions (Free Yourself, etc.)
        )
        self._stop_auto = False  # Signals auto loop to exit (flee during auto)
        self._turn_count = 0  # Hard cap: exhaustion draw at 600 turns
        self.fled = False  # The Rite of Convergence: distinguishes flee from defeat

        self.combat_logger = CombatLogger(player, monster)
        self.combat_logger.log_combat_start(player, monster)

        # Free Yourself is only relevant during a Verdant Colossus encounter.
        # Built without it entirely for every other fight so it never appears.
        self.row1 = CombatActionRow()
        self.row2 = CombatActionRow2()
        if "Verdant Colossus" not in monster.name:
            self.row2.remove_item(self.row2.free_yourself_btn)

        self.update_buttons()
        self._sync_items(self._build_layout(title_override=title_override))

    def _build_layout(self, *, title_override: str = None, compact: bool = False):
        return combat_ui.create_combat_layout(
            self.player,
            self.monster,
            self.logs,
            title_override=title_override,
            compact=compact,
            player_avatar_url=self.player_avatar_url,
        )

    def _sync_items(self, container=None, *, interactive: bool = True):
        """Rebuilds the LayoutView's top-level items: the display Container
        plus whichever action rows are still interactive. row1/row2 keep
        their identity across rebuilds so button .disabled state set by
        update_buttons() carries over. interactive=False fully drops the
        button rows (used for truly-final frames — flee/exhaustion/timeout/
        defeat — matching the old embed+view=None behaviour)."""
        container = container if container is not None else self._build_layout()
        self.clear_items()
        self.add_item(container)
        if interactive:
            self.add_item(self.row1)
            if self.row2.children:
                self.add_item(self.row2)

    async def on_timeout(self):
        # Only trigger flee logic if the fight is still active
        if self.player.current_hp > 0 and self.monster.hp > 0:
            self.logs["Timeout"] = (
                "You hesitated too long! You failed to step up to the challenge."
            )

            self._sync_items(interactive=False)

            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass

            # Save state (HP/XP changes if any occurred prior)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)

        self.combat_logger.log_combat_end(self.player, self.monster, "timeout")
        await super().on_timeout()

    def neutralize(self) -> None:
        """Marks this fight as over and stops any in-flight auto-battle loop
        from continuing to process turns against stale state. `.stop()`
        alone does not interrupt an already-running coroutine — callers
        that are about to discard this view for a fresh CombatView (e.g.
        the Rite's death/flee/phase-transition handling) must call this
        first, or the old loop keeps fighting in the background and
        double-processes the end state."""
        self.monster.hp = 0
        self._auto_running = False
        self._stop_auto = True

    def update_buttons(self):
        # Toggle buttons based on current state (Enabled if both alive, Disabled if one dead)
        is_over = self.player.current_hp <= 0 or self.monster.hp <= 0
        is_snared = getattr(self.player.cs, "is_snared", False)

        row1, row2 = self.row1, self.row2

        for child in (*row1.children, *row2.children):
            # Flee remains accessible even during auto so the player can always escape.
            child.disabled = is_over or (
                self._auto_running and child is not row1.flee_btn
            )

        # always disable fast_auto_btn if player level < 2:
        if self.player.level < 2:
            row1.auto_btn.disabled = True

        # always disable 10 turns if player level < 20:
        if self.player.level < 20:
            row2.fast_auto_btn.disabled = True

        # always disable heal if potions is 0 or hp is >= max
        if (
            self.player.potions <= 0
            or self.player.current_hp >= self.player.get_effective_max_hp()
            or self.disable_potions
        ):
            row1.heal_btn.disabled = True

        # Free Yourself is only in row2's children during Verdant Colossus
        # encounters (removed in __init__ for all other fights).
        snare_locks_combat = False
        if row2.free_yourself_btn in row2.children:
            if is_snared and not is_over and not self._auto_running:
                # Player is snared — only Free Yourself is usable, lock everything else.
                row1.attack_btn.disabled = True
                row1.heal_btn.disabled = True
                row1.flee_btn.disabled = True
                row1.auto_btn.disabled = True
                row2.fast_auto_btn.disabled = True
                row2.free_yourself_btn.disabled = False
                snare_locks_combat = True
            else:
                row2.free_yourself_btn.disabled = True

        # Always update potion count on the heal button label.
        # Re-enable heal normally if combat is ongoing and player isn't locked by a snare.
        row1.heal_btn.label = f"Heal ({self.player.potions}/20)"
        if not is_over and not self._auto_running and not snare_locks_combat:
            row1.heal_btn.disabled = self.player.potions <= 0 or self.disable_potions

    def _do_monster_turn(self, *, context_note: str = "") -> str:
        hp_before = self.player.current_hp
        log = engine.process_monster_turn(
            self.player, self.monster, context_note=context_note
        )
        self.killing_blow = hp_before - max(0, self.player.current_hp)
        self.combat_logger.log_monster_turn(log, self.player)
        self.combat_logger.log_player_stat_snapshot(self.player, self.monster)
        self.combat_logger.log_monster_stat_snapshot(self.monster)
        return log

    def _apply_phase_image_transition(self):
        """Permanently swap monster to image2 once HP drops to or below 50% (one-way)."""
        if self.monster.image2 and self.monster.hp * 2 <= self.monster.max_hp:
            self.monster.image = self.monster.image2
            self.monster.image2 = ""

    def _streak_footer(self) -> str:
        """Returns a footer string showing the active combat streak bonus (if any)."""
        if self.combat_streak <= 0:
            return ""
        streak_pct = min(50, self.combat_streak // 10)
        if streak_pct <= 0:
            return f"{WIN_STREAK} Streak: {self.combat_streak}"
        return f"{WIN_STREAK} Streak: {self.combat_streak}  (+{streak_pct}% EXP & Gold)"

    async def refresh_embed(self, interaction: Interaction):
        self._apply_phase_image_transition()
        self.update_buttons()
        container = self._build_layout()

        streak_txt = self._streak_footer()
        if streak_txt:
            container.add_item(discord.ui.TextDisplay(f"-# {streak_txt}"))

        self._sync_items(container)

        # Check if we have already deferred or responded (e.g. via Fast Auto)
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    async def _on_attack(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # 1. Player Turn
        p_log = engine.process_player_turn(self.player, self.monster)
        self.combat_logger.log_player_turn(p_log, self.monster)
        self.logs = {self.player.name: p_log}

        # 2. Monster Turn (if alive)
        if self.monster.hp > 0:
            m_log = self._do_monster_turn()
            self.logs[self.monster.name] = m_log

        self._turn_count += 1
        if (
            self._turn_count >= 600
            and self.player.current_hp > 0
            and self.monster.hp > 0
        ):
            await self._handle_exhaustion(interaction.message, interaction)
            return

        # 3. Check End State
        # If cull delivered the killing blow, show the result for 3 s before transitioning.
        if p_log.cull_fired and self.monster.hp <= 0:
            self.update_buttons()
            await self.refresh_embed(interaction)
            await asyncio.sleep(3)
            await self.handle_end_state(interaction.message, interaction)
        else:
            # Only release the guard when the fight is still ongoing.
            # If combat is over, handle_end_state (called inside check_combat_state)
            # stops the view, so holding the guard until then prevents double-rewards.
            if self.player.current_hp > 0 and self.monster.hp > 0:
                self._processing = False
            await self.check_combat_state(interaction)

    async def _on_heal(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        h_log = engine.process_heal(self.player, self.monster)
        self.logs = {"Heal": h_log}

        # Monster still hits you when you potion (retaliation turn)
        if self.monster.hp > 0:
            m_log = self._do_monster_turn(context_note="(retaliation to heal/potion)")
            self.logs[self.monster.name] = m_log

        self._turn_count += 1
        if (
            self._turn_count >= 600
            and self.player.current_hp > 0
            and self.monster.hp > 0
        ):
            await self._handle_exhaustion(interaction.message, interaction)
            return

        if self.player.current_hp > 0 and self.monster.hp > 0:
            self._processing = False
        await self.check_combat_state(interaction)

    async def _on_free_yourself(self, interaction: Interaction):
        # Re-entry guard (mandatory for any button that mutates combat state per AGENTS.md)
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        if not getattr(self.player.cs, "is_snared", False):
            await interaction.response.send_message(
                "You are not currently snared.", ephemeral=True
            )
            self._processing = False
            return

        await interaction.response.defer()

        self.player.cs.is_snared = False
        snare_source = getattr(self.monster, "name", "the enemy")
        self.logs = {"Free Yourself": f"You break free from {snare_source}'s snare!"}

        # Monster gets a free retaliation turn after you free yourself (per design)
        if self.monster.hp > 0:
            m_log = self._do_monster_turn(
                context_note="(retaliation after breaking snare)"
            )
            self.logs[self.monster.name] = m_log

        if self.player.current_hp > 0 and self.monster.hp > 0:
            self._processing = False
        await self.check_combat_state(interaction)

    async def _on_auto(self, interaction: Interaction):
        # Simple Auto: Process turns in a loop.
        # For bosses: run all the way through without HP protection.
        # For regular enemies: pause at < 20% HP.
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        await interaction.response.defer()

        hp_threshold = self.player.total_max_hp * 0.2

        self._auto_running = True
        message = interaction.message

        self.update_buttons()
        await message.edit(view=self)

        while True:
            # Inner loop: fight the current phase to completion
            while (
                self.player.current_hp > hp_threshold
                and self.monster.hp > 0
                and self._turn_count < 600
                and not self._stop_auto
            ):
                p_log = engine.process_player_turn(self.player, self.monster)
                self.combat_logger.log_player_turn(p_log, self.monster)
                m_log = ""
                if self.monster.hp > 0:
                    m_log = self._do_monster_turn()

                self.logs = {self.player.name: p_log, self.monster.name: m_log}
                self._turn_count += 1

                self._apply_phase_image_transition()
                self._sync_items(self._build_layout(compact=True))
                await message.edit(view=self)
                await asyncio.sleep(1.0)

            was_auto = self._auto_running
            self._auto_running = False

            # Fled during auto — perform the save and exit cleanly.
            if self._stop_auto:
                self._stop_auto = False
                self.player.cs.is_snared = False
                self.logs["Flee"] = "You managed to escape safely!"
                self._sync_items(interactive=False)
                await message.edit(view=self)
                self.bot.state_manager.clear_active(self.user_id)
                await self.bot.database.users.update_from_player_object(self.player)
                await _je.save_jewel_state(self.bot, self.user_id, self.player)
                if self.crisis_callback:
                    try:
                        await self.crisis_callback(False)
                    except Exception:
                        pass

                # The Rite of Convergence: fleeing returns to the wing lobby
                # with -1 attempt rather than silently ending the view.
                if self.rite_callback:
                    self.fled = True
                    await self.rite_callback(self, message, interaction)
                    return

                self.stop()
                return

            # Exhaustion cap — 600 turns elapsed with both sides still alive.
            if (
                self._turn_count >= 600
                and self.player.current_hp > 0
                and self.monster.hp > 0
            ):
                await self._handle_exhaustion(message)
                return

            # Low HP pause — applies to all fight types including bosses
            if (
                0 < self.player.current_hp <= (self.player.total_max_hp * 0.2)
                and self.monster.hp > 0
            ):
                self.logs["Auto-Battle"] = "🛑 Paused: Low HP Protection triggered!"
                self.update_buttons()
                self._sync_items()
                await message.edit(view=self)
                await message.channel.send(
                    f"<@{self.user_id}> ⚠️ Low HP Protection triggered — auto paused!",
                    delete_after=15,
                )
                self._processing = False
                break

            # Handle end state (victory, defeat, or phase transition)
            self._was_auto = was_auto
            player_was_alive = self.player.current_hp > 0
            await self.handle_end_state(message, interaction)

            # Phase transition: handle_end_state replaces self.monster with the next
            # phase boss (hp > 0) and returns without stopping the view.
            # In all other cases (final victory, defeat) self.monster.hp stays 0.
            if was_auto and self.monster.hp > 0 and player_was_alive:
                self._auto_running = True  # Resume auto for the new phase
                continue
            break

    async def _on_flee(self, interaction: Interaction):
        if self._auto_running:
            # Signal the auto loop to exit on its next iteration, then handle cleanup there.
            self._stop_auto = True
            await interaction.response.defer()
            return

        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        self.player.cs.is_snared = (
            False  # Clean up any transient snare before leaving the fight
        )
        self.logs["Flee"] = "You managed to escape safely!"
        self._sync_items(interactive=False)

        await interaction.response.edit_message(view=self)

        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)

        # Treat fleeing as a failure for crisis combat (same as defeat)
        if self.crisis_callback:
            try:
                await self.crisis_callback(False)
            except Exception:
                pass

        # The Rite of Convergence: fleeing returns to the wing lobby with
        # -1 attempt rather than silently ending the view (see rite_callback).
        if self.rite_callback:
            self.fled = True
            await self.rite_callback(self, interaction.message, interaction)
            return

        self.stop()

    async def _on_fast_auto(self, interaction: Interaction):
        if self.player.level < 20:
            return await interaction.response.send_message(
                "This unlocks at Level 20!", ephemeral=True
            )

        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        await interaction.response.defer()

        # Lock all buttons immediately so rapid clicks can't queue stale
        # deferred interactions that later corrupt the post-combat view.
        for child in (*self.row1.children, *self.row2.children):
            child.disabled = True
        await interaction.message.edit(view=self)

        turns_processed = 0

        for _ in range(10):
            if (
                self.player.current_hp <= (self.player.total_max_hp * 0.2)
                or self.monster.hp <= 0
            ):
                break

            p_log = engine.process_player_turn(self.player, self.monster)
            self.combat_logger.log_player_turn(p_log, self.monster)
            m_log = ""
            if self.monster.hp > 0:
                m_log = self._do_monster_turn()

            self.logs = {self.player.name: p_log, self.monster.name: m_log}
            self._turn_count += 1
            turns_processed += 1

            if (
                self._turn_count >= 600
                and self.monster.hp > 0
                and self.player.current_hp > 0
            ):
                break

        if (
            self._turn_count >= 600
            and self.player.current_hp > 0
            and self.monster.hp > 0
        ):
            await self._handle_exhaustion(interaction.message, interaction)
            return

        status_msg = (
            f"⚡ You flash forward in time, **{turns_processed}** turns have gone by."
        )

        # Ensure HP is strictly greater than 0 to append the pause message
        low_hp_triggered = (
            0 < self.player.current_hp <= (self.player.total_max_hp * 0.2)
            and self.monster.hp > 0
        )
        if low_hp_triggered:
            status_msg += "\n🛑 Paused: Low HP Protection triggered!"

        self.logs["System"] = status_msg

        # Update UI / Check Win/Loss
        if self.player.current_hp <= 0 or self.monster.hp <= 0:
            await self.handle_end_state(interaction.message, interaction)
        else:
            if low_hp_triggered:
                await interaction.message.channel.send(
                    f"<@{self.user_id}> ⚠️ Low HP Protection triggered — auto paused!",
                    delete_after=15,
                )
            if self.player.current_hp > 0 and self.monster.hp > 0:
                self._processing = False
            await self.check_combat_state(interaction)

    async def _handle_exhaustion(self, message, interaction: Interaction | None = None):
        """600-turn cap: end the fight as a draw with no rewards or penalties."""
        self.logs["System"] = (
            "⚔️ After **600 turns** of relentless combat, both sides collapse from exhaustion. "
            "The battle ends in a draw — no rewards granted."
        )
        container = self._build_layout()
        container.add_item(discord.ui.TextDisplay("-# Draw: 600 turn limit reached."))
        self._sync_items(container, interactive=False)

        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(view=self)
        else:
            await message.edit(view=self)

        self.combat_logger.log_combat_end(self.player, self.monster, "exhaustion")
        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)
        self.stop()

    async def check_combat_state(self, interaction: Interaction):
        """Checks if player died or monster died."""
        if self.player.current_hp <= 0 or self.monster.hp <= 0:
            self.update_buttons()  # Disable buttons

            # We use a separate handler because Auto-battle defers interactions,
            # while clicking Attack usually does not.
            if interaction.response.is_done():
                await self.handle_end_state(interaction.message, interaction)
            else:
                await self.refresh_embed(interaction)  # Show final hit
                await self.handle_end_state(interaction.message, interaction)
        else:
            self.update_buttons()
            await self.refresh_embed(interaction)

    async def handle_end_state(self, message, interaction: Interaction):
        """Processes victory or defeat, including phase transitions for boss chains."""

        # --- THE RITE OF CONVERGENCE ---
        if self.rite_callback:
            await self.rite_callback(self, message, interaction)
            return

        # --- UBER ENCOUNTERS ---
        if getattr(self.monster, "is_uber", False):
            await uber_rewards.handle_uber_end_state(self, message, interaction)
            return

        # --- DEFEAT ---
        if self.player.current_hp <= 0:
            self.combat_logger.log_combat_end(self.player, self.monster, "defeat")
            # Reset combat streak on any death
            await self.bot.database.users.reset_combat_streak(self.user_id)

            _DIFFICULTY_NAMES = ["", "Hard", "Extreme", "Nightmarish", "Delirious"]
            _DIFFICULTY_EMOJIS = ["", "☠️", "💀", "👁️", "🌀"]
            exp_protected = await self.bot.database.users.get_exp_protection(
                self.user_id
            )
            if self.hard_mode > 0 and not exp_protected:
                # Any difficulty mode: wipe ALL current-level EXP instead of the standard % loss
                xp_loss = self.player.exp
                self.player.exp = 0
            else:
                base_loss = int(self.player.exp * XP_LOSS_ON_DEFEAT)
                xp_loss = await ExperienceManager.remove_experience(
                    self.bot, self.user_id, self.player, base_loss
                )
            self.player.current_hp = 1
            embed = combat_ui.create_defeat_embed(
                self.player, self.monster, xp_loss, killing_blow=self.killing_blow
            )
            if self.hard_mode > 0:
                diff_name = f"{_DIFFICULTY_EMOJIS[self.hard_mode]} {_DIFFICULTY_NAMES[self.hard_mode]} Mode"
                embed.add_field(
                    name=f"{diff_name}",
                    value="Your EXP for this level has been wiped. Combat streak reset.",
                    inline=False,
                )
            elif self.combat_streak > 0:
                embed.add_field(
                    name="💀 Streak Lost",
                    value=f"Your {self.combat_streak}-win streak has ended.",
                    inline=False,
                )
            self._sync_items(combat_ui.embed_to_container(embed), interactive=False)
            await message.edit(view=self)
            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)
            if self.crisis_callback:
                try:
                    await self.crisis_callback(False)
                except Exception:
                    pass
            self.stop()
            return

        # --- PHASE TRANSITION ---
        if self.current_phase_index < len(self.combat_phases) - 1:
            self.current_phase_index += 1
            next_phase_data = self.combat_phases[self.current_phase_index]

            reset_for_phase_transition(self.player)

            self.monster = await generate_boss(
                self.player, self.monster, next_phase_data, self.current_phase_index
            )
            self.monster.is_boss = True

            engine.apply_stat_effects(self.player, self.monster)
            # apply_combat_start_passives is guarded by player.cs.combat_start_fired —
            # it already fired at Phase 1 start and returns {} here, so Start-of-Combat
            # passives (Gilded Hunger, partner skills, Ward Inoculation, etc.) don't
            # re-trigger/duplicate on every later phase.
            new_logs = engine.apply_combat_start_passives(self.player, self.monster)
            self.logs = new_logs
            self.combat_logger.log_player_stat_snapshot(self.player, self.monster)
            self.combat_logger.log_monster_stat_snapshot(self.monster)

            trans_embed = discord.Embed(
                title="Phase Complete!",
                description=f"**{self.monster.name}** rises from the ashes...",
                color=discord.Color.orange(),
            )
            trans_embed.set_thumbnail(url=self.monster.image)
            self._sync_items(
                combat_ui.embed_to_container(trans_embed), interactive=False
            )
            await message.edit(view=self)
            await asyncio.sleep(2)

            if not self._was_auto:
                self.update_buttons()

            # Release the guard so the next phase's buttons are clickable.
            self._processing = False

            self._sync_items(
                self._build_layout(
                    title_override=f"⚔️ BOSS PHASE {self.current_phase_index + 1}"
                )
            )
            await message.edit(view=self)
            return  # Keep view alive for next phase

        # --- FINAL VICTORY ---
        # Streak bonus is based on the pre-fight streak (what was shown in the footer
        # during combat), so the player always receives exactly what was advertised.
        _DIFFICULTY_REWARD_PCT = [0, 50, 75, 100, 150]
        _DIFFICULTY_NAMES_V = ["", "Hard", "Extreme", "Nightmarish", "Delirious"]
        _DIFFICULTY_EMOJIS_V = ["", "☠️", "💀", "👁️", "🌀"]
        streak_pct = min(50, self.combat_streak // 10)
        hard_mode_pct = _DIFFICULTY_REWARD_PCT[self.hard_mode] if self.hard_mode else 0
        total_bonus_pct = streak_pct + hard_mode_pct

        reward_data = await apply_victory_rewards(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.monster,
            message,
            self.combat_logger,
        )

        # log_rewards (inside apply_victory_rewards) must run before the file
        # is closed, so log_combat_end — which closes the log file — comes last.
        self.combat_logger.log_combat_end(self.player, self.monster, "victory")

        # Increment streak after base rewards are applied (avoids DB write ordering issues).
        new_streak = await self.bot.database.users.increment_combat_streak(self.user_id)

        # Apply streak + hard mode bonus XP and gold on top of base rewards.
        bonus_xp = 0
        bonus_gold = 0
        if total_bonus_pct > 0:
            bonus_xp = int(reward_data["xp"] * total_bonus_pct / 100)
            bonus_gold = int(reward_data["gold"] * total_bonus_pct / 100)
            if bonus_xp > 0:
                bonus_exp_changes = await ExperienceManager.add_experience(
                    self.bot,
                    self.user_id,
                    self.player,
                    bonus_xp,
                    server_id=self.server_id,
                )
                reward_data["msgs"].extend(bonus_exp_changes["msgs"])
            if bonus_gold > 0:
                await self.bot.database.users.modify_gold(self.user_id, bonus_gold)

        # Auto-Reload Potions setting: top off to the 20-potion cap if fully affordable.
        if await self.bot.database.users.get_auto_potion_reload(self.user_id):
            topup_qty = max(0, 20 - self.player.potions)
            if topup_qty > 0:
                topup_cost = (
                    TavernMechanics.calculate_potion_cost(self.player.level) * topup_qty
                )
                if await self.bot.database.users.deduct_gold_atomic(
                    self.user_id, topup_cost
                ):
                    await self.bot.database.users.modify_stat(
                        self.user_id, "potions", topup_qty
                    )
                    self.player.potions += topup_qty
                    reward_data["msgs"].append(
                        f"🧪 **Auto-Reload:** bought {topup_qty} potions for {topup_cost:,} gold"
                    )

        embed = combat_ui.create_victory_embed(
            self.player,
            self.monster,
            reward_data,
            cfg=_boss_victory_cfg(self.monster.name),
        )

        # Streak / hard mode / modifier-difficulty bonus field (shown when any applied this fight)
        difficulty_xp_pct = reward_data.get("difficulty_xp_pct", 0.0)
        difficulty_drop_pct = reward_data.get("difficulty_drop_pct", 0.0)
        if total_bonus_pct > 0 or difficulty_xp_pct > 0:
            bonus_parts = []
            if hard_mode_pct > 0:
                diff_emoji = _DIFFICULTY_EMOJIS_V[self.hard_mode]
                diff_name = _DIFFICULTY_NAMES_V[self.hard_mode]
                bonus_parts.append(f"{diff_emoji} {diff_name} Mode +{hard_mode_pct}%")
            if streak_pct > 0:
                bonus_parts.append(f"{WIN_STREAK} Streak +{streak_pct}%")
            value_lines = [" | ".join(bonus_parts)]
            if total_bonus_pct > 0:
                value_lines.append(f"+{bonus_xp:,} XP  •  +{bonus_gold:,} Gold")
            field_name = (
                f"🎯 Bonus Rewards (+{total_bonus_pct}%)"
                if total_bonus_pct > 0
                else "🎯 Bonus Rewards"
            )
            embed.add_field(
                name=field_name,
                value="\n".join(value_lines),
                inline=False,
            )

        # Victory embed footer: show updated streak so the player knows where they stand.
        if new_streak > 0:
            new_streak_pct = min(50, new_streak // 10)
            footer_txt = f"{WIN_STREAK} Streak: {new_streak}"
            if new_streak_pct > 0:
                footer_txt += f"  (+{new_streak_pct}% bonus next fight)"
            embed.set_footer(text=footer_txt)

        # NEET: conditional void key — DB write and loot field, then regular edit
        if "NEET" in self.monster.name and random.random() < NEET_VOID_KEY_CHANCE:
            embed.add_field(name="Loot", value="Found a **Void Key**.", inline=False)
            await self.bot.database.users.modify_currency(self.user_id, "void_keys", 1)

        # Lucifer: soul core choice view takes over the interaction
        if "Lucifer" in self.monster.name:
            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)
            ping_msg = await message.channel.send(
                f"<@{self.user_id}> A Soul Core has manifested — make your choice!\n\n"
                f"Battle: {message.jump_url}"
            )
            await ping_msg.delete(delay=45)
            contract_choice_view = LuciferChoiceView(
                self.bot,
                self.user_id,
                self.player,
                server_id=self.server_id,
                rematch_callback=self.rematch_callback,
            )
            contract_choice_view.set_content(embed)
            await message.edit(view=contract_choice_view)
            contract_choice_view.message = message
            self.stop()
            return  # LuciferChoiceView takes over

        # Prestige Gathering Boss (Artisan Mastery Phase 2) — custom harvest view
        prestige_type = getattr(self.monster, "prestige_boss_type", None)
        if prestige_type in ("golem", "leviathan", "colossus"):
            self.bot.state_manager.clear_active(self.user_id)
            await self.bot.database.users.update_from_player_object(self.player)
            await _je.save_jewel_state(self.bot, self.user_id, self.player)
            harvest_view = PrestigeBossHarvestView(
                self.bot,
                self.user_id,
                self.server_id,
                self.player,
                self.monster,
                prestige_type,
                self.rematch_callback,
            )
            harvest_view.set_content(embed)
            await message.edit(view=harvest_view)
            harvest_view.message = message
            self.stop()
            return  # Harvest view takes over the interaction

        fire_on_victory_effects(self.player)

        # Save player state and clear combat lock before any callback so the
        # callback can freely set a new active state (e.g. returning to settlement).
        self.bot.state_manager.clear_active(self.user_id)
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)

        if self.crisis_callback:
            try:
                await self.crisis_callback(True)
            except Exception:
                # Settlement transition failed — show a plain recovery message so the
                # player isn't stuck looking at dead combat buttons.
                try:
                    fallback = discord.ui.Container(
                        discord.ui.TextDisplay(
                            "⚔️ Crisis resolved! Your settlement is safe. "
                            "Use `/settlement` to return."
                        )
                    )
                    self._sync_items(fallback, interactive=False)
                    await message.edit(view=self)
                except Exception:
                    pass
            self.stop()
            return  # Caller handles the view transition; skip normal post-combat UI

        # Build post-combat view (Fight Again button or stamina cooldown field)
        stamina_data = await self.bot.database.users.get_stamina(self.user_id)
        stamina = stamina_data["combat_stamina"]

        if stamina == 0:
            equipped_boot = await self.bot.database.equipment.get_equipped(
                self.user_id, "boot"
            )
            speedster_reduction = 0
            if equipped_boot and equipped_boot["passive"] == "speedster":
                speedster_reduction = equipped_boot["passive_lvl"] * 60
            cooldown = max(
                timedelta(seconds=10),
                _COMBAT_COOLDOWN - timedelta(seconds=speedster_reduction),
            )
            last_combat_str = await self.bot.database.users.get_timer(
                self.user_id, "last_combat"
            )
            time_str = "soon"
            if last_combat_str:
                try:
                    elapsed = datetime.now() - datetime.fromisoformat(last_combat_str)
                    remaining = cooldown - elapsed
                    if remaining.total_seconds() > 0:
                        mins = int(remaining.total_seconds()) // 60
                        secs = int(remaining.total_seconds()) % 60
                        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                    else:
                        time_str = "now"
                except ValueError:
                    pass
            embed.add_field(
                name="⚡ Stamina",
                value=f"0/10 — next in **{time_str}**",
                inline=True,
            )
        else:
            embed.add_field(
                name="⚡ Stamina",
                value=f"{stamina}/10 — Fight Again ready!",
                inline=True,
            )

        # If the player levelled up during this fight, show the stat-package picker
        # before the Fight Again button.  The picker's on_done callback fires the
        # final post-combat edit, so we return early here.
        pending_packages = await self.bot.database.users.get_pending_packages(
            self.user_id, self.server_id
        )
        if pending_packages:
            _victory_embed = embed  # captured for the on_done closure
            _stamina = stamina
            _rematch = self.rematch_callback

            async def _after_packages(msg):
                """Transition to the post-combat view once all packages are chosen."""
                post_view = (
                    PostCombatView(
                        self.bot,
                        self.user_id,
                        self.server_id,
                        self.player,
                        _stamina,
                        _rematch,
                    )
                    if _rematch
                    else None
                )
                if post_view is not None:
                    post_view.set_content(_victory_embed)
                    await msg.edit(view=post_view)
                    post_view.message = msg
                else:
                    await msg.edit(
                        view=combat_ui.static_layout_view(
                            combat_ui.embed_to_container(_victory_embed)
                        )
                    )

            picker = StatPackagePicker(
                self.bot,
                self.user_id,
                self.server_id,
                self.player,
                pending_packages,
                on_done=_after_packages,
            )
            await message.edit(view=picker)
            picker.message = message
            self.stop()
            return

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
            await message.edit(view=post_view)
            post_view.message = message
        else:
            self._sync_items(combat_ui.embed_to_container(embed), interactive=False)
            await message.edit(view=self)
        self.stop()
