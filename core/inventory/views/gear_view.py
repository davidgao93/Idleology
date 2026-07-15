import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.combat.calc.calcs import fmt_weapon_passive
from core.inventory.inventory import InventoryUI

# Core Imports
from core.items.factory import (
    create_accessory,
    create_armor,
    create_boot,
    create_glove,
    create_helmet,
    create_weapon,
)
from core.models import Accessory, Armor, Boot, Glove, Helmet, Weapon
from core.util import stars

from .detail_view import ItemDetailView
from .loadout_view import LoadoutView
from .modals import MassDiscardModal
from ._slot_defs import (
    SLOT_EMOJIS as _SLOT_EMOJIS,
    SLOT_LABELS as _SLOT_LABELS,
    SLOT_ORDER,
)

_FACTORIES = [
    create_weapon,
    create_armor,
    create_helmet,
    create_glove,
    create_boot,
    create_accessory,
]
SLOT_CONFIG = {
    slot: {"emoji": _SLOT_EMOJIS[slot], "label": _SLOT_LABELS[slot], "factory": factory}
    for slot, factory in zip(SLOT_ORDER, _FACTORIES)
}


class GearView(BaseView):
    """
    Unified gear management view. Shows all six equipment slots via tab buttons
    and uses a Select menu (up to 25 items per page) instead of number buttons.

    Exposes the same interface as InventoryListView so that ItemDetailView,
    MassDiscardModal, and all upgrade views work without modification:
      .equipped_id          (property — per active slot)
      .items                (property — list for active slot)
      .items_per_page       (property — always 25)
      .total_pages          (property — computed)
      .update_buttons()     (alias for update_components)
      .get_current_embed()  (alias for build_embed)
      ._get_db_type()
    """

    def __init__(
        self,
        bot,
        user_id: str,
        all_items: dict,
        initial_slot: str = "weapon",
        player_name: str = "",
    ):
        super().__init__(bot=bot, user_id=user_id)
        self.bot = bot
        self.user_id = user_id
        self.all_items = all_items  # dict[slot -> List[item model]]
        self.active_slot = initial_slot
        self.player_name = player_name
        self.current_page = 0
        self._processing = False

        # Per-slot equipped IDs — source of truth; updated by ItemDetailView.toggle_equip
        self.equipped_ids: dict = {
            slot: self._scan_equipped_id(slot) for slot in SLOT_ORDER
        }

        self.update_components()

    # ------------------------------------------------------------------
    # Adapter interface for ItemDetailView / MassDiscardModal compatibility
    # ------------------------------------------------------------------

    @property
    def equipped_id(self):
        return self.equipped_ids.get(self.active_slot)

    @equipped_id.setter
    def equipped_id(self, value):
        self.equipped_ids[self.active_slot] = value

    @property
    def items(self):
        return self.all_items[self.active_slot]

    @items.setter
    def items(self, value):
        self.all_items[self.active_slot] = value

    @property
    def items_per_page(self):
        return 25

    @property
    def total_pages(self):
        return self._get_total_pages()

    @total_pages.setter
    def total_pages(self, value):
        pass  # Computed dynamically; writes from MassDiscardModal are no-ops

    def update_buttons(self):
        """Alias used by ItemDetailView and MassDiscardModal."""
        self.update_components()

    async def get_current_embed(self) -> discord.Embed:
        """Alias used by ItemDetailView.go_back."""
        return self.build_embed()

    def _get_db_type(self) -> str:
        """Alias used by MassDiscardModal."""
        return self.active_slot

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_equipped_id(self, slot: str):
        for item in self.all_items.get(slot, []):
            if getattr(item, "is_equipped", False):
                return item.item_id
        return None

    def _get_total_pages(self) -> int:
        count = len(self.all_items.get(self.active_slot, []))
        return max(1, (count + 24) // 25)

    def _find_item_by_id(self, item_id: int):
        for item in self.all_items.get(self.active_slot, []):
            if item.item_id == item_id:
                return item
        return None

    @staticmethod
    def _build_select_description(item) -> str:
        """One-line stat summary for the Select option description (max 100 chars)."""
        parts = []
        if getattr(item, "attack", 0) > 0:
            parts.append(f"ATK:{item.attack}")
        if isinstance(item, Armor):
            main_stat_type = getattr(item, "main_stat_type", "def")
            main_stat = getattr(item, "main_stat", 0)
            if main_stat > 0:
                label = "ATK" if main_stat_type == "atk" else "DEF"
                parts.append(f"{label}:{main_stat}")
        elif getattr(item, "defence", 0) > 0:
            parts.append(f"DEF:{item.defence}")
        if getattr(item, "rarity", 0) > 0:
            parts.append(f"Rar:{item.rarity}%")
        if getattr(item, "ward", 0) > 0:
            parts.append(f"Ward:{item.ward}%")
        if getattr(item, "crit", 0) > 0:
            parts.append(f"Crit:{item.crit}")
        if getattr(item, "block", 0) > 0:
            parts.append(f"Block:{item.block}%")
        if getattr(item, "evasion", 0) > 0:
            parts.append(f"Eva:{item.evasion}%")
        if getattr(item, "pdr", 0) > 0:
            parts.append(f"PDR:{item.pdr}%")
        if getattr(item, "fdr", 0) > 0:
            parts.append(f"FDR:{item.fdr}")

        passives = []
        if getattr(item, "passive", "none") not in ("none", ""):
            if isinstance(item, Weapon):
                passives.append(fmt_weapon_passive(item.passive))
            else:
                lvl = getattr(item, "passive_lvl", 0)
                lvl_str = f" Lv.{lvl}" if lvl > 0 else ""
                passives.append(f"{item.passive.title()}{lvl_str}")
        if isinstance(item, Weapon):
            if getattr(item, "p_passive", "none") not in ("none", ""):
                passives.append(fmt_weapon_passive(item.p_passive))
            if getattr(item, "u_passive", "none") not in ("none", ""):
                passives.append(fmt_weapon_passive(item.u_passive))
            if getattr(item, "infernal_passive", "none") not in ("none", ""):
                passives.append(item.infernal_passive.replace("_", " ").title())
        if isinstance(item, Armor) and getattr(
            item, "celestial_passive", "none"
        ) not in ("none", ""):
            passives.append(item.celestial_passive.replace("_", " ").title())
        if isinstance(item, Accessory) and getattr(
            item, "void_passive", "none"
        ) not in ("none", ""):
            passives.append(item.void_passive.replace("_", " ").title())

        stat_str = " ".join(parts)
        passive_str = " · ".join(passives)
        body = (
            f"{stat_str} | {passive_str}"
            if stat_str and passive_str
            else stat_str or passive_str or "No stats"
        )
        if isinstance(item, Weapon):
            base_rar = getattr(item, "base_rarity", 0)
            prefix = f"[{stars(base_rar)}] " if base_rar > 0 else ""
            desc = prefix + body
        else:
            desc = body

        if len(desc) > 100:
            desc = desc[:97] + "..."
        return desc

    def _build_select_options(self, page_items) -> list:
        options = []
        for item in page_items:
            is_equipped = item.item_id == self.equipped_id

            label = f"{'[E] ' if is_equipped else ''}Lv.{item.level} {item.name}"
            if isinstance(item, Weapon) and item.refinement_lvl > 0:
                label += f" (+{item.refinement_lvl})"
            elif isinstance(item, (Armor, Glove, Boot, Helmet)):
                reinforce_lvl = getattr(item, "reinforcement_lvl", 0)
                if reinforce_lvl > 0:
                    label += f" (+{reinforce_lvl})"
            elif hasattr(item, "passive_lvl") and item.passive_lvl > 0:
                label += f" (+{item.passive_lvl})"
            if len(label) > 100:
                label = label[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(item.item_id),
                    description=self._build_select_description(item),
                )
            )
        return options

    # ------------------------------------------------------------------
    # Component rebuild
    # ------------------------------------------------------------------

    def update_components(self):
        self.clear_items()

        slot_items = self.all_items.get(self.active_slot, [])
        total_pages = self._get_total_pages()

        # Clamp page
        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)

        start = self.current_page * 25
        page_items = slot_items[start : start + 25]

        # Row 0 — Select menu or empty placeholder
        if page_items:
            options = self._build_select_options(page_items)
            select = discord.ui.Select(
                placeholder=f"Choose a {SLOT_CONFIG[self.active_slot]['label'].lower()}...",
                options=options,
                row=0,
            )

            # Capture select in closure so the callback can read .values
            async def _on_select(interaction: Interaction, s=select):
                await self._handle_select(interaction, s)

            select.callback = _on_select
            self.add_item(select)
        else:
            cfg = SLOT_CONFIG[self.active_slot]
            empty = Button(
                label=f"No {cfg['label']}s in inventory",
                style=ButtonStyle.secondary,
                disabled=True,
                row=0,
            )
            self.add_item(empty)

        # Rows 1–2 — Slot tab buttons (3 per row)
        for row_idx, slots in enumerate([SLOT_ORDER[:3], SLOT_ORDER[3:]], start=1):
            for slot in slots:
                cfg = SLOT_CONFIG[slot]
                style = (
                    ButtonStyle.primary
                    if slot == self.active_slot
                    else ButtonStyle.secondary
                )
                btn = Button(
                    label=cfg["label"], emoji=cfg["emoji"], style=style, row=row_idx
                )
                btn.callback = lambda i, s=slot: self.switch_slot(i, s)
                self.add_item(btn)

        # Row 3 — Prev / Next (only when multi-page)
        if total_pages > 1:
            prev = Button(label="◀ Prev", disabled=(self.current_page == 0), row=3)
            prev.callback = self.prev_page
            self.add_item(prev)

            nxt = Button(
                label="▶ Next", disabled=(self.current_page >= total_pages - 1), row=3
            )
            nxt.callback = self.next_page
            self.add_item(nxt)

        # Row 4 — Mass Discard | Loadouts | Close
        mass = Button(
            label="Mass Discard",
            style=ButtonStyle.danger,
            emoji="🗑️",
            disabled=(len(slot_items) == 0),
            row=4,
        )
        mass.callback = self.mass_discard_callback
        self.add_item(mass)

        loadouts_btn = Button(label="📦 Loadouts", style=ButtonStyle.secondary, row=4)
        loadouts_btn.callback = self.open_loadouts
        self.add_item(loadouts_btn)

        close = Button(label="Close", style=ButtonStyle.secondary, emoji="✖️", row=4)
        close.callback = self.close_view
        self.add_item(close)

    # ------------------------------------------------------------------
    # Embed builder
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        return InventoryUI.get_gear_embed(
            self.player_name,
            self.all_items,
            self.active_slot,
            self.equipped_ids,
            self.current_page,
            self._get_total_pages(),
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def switch_slot(self, interaction: Interaction, slot_key: str):
        self.active_slot = slot_key
        self.current_page = 0
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
        self.message = await interaction.original_response()

    async def _handle_select(self, interaction: Interaction, select: discord.ui.Select):
        item_id = int(select.values[0])
        item = self._find_item_by_id(item_id)
        if item is None:
            return await interaction.response.send_message(
                "Item not found.", ephemeral=True
            )

        detail_view = ItemDetailView(self.bot, self.user_id, item, self)
        await detail_view.fetch_data()
        embed = InventoryUI.get_item_details_embed(
            item, item.item_id == self.equipped_id
        )
        await interaction.response.edit_message(
            content=None, embed=embed, view=detail_view
        )
        self.message = await interaction.original_response()

    async def prev_page(self, interaction: Interaction):
        self.current_page = max(0, self.current_page - 1)
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
        self.message = await interaction.original_response()

    async def next_page(self, interaction: Interaction):
        self.current_page = min(self._get_total_pages() - 1, self.current_page + 1)
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
        self.message = await interaction.original_response()

    async def mass_discard_callback(self, interaction: Interaction):
        await interaction.response.send_modal(MassDiscardModal(self))

    async def open_loadouts(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        server_id = str(interaction.guild_id)
        try:
            view = await LoadoutView.create(
                self.bot,
                self.user_id,
                server_id,
                mode="from_gear",
                parent_view=self,
                player_name=self.player_name,
            )
        except Exception:
            self._processing = False
            raise
        await interaction.response.edit_message(embed=view.build_embed(), view=view)
        self.message = await interaction.original_response()

    async def close_view(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()
