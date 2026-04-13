"""
Essence UI — EssenceView, EssenceSelectView, ConfirmApplyView, ConfirmUtilityView.

Flow:
  EssenceView (hub) → EssenceSelectView (pick essence) → ConfirmApplyView
                    → ConfirmUtilityView (cleanse / chaos / annul)
"""

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button, Select, View

from core.items.essence_mechanics import (
    CORRUPTED_ESSENCE_TYPES,
    ESSENCE_VALUE_RANGES,
    REGULAR_ESSENCE_TYPES,
    can_apply_essence,
    can_apply_utility,
    get_essence_slots,
    next_open_slot,
    reroll_all_values,
    roll_essence_value,
)
from core.models import Boot, Glove, Helmet

# ---------------------------------------------------------------------------
# Display constants
# ---------------------------------------------------------------------------

ESSENCE_DISPLAY = {
    "power": ("✦ Essence of Power", "🔆"),
    "protection": ("✦ Essence of Protection", "🛡️"),
    "insight": ("✦ Essence of Insight", "👁️"),
    "evasion": ("✦ Essence of Evasion", "💨"),
    "warding": ("✦ Essence of Unyielding", "🧱"),
    "cleansing": ("✦ Essence of Cleansing", "🌊"),
    "chaos": ("✦ Essence of Chaos", "🌀"),
    "annulment": ("✦ Essence of Annulment", "✂️"),
    "aphrodite": ("✦ Essence of Aphrodite's Disciple", "💠"),
    "lucifer": ("✦ Essence of Lucifer's Heir", "💠"),
    "gemini": ("✦ Essence of Gemini's Lost Twin", "💠"),
    "neet": ("✦ Essence of NEET's Voidling", "💠"),
}

ESSENCE_BRIEF = {
    "power": "Boosts item's main stat (ATK on gloves/boots, DEF+WARD on helmets)",
    "protection": "Amplifies existing PDR and FDR on the item",
    "insight": "Grants flat critical hit chance reduction",
    "evasion": "Grants flat evasion chance",
    "warding": "Grants flat block chance",
    "cleansing": "Removes all 3 regular essence slots from the item",
    "chaos": "Rerolls values on all occupied regular essence slots",
    "annulment": "Removes one random regular essence slot",
    "aphrodite": "Glove: ward-break on hit · Boot: lucky gear drops · Helmet: ward disable immunity",
    "lucifer": "Glove: bonus dmg from ward · Boot: gold scales with modifiers · Helmet: PDR burst on ward break",
    "gemini": "Glove: double strike on crit · Boot: PDR→rarity · Helmet: dmg splits ward and HP",
    "neet": "Glove: def pierce = FDR · Boot: stacking kill rarity · Helmet: ward regen from missing HP",
}


# ---------------------------------------------------------------------------
# Embed helpers
# ---------------------------------------------------------------------------


def _format_slot_value(essence_type: str, value: float, item) -> str:
    """Returns a human-readable stat line for an occupied essence slot."""
    is_helmet = isinstance(item, Helmet)

    if essence_type == "power":
        if is_helmet:
            def_bonus = int(item.defence * value / 100)
            ward_bonus = int(item.ward * value / 100)
            return f"+{def_bonus} DEF, +{ward_bonus}% WARD  ({value:.0f}% of base)"
        else:
            atk_bonus = int(item.attack * value / 100)
            return f"+{atk_bonus} ATK  ({value:.0f}% of base)"

    elif essence_type == "protection":
        pdr_bonus = int(item.pdr * value / 100)
        fdr_bonus = int(item.fdr * value / 100)
        return f"+{pdr_bonus}% PDR, +{fdr_bonus} FDR  ({value:.0f}% of base)"

    elif essence_type == "insight":
        return f"+{int(value)} Crit Target Reduction"

    elif essence_type == "evasion":
        return f"+{int(value)} Evasion"

    elif essence_type == "warding":
        return f"+{int(value)} Block Chance"

    return str(value)


