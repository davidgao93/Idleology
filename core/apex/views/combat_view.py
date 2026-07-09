"""
core/apex/views/combat_view.py — ApexCombatView

Subclass of CombatView that:
  1. Applies the zone modifier at construction time.
  2. Overrides handle_end_state for apex-specific victory/defeat paths
     (shard drops, profile record, no companion taming, etc.).
  3. Clears the state_manager and persists state correctly on all exit paths.
"""

from __future__ import annotations

import discord

from core.apex.data import ZONE_DEFS
from core.apex.mechanics import ApexMechanics
from core.apex.models import (
    profile_from_db,
    soul_stone_from_db,
)
from core.base_layout_view import BaseLayoutView
from core.combat import jewel_engine as _je
from core.combat import ui as combat_ui
from core.combat.economy.config import XP_LOSS_ON_DEFEAT
from core.combat.economy.experience import ExperienceManager
from core.combat.economy.rewards import calculate_rewards
from core.combat.views.views import CombatView
from core.models import Monster, Player


class ApexCombatView(CombatView):
    """
    Apex hunt combat view.  Inherits the full combat UI from CombatView and
    overrides handle_end_state to route to apex victory/defeat logic.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        monster: Monster,
        zone_key: str,
        initial_logs: dict,
        title_override: str | None = None,
        player_avatar_url: str | None = None,
    ):
        super().__init__(
            bot,
            user_id,
            server_id,
            player,
            monster,
            initial_logs,
            title_override=title_override,
            player_avatar_url=player_avatar_url,
        )
        self.zone_key = zone_key

    # ------------------------------------------------------------------
    # Override handle_end_state for apex-specific routing
    # ------------------------------------------------------------------

    async def handle_end_state(self, message, interaction: discord.Interaction):
        """Apex-specific end state: records win/loss, grants shards."""

        # --- DEFEAT ---
        if self.player.current_hp <= 0:
            self.combat_logger.log_combat_end(self.player, self.monster, "defeat")
            base_loss = int(self.player.exp * XP_LOSS_ON_DEFEAT)
            xp_loss = await ExperienceManager.remove_experience(
                self.bot, self.user_id, self.player, base_loss
            )
            self.player.current_hp = 1

            # Record loss
            await self.bot.database.apex.record_loss(
                self.user_id, self.server_id, self.zone_key
            )

            # Drop soul fragments as consolation
            frags = ApexMechanics.roll_defeat_drops()
            await self.bot.database.apex.modify_shard(
                self.user_id, self.server_id, "soul_fragments", frags
            )

            reward_data = {
                "xp": 0,
                "gold": 0,
                "msgs": [],
                "items": [],
                "soul_fragments": frags,
            }

            embed = combat_ui.create_defeat_embed(
                self.player, self.monster, xp_loss, killing_blow=self.killing_blow
            )
            embed.add_field(
                name="🔘 Consolation",
                value=f"You received **{frags}** Soul Fragment{'s' if frags > 1 else ''} for your effort.",
                inline=False,
            )
            self._sync_items(combat_ui.embed_to_container(embed), interactive=False)
            await message.edit(view=self)

            await self._cleanup()
            return

        # --- APEX VICTORY ---
        self.combat_logger.log_combat_end(self.player, self.monster, "victory")

        # Calculate XP/Gold rewards
        reward_data = calculate_rewards(self.player, self.monster)
        reward_data["special"] = []

        # Apply XP gain
        exp_changes = await ExperienceManager.add_experience(
            self.bot,
            self.user_id,
            self.player,
            reward_data["xp"],
            server_id=self.server_id,
        )
        reward_data["xp"] = exp_changes["xp_added"]
        reward_data["msgs"].extend(exp_changes["msgs"])

        # Gold
        await self.bot.database.users.modify_gold(self.user_id, reward_data["gold"])

        # Roll shard drops and persist
        drops = ApexMechanics.roll_victory_drops(self.zone_key)
        shard_type = drops["shard_type"]
        shard_amount = drops["shard_amount"]

        await self.bot.database.apex.modify_shard(
            self.user_id, self.server_id, shard_type, shard_amount
        )
        reward_data["apex_shards"] = {
            "shard_type": shard_type,
            "shard_amount": shard_amount,
        }

        # Meta shard drops
        meta_gained = {}
        for meta_key, count in drops.get("meta", {}).items():
            await self.bot.database.apex.modify_meta_shard(
                self.user_id, self.server_id, meta_key, count
            )
            meta_gained[meta_key] = count
        if meta_gained:
            reward_data["apex_meta"] = meta_gained

        # Record win
        await self.bot.database.apex.record_win(
            self.user_id, self.server_id, self.zone_key
        )

        try:
            from core.quests.mechanics import tick_quest_progress

            reward_data["msgs"].extend(
                await tick_quest_progress(
                    self.bot, self.user_id, self.server_id, "apex_complete"
                )
            )
        except Exception as e:
            print(f"[Quest tick error in apex]: {e}")

        # Persist player state
        await self.bot.database.users.update_from_player_object(self.player)
        await _je.save_jewel_state(self.bot, self.user_id, self.player)

        # Build victory embed
        zone = ZONE_DEFS.get(self.zone_key)
        from core.combat.ui.victory_screen import create_victory_embed

        cfg = {
            "title": f"Apex Victory! {zone.emoji if zone else '🏆'}",
            "extra_fields": [
                {
                    "name": f"{zone.emoji if zone else '💎'} {zone.name if zone else 'Apex Hunt'} Complete!",
                    "value": (
                        "Zone shards, upgrades, and extractions available via `/apex`.\n"
                        "Hunt charges: check `/apex` for remaining charges."
                    ),
                    "inline": False,
                }
            ],
        }

        embed = create_victory_embed(self.player, self.monster, reward_data, cfg=cfg)

        # Post-victory view lets the player challenge again or return to lobby.
        # State is NOT cleared here — _PostApexView owns cleanup on action/timeout.
        # Same message: _PostApexView is Components V2 too, so no hand-off needed.
        post_view = _PostApexView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player.name,
            self.zone_key,
        )
        post_view.set_content(embed)
        await message.edit(view=post_view)
        post_view.message = message
        self.stop()  # release this view without clearing active state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _cleanup(self):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


# ---------------------------------------------------------------------------
# Post-victory routing view
# ---------------------------------------------------------------------------


class PostApexRow(discord.ui.ActionRow["_PostApexView"]):
    @discord.ui.button(
        label="Challenge Again", style=discord.ButtonStyle.danger, emoji="⚔️"
    )
    async def challenge_again(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.view._on_challenge_again(interaction)

    @discord.ui.button(
        label="Return to Lobby", style=discord.ButtonStyle.secondary, emoji="🏹"
    )
    async def return_to_lobby(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.view._on_return_to_lobby(interaction)


class _PostApexView(BaseLayoutView):
    """
    Shown after an Apex victory.  Gives the player two choices:
      • Challenge Again — same zone, fresh monster, consumes 1 charge
      • Return to Lobby — rebuild the ApexLobbyView in-place
    State is cleared when an action is taken or when this view times out.
    BaseLayoutView.on_timeout handles clear_active + button removal automatically.
    """

    def __init__(
        self, bot, user_id: str, server_id: str, player_name: str, zone_key: str
    ):
        super().__init__(bot, user_id, server_id)
        self.player_name = player_name
        self.zone_key = zone_key
        self._processing = False
        self.row = PostApexRow()

    def set_content(self, embed: discord.Embed) -> None:
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(self.row)

    async def _on_challenge_again(self, interaction: discord.Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        # Re-check charges
        profile_row = await self.bot.database.apex.get_or_create_profile(
            self.user_id, self.server_id
        )
        profile = profile_from_db(profile_row)
        charges, new_ts = ApexMechanics.calculate_charges(profile)
        if new_ts != profile.last_charge_time:
            await self.bot.database.apex.restore_charges(
                self.user_id, self.server_id, charges, new_ts
            )

        if charges < 1:
            secs = ApexMechanics.seconds_until_next_charge(profile)
            h, rem = divmod(secs, 3600)
            m = rem // 60
            time_str = f"{h}h {m}m" if h > 0 else f"{m}m"
            self.clear_items()
            self.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"⚠️ No hunt charges remaining. Next charge in **{time_str}**."
                    )
                )
            )
            await interaction.edit_original_response(view=self)
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
            return

        # Consume 1 charge
        await self.bot.database.apex.consume_charge(self.user_id, self.server_id)

        # Load fresh player + soul stone
        from core.items.factory import load_player

        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        player = await load_player(self.user_id, user_row, self.bot.database)

        ss_row = await self.bot.database.apex.get_or_create_soul_stone(
            self.user_id, self.server_id
        )
        player.soul_stone = soul_stone_from_db(ss_row)

        # Build a fresh apex monster from the same zone (different random pick)
        apex_def = ApexMechanics.select_apex(self.zone_key)
        monster = ApexMechanics.build_apex_monster(apex_def, player.level)

        from core.combat.turns import engine

        zone_log = ApexMechanics.apply_zone_modifier(player, monster, self.zone_key)
        engine.apply_stat_effects(player, monster)
        start_logs = engine.apply_combat_start_passives(player, monster)
        if zone_log:
            start_logs = {
                f"🌐 Zone — {ZONE_DEFS[self.zone_key].modifier_name}": zone_log,
                **start_logs,
            }

        zone = ZONE_DEFS[self.zone_key]
        view = ApexCombatView(
            self.bot,
            self.user_id,
            self.server_id,
            player,
            monster,
            self.zone_key,
            start_logs,
            title_override=f"{zone.emoji} Apex Hunt — {zone.name}",
            player_avatar_url=user_row["appearance"],
        )

        await interaction.edit_original_response(view=view)
        view.message = await interaction.original_response()
        self.stop()

    async def _on_return_to_lobby(self, interaction: discord.Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        from core.apex.views.lobby_view import ApexLobbyView

        profile_row = await self.bot.database.apex.get_or_create_profile(
            self.user_id, self.server_id
        )
        profile = profile_from_db(profile_row)
        charges, new_ts = ApexMechanics.calculate_charges(profile)
        if new_ts != profile.last_charge_time:
            await self.bot.database.apex.restore_charges(
                self.user_id, self.server_id, charges, new_ts
            )
            profile.hunt_charges = charges
            profile.last_charge_time = new_ts

        # ApexLobbyView is Components V2 too — same message, no hand-off needed.
        lobby_view = ApexLobbyView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player_name,
            profile,
            charges,
        )
        await interaction.edit_original_response(view=lobby_view)
        lobby_view.message = await interaction.original_response()
        self.stop()
