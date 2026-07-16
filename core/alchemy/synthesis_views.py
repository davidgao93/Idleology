"""
core/alchemy/synthesis_views.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Synthesis hub: disenchant boss keys, elemental materials, and essences into
Cosmic Dust via up to 3 timed queues (unlocked by alchemy level), and spend
Cosmic Dust (+ gold) to synthesize boss keys.

Layout
------
AlchemySynthesisHubView   — main screen; shows all queue slots, dust balance, reference table
  └─ _DisenchantSelectView  — category picker → auto-loads item picker; confirm sends to queue
  └─ _SynthesizeSelectView  — item picker → auto-opens quantity modal → instant craft
"""

from __future__ import annotations

from datetime import datetime, timedelta

import discord
from discord import ButtonStyle, Interaction, ui

from core.alchemy.mechanics import AlchemyMechanics
from core.base_view import BaseView
from core.emojis import (
    CAPRICIOUS_CARP,
    COSMIC_DUST,
    DRAGON_KEY,
    ESSENCE_COMMON,
    GOLD_COIN,
    PARADISE_JEWEL_UNCUT,
)
from core.images import ELYNDRA_PORTRAIT, ELYNDRA_THUMBNAIL
from core.npc_voices import get_quip
from core.paradise.mechanics import dust_from_jewel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Item categories for the disenchant picker
_CATEGORY_BOSS_KEYS = "boss_keys"
_CATEGORY_ELEMENTAL = "elemental"
_CATEGORY_ESSENCES = "essences"
_CATEGORY_JEWELS = "jewels"

_CATEGORY_LABELS = {
    _CATEGORY_BOSS_KEYS: "Boss Keys",
    _CATEGORY_ELEMENTAL: "Elemental Materials",
    _CATEGORY_ESSENCES: "Essences",
    _CATEGORY_JEWELS: "Paradise Jewels",
}

_JEWEL_ITEM_TYPE = "paradise_jewel"
_JEWEL_SYNTH_DUST = 20_000
_JEWEL_SYNTH_GOLD = 10_000_000
_JEWEL_DISENCHANT_MINS = 240  # 4 hours per jewel


def _fmt_duration(td: timedelta) -> str:
    total = max(0, int(td.total_seconds()))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _get_per_item_minutes(item_type: str, alchemy_level: int) -> int:
    """Minutes to disenchant one item of the given type."""
    if item_type == _JEWEL_ITEM_TYPE:
        return _JEWEL_DISENCHANT_MINS
    return AlchemyMechanics.get_disenchant_minutes(alchemy_level)


async def _build_synthesis_hub(
    bot, user_id: str, server_id: str
) -> AlchemySynthesisHubView:
    alchemy_level = await bot.database.alchemy.get_level(user_id)
    cosmic_dust = await bot.database.alchemy.get_cosmic_dust(user_id)
    all_queues = await bot.database.alchemy.get_all_queues(user_id)
    player_gold = await bot.database.users.get_gold(user_id)
    return AlchemySynthesisHubView(
        bot,
        user_id,
        server_id,
        alchemy_level,
        cosmic_dust,
        all_queues,
        player_gold,
    )


# ---------------------------------------------------------------------------
# Synthesis Hub
# ---------------------------------------------------------------------------