def _build_essence_embed(item, essence_inventory: dict) -> discord.Embed:
    """Builds the main essence management embed for a given item."""
    if isinstance(item, Glove):
        item_type_label = "Glove"
    elif isinstance(item, Boot):
        item_type_label = "Boot"
    else:
        item_type_label = "Helmet"

    embed = discord.Embed(
        title=f"✦ Essence Forge — {item.name}",
        description=f"*{item_type_label} · Level {item.level}*",
        color=0x9B59B6,
    )

    # --- Regular slots ---
    slot_lines = []
    for i in (1, 2, 3):
        t = getattr(item, f"essence_{i}", "none") or "none"
        v = getattr(item, f"essence_{i}_val", 0.0) or 0.0
        if t != "none":
            e_name, emoji = ESSENCE_DISPLAY.get(t, (t.title(), "💠"))
            stat_str = _format_slot_value(t, v, item)
            slot_lines.append(f"**Slot {i}:** {emoji} {e_name}\n   ↳ {stat_str}")
        else:
            slot_lines.append(f"**Slot {i}:** *— Empty —*")

    embed.add_field(
        name="Regular Essence Slots", value="\n".join(slot_lines), inline=False
    )

    # --- Corrupted slot ---
    corrupted = getattr(item, "corrupted_essence", "none") or "none"
    if corrupted != "none":
        c_name, c_emoji = ESSENCE_DISPLAY.get(corrupted, (corrupted.title(), "💠"))
        c_brief = ESSENCE_BRIEF.get(corrupted, "")
        embed.add_field(
            name="Corrupted Slot",
            value=f"{c_emoji} {c_name}\n   ↳ {c_brief}",
            inline=False,
        )
    else:
        embed.add_field(name="Corrupted Slot", value="*— Empty —*", inline=False)

    # --- Owned essences summary ---
    owned_lines = []
    for cat_name, types in [
        ("Common", ["power", "protection"]),
        ("Rare", ["insight", "evasion", "warding"]),
        ("Utility", ["cleansing", "chaos", "annulment"]),
        ("Corrupted", ["aphrodite", "lucifer", "gemini", "neet"]),
    ]:
        cat_parts = []
        for etype in types:
            qty = essence_inventory.get(etype, 0)
            if qty > 0:
                e_name, emoji = ESSENCE_DISPLAY.get(etype, (etype.title(), "💠"))
                cat_parts.append(f"{emoji} {e_name}: **×{qty}**")
        if cat_parts:
            owned_lines.append(f"**{cat_name}:** " + "  ·  ".join(cat_parts))

    inv_text = "\n".join(owned_lines) if owned_lines else "*You have no essences.*"
    embed.add_field(name="Your Essences", value=inv_text, inline=False)

    return embed


# ---------------------------------------------------------------------------
# ConfirmApplyView
# ---------------------------------------------------------------------------


class ConfirmApplyView(View):
    """Yes/No confirmation before applying a regular or corrupted essence."""

    def __init__(self, hub: "EssenceView", essence_type: str, corrupted: bool):
        super().__init__(timeout=60)
        self.hub = hub
        self.essence_type = essence_type
        self.corrupted = corrupted

    @discord.ui.button(label="Confirm", style=ButtonStyle.success)
    async def confirm(self, interaction: Interaction, button: Button):
        await interaction.response.defer()

        consumed = await self.hub.bot.database.essences.consume(
            self.hub.user_id, self.essence_type
        )
        if not consumed:
            await interaction.followup.send(
                "You no longer have that essence.", ephemeral=True
            )
            self.hub._build_buttons()
            await interaction.edit_original_response(
                embed=self.hub._get_embed(), view=self.hub
            )
            self.stop()
            return

        if self.corrupted:
            await self.hub.bot.database.equipment.apply_corrupted_essence(
                self.hub.item.item_id, self.hub.item_type, self.essence_type
            )
        else:
            slot = next_open_slot(self.hub.item)
            value = roll_essence_value(self.essence_type)
            await self.hub.bot.database.equipment.apply_essence(
                self.hub.item.item_id,
                self.hub.item_type,
                slot,
                self.essence_type,
                value,
            )

        await self.hub.refresh(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: Button):
        self.hub._build_buttons()
        await interaction.response.edit_message(
            embed=self.hub._get_embed(), view=self.hub
        )
        self.stop()

    async def on_timeout(self):
        self.hub.bot.state_manager.clear_active(self.hub.user_id)


# ---------------------------------------------------------------------------
# ConfirmUtilityView
# ---------------------------------------------------------------------------


class ConfirmUtilityView(View):
    """Yes/No confirmation before consuming a utility essence (cleanse / chaos / annul)."""

    def __init__(self, hub: "EssenceView", utility_type: str):
        super().__init__(timeout=60)
        self.hub = hub
        self.utility_type = utility_type

    @discord.ui.button(label="Confirm", style=ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: Button):
        await interaction.response.defer()

        consumed = await self.hub.bot.database.essences.consume(
            self.hub.user_id, self.utility_type
        )
        if not consumed:
            await interaction.followup.send(
                "You no longer have that essence.", ephemeral=True
            )
            self.hub._build_buttons()
            await interaction.edit_original_response(
                embed=self.hub._get_embed(), view=self.hub
            )
            self.stop()
            return

        if self.utility_type == "cleansing":
            await self.hub.bot.database.equipment.clear_essences(
                self.hub.item.item_id, self.hub.item_type
            )
        elif self.utility_type == "chaos":
            slots = get_essence_slots(self.hub.item)
            new_values = reroll_all_values(slots)
            await self.hub.bot.database.equipment.reroll_essences(
                self.hub.item.item_id, self.hub.item_type, new_values
            )
        elif self.utility_type == "annulment":
            await self.hub.bot.database.equipment.remove_random_essence(
                self.hub.item.item_id, self.hub.item_type
            )

        await self.hub.refresh(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: Button):
        self.hub._build_buttons()
        await interaction.response.edit_message(
            embed=self.hub._get_embed(), view=self.hub
        )
        self.stop()

    async def on_timeout(self):
        self.hub.bot.state_manager.clear_active(self.hub.user_id)


