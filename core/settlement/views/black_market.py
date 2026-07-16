"""
core/settlement/views/black_market.py
Redesigned Black Market — Merchant Mini-Game with Passive Tree.

Flow:
  1. Main view: shows Mysterious Merchant Max greeting, pending deal status, buttons.
  2. "Make Offer" → OfferBuilderView: build a resource bundle across pages.
  3. "Submit Offer" → calculate value / turns, deduct resources, create pending deal.
  4. "Passive Tree" → BMPassiveTreeView: spend Idlem to unlock/upgrade nodes.
  5. Deals process automatically on each Next Turn click.
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.emojis import RESOURCE_EMOJI, RUNE_GENERIC
from core.images import BLACK_MARKET_AUTHOR, SETTLEMENT_BUILDINGS
from core.npc_voices import get_quip
from core.settlement.constants import (
    BM_ITEM_VALUES,
    BM_TREE_NODES,
)
from core.settlement.mechanics import SettlementMechanics, execute_bm_offer
from core.settlement.turn_engine import (
    calculate_offer_value,
    compute_processing_turns,
    resolve_bm_event_value_bonus,
)

from .base import SettlementBaseView

# Resource (key, plain name) grouped by category, up to 25 per select page.
# Emoji are looked up centrally from RESOURCE_EMOJI, never hardcoded here.
_BM_RESOURCE_NAMES: list[list[tuple[str, str]]] = [
    [  # Page 1: Settlement basics + ores
        ("timber", "Timber"),
        ("stone", "Stone"),
        ("iron_ore", "Iron Ore"),
        ("coal_ore", "Coal"),
        ("gold_ore", "Gold Ore"),
        ("platinum_ore", "Platinum Ore"),
        ("idea_ore", "Idea Ore"),
        ("iron_bar", "Iron Bars"),
        ("steel_bar", "Steel Bars"),
        ("gold_bar", "Gold Bars"),
        ("platinum_bar", "Platinum Bars"),
        ("idea_bar", "Idea Bars"),
        ("oak_logs", "Oak Logs"),
        ("willow_logs", "Willow Logs"),
        ("mahogany_logs", "Mahogany Logs"),
        ("magic_logs", "Magic Logs"),
        ("idea_logs", "Idea Logs"),
        ("oak_plank", "Oak Planks"),
        ("willow_plank", "Willow Planks"),
        ("mahogany_plank", "Mahogany Planks"),
        ("magic_plank", "Magic Planks"),
        ("idea_plank", "Idea Planks"),
        ("desiccated_bones", "Desiccated Bones"),
        ("regular_bones", "Regular Bones"),
        ("sturdy_bones", "Sturdy Bones"),
    ],
    [  # Page 2: High-value + runes + keys
        ("reinforced_bones", "Reinforced Bones"),
        ("titanium_bones", "Titanium Bones"),
        ("refinement_runes", "Refinement Runes"),
        ("potential_runes", "Potential Runes"),
        ("shatter_runes", "Shatter Runes"),
        ("imbue_runes", "Imbuing Runes"),
        ("partnership_runes", "Partnership Runes"),
        ("runes_of_nature", "Rune of Nature"),
        ("rune_of_regret", "Rune of Regret"),
        ("dragon_key", "Draconic Keys"),
        ("angel_key", "Angelic Keys"),
        ("soul_cores", "Soul Cores"),
        ("balance_fragment", "Fragments of Balance"),
        ("void_frags", "Void Fragments"),
        ("magma_core", "Magma Cores"),
        ("life_root", "Life Roots"),
        ("spirit_shard", "Spirit Shards"),
        ("curios", "Curios"),
        ("unidentified_blueprint", "Blueprints"),
        ("spirit_stones", "Spirit Stones"),
        ("celestial_stone", "Celestial Stone"),
        ("infernal_cinder", "Infernal Cinder"),
        ("void_crystal", "Void Crystal"),
        ("bound_crystal", "Bound Crystal"),
        ("corrupted_core", "Corrupted Core"),
        ("blessed_bismuth", "Blessed Bismuth"),
        ("sparkling_sprig", "Sparkling Sprig"),
        ("capricious_carp", "Capricious Carp"),
    ],
    [  # Page 3: Refined essences (produced by Reliquary; stored in fishing skill table)
        ("desiccated_essence", "Desiccated Essence"),
        ("regular_essence", "Regular Essence"),
        ("sturdy_essence", "Sturdy Essence"),
        ("reinforced_essence", "Reinforced Essence"),
        ("titanium_essence", "Titanium Essence"),
    ],
]

_BM_RESOURCE_PAGES: list[list[tuple[str, str]]] = [
    [(key, f"{RESOURCE_EMOJI[key]} {name}") for key, name in page]
    for page in _BM_RESOURCE_NAMES
]

# Flat key→label lookup built from all pages. _BM_ALL_LABELS bakes the emoji
# into the string — only safe in embed/message text, NOT in a SelectOption
# label, Button label, or Modal title (those don't render custom emoji tags,
# they'd show the literal "<:name:id>" text). Use _BM_ALL_NAMES + the
# emoji= kwarg for those.
_BM_ALL_LABELS: dict[str, str] = {
    key: label for page in _BM_RESOURCE_PAGES for key, label in page
}
_BM_ALL_NAMES: dict[str, str] = {
    key: name for page in _BM_RESOURCE_NAMES for key, name in page
}

# Category filter buttons: (id, button_label, [resource_keys])
_BM_CATEGORIES: list[tuple[str, str, list[str]]] = [
    (
        "settlement",
        "🏗️ Settlement",
        [
            "timber",
            "stone",
            "magma_core",
            "life_root",
            "spirit_shard",
            "celestial_stone",
            "infernal_cinder",
            "void_crystal",
            "bound_crystal",
            "corrupted_core",
        ],
    ),
    (
        "mining",
        "⛏️ Mining",
        [
            "iron_ore",
            "coal_ore",
            "gold_ore",
            "platinum_ore",
            "idea_ore",
            "iron_bar",
            "steel_bar",
            "gold_bar",
            "platinum_bar",
            "idea_bar",
        ],
    ),
    (
        "lumber",
        "🌲 Lumber",
        [
            "oak_logs",
            "willow_logs",
            "mahogany_logs",
            "magic_logs",
            "idea_logs",
            "oak_plank",
            "willow_plank",
            "mahogany_plank",
            "magic_plank",
            "idea_plank",
        ],
    ),
    (
        "fishing",
        "🦴 Fishing",
        [
            "desiccated_bones",
            "regular_bones",
            "sturdy_bones",
            "reinforced_bones",
            "titanium_bones",
            "desiccated_essence",
            "regular_essence",
            "sturdy_essence",
            "reinforced_essence",
            "titanium_essence",
        ],
    ),
    (
        "boss_keys",
        "🗝️ Boss Keys",
        [
            "dragon_key",
            "angel_key",
            "soul_cores",
            "balance_fragment",
            "void_frags",
        ],
    ),
    (
        "runes",
        f"{RUNE_GENERIC} Runes",
        [
            "refinement_runes",
            "potential_runes",
            "shatter_runes",
            "imbue_runes",
            "partnership_runes",
            "runes_of_nature",
            "rune_of_regret",
        ],
    ),
    (
        "materials",
        "💎 Materials",
        [
            "curios",
            "unidentified_blueprint",
            "spirit_stones",
            "blessed_bismuth",
            "sparkling_sprig",
            "capricious_carp",
        ],
    ),
]

# Sort each category's keys by BM value ascending so the select menus display
# items from cheapest to most valuable within their category.
_BM_CATEGORIES = [
    (cat_id, label, sorted(keys, key=lambda k: BM_ITEM_VALUES.get(k, 0)))
    for cat_id, label, keys in _BM_CATEGORIES
]

# Merchanting (BM passive tree) branch tabs: (branch_id, button/field label)
_BM_TREE_BRANCHES: list[tuple[str, str]] = [
    ("efficiency", "⚡ Efficiency"),
    ("value", "💹 Value"),
    ("bias", "🎯 Biases"),
]

# Resources stored in skill / settlement tables vs. user currency columns
_SETTLEMENT_RESOURCE_KEYS: frozenset[str] = frozenset(["timber", "stone"])
_SETTLEMENT_MATERIAL_KEYS: frozenset[str] = frozenset(
    [
        "magma_core",
        "life_root",
        "spirit_shard",
        "celestial_stone",
        "infernal_cinder",
        "void_crystal",
        "bound_crystal",
        "diviners_rod",
        "unidentified_blueprint",
        "corrupted_core",
    ]
)
_SKILL_RESOURCE_KEYS: frozenset[str] = frozenset(
    [
        "iron_ore",
        "coal_ore",
        "gold_ore",
        "platinum_ore",
        "idea_ore",
        "iron_bar",
        "steel_bar",
        "gold_bar",
        "platinum_bar",
        "idea_bar",
        "oak_logs",
        "willow_logs",
        "mahogany_logs",
        "magic_logs",
        "idea_logs",
        "oak_plank",
        "willow_plank",
        "mahogany_plank",
        "magic_plank",
        "idea_plank",
        "desiccated_bones",
        "regular_bones",
        "sturdy_bones",
        "reinforced_bones",
        "titanium_bones",
        "desiccated_essence",
        "regular_essence",
        "sturdy_essence",
        "reinforced_essence",
        "titanium_essence",
    ]
)

_MINING_COLS = [
    "iron_ore",
    "coal_ore",
    "gold_ore",
    "platinum_ore",
    "idea_ore",
    "iron_bar",
    "steel_bar",
    "gold_bar",
    "platinum_bar",
    "idea_bar",
]
_WOOD_COLS = [
    "oak_logs",
    "willow_logs",
    "mahogany_logs",
    "magic_logs",
    "idea_logs",
    "oak_plank",
    "willow_plank",
    "mahogany_plank",
    "magic_plank",
    "idea_plank",
]
_FISH_COLS = [
    "desiccated_bones",
    "regular_bones",
    "sturdy_bones",
    "reinforced_bones",
    "titanium_bones",
    "desiccated_essence",
    "regular_essence",
    "sturdy_essence",
    "reinforced_essence",
    "titanium_essence",
]


async def _load_player_inventory(bot, user_id: str, server_id: str) -> dict[str, int]:
    """Loads all BM-tradeable resources for the player into a flat key→qty dict."""
    settlement = await bot.database.settlement.get_settlement(user_id, server_id)
    skill_mining = await bot.database.skills.get_data(user_id, server_id, "mining")
    skill_wood = await bot.database.skills.get_data(user_id, server_id, "woodcutting")
    skill_fish = await bot.database.skills.get_data(user_id, server_id, "fishing")

    inv: dict[str, int] = {}
    inv["timber"] = int(getattr(settlement, "timber", 0))
    inv["stone"] = int(getattr(settlement, "stone", 0))

    if skill_mining:
        for i, col in enumerate(_MINING_COLS):
            inv[col] = int(skill_mining[3 + i]) if len(skill_mining) > 3 + i else 0
    if skill_wood:
        for i, col in enumerate(_WOOD_COLS):
            inv[col] = int(skill_wood[3 + i]) if len(skill_wood) > 3 + i else 0
    if skill_fish:
        for i, col in enumerate(_FISH_COLS):
            inv[col] = int(skill_fish[3 + i]) if len(skill_fish) > 3 + i else 0

    _handled = {"timber", "stone", *_MINING_COLS, *_WOOD_COLS, *_FISH_COLS}
    remaining = [
        k for _cat_id, _lbl, keys in _BM_CATEGORIES for k in keys if k not in _handled
    ]
    mat_data = await bot.database.settlement_materials.get_all(user_id)
    for key in remaining:
        if key in _SETTLEMENT_MATERIAL_KEYS:
            inv[key] = mat_data.get(key, 0)
        else:
            try:
                inv[key] = int(await bot.database.users.get_currency(user_id, key))
            except Exception:
                inv[key] = 0

    return inv


class BlackMarketView(SettlementBaseView):
    """Main Black Market hub — shows pending deal, make offer, passive tree."""

    def __init__(
        self,
        bot,
        user_id: str,
        parent_view,
        building,
        *,
        has_pending_deal: bool = False,
        server_id: str | None = None,
    ):
        super().__init__(bot, user_id)
        self.parent = parent_view
        self.server_id = server_id if server_id is not None else parent_view.server_id
        self.building = building
        self._processing = False
        self.has_pending_deal = has_pending_deal
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.clear_items()

        offer_btn = ui.Button(
            label="Make Offer",
            style=ButtonStyle.primary,
            emoji="📦",
            row=0,
            disabled=self.has_pending_deal,
        )
        offer_btn.callback = self._on_make_offer
        self.add_item(offer_btn)

        tree_btn = ui.Button(
            label="Merchanting", style=ButtonStyle.blurple, emoji="🪙", row=0
        )
        tree_btn.callback = self._on_passive_tree
        self.add_item(tree_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=1
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def build_embed(
        self,
        pending_deal: dict | None = None,
        zeal_data: dict | None = None,
    ) -> discord.Embed:
        tier = self.building.tier
        mult = SettlementMechanics.get_multiplier(tier)

        embed = discord.Embed(
            title=f"The Black Market (Tier {tier})",
            description=get_quip("black_market"),
            color=discord.Color.dark_gray(),
        )
        embed.set_author(name="Mysterious Merchant Max", icon_url=BLACK_MARKET_AUTHOR)
        embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["black_market"])

        embed.add_field(
            name="📊 Facility Tier",
            value=f"Tier **{tier}** — {int((mult - 1) * 100)}% turn cost reduction",
            inline=True,
        )
        if zeal_data:
            embed.add_field(
                name="⚗️ Idlem Available",
                value=f"{zeal_data.get('idlem', 0):,}",
                inline=True,
            )
        embed.add_field(name="​", value="​", inline=True)  # spacer

        embed.add_field(
            name="📖 How it works",
            value=(
                "Bring a bundle of resources. Max calculates their **Value** "
                "and processes the deal over **Development Turns**, returning a "
                "curated loot package based on your passive tree biases."
            ),
            inline=False,
        )

        if pending_deal:
            embed.add_field(
                name="⏳ Deal in Progress",
                value=(
                    f"Value: **{pending_deal['total_value'] * 100:,}** — "
                    f"**{pending_deal['turns_remaining']}** turn(s) remaining\n"
                    f"Biases: {', '.join(BM_TREE_NODES[b]['name'] for b in pending_deal.get('active_biases', []) if b in BM_TREE_NODES) or 'none'}"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="✅ Ready for a Deal",
                value="No active deal. Make an offer to get started!",
                inline=False,
            )

        if tier < 5:
            embed.add_field(
                name="⬆️ Upgrading?",
                value="Manage this facility's upgrade from its plot in the settlement grid.",
                inline=False,
            )

        return embed

    async def _on_make_offer(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return

        # Check if a deal is already active
        pending = await self.bot.database.settlement.get_pending_deal(
            self.user_id, self.server_id
        )
        if pending:
            await interaction.response.defer()
            zeal_data = await self.bot.database.settlement.get_zeal_data(
                self.user_id, self.server_id
            )
            self.has_pending_deal = True
            self._setup_ui()
            await interaction.edit_original_response(
                embed=self.build_embed(pending_deal=pending, zeal_data=zeal_data),
                view=self,
            )
            return

        await interaction.response.defer()
        tree_nodes = await self.bot.database.settlement.get_bm_tree(
            self.user_id, self.server_id
        )
        inventory = await _load_player_inventory(self.bot, self.user_id, self.server_id)
        active_events = await self.bot.database.settlement.get_active_events(
            self.user_id, self.server_id
        )
        event_value_bonus = resolve_bm_event_value_bonus(active_events)
        view = OfferBuilderView(
            self.bot,
            self.user_id,
            self.server_id,
            self.building,
            self,
            tree_nodes=tree_nodes,
            inventory=inventory,
            event_value_bonus=event_value_bonus,
        )
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    async def _on_passive_tree(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        tree_nodes = await self.bot.database.settlement.get_bm_tree(
            self.user_id, self.server_id
        )
        zeal_data = await self.bot.database.settlement.get_zeal_data(
            self.user_id, self.server_id
        )
        view = BMPassiveTreeView(
            self.bot,
            self.user_id,
            self.server_id,
            self.building,
            self,
            tree_nodes=tree_nodes,
            idlem=zeal_data.get("idlem", 0),
        )
        await interaction.edit_original_response(embed=view.build_embed(), view=view)

    async def _on_back(self, interaction: Interaction) -> None:
        if self.parent is None:
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
            await interaction.response.defer()
            await interaction.delete_original_response()
            return
        if hasattr(self.parent, "_rebuild_ui"):
            self.parent._rebuild_ui()
        elif hasattr(self.parent, "_build_buttons"):
            self.parent._build_buttons()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


# ---------------------------------------------------------------------------
# Offer Builder
# ---------------------------------------------------------------------------


class _InstantDealConfirmView(SettlementBaseView):
    """Shown after an instant deal completes. Single button returns to the market."""

    def __init__(
        self, bot, user_id: str, server_id: str, parent_market: "BlackMarketView"
    ):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.parent_market = parent_market
        btn = ui.Button(label="Collect & Return", style=ButtonStyle.success, emoji="✅")
        btn.callback = self._on_collect
        self.add_item(btn)

    async def _on_collect(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        pending = await self.bot.database.settlement.get_pending_deal(
            self.user_id, self.server_id
        )
        zeal_data = await self.bot.database.settlement.get_zeal_data(
            self.user_id, self.server_id
        )
        self.parent_market.has_pending_deal = bool(pending)
        self.parent_market._setup_ui()
        await interaction.edit_original_response(
            embed=self.parent_market.build_embed(
                pending_deal=pending, zeal_data=zeal_data
            ),
            view=self.parent_market,
        )
        self.stop()


class OfferBuilderView(SettlementBaseView):
    """
    Offer builder with category filter buttons.
    Row 0: resource select (filtered to selected category, owned, not-yet-offered)
    Row 1: category filter buttons
    Row 2: Submit / Clear / Cancel
    Row 3: Bias toggles
    """

    MAX_OFFER_ITEMS = 8

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        building,
        parent_market: "BlackMarketView",
        tree_nodes: dict | None = None,
        inventory: dict | None = None,
        event_value_bonus: float = 0.0,
    ):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.building = building
        self.parent_market = parent_market
        self.tree_nodes = tree_nodes or {}
        self._inventory: dict[str, int] = inventory or {}
        self._event_value_bonus = event_value_bonus
        self._current_category: str = _BM_CATEGORIES[0][0]
        self._offer: dict[str, int] = {}
        self._active_biases: list[str] = []
        self._processing = False
        self._build_ui()

    def _category_options(self) -> list[SelectOption]:
        """Build select options for the current category, filtered to owned + not-yet-offered."""
        _, _lbl, keys = next(
            c for c in _BM_CATEGORIES if c[0] == self._current_category
        )
        options = []
        for key in keys:
            if key in self._offer:
                continue  # already added
            qty = self._inventory.get(key, 0)
            if qty <= 0:
                continue  # player doesn't have any
            label = _BM_ALL_NAMES.get(key, key)
            unit_val = BM_ITEM_VALUES.get(key, 0)
            options.append(
                SelectOption(
                    label=label,
                    value=key,
                    description=f"Owned: {qty:,} | {unit_val:,}/unit",
                )
            )
        return options[:25]

    def _build_ui(self) -> None:
        self.clear_items()

        # Row 0: resource select (or disabled placeholder if nothing available)
        options = self._category_options()
        if options:
            sel = ui.Select(
                placeholder="Choose a resource to add to your offer…",
                options=options,
                row=0,
            )
            sel.callback = self._on_resource_select
        else:
            sel = ui.Select(
                placeholder="No resources available in this category",
                options=[SelectOption(label="—", value="__none__")],
                disabled=True,
                row=0,
            )
        self.add_item(sel)

        # Row 1 + 2: category filter buttons (max 5 per row; overflow to row 2)
        half = -(-len(_BM_CATEGORIES) // 2)  # ceil split so row 1 fills first
        for i, (cat_id, cat_label, _) in enumerate(_BM_CATEGORIES):
            btn = ui.Button(
                label=cat_label,
                style=(
                    ButtonStyle.blurple
                    if cat_id == self._current_category
                    else ButtonStyle.secondary
                ),
                row=1 if i < half else 2,
            )
            btn.callback = self._make_category_switch(cat_id)
            self.add_item(btn)

        # Row 3: action buttons
        if self._offer:
            submit_btn = ui.Button(
                label="Submit Offer", style=ButtonStyle.success, emoji="✅", row=3
            )
            submit_btn.callback = self._on_submit
            self.add_item(submit_btn)

            clear_btn = ui.Button(
                label="Clear Offer", style=ButtonStyle.danger, emoji="🗑️", row=3
            )
            clear_btn.callback = self._on_clear
            self.add_item(clear_btn)

        cancel_btn = ui.Button(
            label="Cancel", style=ButtonStyle.secondary, emoji="❌", row=3
        )
        cancel_btn.callback = self._on_cancel
        self.add_item(cancel_btn)

        # Row 4: bias toggles (unlocked nodes only, max 5)
        bias_count = 0
        for node_key, node in BM_TREE_NODES.items():
            if node.get("branch") != "bias":
                continue
            if node_key not in self.tree_nodes:
                continue
            if bias_count >= 5:
                break
            toggled = node_key in self._active_biases
            btn = ui.Button(
                label=f"{'✅' if toggled else '○'} {node['name']}",
                style=ButtonStyle.blurple if toggled else ButtonStyle.secondary,
                row=4,
            )
            btn.callback = self._make_bias_toggle(node_key)
            self.add_item(btn)
            bias_count += 1

    def _make_category_switch(self, cat_id: str):
        async def callback(interaction: Interaction) -> None:
            await interaction.response.defer()
            self._current_category = cat_id
            self._build_ui()
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        return callback

    def _make_bias_toggle(self, node_key: str):
        async def callback(interaction: Interaction) -> None:
            await interaction.response.defer()
            if node_key in self._active_biases:
                self._active_biases.remove(node_key)
            else:
                self._active_biases.append(node_key)
            self._build_ui()
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        return callback

    def build_embed(self) -> discord.Embed:
        _, cat_label, _ = next(
            c for c in _BM_CATEGORIES if c[0] == self._current_category
        )
        embed = discord.Embed(
            title="📦 Build Your Offer",
            description=(
                f"Browsing: **{cat_label}**\n"
                "Select a resource to set the quantity. "
                "Resources already in your offer are hidden until you Clear."
            ),
            color=discord.Color.dark_gray(),
        )
        embed.set_author(name="Mysterious Merchant Max", icon_url=BLACK_MARKET_AUTHOR)
        embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["black_market"])

        if self._offer:
            offer_lines = []
            estimated = calculate_offer_value(
                self._offer, self.tree_nodes, self.building.tier
            )
            estimated = int(estimated * (1 + self._event_value_bonus))
            for key, qty in self._offer.items():
                label = _BM_ALL_LABELS.get(key, key)
                val = BM_ITEM_VALUES.get(key, 0) * qty
                offer_lines.append(f"• {label}: **{qty:,}** (≈ {val:,} value)")
            value_label = f"🧾 Current Offer (Value ≈ {estimated:,})"
            if self._event_value_bonus:
                _pct = int(self._event_value_bonus * 100)
                _icon = "🐪" if _pct >= 0 else "📉"
                value_label += f" [{_icon} {'+' if _pct >= 0 else ''}{_pct}%]"
            embed.add_field(
                name=value_label,
                value="\n".join(offer_lines),
                inline=False,
            )
            turns = compute_processing_turns(
                estimated // 100, self.building.tier, self.tree_nodes
            )
            embed.add_field(
                name="⏭️ Estimated Processing",
                value=f"**{turns}** Development Turn(s)",
                inline=True,
            )
        else:
            embed.add_field(
                name="🧾 Current Offer",
                value="*Nothing added yet. Pick a category and select a resource.*",
                inline=False,
            )

        if self._active_biases:
            bias_names = [
                BM_TREE_NODES[b]["name"]
                for b in self._active_biases
                if b in BM_TREE_NODES
            ]
            embed.add_field(
                name="🎯 Active Biases", value=", ".join(bias_names), inline=True
            )

        return embed

    async def _on_resource_select(self, interaction: Interaction) -> None:
        resource_key = interaction.data["values"][0]
        if resource_key == "__none__":
            await interaction.response.defer()
            return
        if len(self._offer) >= self.MAX_OFFER_ITEMS:
            await interaction.response.send_message(
                f"Maximum {self.MAX_OFFER_ITEMS} distinct resource types per offer.",
                ephemeral=True,
            )
            return

        label = _BM_ALL_NAMES.get(resource_key, resource_key)
        max_qty = self._inventory.get(resource_key, 0)
        modal = QuantityInputModal(self, resource_key, label, max_qty)
        await interaction.response.send_modal(modal)

    async def _on_clear(self, interaction: Interaction) -> None:
        self._offer.clear()
        self._build_ui()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_submit(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            if not self._offer:
                await interaction.followup.send(
                    "Nothing in your offer.", ephemeral=True
                )
                return

            uid, sid = self.user_id, self.server_id

            # Re-validate against live inventory at submission time
            live_inv = await _load_player_inventory(self.bot, uid, sid)
            for res, qty in self._offer.items():
                if live_inv.get(res, 0) < qty:
                    label = _BM_ALL_LABELS.get(res, res)
                    await interaction.followup.send(
                        f"Not enough **{label}**! You now have {live_inv.get(res, 0):,}, need {qty:,}.",
                        ephemeral=True,
                    )
                    return

            result = await execute_bm_offer(
                self.bot,
                uid,
                sid,
                offer=self._offer,
                active_biases=self._active_biases,
                building_tier=self.building.tier,
            )

            if result.get("error") == "no_value":
                await interaction.followup.send(
                    "This offer has no tradeable value.", ephemeral=True
                )
                return

            import asyncio

            raw_value = result["raw_value"]
            turns = result["turns"]

            if result.get("instant"):
                rewards = result["rewards"]
                summary_text = (
                    " | ".join(rewards["summary_lines"])
                    if rewards["summary_lines"]
                    else "Nothing"
                )
                embed = discord.Embed(
                    title="⚡ Instant Deal Complete!",
                    description=(
                        f"**Max nods approvingly — no waiting needed.**\n\n"
                        f"Value: **{raw_value:,}**\n\n"
                        f"**Rewards:** {summary_text}"
                    ),
                    color=discord.Color.gold(),
                )
                embed.set_author(
                    name="Mysterious Merchant Max", icon_url=BLACK_MARKET_AUTHOR
                )
                embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["black_market"])
                confirm_view = _InstantDealConfirmView(
                    self.bot, uid, sid, self.parent_market
                )
                await interaction.edit_original_response(embed=embed, view=confirm_view)
                self.stop()
                return

            embed = discord.Embed(
                title="✅ Deal Submitted",
                description=(
                    f"**Max eyes the goods and gives a thin smile.**\n\n"
                    f"Value assessed: **{raw_value:,}**\n"
                    f"Processing: **{turns}** Development Turn(s)\n\n"
                    f"Advance turns on the dashboard to collect your loot."
                ),
                color=discord.Color.green(),
            )
            embed.set_author(
                name="Mysterious Merchant Max", icon_url=BLACK_MARKET_AUTHOR
            )
            embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["black_market"])
            await interaction.edit_original_response(
                embed=embed, view=discord.ui.View()
            )
            await asyncio.sleep(2)

            # Return to main market view
            pending = await self.bot.database.settlement.get_pending_deal(uid, sid)
            zeal_data = await self.bot.database.settlement.get_zeal_data(uid, sid)
            self.parent_market.has_pending_deal = bool(pending)
            self.parent_market._setup_ui()
            await interaction.edit_original_response(
                embed=self.parent_market.build_embed(
                    pending_deal=pending, zeal_data=zeal_data
                ),
                view=self.parent_market,
            )
            self.stop()

        finally:
            self._processing = False

    async def _on_cancel(self, interaction: Interaction) -> None:
        pending = await self.bot.database.settlement.get_pending_deal(
            self.user_id, self.server_id
        )
        zeal_data = await self.bot.database.settlement.get_zeal_data(
            self.user_id, self.server_id
        )
        self.parent_market.has_pending_deal = bool(pending)
        self.parent_market._setup_ui()
        await interaction.response.edit_message(
            embed=self.parent_market.build_embed(
                pending_deal=pending, zeal_data=zeal_data
            ),
            view=self.parent_market,
        )
        self.stop()


class QuantityInputModal(ui.Modal):
    def __init__(
        self,
        offer_view: "OfferBuilderView",
        resource_key: str,
        resource_label: str,
        max_qty: int,
    ):
        super().__init__(title=f"Add {resource_label[:40]}")
        self.offer_view = offer_view
        self.resource_key = resource_key
        self.max_qty = max_qty
        self.qty_input = ui.TextInput(
            label=f"How many? (you have {max_qty:,})",
            placeholder=f"1 – {max_qty:,}",
            min_length=1,
            max_length=10,
        )
        self.add_item(self.qty_input)

    async def on_submit(self, interaction: Interaction) -> None:
        try:
            qty = int(self.qty_input.value.replace(",", "").replace(".", ""))
            if qty <= 0:
                raise ValueError
        except (ValueError, TypeError):
            await interaction.response.send_message(
                "Please enter a positive whole number.", ephemeral=True
            )
            return

        if qty > self.max_qty:
            await interaction.response.send_message(
                f"You only have **{self.max_qty:,}** available.", ephemeral=True
            )
            return

        self.offer_view._offer[self.resource_key] = qty  # set, not accumulate
        self.offer_view._build_ui()
        await interaction.response.edit_message(
            embed=self.offer_view.build_embed(), view=self.offer_view
        )


# ---------------------------------------------------------------------------
# BM Passive Tree
# ---------------------------------------------------------------------------


class BMPassiveTreeView(SettlementBaseView):
    """Spend Idlem to unlock/upgrade Black Market passive tree nodes."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        building,
        parent_market: BlackMarketView,
        tree_nodes: dict | None = None,
        idlem: int = 0,
    ):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.building = building
        self.parent_market = parent_market
        self.tree_nodes = tree_nodes or {}
        self.idlem = idlem
        self._processing = False
        self.current_branch = "efficiency"
        self._build_ui()

    def _build_ui(self) -> None:
        self.clear_items()

        # Row 0 — branch tabs
        for branch_id, branch_label in _BM_TREE_BRANCHES:
            tab_btn = ui.Button(
                label=branch_label,
                style=(
                    ButtonStyle.primary
                    if branch_id == self.current_branch
                    else ButtonStyle.secondary
                ),
                row=0,
            )
            tab_btn.callback = self._make_branch_switch(branch_id)
            self.add_item(tab_btn)

        options = []
        for key, node in BM_TREE_NODES.items():
            if node.get("branch") != self.current_branch:
                continue
            current_lvl = self.tree_nodes.get(key, 0)
            max_lvl = node["max_level"]
            if current_lvl >= max_lvl:
                continue  # fully unlocked
            next_cost = node["idlem_costs"][current_lvl]  # cost for next level
            label = f"{node['name']} (Lv{current_lvl} → {current_lvl + 1})"
            desc = f"{node['description'][:50]} | Cost: {next_cost} Idlem"
            options.append(SelectOption(label=label, value=key, description=desc))

        if options:
            sel = ui.Select(
                placeholder="Choose a node to unlock/upgrade...",
                options=options[:25],
                row=1,
            )
            sel.callback = self._on_unlock
            self.add_item(sel)
        else:
            no_btn = ui.Button(
                label="All Nodes Unlocked!",
                style=ButtonStyle.success,
                disabled=True,
                row=1,
            )
            self.add_item(no_btn)

        back_btn = ui.Button(
            label="Back", style=ButtonStyle.secondary, emoji="⬅️", row=2
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def _make_branch_switch(self, branch_id: str):
        async def _cb(interaction: Interaction) -> None:
            self.current_branch = branch_id
            self._build_ui()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

        return _cb

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🪙 Merchanting",
            description=(
                f"Invest **Idlem** to unlock and upgrade passive nodes that modify "
                f"your deal processing, value, and reward composition.\n\n"
                f"⚗️ **Your Idlem:** {self.idlem:,}"
            ),
            color=discord.Color.dark_teal(),
        )

        lines: list[str] = []
        for key, node in BM_TREE_NODES.items():
            if node.get("branch") != self.current_branch:
                continue
            current_lvl = self.tree_nodes.get(key, 0)
            max_lvl = node["max_level"]
            status = (
                "✅"
                if current_lvl >= max_lvl
                else (f"Lv{current_lvl}" if current_lvl > 0 else "🔒")
            )
            if current_lvl >= max_lvl:
                cost_str = "✅ Max Tier"
            else:
                cost_str = f"next: {node['idlem_costs'][current_lvl]} Idlem"
            lines.append(
                f"{status} **{node['name']}** — {node['description']} ({cost_str})"
            )

        branch_label = dict(_BM_TREE_BRANCHES).get(
            self.current_branch, self.current_branch.title()
        )
        embed.add_field(
            name=branch_label,
            value="\n".join(lines) if lines else "*No nodes in this branch.*",
            inline=False,
        )

        return embed

    async def _on_unlock(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            node_key = interaction.data["values"][0]
            node = BM_TREE_NODES.get(node_key)
            if not node:
                return

            current_lvl = self.tree_nodes.get(node_key, 0)
            if current_lvl >= node["max_level"]:
                await interaction.followup.send(
                    "This node is already fully unlocked.", ephemeral=True
                )
                return

            cost = node["idlem_costs"][current_lvl]
            ok = await self.bot.database.settlement.spend_idlem(
                self.user_id, self.server_id, cost
            )
            if not ok:
                await interaction.followup.send(
                    f"Need **{cost} Idlem** to unlock this. You have {self.idlem}.",
                    ephemeral=True,
                )
                return

            new_lvl = current_lvl + 1
            await self.bot.database.settlement.set_bm_node(
                self.user_id, self.server_id, node_key, new_lvl
            )

            self.tree_nodes[node_key] = new_lvl
            self.idlem -= cost

            self._build_ui()
            embed = self.build_embed()
            embed.add_field(
                name="✅ Node Unlocked",
                value=f"**{node['name']}** upgraded to level {new_lvl}!",
                inline=False,
            )
            await interaction.edit_original_response(embed=embed, view=self)
        finally:
            self._processing = False

    async def _on_back(self, interaction: Interaction) -> None:
        pending = await self.bot.database.settlement.get_pending_deal(
            self.user_id, self.server_id
        )
        zeal_data = await self.bot.database.settlement.get_zeal_data(
            self.user_id, self.server_id
        )
        self.parent_market.has_pending_deal = bool(pending)
        self.parent_market._setup_ui()
        await interaction.response.edit_message(
            embed=self.parent_market.build_embed(
                pending_deal=pending, zeal_data=zeal_data
            ),
            view=self.parent_market,
        )
        self.stop()
