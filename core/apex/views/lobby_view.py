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
from core.apex.mechanics import FRAGMENT_CHARGE_COST, MAX_CHARGES, ApexMechanics
from core.apex.models import (
    ApexHuntProfile,
    meta_shards_from_db,
    profile_from_db,
    shards_from_db,
    soul_stone_from_db,
)
from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.emojis import APEX_SHARD_EMOJI, SOUL_FRAGMENT, SOUL_STONE
from core.images import APEX_HUB, LUCIEN_PORTRAIT, LUCIEN_THUMBNAIL
from core.npc_voices import get_quip


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
            f"*{get_quip('apex')}*\n\n"
            f"Welcome back, **{player_name}**. "
            "Apex Hunts pit you against powerful monsters in lethal zones. "
            "Each zone grants unique shards used to empower your Soul Stone.\n\n"
            "Select a zone below to begin your hunt."
        ),
        color=0x9900CC,
    )
    embed.set_author(name="Lucien", icon_url=LUCIEN_PORTRAIT)
    embed.set_thumbnail(url=LUCIEN_THUMBNAIL)

    # Charges
    charge_bar = "🔵" * charges + "⚫" * (MAX_CHARGES - charges)
    charge_line = f"{charge_bar}  **{charges}/{MAX_CHARGES} charges**"
    if charges < MAX_CHARGES and seconds_to_next > 0:
        charge_line += f"\nNext charge in: **{_fmt_time(seconds_to_next)}**"
    elif charges >= MAX_CHARGES:
        charge_line += "\nAll charges ready!"
    embed.add_field(name="⚡ Hunt Charges", value=charge_line, inline=False)

    # Per-zone stats
    zone_lines = []
    for zone_key, zone in ZONE_DEFS.items():
        if zone_key == "shattered":
            continue  # shown separately
        stats = profile.zone_stats.get(zone_key, {})
        w = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        zone_lines.append(
            f"{zone.emoji} **{zone.name}** — W: {w} / L: {losses}\n"
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
        f"Charges regenerate 1 per 2 hours (max {MAX_CHARGES})."
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
    losses = stats.get("losses", 0)

    embed = discord.Embed(
        title=f"{zone.emoji} {zone.name}",
        description=(
            f"**Zone Modifier — {zone.modifier_name}:**\n"
            f"{zone.modifier_desc}\n\n"
            "Are you ready to enter? This will consume **1 hunt charge**."
        ),
        color=zone.color,
    )
    shard_emoji = APEX_SHARD_EMOJI.get(zone.shard_type, f"{SOUL_FRAGMENT}")
    embed.add_field(
        name="Shard Type", value=f"{shard_emoji} {zone.shard_type.title()}", inline=True
    )
    embed.add_field(name="📊 Your Record", value=f"W: {w} / L: {losses}", inline=True)
    embed.add_field(
        name="⚡ Charges After",
        value=f"**{max(0, charges - 1)}/{MAX_CHARGES}**",
        inline=True,
    )
    embed.set_thumbnail(url=APEX_HUB)
    embed.set_footer(
        text="On victory: item shards + chance at meta shards. "
        "On defeat: 1–3 soul fragments consolation."
    )
    return embed


class ApexLobbyView(BaseLayoutView):
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

        self._show_zone_list()

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _build_zone_list_rows(self) -> list[discord.ui.ActionRow]:
        """Builds the six zone buttons and a Soul Stone shortcut."""
        row0 = discord.ui.ActionRow()
        row1 = discord.ui.ActionRow()

        _ORDER = ["ashen", "storm", "citadel", "grove", "vault"]
        for zone_key in _ORDER:
            zone = ZONE_DEFS[zone_key]
            btn = Button(
                label=zone.name,
                style=ButtonStyle.primary,
                emoji=zone.emoji,
            )
            btn.callback = self._make_zone_callback(zone_key)
            row0.add_item(btn)

        # Shattered Realm — row 1
        shattered = ZONE_DEFS["shattered"]
        if self.profile.shattered_realm_unlocked:
            shat_btn = Button(
                label=shattered.name,
                style=ButtonStyle.danger,
                emoji=shattered.emoji,
            )
            shat_btn.callback = self._make_zone_callback("shattered")
        else:
            shat_btn = Button(
                label="Shattered Realm (Locked)",
                style=ButtonStyle.secondary,
                emoji="🔒",
                disabled=True,
            )
        row1.add_item(shat_btn)

        # Soul Stone shortcut
        ss_btn = Button(
            label="Soul Stone",
            style=ButtonStyle.secondary,
            emoji=SOUL_STONE,
        )
        ss_btn.callback = self._open_soul_stone
        row1.add_item(ss_btn)

        # Close
        close_btn = Button(
            label="Close",
            style=ButtonStyle.secondary,
            emoji="✖️",
        )
        close_btn.callback = self._close
        row1.add_item(close_btn)

        return [row0, row1]

    def _show_zone_list(self) -> None:
        secs = ApexMechanics.seconds_until_next_charge(self.profile)
        embed = _build_lobby_embed(self.player_name, self.profile, self._charges, secs)
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(embed))
        for row in self._build_zone_list_rows():
            self.add_item(row)

    def _make_zone_callback(self, zone_key: str):
        async def _show_zone_confirm(interaction: Interaction):
            """(Re)builds and displays the zone confirmation screen for zone_key."""
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

            # Show zone confirmation — always the full zone view, even out of charges
            embed = _build_zone_confirm_embed(zone_key, profile, charges)
            row = discord.ui.ActionRow()

            if charges < 1:
                secs = ApexMechanics.seconds_until_next_charge(profile)
                embed.color = 0xCC0000
                embed.add_field(
                    name="⚠️ No Hunt Charges",
                    value=(
                        "You have no hunt charges remaining. "
                        f"Next charge in **{_fmt_time(secs)}**."
                    ),
                    inline=False,
                )
                shards_row = await self.bot.database.apex.get_or_create_shards(
                    self.user_id, self.server_id
                )
                fragments = shards_row.get("soul_fragments", 0)
                embed.add_field(
                    name=f"{SOUL_FRAGMENT} Soul Fragments",
                    value=f"You have **{fragments}** Soul Fragment{'s' if fragments != 1 else ''}.",
                    inline=False,
                )
                if fragments >= FRAGMENT_CHARGE_COST:
                    convert_btn = Button(
                        label=f"Convert {FRAGMENT_CHARGE_COST} Fragments → 1 Charge",
                        style=ButtonStyle.primary,
                        emoji=SOUL_FRAGMENT,
                    )
                    convert_btn.callback = _convert_fragments
                    row.add_item(convert_btn)
            else:
                confirm_btn = Button(
                    label="Confirm Hunt",
                    style=ButtonStyle.danger,
                    emoji="⚔️",
                )
                confirm_btn.callback = self._confirm_hunt
                row.add_item(confirm_btn)

            back_btn = Button(label="Back", style=ButtonStyle.secondary)
            back_btn.callback = self._back_to_zones
            row.add_item(back_btn)

            self.clear_items()
            self.add_item(combat_ui.embed_to_container(embed))
            self.add_item(row)

            await interaction.edit_original_response(view=self)

        async def _callback(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()
            self._selected_zone = zone_key
            await _show_zone_confirm(interaction)
            self._processing = False

        async def _convert_fragments(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            shards_row = await self.bot.database.apex.get_or_create_shards(
                self.user_id, self.server_id
            )
            if shards_row.get("soul_fragments", 0) >= FRAGMENT_CHARGE_COST:
                async with self.bot.database.transaction():
                    await self.bot.database.apex.modify_shard(
                        self.user_id,
                        self.server_id,
                        "soul_fragments",
                        -FRAGMENT_CHARGE_COST,
                    )
                    await self.bot.database.apex.add_charge(
                        self.user_id, self.server_id, 1, MAX_CHARGES
                    )

            await _show_zone_confirm(interaction)
            self._processing = False

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
            self.clear_items()
            self.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay(
                        f"⚠️ No hunt charges remaining. "
                        f"Next charge in **{_fmt_time(secs)}**."
                    )
                )
            )
            await interaction.edit_original_response(view=self)
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
            start_logs = {
                f"🌐 Zone — {ZONE_DEFS[zone_key].modifier_name}": zone_log,
                **start_logs,
            }

        # Build initial combat view
        from core.apex.views.combat_view import ApexCombatView
        from core.combat import jewel_engine as _je

        # Reset jewel charges before building the layout so the status bar
        # shows 0 on the very first frame. The reset in CombatView.__init__
        # is kept as a guard.
        _je.reset_jewel_charges(player)
        zone = ZONE_DEFS[zone_key]
        view = ApexCombatView(
            self.bot,
            self.user_id,
            self.server_id,
            player,
            monster,
            zone_key,
            start_logs,
            title_override=f"{zone.emoji} Apex Hunt — {zone.name}",
            player_avatar_url=user_row["appearance"],
        )

        await interaction.edit_original_response(view=view)
        view.message = await interaction.original_response()

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    async def _back_to_zones(self, interaction: Interaction):
        await interaction.response.defer()
        self._selected_zone = None
        self._processing = False

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

        self._show_zone_list()
        await interaction.edit_original_response(view=self)

    async def _open_soul_stone(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        from core.apex.views.soul_stone_view import (
            SoulStoneView,
            _build_soul_stone_embed,
        )
        from core.items.factory import load_player

        # Load full player (needed for player.name display in the Soul Stone hub)
        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        player = await load_player(self.user_id, user_row, self.bot.database)

        view = SoulStoneView(
            self.bot,
            self.user_id,
            self.server_id,
            player,
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

        # SoulStoneView stays classic — a genuine scene change out of the
        # apex hunt loop — so it gets a fresh message rather than reusing
        # this one.
        view.apply_gating(soul_stone)
        embed = _build_soul_stone_embed(soul_stone, shards, meta, player.name)
        await combat_ui.freeze_and_handoff(interaction.message, embed, view)
        self.stop()  # lobby view is superseded; SoulStoneView has the "← Lobby" back button

    async def _close(self, interaction: Interaction):
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()