class AlchemySynthesisHubView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        alchemy_level: int,
        cosmic_dust: int,
        all_queues: list,  # [(slot, item_type, quantity, start_time), ...]
        player_gold: int,
    ):
        super().__init__(bot, user_id, server_id)
        self.alchemy_level = alchemy_level
        self.cosmic_dust = cosmic_dust
        self.all_queues = all_queues
        self.player_gold = player_gold
        self._processing = False

        slot_count = AlchemyMechanics.get_disenchant_queue_slots(alchemy_level)
        active_slots = {q[0] for q in all_queues}

        # Any ready queues to collect?
        any_ready = False
        for _, item_type, qty, start_str in all_queues:
            item_mins = _get_per_item_minutes(item_type, alchemy_level)
            end = datetime.fromisoformat(start_str) + timedelta(minutes=item_mins * qty)
            if datetime.now() >= end:
                any_ready = True
                break

        # Disenchant — disabled if all unlocked slots are busy
        all_busy = len(active_slots) >= slot_count
        disenchant_btn = ui.Button(
            label="Disenchant",
            style=ButtonStyle.blurple,
            emoji="🔨",
            row=0,
            disabled=all_busy,
        )
        disenchant_btn.callback = self._on_disenchant
        self.add_item(disenchant_btn)

        collect_btn = ui.Button(
            label="Collect Dust",
            style=ButtonStyle.green if any_ready else ButtonStyle.secondary,
            emoji=COSMIC_DUST,
            row=0,
            disabled=not any_ready,
        )
        collect_btn.callback = self._on_collect
        self.add_item(collect_btn)

        synth_btn = ui.Button(
            label="Synthesize Item",
            style=ButtonStyle.primary,
            emoji="⚗️",
            row=0,
        )
        synth_btn.callback = self._on_synthesize
        self.add_item(synth_btn)

        back_btn = ui.Button(
            label="Back",
            style=ButtonStyle.secondary,
            emoji="⬅️",
            row=1,
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        level = self.alchemy_level
        slot_count = AlchemyMechanics.get_disenchant_queue_slots(level)
        discount = level

        embed = discord.Embed(title="⚗️ Synthesis", color=discord.Color.teal())
        embed.set_author(name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT)
        embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)
        embed.set_footer(text=get_quip("alchemy"))
        embed.description = (
            f"**Cosmic Dust:** {COSMIC_DUST} {self.cosmic_dust:,}\n"
            f"**Gold:** {GOLD_COIN} {self.player_gold:,}\n"
            f"**Alchemy Lv {level}** — {discount}% dust discount · {slot_count} queue slot(s)"
        )

        # --- Queue slots ---
        queues_by_slot = {q[0]: q for q in self.all_queues}
        for slot in range(1, slot_count + 1):
            if slot not in queues_by_slot:
                embed.add_field(
                    name=f"🔨 Queue {slot} — Empty",
                    value="*No active task. Click **Disenchant** to begin.*",
                    inline=False,
                )
            else:
                _, item_type, qty, start_str = queues_by_slot[slot]
                item_mins = _get_per_item_minutes(item_type, level)
                end = datetime.fromisoformat(start_str) + timedelta(
                    minutes=item_mins * qty
                )
                now = datetime.now()
                name, emoji, yield_val = _get_item_display(item_type)
                if item_type == _JEWEL_ITEM_TYPE:
                    yield_val = dust_from_jewel(level)
                total_dust = yield_val * qty

                if now >= end:
                    embed.add_field(
                        name=f"🔨 Queue {slot} — ✅ READY",
                        value=(
                            f"{emoji} **{qty}× {name}**\n"
                            f"Yield: {COSMIC_DUST} **{total_dust:,} Cosmic Dust** — click **Collect Dust** to claim!"
                        ),
                        inline=False,
                    )
                else:
                    remaining = end - now
                    embed.add_field(
                        name=f"🔨 Queue {slot} — ⏳ In Progress",
                        value=(
                            f"{emoji} **{qty}× {name}**\n"
                            f"Yield: {COSMIC_DUST} {total_dust:,} Cosmic Dust\n"
                            f"Ready in: **{_fmt_duration(remaining)}**"
                        ),
                        inline=False,
                    )

        # --- Reference table (split so no single field can exceed Discord's 1024-char cap) ---
        synth_lines = []
        for col, name in AlchemyMechanics.KEY_DISPLAY_NAMES.items():
            emoji = AlchemyMechanics.KEY_EMOJIS[col]
            de_yield = AlchemyMechanics.DUST_YIELD[col]
            synth_dust = AlchemyMechanics.get_synthesis_dust_cost(level, col)
            synth_lines.append(
                f"{emoji} **{name}** — DE: {de_yield} {COSMIC_DUST} · Synth: {synth_dust:,} {COSMIC_DUST} + {GOLD_COIN} 100k"
            )
        embed.add_field(
            name="⚗️ Synthesizable (Disenchant · Synthesis)",
            value="\n".join(synth_lines),
            inline=False,
        )
        jewel_yield = dust_from_jewel(level)
        embed.add_field(
            name=f"{PARADISE_JEWEL_UNCUT} Jewel of Paradise",
            value=(
                f"DE: {jewel_yield:,} {COSMIC_DUST} · "
                f"Synth: {_JEWEL_SYNTH_DUST:,} {COSMIC_DUST} + {GOLD_COIN} 10M"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔨 Disenchant Only",
            value="**Elemental Keys** and **Essences** cannot be synthesized",
            inline=False,
        )

        return embed

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _on_disenchant(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        # Find the first free slot
        slot_count = AlchemyMechanics.get_disenchant_queue_slots(self.alchemy_level)
        active_slots = {q[0] for q in self.all_queues}
        free_slot = next(
            (s for s in range(1, slot_count + 1) if s not in active_slots), None
        )
        if free_slot is None:
            await interaction.followup.send("All queue slots are busy.", ephemeral=True)
            return

        view = _DisenchantSelectView(
            self.bot,
            self.user_id,
            self.server_id,
            self.alchemy_level,
            free_slot,
        )
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    async def _on_collect(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        level = self.alchemy_level
        collected_total = 0
        collected_lines = []

        all_queues = await self.bot.database.alchemy.get_all_queues(self.user_id)
        for slot, item_type, qty, start_str in all_queues:
            item_mins = _get_per_item_minutes(item_type, level)
            end = datetime.fromisoformat(start_str) + timedelta(minutes=item_mins * qty)
            if datetime.now() < end:
                continue
            name, emoji, yield_val = _get_item_display(item_type)
            if item_type == _JEWEL_ITEM_TYPE:
                yield_val = dust_from_jewel(level)
            dust = yield_val * qty
            collected_total += dust
            collected_lines.append(f"{emoji} {qty}× {name} → {COSMIC_DUST} {dust:,}")
            await self.bot.database.alchemy.clear_synthesis_queue(self.user_id, slot)

        if collected_total == 0:
            await interaction.followup.send(
                "Nothing is ready to collect yet.", ephemeral=True
            )
            return

        await self.bot.database.alchemy.modify_cosmic_dust(
            self.user_id, collected_total
        )

        view = await _build_synthesis_hub(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        embed.colour = discord.Color.gold()
        embed.title = f"{COSMIC_DUST} Collected {collected_total:,} Cosmic Dust!"
        embed.description = (
            "\n".join(collected_lines) + "\n\n" + (embed.description or "")
        )
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    async def _on_synthesize(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = _SynthesizeSelectView(
            self.bot,
            self.user_id,
            self.server_id,
            self.alchemy_level,
            self.cosmic_dust,
            self.player_gold,
        )
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()

    async def _on_back(self, interaction: Interaction) -> None:
        from core.alchemy.views import _hub_from_db

        await interaction.response.defer()
        view = await _hub_from_db(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()


# ---------------------------------------------------------------------------
# Item display helper — works for all categories
# ---------------------------------------------------------------------------


def _get_item_display(item_type: str) -> tuple[str, str, int]:
    """Returns (name, emoji, dust_yield) for any disenchantable item type."""
    if item_type == _JEWEL_ITEM_TYPE:
        return (
            "Jewel of Paradise",
            f"{PARADISE_JEWEL_UNCUT}",
            0,
        )  # yield is level-dependent; computed at call sites
    if item_type in AlchemyMechanics.KEY_DISPLAY_NAMES:
        return (
            AlchemyMechanics.KEY_DISPLAY_NAMES[item_type],
            AlchemyMechanics.KEY_EMOJIS[item_type],
            AlchemyMechanics.DUST_YIELD[item_type],
        )
    if item_type in AlchemyMechanics.ELEMENTAL_DISPLAY_NAMES:
        return (
            AlchemyMechanics.ELEMENTAL_DISPLAY_NAMES[item_type],
            AlchemyMechanics.ELEMENTAL_EMOJIS[item_type],
            AlchemyMechanics.ELEMENTAL_DUST_YIELD[item_type],
        )
    if item_type in AlchemyMechanics.ESSENCE_DISPLAY_NAMES:
        return (
            AlchemyMechanics.ESSENCE_DISPLAY_NAMES[item_type],
            AlchemyMechanics.ESSENCE_EMOJIS[item_type],
            AlchemyMechanics.ESSENCE_DUST_YIELD[item_type],
        )
    return (item_type, "❓", 0)


async def _get_item_owned(bot, user_id: str, server_id: str, item_type: str) -> int:
    """Returns how many of an item the player owns, across all item categories."""
    if item_type == _JEWEL_ITEM_TYPE:
        uber = await bot.database.uber.get_uber_progress(user_id, server_id)
        return uber.get("paradise_jewels", 0)
    if item_type in AlchemyMechanics.KEY_DISPLAY_NAMES:
        return await bot.database.users.get_currency(user_id, item_type)
    if item_type in AlchemyMechanics.ELEMENTAL_DISPLAY_NAMES:
        return await bot.database.alchemy.get_uber_material(
            user_id, server_id, item_type
        )
    if item_type in AlchemyMechanics.ESSENCE_DISPLAY_NAMES:
        return await bot.database.alchemy.get_essence_quantity(user_id, item_type)
    return 0


async def _deduct_item(
    bot, user_id: str, server_id: str, item_type: str, qty: int
) -> None:
    """Deducts qty of item from the appropriate table."""
    if item_type == _JEWEL_ITEM_TYPE:
        await bot.database.uber.increment_paradise_jewels(user_id, server_id, -qty)
    elif item_type in AlchemyMechanics.KEY_DISPLAY_NAMES:
        await bot.database.users.modify_currency(user_id, item_type, -qty)
    elif item_type in AlchemyMechanics.ELEMENTAL_DISPLAY_NAMES:
        await bot.database.alchemy.deduct_uber_material(
            user_id, server_id, item_type, qty
        )
    elif item_type in AlchemyMechanics.ESSENCE_DISPLAY_NAMES:
        await bot.database.alchemy.deduct_essence(user_id, item_type, qty)


# ---------------------------------------------------------------------------
# Disenchant — category select → auto-load item select + queue
# ---------------------------------------------------------------------------


# Category dropdown replaced with buttons — no _DisenchantCategorySelect class needed.


class _DisenchantItemSelect(ui.Select):
    def __init__(self, options_data: list[dict]) -> None:
        opts = [
            discord.SelectOption(
                label=d["name"][:100],
                description=d["select_desc"][:100],
                value=d["col"],
                emoji=d["emoji"],
            )
            for d in options_data
            if d["owned"] > 0
        ]
        if not opts:
            opts = [discord.SelectOption(label="No valid items owned", value="_none")]
        super().__init__(
            placeholder="Select an item to disenchant…", options=opts, row=1
        )
        self._data_by_col = {d["col"]: d for d in options_data}
        self.selected: str | None = None

    async def callback(self, interaction: Interaction) -> None:
        if self.values[0] == "_none":
            await interaction.response.send_message(
                "You have no valid items to disenchant.", ephemeral=True
            )
            return
        self.selected = self.values[0]
        await interaction.response.defer()


class _DisenchantQuantityModal(ui.Modal, title="How many items to disenchant?"):
    quantity = ui.TextInput(
        label="Quantity",
        placeholder="Enter a number (e.g. 5)",
        min_length=1,
        max_length=4,
    )

    def __init__(self, parent: _DisenchantSelectView, item_type: str, owned: int):
        super().__init__()
        self._parent = parent
        self._item_type = item_type
        self._owned = owned

    async def on_submit(self, interaction: Interaction) -> None:
        raw = self.quantity.value.strip()
        if not raw.isdigit() or int(raw) < 1:
            await interaction.response.send_message(
                "Please enter a positive whole number.", ephemeral=True
            )
            return

        qty = int(raw)
        if qty > self._owned:
            name, _, _ = _get_item_display(self._item_type)
            await interaction.response.send_message(
                f"You only have **{self._owned}** {name}.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Guard: slot not grabbed by a race condition
        existing = await self._parent.bot.database.alchemy.get_synthesis_queue(
            self._parent.user_id, self._parent.target_slot
        )
        if existing:
            await interaction.followup.send(
                "That queue slot is now busy. Try again.", ephemeral=True
            )
            return

        await _deduct_item(
            self._parent.bot,
            self._parent.user_id,
            self._parent.server_id,
            self._item_type,
            qty,
        )
        await self._parent.bot.database.alchemy.start_disenchant(
            self._parent.user_id,
            self._item_type,
            qty,
            datetime.now().isoformat(),
            self._parent.target_slot,
        )

        level = self._parent.alchemy_level
        item_mins = _get_per_item_minutes(self._item_type, level)
        total_mins = item_mins * qty
        name, emoji, yield_val = _get_item_display(self._item_type)
        if self._item_type == _JEWEL_ITEM_TYPE:
            yield_val = dust_from_jewel(level)
        total_dust = yield_val * qty

        # Format time display
        if total_mins >= 60:
            time_str = (
                f"{total_mins // 60}h {total_mins % 60}m"
                if total_mins % 60
                else f"{total_mins // 60}h"
            )
        else:
            time_str = f"{total_mins} minutes"

        view = await _build_synthesis_hub(
            self._parent.bot, self._parent.user_id, self._parent.server_id
        )
        embed = view.build_embed()
        embed.colour = discord.Color.blurple()
        embed.title = f"🔨 Queued: {qty}× {name} (Slot {self._parent.target_slot})"
        embed.description = (
            f"{emoji} **{qty}× {name}** sent to queue slot {self._parent.target_slot}.\n"
            f"⏳ Ready in **{time_str}** · Yield: {COSMIC_DUST} **{total_dust:,} Cosmic Dust**\n\n"
        ) + (embed.description or "")
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self._parent.stop()


_CATEGORY_DEFS = [
    (_CATEGORY_BOSS_KEYS, "Boss Keys", f"{DRAGON_KEY}"),
    (_CATEGORY_ELEMENTAL, "Elemental", f"{CAPRICIOUS_CARP}"),
    (_CATEGORY_ESSENCES, "Essences", f"{ESSENCE_COMMON}"),
    (_CATEGORY_JEWELS, "Jewels", f"{PARADISE_JEWEL_UNCUT}"),
]


class _DisenchantSelectView(BaseView):
    def __init__(
        self, bot, user_id: str, server_id: str, alchemy_level: int, target_slot: int
    ) -> None:
        super().__init__(bot, user_id, server_id)
        self.alchemy_level = alchemy_level
        self.target_slot = target_slot
        self._options_data: list[dict] = []
        self._item_select: _DisenchantItemSelect | None = None
        self._active_category: str | None = None

        # Row 0: category buttons
        for cat_key, cat_label, cat_emoji in _CATEGORY_DEFS:
            btn = ui.Button(
                label=cat_label,
                style=ButtonStyle.secondary,
                emoji=cat_emoji,
                row=0,
            )
            btn.callback = self._make_category_callback(cat_key)
            self.add_item(btn)

        # Row 2: confirm + back (item select will occupy row 1 when loaded)
        self._confirm_btn = ui.Button(
            label="Queue Disenchant", style=ButtonStyle.green, emoji="🔨", row=2
        )
        self._confirm_btn.callback = self._on_confirm
        self.add_item(self._confirm_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=2
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def _make_category_callback(self, cat_key: str):
        async def _cb(interaction: Interaction) -> None:
            self._active_category = cat_key
            # Highlight the clicked category button, reset others
            active_label = next(
                (lbl for k, lbl, _ in _CATEGORY_DEFS if k == cat_key), None
            )
            for child in self.children:
                if isinstance(child, ui.Button) and child.row == 0:
                    child.style = (
                        ButtonStyle.primary
                        if child.label == active_label
                        else ButtonStyle.secondary
                    )
            await self._load_items_for_category(interaction, cat_key)

        return _cb

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🔨 Disenchant Items — Queue Slot {self.target_slot}",
            color=discord.Color.blurple(),
        )
        embed.set_author(name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT)
        embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)
        embed.set_footer(text=get_quip("alchemy"))
        embed.description = (
            "*Everything has latent value — you just have to render it down.*\n\n"
            "Choose a **category** above to see the items you own.\n"
            "Then select an item and click **Queue Disenchant**."
        )
        return embed

    async def _load_items_for_category(
        self, interaction: Interaction, category: str
    ) -> None:
        await interaction.response.defer()
        mins = AlchemyMechanics.get_disenchant_minutes(self.alchemy_level)

        if category == _CATEGORY_JEWELS:
            owned = await _get_item_owned(
                self.bot, self.user_id, self.server_id, _JEWEL_ITEM_TYPE
            )
            jewel_yield = dust_from_jewel(self.alchemy_level)
            self._options_data = [
                {
                    "col": _JEWEL_ITEM_TYPE,
                    "name": "Jewel of Paradise",
                    "emoji": f"{PARADISE_JEWEL_UNCUT}",
                    "owned": owned,
                    "yield": jewel_yield,
                    "select_desc": f"Own: {owned}  ·  {jewel_yield:,} Cosmic Dust/jewel  ·  4h/jewel",
                }
            ]
        else:
            if category == _CATEGORY_BOSS_KEYS:
                items_map = AlchemyMechanics.KEY_DISPLAY_NAMES
                emojis_map = AlchemyMechanics.KEY_EMOJIS
                yield_map = AlchemyMechanics.DUST_YIELD
            elif category == _CATEGORY_ELEMENTAL:
                items_map = AlchemyMechanics.ELEMENTAL_DISPLAY_NAMES
                emojis_map = AlchemyMechanics.ELEMENTAL_EMOJIS
                yield_map = AlchemyMechanics.ELEMENTAL_DUST_YIELD
            else:
                items_map = AlchemyMechanics.ESSENCE_DISPLAY_NAMES
                emojis_map = AlchemyMechanics.ESSENCE_EMOJIS
                yield_map = AlchemyMechanics.ESSENCE_DUST_YIELD

            self._options_data = []
            for col, name in items_map.items():
                owned = await _get_item_owned(
                    self.bot, self.user_id, self.server_id, col
                )
                self._options_data.append(
                    {
                        "col": col,
                        "name": name,
                        "emoji": emojis_map[col],
                        "owned": owned,
                        "yield": yield_map[col],
                        "select_desc": f"Own: {owned}  ·  {yield_map[col]} Cosmic Dust/item  ·  {mins}min/item",
                    }
                )

        # Rebuild item select (remove old one if present)
        if self._item_select is not None:
            self.remove_item(self._item_select)
        self._item_select = _DisenchantItemSelect(self._options_data)
        self.add_item(self._item_select)

        await interaction.edit_original_response(view=self)

    async def _on_confirm(self, interaction: Interaction) -> None:
        if self._item_select is None or not self._item_select.selected:
            await interaction.response.send_message(
                "Select a category and item first.", ephemeral=True
            )
            return
        col = self._item_select.selected
        data = next(d for d in self._options_data if d["col"] == col)
        if data["owned"] == 0:
            await interaction.response.send_message(
                "You don't own any of that item.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            _DisenchantQuantityModal(self, col, data["owned"])
        )

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = await _build_synthesis_hub(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()


# ---------------------------------------------------------------------------
# Synthesize — item select → auto-open quantity modal → instant craft
# ---------------------------------------------------------------------------


class _SynthesizeItemSelect(ui.Select):
    def __init__(self, options_data: list[dict]) -> None:
        opts = [
            discord.SelectOption(
                label=d["name"][:100],
                description=d["select_desc"][:100],
                value=d["col"],
                emoji=d["emoji"],
            )
            for d in options_data
        ]
        super().__init__(placeholder="Select an item to synthesize…", options=opts)
        self.selected: str | None = None

    async def callback(self, interaction: Interaction) -> None:
        self.selected = self.values[0]
        await self.view._trigger_synth_modal(interaction)


class _SynthesizeQuantityModal(ui.Modal, title="How many items to synthesize?"):
    quantity = ui.TextInput(
        label="Quantity",
        placeholder="Enter a number (e.g. 3)",
        min_length=1,
        max_length=4,
    )

    def __init__(
        self,
        parent: "_SynthesizeSelectView",
        item_type: str,
        dust_cost_each: int,
        gold_cost_each: int,
    ) -> None:
        super().__init__()
        self._parent = parent
        self._item_type = item_type
        self._dust_cost_each = dust_cost_each
        self._gold_cost_each = gold_cost_each

    async def on_submit(self, interaction: Interaction) -> None:
        raw = self.quantity.value.strip()
        if not raw.isdigit() or int(raw) < 1:
            await interaction.response.send_message(
                "Please enter a positive whole number.", ephemeral=True
            )
            return

        qty = int(raw)
        total_dust = self._dust_cost_each * qty
        total_gold = self._gold_cost_each * qty

        cosmic_dust = await self._parent.bot.database.alchemy.get_cosmic_dust(
            self._parent.user_id
        )
        gold = await self._parent.bot.database.users.get_gold(self._parent.user_id)

        if cosmic_dust < total_dust:
            await interaction.response.send_message(
                f"Not enough Cosmic Dust! Need {COSMIC_DUST} **{total_dust:,}** for {qty}×, "
                f"have **{cosmic_dust:,}**.",
                ephemeral=True,
            )
            return
        if gold < total_gold:
            await interaction.response.send_message(
                f"Not enough gold! Need {GOLD_COIN} **{total_gold:,}** for {qty}×, "
                f"have **{gold:,}**.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        await self._parent.bot.database.alchemy.modify_cosmic_dust(
            self._parent.user_id, -total_dust
        )
        await self._parent.bot.database.users.modify_gold(
            self._parent.user_id, -total_gold
        )

        if self._item_type == _JEWEL_ITEM_TYPE:
            await self._parent.bot.database.uber.increment_paradise_jewels(
                self._parent.user_id, self._parent.server_id, qty
            )
            name, emoji = "Jewel of Paradise", f"{PARADISE_JEWEL_UNCUT}"
        else:
            await self._parent.bot.database.users.modify_currency(
                self._parent.user_id, self._item_type, qty
            )
            name = AlchemyMechanics.KEY_DISPLAY_NAMES[self._item_type]
            emoji = AlchemyMechanics.KEY_EMOJIS[self._item_type]

        view = await _build_synthesis_hub(
            self._parent.bot, self._parent.user_id, self._parent.server_id
        )
        embed = view.build_embed()
        embed.colour = discord.Color.gold()
        embed.title = f"⚗️ Synthesized: {qty}× {emoji} {name}!"
        embed.description = (
            f"You spent {COSMIC_DUST} **{total_dust:,} Cosmic Dust** + {GOLD_COIN} **{total_gold:,} Gold** "
            f"and received **{qty}× {emoji} {name}**.\n\n"
        ) + (embed.description or "")
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self._parent.stop()


class _SynthesizeSelectView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        alchemy_level: int,
        cosmic_dust: int,
        player_gold: int,
    ) -> None:
        super().__init__(bot, user_id, server_id)
        self.alchemy_level = alchemy_level
        self.cosmic_dust = cosmic_dust
        self.player_gold = player_gold

        options_data = []
        for col, name in AlchemyMechanics.KEY_DISPLAY_NAMES.items():
            dust_cost = AlchemyMechanics.get_synthesis_dust_cost(alchemy_level, col)
            options_data.append(
                {
                    "col": col,
                    "name": name,
                    "emoji": AlchemyMechanics.KEY_EMOJIS[col],
                    "dust_cost": dust_cost,
                    "gold_cost": AlchemyMechanics.SYNTHESIS_GOLD_COST,
                    "select_desc": f"{dust_cost:,} Cosmic Dust + 100k Gold → 1× {name}",
                }
            )
        options_data.append(
            {
                "col": _JEWEL_ITEM_TYPE,
                "name": "Jewel of Paradise",
                "emoji": f"{PARADISE_JEWEL_UNCUT}",
                "dust_cost": _JEWEL_SYNTH_DUST,
                "gold_cost": _JEWEL_SYNTH_GOLD,
                "select_desc": f"{_JEWEL_SYNTH_DUST:,} Cosmic Dust + 10M Gold → 1× Jewel of Paradise",
            }
        )
        self._options_data = options_data

        self._select = _SynthesizeItemSelect(options_data)
        self.add_item(self._select)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=1
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def build_embed(self) -> discord.Embed:
        level = self.alchemy_level
        discount = level

        embed = discord.Embed(title="⚗️ Synthesize Item", color=discord.Color.purple())
        embed.set_author(name="Master Alchemist Elyndra", icon_url=ELYNDRA_PORTRAIT)
        embed.set_thumbnail(url=ELYNDRA_THUMBNAIL)
        embed.set_footer(text=get_quip("alchemy"))
        embed.description = (
            f"**Cosmic Dust:** {COSMIC_DUST} {self.cosmic_dust:,}  |  **Gold:** {GOLD_COIN} {self.player_gold:,}\n"
            f"**Synthesis Discount:** {discount}% (Alchemy Level {level})\n\n"
            "*Dust in, item out. Select what you want synthesized.*"
        )

        lines = []
        for d in self._options_data:
            dust_cost = (
                d["dust_cost"]
                if d["col"] == _JEWEL_ITEM_TYPE
                else AlchemyMechanics.get_synthesis_dust_cost(level, d["col"])
            )
            gold_cost = d["gold_cost"]
            can_afford = self.cosmic_dust >= dust_cost and self.player_gold >= gold_cost
            status = "✅" if can_afford else "❌"
            lines.append(
                f"{status} {d['emoji']} **{d['name']}** — {COSMIC_DUST} {dust_cost:,}  +  {GOLD_COIN} {gold_cost:,}"
            )
        embed.add_field(
            name="Available Syntheses", value="\n".join(lines), inline=False
        )
        return embed

    async def _trigger_synth_modal(self, interaction: Interaction) -> None:
        col = self._select.selected
        if not col:
            await interaction.response.send_message(
                "Please select an item first.", ephemeral=True
            )
            return
        data = next(d for d in self._options_data if d["col"] == col)
        dust_cost = (
            data["dust_cost"]
            if col == _JEWEL_ITEM_TYPE
            else AlchemyMechanics.get_synthesis_dust_cost(self.alchemy_level, col)
        )
        gold_cost = data["gold_cost"]
        await interaction.response.send_modal(
            _SynthesizeQuantityModal(self, col, dust_cost, gold_cost)
        )

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        view = await _build_synthesis_hub(self.bot, self.user_id, self.server_id)
        embed = view.build_embed()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view.message = msg
        self.stop()