# ---------------------------------------------------------------------------
# EssenceSelectView
# ---------------------------------------------------------------------------


class EssenceSelectView(View):
    """Select menu to choose which essence to apply (regular or corrupted)."""

    def __init__(self, hub: "EssenceView", applicable: list, corrupted: bool):
        super().__init__(timeout=120)
        self.hub = hub
        self.corrupted = corrupted

        options = []
        for etype, qty in applicable:
            e_name, emoji = ESSENCE_DISPLAY.get(etype, (etype.title(), "💠"))
            brief = ESSENCE_BRIEF.get(etype, "")
            label = f"{e_name} ×{qty}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=etype,
                    description=brief[:100],
                    emoji=emoji,
                )
            )

        select = Select(placeholder="Choose an essence…", options=options, row=0)
        select.callback = self._on_select
        self.add_item(select)

        back_btn = Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self._go_back
        self.add_item(back_btn)

    async def _on_select(self, interaction: Interaction):
        chosen = interaction.data["values"][0]
        qty = self.hub.essence_inventory.get(chosen, 0)
        e_name, emoji = ESSENCE_DISPLAY.get(chosen, (chosen.title(), "💠"))

        embed = discord.Embed(
            title=f"{emoji} Apply: {e_name}",
            color=0xE74C3C if self.corrupted else 0x9B59B6,
        )
        embed.add_field(
            name="Item",
            value=f"**{self.hub.item.name}** (Lv.{self.hub.item.level})",
            inline=False,
        )
        embed.add_field(
            name="Effect", value=ESSENCE_BRIEF.get(chosen, ""), inline=False
        )

        if not self.corrupted:
            r = ESSENCE_VALUE_RANGES.get(chosen)
            if r:
                embed.add_field(name="Roll Range", value=f"{r[0]}–{r[1]}", inline=True)

        if self.corrupted:
            embed.add_field(
                name="⚠️ Warning",
                value="Corrupted essences **cannot be removed** once applied.",
                inline=False,
            )

        embed.set_footer(text=f"You own ×{qty}. This will consume 1.")
        confirm_view = ConfirmApplyView(self.hub, chosen, self.corrupted)
        await interaction.response.edit_message(embed=embed, view=confirm_view)

    async def _go_back(self, interaction: Interaction):
        self.hub._build_buttons()
        await interaction.response.edit_message(
            embed=self.hub._get_embed(), view=self.hub
        )

    async def on_timeout(self):
        self.hub.bot.state_manager.clear_active(self.hub.user_id)


# ---------------------------------------------------------------------------
# EssenceView — main hub
# ---------------------------------------------------------------------------


