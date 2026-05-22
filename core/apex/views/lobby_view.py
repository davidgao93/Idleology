"""
core/apex/views/lobby_view.py — Apex Hunt lobby (zone selection hub).

Shows the six hunt zones, charge status, per-zone win/loss records,
and routes into ApexCombatView when the player confirms a hunt.

Zones: Ashen Wastes, Storm Reach, Iron Citadel, Eternal Grove,
       Golden Vault, Shattered Realm (locked until 1+ win in all 5 base zones).
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.apex.data import ZONE_DEFS
from core.apex.mechanics import ApexMechanics
from core.apex.models import (
    ApexHuntProfile,
    meta_shards_from_db,
    profile_from_db,
    shards_from_db,
    soul_stone_from_db,
)
from core.base_view import BaseView


def _fmt_time(seconds: int) -> str:
    """Formats seconds into Xh Ym."""
    if seconds <= 0:
        return "now"
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def _build_lobby_embed(
    player_name: str,
    profile: ApexHuntProfile,
    charges: int,
    seconds_to_next: int,
) -> discord.Embed:
    """Builds the main lobby embed showing zones and charge state."""
    embed = discord.Embed(
        title="🏹 Apex Hunt — Lobby",
        description=(
            f"Welcome, **{player_name}**.\n"
            "Apex Hunts pit you against powerful monsters in lethal zones. "
            "Each zone grants unique shards used to empower your Soul Stone.\n\n"
            "Select a zone below to begin your hunt."
        ),
        color=0x9900CC,
    )

    # Charges
    charge_bar = "🔵" * charges + "⚫" * (3 - charges)
    charge_line = f"{charge_bar}  **{charges}/3 charges**"
    if charges < 3 and seconds_to_next > 0:
        charge_line += f"\nNext charge in: **{_fmt_time(seconds_to_next)}**"
    elif charges >= 3:
        charge_line += "\nAll charges ready!"
    embed.add_field(name="⚡ Hunt Charges", value=charge_line, inline=False)

    # Per-zone stats
    zone_lines = []
    for zone_key, zone in ZONE_DEFS.items():
        if zone_key == "shattered":
            continue  # shown separately
        stats = profile.zone_stats.get(zone_key, {})
        w = stats.get("wins", 0)
        l = stats.get("losses", 0)
        zone_lines.append(
            f"{zone.emoji} **{zone.name}** — W: {w} / L: {l}\n"
            f"  *{zone.shard_type.title()} Shards · {zone.modifier_name}*"
        )

    shattered = ZONE_DEFS["shattered"]
    shattered_stats = profile.zone_stats.get("shattered", {})
    sw = shattered_stats.get("wins", 0)
    sl = shattered_stats.get("losses", 0)
    if profile.shattered_realm_unlocked:
        zone_lines.append(
            f"{shattered.emoji} **{shattered.name}** — W: {sw} / L: {sl}\n"
            f"  *{shattered.shard_type.title()} Shards · {shattered.modifier_name}*"
        )
    else:
        zone_lines.append(
            f"🔒 **{shattered.name}** — *Locked*\n"
            "  *Earn at least 1 win in each of the 5 base zones to unlock.*"
        )

    embed.add_field(name="🗺️ Zones", value="\n".join(zone_lines), inline=False)
    embed.set_footer(
        text="Apex Hunts consume 1 charge per attempt. "
             "Charges regenerate 1 per 8 hours (max 3)."
    )
    return embed


def _build_zone_confirm_embed(
    zone_key: str,
    profile: ApexHuntProfile,
    charges: int,
) -> discord.Embed:
    """Builds the zone confirmation embed shown after selecting a zone."""
    zone = ZONE_DEFS[zone_key]
    stats = profile.zone_stats.get(zone_key, {})
    w = stats.get("wins", 0)
    l = stats.get("losses", 0)

    embed = discord.Embed(
        title=f"{zone.emoji} {zone.name}",
        description=(
            f"**Zone Modifier — {zone.modifier_name}:**\n"
            f"{zone.modifier_desc}\n\n"
            "Are you ready to enter? This will consume **1 hunt charge**."
        ),
        color=zone.color,
    )
    embed.add_field(name="🔮 Shard Type", value=zone.shard_type.title(), inline=True)
    embed.add_field(name="📊 Your Record", value=f"W: {w} / L: {l}", inline=True)
    embed.add_field(
        name="⚡ Charges After",
        value=f"**{max(0, charges - 1)}/3**",
        inline=True,
    )
    embed.set_footer(
        text="On victory: item shards + chance at meta shards. "
             "On defeat: 1–3 soul fragments consolation."
    )
    return embed


class ApexLobbyView(BaseView):
    """
    Hub view for apex hunt zone selection.

    Loads charge state fresh on construction. Zone buttons route to a
    confirmation step, and confirming starts ApexCombatView in-place.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player_name: str,
        profile: ApexHuntProfile,
        charges: int,
        *,
        parent=None,
    ):
        if parent:
            super().__init__(bot, parent=parent)
        else:
            super().__init__(bot, user_id, server_id)

        self.player_name = player_name
        self.profile = profile
        self._charges = charges
        self._processing = False
        self._selected_zone: str | None = None

        self._build_zone_buttons()

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _build_zone_buttons(self):
        """Adds the six zone buttons and a Soul Stone shortcut."""
        self.clear_items()

        _ORDER = ["ashen", "storm", "citadel", "grove", "vault"]
        for zone_key in _ORDER:
            zone = ZONE_DEFS[zone_key]
            btn = Button(
                label=zone.name,
                style=ButtonStyle.primary,
                emoji=zone.emoji,
                row=0,
            )
            btn.callback = self._make_zone_callback(zone_key)
            self.add_item(btn)

        # Shattered Realm — row 1
        shattered = ZONE_DEFS["shattered"]
        if self.profile.shattered_realm_unlocked:
            shat_btn = Button(
                label=shattered.name,
                style=ButtonStyle.danger,
                emoji=shattered.emoji,
                row=1,
            )
            shat_btn.callback = self._make_zone_callback("shattered")
        else:
            shat_btn = Button(
                label="Shattered Realm (Locked)",
                style=ButtonStyle.secondary,
                emoji="🔒",
                disabled=True,
                row=1,
            )
        self.add_item(shat_btn)

        # Soul Stone shortcut
        ss_btn = Button(
            label="Soul Stone",
            style=ButtonStyle.secondary,
            emoji="💎",
            row=1,
        )
        ss_btn.callback = self._open_soul_stone
        self.add_item(ss_btn)

        # Close
        close_btn = Button(
            label="Close",
            style=ButtonStyle.secondary,
            emoji="✖️",
            row=1,
        )
        close_btn.callback = self._close
        self.add_item(close_btn)

    def _make_zone_callback(self, zone_key: str):
        async def _callback(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            await interaction.response.defer()
            self._selected_zone = zone_key

            # Re-fetch charges to show fresh state
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
            self._charges = charges
            self.profile = profile

            if charges < 1:
                secs = ApexMechanics.seconds_until_next_charge(profile)
                await interaction.edit_original_response(
                    content=(
                        f"⚠️ No hunt charges remaining. "
                        f"Next charge in **{_fmt_time(secs)}**."
                    ),
                    embed=None,
                    view=self,
                )
                return

            # Show zone confirmation
            embed = _build_zone_confirm_embed(zone_key, profile, charges)
            self.clear_items()

            confirm_btn = Button(
                label="Confirm Hunt",
                style=ButtonStyle.danger,
                emoji="⚔️",
                row=0,
            )
            confirm_btn.callback = self._confirm_hunt
            self.add_item(confirm_btn)

            back_btn = Button(label="Back", style=ButtonStyle.secondary, row=0)
            back_btn.callback = self._back_to_zones
            self.add_item(back_btn)

            await interaction.edit_original_response(embed=embed, view=self)

        return _callback

    # ------------------------------------------------------------------
    # Confirm hunt
    # ------------------------------------------------------------------

    async def _confirm_hunt(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        if not self._selected_zone:
            self._processing = False
            return

        # Re-check charges one last time (double-click guard / race)
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
            await interaction.edit_original_response(
                content=(
                    f"⚠️ No hunt charges remaining. "
                    f"Next charge in **{_fmt_time(secs)}**."
                ),
                embed=None,
                view=None,
            )
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
            return

        # Consume 1 charge
        await self.bot.database.apex.consume_charge(self.user_id, self.server_id)

        # Load fresh player with full gear
        from core.items.factory import load_player

        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        player = await load_player(self.user_id, user_row, self.bot.database)

        # Attach soul stone
        ss_row = await self.bot.database.apex.get_or_create_soul_stone(
            self.user_id, self.server_id
        )
        player.soul_stone = soul_stone_from_db(ss_row)

        # Build apex monster
        zone_key = self._selected_zone
        apex_def = ApexMechanics.select_apex(zone_key)
        monster = ApexMechanics.build_apex_monster(apex_def, player.level)

        # Apply zone modifier at combat start
        from core.combat.turns import engine

        zone_log = ApexMechanics.apply_zone_modifier(player, monster, zone_key)
        engine.apply_stat_effects(player, monster)
        start_logs = engine.apply_combat_start_passives(player, monster)

        # Prepend zone modifier log if present
        if zone_log:
            start_logs = {f"🌐 Zone — {ZONE_DEFS[zone_key].modifier_name}": zone_log, **start_logs}

        # Build initial combat embed
        from core.combat import ui as combat_ui
        from core.apex.views.combat_view import ApexCombatView

        zone = ZONE_DEFS[zone_key]
        embed = combat_ui.create_combat_embed(
            player, monster, start_logs,
            title_override=f"{zone.emoji} Apex Hunt — {zone.name}",
        )

        view = ApexCombatView(
            self.bot,
            self.user_id,
            self.server_id,
            player,
            monster,
            zone_key,
            start_logs,
        )

        await interaction.edit_original_response(embed=embed, view=view)
        view.message = await interaction.original_response()

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    async def _back_to_zones(self, interaction: Interaction):
        await interaction.response.defer()
        self._selected_zone = None
        self._processing = False
        self._build_zone_buttons()

        # Re-fetch profile for fresh charge display
        profile_row = await self.bot.database.apex.get_or_create_profile(
            self.user_id, self.server_id
        )
        profile = profile_from_db(profile_row)
        charges, new_ts = ApexMechanics.calculate_charges(profile)
        if new_ts != profile.last_charge_time:
            await self.bot.database.apex.restore_charges(
                self.user_id, self.server_id, charges, new_ts
            )
        self._charges = charges
        self.profile = profile
        secs = ApexMechanics.seconds_until_next_charge(profile)

        embed = _build_lobby_embed(self.player_name, profile, charges, secs)
        await interaction.edit_original_response(embed=embed, view=self)

    async def _open_soul_stone(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        await interaction.response.defer()

        from core.apex.views.soul_stone_view import SoulStoneView, _build_soul_stone_embed
        from core.items.factory import load_player

        # Load full player (ImprintView needs equipped gear access)
        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        player = await load_player(self.user_id, user_row, self.bot.database)

        view = SoulStoneView(
            self.bot, self.user_id, self.server_id,
            player, parent=self,
        )

        # Load soul stone data and build embed
        ss_row = await self.bot.database.apex.get_or_create_soul_stone(
            self.user_id, self.server_id
        )
        shards_row = await self.bot.database.apex.get_or_create_shards(
            self.user_id, self.server_id
        )
        meta_row = await self.bot.database.apex.get_or_create_meta_shards(
            self.user_id, self.server_id
        )

        soul_stone = soul_stone_from_db(ss_row)
        shards = shards_from_db(shards_row)
        meta = meta_shards_from_db(meta_row)

        embed = _build_soul_stone_embed(soul_stone, shards, meta, player.name)
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.message = msg

    async def _close(self, interaction: Interaction):
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.edit_original_response(
            content="Apex lobby closed.", embed=None, view=None
        )
        self.stop()
