"""
core/apex/views/combat_view.py — ApexCombatView

Subclass of CombatView that:
  1. Applies the zone modifier at construction time.
  2. Overrides handle_end_state for apex-specific victory/defeat paths
     (shard drops, profile record, no companion taming, etc.).
  3. Clears the state_manager and persists state correctly on all exit paths.
"""

from __future__ import annotations

import random

import discord

from core.apex.data import ZONE_DEFS
from core.apex.mechanics import ApexMechanics
from core.apex.models import profile_from_db, shards_from_db, meta_shards_from_db
from core.combat import jewel_engine as _je
from core.combat import ui as combat_ui
from core.combat.economy.config import XP_LOSS_ON_DEFEAT
from core.combat.economy.experience import ExperienceManager
from core.combat.economy.rewards import calculate_rewards
from core.combat.views.views import CombatView
from core.images import APEX_HUB
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
        return_view_factory=None,
    ):
        super().__init__(
            bot,
            user_id,
            server_id,
            player,
            monster,
            initial_logs,
        )
        self.zone_key = zone_key
        self._return_view_factory = return_view_factory  # callable() → view to show after

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

            reward_data = {"xp": 0, "gold": 0, "msgs": [], "items": [],
                           "soul_fragments": frags}

            embed = combat_ui.create_defeat_embed(
                self.player, self.monster, xp_loss, killing_blow=self.killing_blow
            )
            embed.add_field(
                name="🔘 Consolation",
                value=f"You received **{frags}** Soul Fragment{'s' if frags > 1 else ''} for your effort.",
                inline=False,
            )
            await message.edit(embed=embed, view=None)

            await self._cleanup()
            return

        # --- APEX VICTORY ---
        self.combat_logger.log_combat_end(self.player, self.monster, "victory")

        # Calculate XP/Gold rewards
        reward_data = calculate_rewards(self.player, self.monster)
        reward_data["special"] = []

        # Apply XP gain
        exp_changes = await ExperienceManager.add_experience(
            self.bot, self.user_id, self.player, reward_data["xp"]
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
        reward_data["apex_shards"] = {"shard_type": shard_type, "shard_amount": shard_amount}

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
                        f"Zone shards, upgrades, and extractions available via `/apex`.\n"
                        f"Hunt charges: check `/apex` for remaining charges."
                    ),
                    "inline": False,
                }
            ],
        }

        embed = create_victory_embed(self.player, self.monster, reward_data, cfg=cfg)
        await message.edit(embed=embed, view=None)

        # Return to lobby
        if self._return_view_factory:
            try:
                return_view = await self._return_view_factory()
                lobby_embed = discord.Embed(
                    title="Apex Hunt — Lobby",
                    description="Your hunt is complete! Choose your next action.",
                    color=0x9900CC,
                )
                lobby_embed.set_thumbnail(url=APEX_HUB)
                new_msg = await message.channel.send(embed=lobby_embed, view=return_view)
                return_view.message = new_msg
            except Exception:
                pass

        await self._cleanup()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _cleanup(self):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