class EssenceView(View):
    """
    Hub for managing essences on a single glove / boot / helmet.
    Opened from ItemDetailView via the "Essences" button.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        item,
        item_type: str,
        parent_view,
        essence_inventory: dict,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.item = item
        self.item_type = item_type  # "glove" | "boot" | "helmet"
        self.parent = parent_view  # ItemDetailView
        self.essence_inventory = essence_inventory
        self._build_buttons()

    # ------------------------------------------------------------------
    # Button layout
    # ------------------------------------------------------------------

    def _build_buttons(self):
        self.clear_items()
        slots = get_essence_slots(self.item)
        corrupted = getattr(self.item, "corrupted_essence", "none") or "none"

        # Row 0 — apply buttons
        if len(slots) < 3:
            apply_btn = Button(
                label="Apply Essence", style=ButtonStyle.success, row=0
            )
            apply_btn.callback = self._open_apply_regular
            self.add_item(apply_btn)

        if corrupted == "none":
            cor_btn = Button(
                label="Apply Corrupted", style=ButtonStyle.primary, emoji="💠", row=0
            )
            cor_btn.callback = self._open_apply_corrupted
            self.add_item(cor_btn)

        # Row 1 — utility buttons (only if there are slots to act on)
        if slots:
            for label, emoji_char, util_type in [
                ("Cleanse", "🌊", "cleansing"),
                ("Chaos", "🌀", "chaos"),
                ("Annul", "✂️", "annulment"),
            ]:
                qty = self.essence_inventory.get(util_type, 0)
                btn = Button(
                    label=f"{label} ×{qty}",
                    style=(
                        ButtonStyle.danger
                        if label == "Cleanse"
                        else ButtonStyle.secondary
                    ),
                    emoji=emoji_char,
                    disabled=qty == 0,
                    row=1,
                )
                btn.callback = self._make_utility_cb(util_type)
                self.add_item(btn)

        # Row 2 — navigation
        back_btn = Button(label="Back", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self._go_back
        self.add_item(back_btn)

    def _make_utility_cb(self, utility_type: str):
        async def _cb(interaction: Interaction):
            await self._confirm_utility(interaction, utility_type)

        return _cb

    # ------------------------------------------------------------------
    # Embed helper
    # ------------------------------------------------------------------

    def _get_embed(self) -> discord.Embed:
        return _build_essence_embed(self.item, self.essence_inventory)

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _open_apply_regular(self, interaction: Interaction):
        applicable = []
        for etype in sorted(REGULAR_ESSENCE_TYPES):
            qty = self.essence_inventory.get(etype, 0)
            if qty > 0:
                ok, _ = can_apply_essence(self.item, etype)
                if ok:
                    applicable.append((etype, qty))

        if not applicable:
            return await interaction.response.send_message(
                "You have no applicable regular essences for this item.", ephemeral=True
            )

        embed = discord.Embed(
            title="Apply Essence",
            description="Choose a regular essence from your inventory.",
            color=0x9B59B6,
        )
        await interaction.response.edit_message(
            embed=embed, view=EssenceSelectView(self, applicable, corrupted=False)
        )

    async def _open_apply_corrupted(self, interaction: Interaction):
        applicable = []
        for etype in sorted(CORRUPTED_ESSENCE_TYPES):
            qty = self.essence_inventory.get(etype, 0)
            if qty > 0:
                ok, _ = can_apply_essence(self.item, etype)
                if ok:
                    applicable.append((etype, qty))

        if not applicable:
            return await interaction.response.send_message(
                "You have no corrupted essences.", ephemeral=True
            )

        embed = discord.Embed(
            title="Apply Corrupted Essence",
            description="⚠️ Corrupted essences cannot be removed once applied.",
            color=0xE74C3C,
        )
        await interaction.response.edit_message(
            embed=embed, view=EssenceSelectView(self, applicable, corrupted=True)
        )

    async def _confirm_utility(self, interaction: Interaction, utility_type: str):
        ok, reason = can_apply_utility(self.item, utility_type)
        if not ok:
            return await interaction.response.send_message(reason, ephemeral=True)

        qty = self.essence_inventory.get(utility_type, 0)
        if qty == 0:
            return await interaction.response.send_message(
                f"You don't have any {utility_type} essences.", ephemeral=True
            )

        e_name, emoji = ESSENCE_DISPLAY.get(utility_type, (utility_type.title(), "💠"))
        desc_map = {
            "cleansing": "This will **remove all 3 regular essence slots** from the item.",
            "chaos": "This will **reroll the values** on all occupied essence slots. Types are preserved.",
            "annulment": "This will **remove one random** regular essence slot from the item.",
        }

        embed = discord.Embed(
            title=f"{emoji} {e_name}",
            description=desc_map.get(utility_type, ""),
            color=0xE67E22,
        )
        embed.add_field(
            name="Item", value=f"**{self.item.name}** (Lv.{self.item.level})"
        )
        embed.set_footer(text="You will consume 1 essence.")
        await interaction.response.edit_message(
            embed=embed, view=ConfirmUtilityView(self, utility_type)
        )

    async def _go_back(self, interaction: Interaction):
        from core.ui.inventory import InventoryUI

        embed = InventoryUI.get_item_details_embed(
            self.parent.item, self.parent.is_equipped
        )
        await interaction.response.edit_message(embed=embed, view=self.parent)

    # ------------------------------------------------------------------
    # Refresh — re-fetch item and essence inventory after a change
    # ------------------------------------------------------------------

    async def refresh(self, interaction: Interaction):
        from core.items.factory import create_boot, create_glove, create_helmet

        factories = {
            "glove": create_glove,
            "boot": create_boot,
            "helmet": create_helmet,
        }
        factory = factories[self.item_type]

        rows = await self.bot.database.equipment.get_all(self.user_id, self.item_type)
        for row in rows:
            new_item = factory(row)
            if new_item.item_id == self.item.item_id:
                self.item = new_item
                self.parent.item = new_item  # keep ItemDetailView in sync
                break

        self.essence_inventory = await self.bot.database.essences.get_all(self.user_id)
        self._build_buttons()
        await interaction.edit_original_response(embed=self._get_embed(), view=self)

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
