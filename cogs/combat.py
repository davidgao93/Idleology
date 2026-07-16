# cogs/combat.py

import asyncio
import json
import random
from datetime import datetime, timedelta

import discord
from discord import ButtonStyle, Interaction, app_commands
from discord.ext import commands
from discord.ui import Button

from core.base_view import BaseView
from core.combat import jewel_engine as _je
from core.combat.dojo.views_dojo import DummyConfigView
from core.combat.economy.config import CORRUPTED_MIN_LEVEL, get_corrupted_base_chance
from core.combat.mobgen.encounters import EncounterManager
from core.combat.mobgen.gen_mob import (
    generate_boss,
    generate_corrupted_encounter,
    generate_encounter,
    generate_incubated_monster,
    generate_prestige_colossus,
    generate_prestige_golem,
    generate_prestige_leviathan,
)
from core.combat.turns import engine
from core.combat.ui.combat_embed import freeze_and_handoff
from core.combat.views.views import CombatView
from core.combat.views.warning_views import (
    CorruptedEncounterGateView,
    LowHealthWarningView,
)
from core.first_use import TUTORIALS
from core.inner_sanctum.mechanics import get_tree_bonuses
from core.items.factory import load_player
from core.models import Monster


class CombatTutorialView(BaseView):
    """First-time combat tutorial gate. Shown once; 'Begin Combat' re-enters the full combat flow."""

    def __init__(self, bot, cog, user_id: str, server_id: str, existing_user):
        super().__init__(bot, user_id, server_id)
        self._cog = cog
        self._existing_user = existing_user
        self._processing = False

        btn = discord.ui.Button(
            label="Begin Combat →",
            style=ButtonStyle.success,
            emoji="⚔️",
        )
        btn.callback = self._begin
        self.add_item(btn)

    def build_embed(self) -> discord.Embed:
        data = TUTORIALS["combat"]
        embed = discord.Embed(
            title=data["title"],
            description=data["description"],
            color=data.get("color", discord.Color.red()),
        )
        if tips := data.get("tips"):
            embed.add_field(
                name="Quick Tips",
                value="\n".join(f"• {t}" for t in tips),
                inline=False,
            )
        if img := data.get("image"):
            embed.set_thumbnail(url=img)
        embed.set_footer(text="First visit — this message only appears once.")
        return embed

    async def _begin(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # Re-check state (in case player opened another activity while reading)
        user_id = self.user_id
        server_id = self.server_id
        if self.bot.state_manager.is_active(user_id):
            await interaction.response.send_message(
                "You're already in an active session.", ephemeral=True
            )
            self._processing = False
            return

        # Fresh data — stamina may have changed since the tutorial was shown
        existing_user = await self.bot.database.users.get(user_id, server_id)
        is_tree = await self.bot.database.inner_sanctum.get(user_id, server_id)
        is_bonuses = get_tree_bonuses(is_tree["nodes_owned"])
        if not await self._cog._check_stamina(
            interaction, user_id, existing_user, is_bonuses
        ):
            self.bot.state_manager.clear_active(user_id)
            self._processing = False
            return

        self.bot.state_manager.set_active(user_id, "combat")
        player = await load_player(user_id, existing_user, self.bot.database)

        # Health check
        if player.current_hp < (player.total_max_hp * 0.25):
            view = LowHealthWarningView(
                self.bot,
                user_id,
                server_id,
                existing_user,
                player,
                self._cog._execute_combat,
            )
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
            view.message = interaction.message
            self.stop()
            return

        await interaction.response.defer()
        self.stop()
        await self._cog._execute_combat(
            interaction, user_id, server_id, existing_user, player
        )


class DoorPromptView(BaseView):
    def __init__(self, bot, user_id, cost_dict, boss_type):
        super().__init__(bot, user_id)
        self.cost_dict = cost_dict
        self.boss_type = boss_type
        self.accepted = False
        self._entering = False  # Re-entry guard

    @discord.ui.button(label="Enter", style=ButtonStyle.danger)
    async def enter(self, interaction: Interaction, button: Button):
        if self._entering:
            await interaction.response.defer()
            return
        self._entering = True

        await interaction.response.defer()

        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

        self.accepted = True
        for currency, amount in self.cost_dict.items():
            await self.bot.database.users.modify_currency(
                self.user_id, currency, -amount
            )
        self.stop()

    @discord.ui.button(label="Close", style=ButtonStyle.secondary)
    async def leave(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        self.stop()


MAX_STAMINA = 10
COMBAT_COOLDOWN = timedelta(minutes=10)


class Combat(commands.Cog, name="combat"):
    def __init__(self, bot):
        self.bot = bot

    def _get_speedster_reduction(
        self, equipped_boot, ss_speedster_tier: int = 0
    ) -> int:
        """Returns the Speedster passive cooldown reduction in seconds.

        Priority: equipped boot passive > soul stone passive (conflict guard).
        """
        if equipped_boot and equipped_boot["passive"] == "speedster":
            return equipped_boot["passive_lvl"] * 60
        if ss_speedster_tier > 0:
            from core.apex.data import SOUL_STONE_TIER_VALUES

            return SOUL_STONE_TIER_VALUES["speedster"][ss_speedster_tier - 1]
        return 0

    def _effective_cooldown(
        self, speedster_reduction_sec: int, cooldown_penalty_sec: int = 0
    ) -> timedelta:
        return max(
            timedelta(seconds=10),
            COMBAT_COOLDOWN
            + timedelta(seconds=cooldown_penalty_sec)
            - timedelta(seconds=speedster_reduction_sec),
        )

    async def _check_stamina(
        self, interaction: Interaction, user_id: str, existing_user, is_bonuses: dict
    ) -> bool:
        """If the player has stamina, pass immediately.
        If empty, fall back to the regular 10-minute cooldown check."""
        if existing_user["combat_stamina"] > 0:
            return True

        # No stamina — enforce the regular combat cooldown
        equipped_boot = await self.bot.database.equipment.get_equipped(user_id, "boot")
        # Soul stone speedster: only checked when no speedster boot is equipped
        ss_speedster_tier = 0
        if not (equipped_boot and equipped_boot["passive"] == "speedster"):
            server_id = str(interaction.guild.id)
            from core.apex.models import soul_stone_from_db

            ss_row = await self.bot.database.apex.get_or_create_soul_stone(
                user_id, server_id
            )
            ss = soul_stone_from_db(ss_row)
            ss_speedster_tier = ss.get_passive_tier("speedster") or 0
        reduction = self._get_speedster_reduction(equipped_boot, ss_speedster_tier)
        # Inner Sanctum Recovery — Frugal Spirit / Deep Reserves: flat seconds
        # added to the no-stamina cooldown as the trade-off for their chances.
        cooldown = self._effective_cooldown(
            reduction, is_bonuses["recovery_cooldown_penalty_sec"]
        )

        last_combat_str = existing_user["last_combat"]
        if last_combat_str:
            try:
                last_combat_dt = datetime.fromisoformat(last_combat_str)
                elapsed = datetime.now() - last_combat_dt
                if elapsed < cooldown:
                    remaining = cooldown - elapsed
                    mins = remaining.seconds // 60
                    secs = remaining.seconds % 60
                    await interaction.response.send_message(
                        f"You're too tired for another encounter, try again in {mins}m {secs}s.",
                        ephemeral=True,
                    )
                    return False
            except ValueError:
                pass
        return True

    @app_commands.command(name="combat", description="Engage in combat.")
    async def combat(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        is_tree = await self.bot.database.inner_sanctum.get(user_id, server_id)
        is_bonuses = get_tree_bonuses(is_tree["nodes_owned"])
        if not await self._check_stamina(interaction, user_id, existing_user, is_bonuses):
            return

        # First-time combat tutorial — show once before entering the fight
        if not await self.bot.database.tutorials.has_seen(user_id, "combat"):
            await self.bot.database.tutorials.mark_seen(user_id, "combat")
            gate = CombatTutorialView(self.bot, self, user_id, server_id, existing_user)
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        # set_active is called here, before any gate views, so that the
        # LowHealthWarningView and any downstream gate (CorruptedEncounterGateView /
        # DoorPromptView) share the same active-state lifetime.
        # Safety net: every gate view inherits BaseView whose on_timeout calls
        # clear_active, so a user who ignores a gate for 10 min won't be stuck.
        # If an unhandled exception fires between this line and CombatView.send,
        # StateManager's stale-lock expiry (45 min) serves as the final fallback.
        self.bot.state_manager.set_active(user_id, "combat")

        player = await load_player(user_id, existing_user, self.bot.database)

        # Health check interceptor (low HP warning gate)
        if player.current_hp < (player.total_max_hp * 0.25):
            view = LowHealthWarningView(
                self.bot,
                user_id,
                server_id,
                existing_user,
                player,
                self._execute_combat,
            )
            await interaction.response.send_message(embed=view.build_embed(), view=view)
            view.message = await interaction.original_response()
            return  # Pause execution here. The view will call _execute_combat if they proceed.

        # If health is fine, proceed immediately.
        await interaction.response.defer()
        await self._execute_combat(
            interaction, user_id, server_id, existing_user, player, is_tree=is_tree
        )

    async def _rematch_execute(
        self,
        interaction: Interaction,
        user_id: str,
        server_id: str,
        existing_user,
        player,
    ):
        """Thin wrapper used by PostCombatView's Fight Again button.
        Skips the state-guard and stamina-check (both handled by the view)."""
        await self._execute_combat(
            interaction, user_id, server_id, existing_user, player
        )

    async def _execute_combat(
        self,
        interaction: Interaction,
        user_id: str,
        server_id: str,
        existing_user,
        player,
        is_tree: dict | None = None,
    ):
        """The actual combat generation and UI loading logic. Called directly or via the Warning View.

        `is_tree` lets the `combat()` entry point pass along the Inner Sanctum
        tree it already fetched for the stamina-cooldown check, avoiding a
        second query. Callers that don't have it yet (the Warning View's
        callback, `_rematch_execute`) simply omit it and it's fetched here."""
        # `screen_msg` tracks whichever message is currently displaying this
        # combat flow. It's normally the interaction's own response, but a
        # rematch launched from PostCombatView's Fight Again button starts on
        # a Components V2 message — that flag can never be removed, so any
        # classic embed screen shown mid-flow (corrupted gate, boss door) must
        # hand off to a brand new message instead of editing embeds into it.
        # Once that happens screen_msg is a plain message no longer tied to
        # the interaction, so every later update below goes through
        # screen_msg.edit(...) rather than interaction.edit_original_response(...).
        screen_msg = await interaction.original_response()

        # Consume 1 stamina. Use consume_stamina (SQL MAX(0, val-1)) so over-cap
        # values (e.g. 12.5 from War Camp) drain correctly without being truncated.
        # Inner Sanctum Recovery — Frugal Spirit: chance to skip the consumption entirely.
        if is_tree is None:
            is_tree = await self.bot.database.inner_sanctum.get(user_id, server_id)
        is_bonuses = get_tree_bonuses(is_tree["nodes_owned"])
        stamina_saved = random.random() < is_bonuses["stamina_save_chance"]

        current_stamina = existing_user["combat_stamina"]
        if not stamina_saved:
            await self.bot.database.users.consume_stamina(user_id)
        # Start the regen clock the moment we cross below the normal cap.
        # Over-cap stamina (from War Camp) delays the stamp until that crossing.
        if (
            not stamina_saved
            and current_stamina >= MAX_STAMINA
            and current_stamina - 1 < MAX_STAMINA
        ):
            await self.bot.database.users.set_stamina_regen_time(user_id)

        is_boss = False
        is_corrupted = False
        combat_phases = []

        # Fetch difficulty level (0=off, 1=hard, 2=extreme, 3=nightmarish, 4=delirious)
        hard_mode = await self.bot.database.users.get_hard_mode(user_id)
        combat_streak = await self.bot.database.users.get_combat_streak(user_id)
        nsfw_enabled = await self.bot.database.users.get_nsfw_enabled(user_id)

        _DIFFICULTY_CORRUPTED_BONUS = [0.0, 0.02, 0.05, 0.08, 0.10]

        # 3a. Corrupted encounter roll — resolves first (level 70+)
        # Gate-view state-clear contract: CorruptedEncounterGateView and
        # DoorPromptView do NOT clear active state on their own.  They are
        # fire-and-wait gates inside _execute_combat, which always continues
        # to a CombatView after the gate resolves (even on "flee/decline" it
        # falls through to a regular fight).  The CombatView owns the
        # clear_active call on combat end; BaseView.on_timeout handles the gate
        # timeout case by clearing state early (10-min fallback).
        corrupted_enabled = (
            await self.bot.database.users.get_corrupted_encounters_enabled(user_id)
        )
        if player.level >= CORRUPTED_MIN_LEVEL and corrupted_enabled:
            corrupted_chance = (
                get_corrupted_base_chance(player.level)
                + player.get_emblem_bonus("corrupted_find") * 0.002
                + _DIFFICULTY_CORRUPTED_BONUS[hard_mode]
            )

            async def _try_corrupted_gate() -> None:
                nonlocal screen_msg, is_corrupted
                gate_view = CorruptedEncounterGateView(self.bot, user_id)
                if screen_msg.flags.components_v2:
                    screen_msg = await freeze_and_handoff(
                        screen_msg, gate_view.build_embed(), gate_view
                    )
                else:
                    screen_msg = await screen_msg.edit(
                        content=None, embed=gate_view.build_embed(), view=gate_view
                    )
                    gate_view.message = screen_msg
                await gate_view.wait()
                is_corrupted = gate_view.accepted
                if not is_corrupted:
                    # Player fled — clear gate message, fall through to boss door check
                    turn_embed = discord.Embed(
                        description="*You turn away from the corrupted presence... Live to fight another day.*",
                        color=discord.Color.dark_grey(),
                    )
                    screen_msg = await screen_msg.edit(
                        content=None,
                        embed=turn_embed,
                        view=None,
                    )
                    await asyncio.sleep(1.0)

            if random.random() < corrupted_chance:
                await _try_corrupted_gate()
            elif (
                # Inner Sanctum Deicide — Corrupted Affinity: rank-scaled chance
                # for one independent re-roll of the same check if it fails.
                random.random() < is_bonuses["corrupted_reroll_chance"]
                and random.random() < corrupted_chance
            ):
                await _try_corrupted_gate()

        # 3b. Boss door check — skipped entirely if a corrupted encounter was accepted
        triggered = False
        if not is_corrupted:
            doors_enabled = await self.bot.database.users.get_doors_enabled(user_id)
            if doors_enabled:
                all_currencies = await self.bot.database.users.get_all_currencies(
                    user_id
                )
                currencies = {
                    "dragon_key": all_currencies["dragon_key"],
                    "angel_key": all_currencies["angel_key"],
                    "soul_cores": all_currencies["soul_cores"],
                    "void_frags": all_currencies["void_frags"],
                    "balance_fragment": all_currencies["balance_fragment"],
                }
                triggered, boss_type, cost_dict = EncounterManager.check_boss_door(
                    player.level,
                    currencies,
                    boss_chance_bonus=is_bonuses["boss_chance_bonus_pct"],
                    affinity=is_bonuses["boss_affinity"],
                    affinity_shift=is_bonuses["boss_affinity_shift"],
                )

            if triggered:
                details = EncounterManager.get_door_details(boss_type)
                embed = discord.Embed(
                    title=details["title"], description=details["desc"], color=0x00FF00
                )
                if details["img"]:
                    embed.set_image(url=details["img"])
                embed.set_footer(text=f"Cost: {details['cost_str']}")

                view = DoorPromptView(self.bot, user_id, cost_dict, boss_type)
                if screen_msg.flags.components_v2:
                    screen_msg = await freeze_and_handoff(screen_msg, embed, view)
                else:
                    screen_msg = await screen_msg.edit(
                        content=None, embed=embed, view=view
                    )
                    view.message = screen_msg
                await view.wait()

                if view.accepted:
                    is_boss = True
                    combat_phases = EncounterManager.get_boss_phases(
                        boss_type, player.level
                    )
                    await self.bot.database.users.update_timer(user_id, "last_combat")
                else:
                    turn_embed = discord.Embed(
                        description="*You turn away from the ominous presence... Live to fight another day.*",
                        color=discord.Color.dark_grey(),
                    )
                    screen_msg = await screen_msg.edit(
                        content=None, embed=turn_embed, view=None
                    )
                    await asyncio.sleep(1.0)

        if not is_boss:
            await self.bot.database.users.update_timer(user_id, "last_combat")

        # 3c. Incubated encounter — takes priority over a normal random fight
        #     (skipped if a boss or corrupted encounter was accepted)
        is_incubated = False
        incubated_encounter = None
        if not is_boss and not is_corrupted:
            incubated_encounter = await self.bot.database.eggs.get_next_incubated(
                user_id
            )
            if incubated_encounter:
                is_incubated = True

        slayer_profile = await self.bot.database.slayer.get_profile(user_id, server_id)
        task_species = slayer_profile["active_task_species"]
        slayer_tree_data = await self.bot.database.slayer.get_tree(user_id, server_id)
        player.slayer_tree_nodes = slayer_tree_data["nodes_owned"]
        # is_tree/is_bonuses were already fetched above for the stamina-save roll.
        player.inner_sanctum_nodes = is_tree["nodes_owned"]

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
        )

        if is_boss:
            monster = await generate_boss(
                player, monster, combat_phases[0], 0, nsfw_enabled
            )
            monster.is_boss = True
        elif is_corrupted:
            monster = generate_corrupted_encounter(player, monster)
            combat_phases = [None]
        elif is_incubated:
            monster = await generate_incubated_monster(
                incubated_encounter, player.level
            )
            combat_phases = [None]
        else:
            treasure_chance = 1.0
            if player.get_boot_passive() == "treasure-tracker":
                treasure_chance += player.equipped_boot.passive_lvl * 0.5
            else:
                # Soul stone: treasure-tracker — 1:1 tier match to boot lvl.
                ss_treasure_tracker = player.get_soul_stone_passive("treasure-tracker")
                if ss_treasure_tracker:
                    treasure_chance += ss_treasure_tracker * 0.5
            # Inner Sanctum Vice — Treasure Sense
            treasure_chance += is_bonuses["treasure_chance_pct"]
            is_treasure = random.random() * 100 < treasure_chance
            monster = await generate_encounter(
                player,
                monster,
                is_treasure=is_treasure,
                task_species=task_species,
                slayer_tree_nodes=player.slayer_tree_nodes,
                nsfw_enabled=nsfw_enabled,
            )
            combat_phases = [None]

            # Prestige Gathering Boss (Artisan Mastery Phase 2) — rare treasure bosses
            # Each owned capstone gives an independent ~1% chance.
            # If multiple are owned, one is chosen uniformly at random when the roll succeeds.
            if (
                not is_treasure
                and not is_boss
                and not is_corrupted
                and not is_incubated
            ):
                from core.skills.mastery import get_unlocked_nodes

                mrow = await self.bot.database.skills.get_mastery(user_id, server_id)

                owned = []
                if "echo_first_vein" in get_unlocked_nodes(
                    json.loads(mrow.get("mining_alloc", "{}") or "{}"), "synergy"
                ):
                    owned.append("golem")
                if "lord_of_the_deep" in get_unlocked_nodes(
                    json.loads(mrow.get("fishing_alloc", "{}") or "{}"), "synergy"
                ):
                    owned.append("leviathan")
                if "elderheart" in get_unlocked_nodes(
                    json.loads(mrow.get("woodcutting_alloc", "{}") or "{}"), "synergy"
                ):
                    owned.append("colossus")

                if owned:
                    # 1% base chance per owned prestige capstone + bonus from extra Synergy investment
                    from core.skills.mastery import get_prestige_spawn_bonus

                    base_chance = len(owned) * 1.0
                    bonus = 0.0
                    if "golem" in owned:
                        bonus += get_prestige_spawn_bonus("mining", mrow) * 100
                    if "leviathan" in owned:
                        bonus += get_prestige_spawn_bonus("fishing", mrow) * 100
                    if "colossus" in owned:
                        bonus += get_prestige_spawn_bonus("woodcutting", mrow) * 100

                    prestige_chance = base_chance + bonus
                    if random.random() * 100 < prestige_chance:
                        chosen = random.choice(owned)
                        if chosen == "golem":
                            monster = await generate_prestige_golem(player, monster)
                        elif chosen == "leviathan":
                            monster = await generate_prestige_leviathan(player, monster)
                        else:
                            monster = await generate_prestige_colossus(player, monster)
                        combat_phases = [None]

        _DIFFICULTY_ATK_MULT = [1.0, 2.0, 2.5, 3.0, 4.0]
        _DIFFICULTY_DR = [0.0, 0.0, 0.0, 0.10, 0.25]
        if hard_mode > 0:
            mult = _DIFFICULTY_ATK_MULT[hard_mode]
            # Apply as bonus (additive with other spawn bonuses)
            monster.bonus_attack_pct += mult - 1.0
            monster.bonus_defence_pct += mult - 1.0

            # HP scaling still direct for now
            monster.hp = int(monster.hp * 1.5)
            monster.max_hp = monster.hp

            monster.difficulty_level = hard_mode
            monster.difficulty_dr = _DIFFICULTY_DR[hard_mode]

            # Dual-write live fields
            monster.attack = int(monster.base_attack * (1 + monster.bonus_attack_pct))
            monster.defence = int(
                monster.base_defence * (1 + monster.bonus_defence_pct)
            )

        # Phase 3: Ensure all combat bonuses are reset before the fight begins
        monster.reset_combat_bonuses()

        # Apply start-of-combat stat effects and passives (weapon/armor/etc.)
        engine.apply_stat_effects(player, monster)
        start_logs = engine.apply_combat_start_passives(player, monster)

        # Reset jewel charges before building the embed so the status bar shows 0
        # on the very first frame. The reset in CombatView.__init__ is kept as a guard.
        _je.reset_jewel_charges(player)
        title = "⚔️ BOSS PHASE 1" if is_boss else None
        view = CombatView(
            self.bot,
            user_id,
            server_id,
            player,
            monster,
            start_logs,
            combat_phases if is_boss else None,
            rematch_callback=self._rematch_execute,
            hard_mode=hard_mode,
            combat_streak=combat_streak,
            player_avatar_url=existing_user["appearance"],
            title_override=title,
            nsfw_enabled=nsfw_enabled,
        )

        if screen_msg.flags.components_v2:
            screen_msg = await screen_msg.edit(embed=None, view=view)
        else:
            screen_msg = await screen_msg.edit(content=None, embed=None, view=view)
        view.message = screen_msg

    @app_commands.command(
        name="dojo", description="Test your DPS against a customizable dummy."
    )
    async def dojo(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "dojo")

        from core.items.factory import load_player

        player = await load_player(user_id, existing_user, self.bot.database)

        view = DummyConfigView(self.bot, user_id, player)
        embed = view.build_embed()

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Combat(bot))
