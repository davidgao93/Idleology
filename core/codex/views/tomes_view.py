import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.images import CODEX_TOME
from core.models import Player
from database.repositories.codex import (
    TOME_GOLD_COSTS,
    TOME_UPGRADE_COSTS,
    get_reroll_cost,
    get_reroll_gold_cost,
)

_PASSIVE_LABELS = {
    "vitality": ("Vitality", "+{v:.1f}% Max HP"),
    "wrath": ("Wrath", "+{v:.1f}% DEF → ATK"),
    "bastion": ("Bastion", "+{v:.1f}% ATK → DEF"),
    "tenacity": ("Tenacity", "{v:.1f}% chance halve dmg"),
    "bloodthirst": ("Bloodthirst", "{v:.2f}% crit HP drain"),
    "providence": ("Providence", "+{v:.1f}% more Rarity"),
    "precision": ("Insight", "+{v:.1f} Crit Chance"),
    "affluence": ("Affluence", "+{v:.1f}% XP & Gold"),
    "bulwark": ("Bulwark", "+{v:.1f}% PDR"),
    "resilience": ("Resilience", "+{v:.0f} FDR"),
}


def _tome_field(tome) -> tuple[str, str]:
    """Returns (name, value) for an embed field showing a tome slot."""
    name_tmpl, val_tmpl = _PASSIVE_LABELS.get(
        tome.passive_type, (tome.passive_type, "{v:.1f}")
    )
    stat_str = val_tmpl.format(v=tome.value) if tome.value > 0 else "Not upgraded"
    return name_tmpl, f"Tier {tome.tier}/5 — {stat_str}"


class CodexTomsView(BaseView):
    """Shows a player's 5 tome slots and allows upgrading/rerolling."""

    def __init__(
        self,
        bot,
        user_id: str,
        player: Player,
        fragments: int,
        pages: int,
        rerolls: int,
        chapter_history: dict,
    ):
        super().__init__(bot, user_id, timeout=600)
        self.player = player
        self.fragments = fragments
        self.pages = pages
        self.rerolls = rerolls
        self.chapter_history = chapter_history
        self.selected_slot: int | None = None
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        tomes = self.player.codex_tomes
        slots = len(tomes)

        if slots > 0:
            options = [
                discord.SelectOption(
                    label=f"Slot {t.slot + 1}: {_PASSIVE_LABELS.get(t.passive_type, (t.passive_type, ''))[0]}",
                    value=str(t.slot),
                    description=f"Tier {t.tier}/5",
                )
                for t in tomes
            ]
            select = ui.Select(
                placeholder="Select a tome slot...", options=options, row=0
            )
            select.callback = self._on_slot_select
            self.add_item(select)

        can_unlock = slots < 5 and self.pages > 0
        unlock_btn = ui.Button(
            label=f"Unlock Slot ({self.pages} page{'s' if self.pages != 1 else ''})",
            style=ButtonStyle.success,
            disabled=not can_unlock,
            row=1,
        )
        unlock_btn.callback = self._on_unlock
        self.add_item(unlock_btn)

        if self.selected_slot is not None:
            tome = next((t for t in tomes if t.slot == self.selected_slot), None)
            if tome:
                can_upgrade = (
                    tome.tier < 5 and self.fragments >= TOME_UPGRADE_COSTS[tome.tier]
                )
                upgrade_cost = TOME_UPGRADE_COSTS[tome.tier] if tome.tier < 5 else 0
                upgrade_gold = TOME_GOLD_COSTS[tome.tier] if tome.tier < 5 else 0
                upgrade_btn = ui.Button(
                    label=f"Upgrade T{tome.tier}→T{tome.tier + 1} ({upgrade_cost}🔷 + {upgrade_gold // 1_000_000}m💰)",
                    style=ButtonStyle.primary,
                    disabled=not can_upgrade,
                    row=2,
                )
                upgrade_btn.callback = self._on_upgrade
                self.add_item(upgrade_btn)

                reroll_val_cost = get_reroll_cost(tome.tier)
                reroll_val_gold = get_reroll_gold_cost(tome.tier)
                can_reroll_val = tome.tier > 0 and self.fragments >= reroll_val_cost
                reroll_val_btn = ui.Button(
                    label=f"Reroll Value ({reroll_val_cost}🔷 + {reroll_val_gold // 1_000_000}m💰)",
                    style=ButtonStyle.secondary,
                    disabled=not can_reroll_val,
                    row=2,
                )
                reroll_val_btn.callback = self._on_reroll_value
                self.add_item(reroll_val_btn)

                can_reroll_type = self.pages > 0
                reroll_type_btn = ui.Button(
                    label="Reroll Type (1📄)",
                    style=ButtonStyle.danger,
                    disabled=not can_reroll_type,
                    row=2,
                )
                reroll_type_btn.callback = self._on_reroll_type
                self.add_item(reroll_type_btn)

        exit_btn = ui.Button(label="Close", style=ButtonStyle.secondary, row=3)
        exit_btn.callback = self._on_exit
        self.add_item(exit_btn)

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📚 Codex Tomes",
            color=discord.Color.dark_purple(),
        )
        embed.add_field(
            name="Resources",
            value=f"🔷 {self.fragments} Fragments  |  📄 {self.pages} Pages  |  🔁 {self.rerolls} Reroll Tokens",
            inline=False,
        )
        tomes = self.player.codex_tomes
        if not tomes:
            embed.add_field(
                name="No slots unlocked",
                value="Use a Codex Page to unlock your first slot.",
                inline=False,
            )
        else:
            for tome in tomes:
                name, value = _tome_field(tome)
                embed.add_field(
                    name=f"Slot {tome.slot + 1}: {name}", value=value, inline=True
                )
            unlocked = len(tomes)
            if unlocked < 5:
                for i in range(unlocked, 5):
                    embed.add_field(
                        name=f"Slot {i + 1}: 🔒 Locked",
                        value="Requires a Codex Page",
                        inline=True,
                    )

        if self.selected_slot is not None:
            tome = next((t for t in tomes if t.slot == self.selected_slot), None)
            if tome:
                name, _ = _PASSIVE_LABELS.get(
                    tome.passive_type, (tome.passive_type, "")
                )
                embed.set_footer(
                    text=f"Selected: Slot {self.selected_slot + 1} — {name} (Tier {tome.tier}/5, Value {tome.value:.2f})"
                )
        embed.set_thumbnail(url=CODEX_TOME)
        return embed

    async def _refresh(self, interaction: Interaction):
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _on_slot_select(self, interaction: Interaction):
        self.selected_slot = int(interaction.data["values"][0])
        await self._refresh(interaction)

    async def _on_unlock(self, interaction: Interaction):
        await interaction.response.defer()
        tome = await self.bot.database.codex.unlock_tome_slot(self.user_id)
        if tome is None:
            await interaction.followup.send(
                "All 5 slots are already unlocked.", ephemeral=True
            )
            return
        await self.bot.database.users.modify_currency(self.user_id, "codex_pages", -1)
        self.pages -= 1
        self.player.codex_tomes = await self.bot.database.codex.get_tomes(self.user_id)
        self.selected_slot = tome.slot
        self._rebuild()
        await interaction.edit_original_response(embed=self._build_embed(), view=self)

    async def _on_upgrade(self, interaction: Interaction):
        await interaction.response.defer()
        tome = next(
            (t for t in self.player.codex_tomes if t.slot == self.selected_slot), None
        )
        if not tome or tome.tier >= 5:
            return
        cost = TOME_UPGRADE_COSTS[tome.tier]
        gold_cost = TOME_GOLD_COSTS[tome.tier]
        if self.fragments < cost:
            await interaction.followup.send(
                "Not enough Codex Fragments.", ephemeral=True
            )
            return
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < gold_cost:
            await interaction.followup.send(
                f"You need **{gold_cost:,} gold** to upgrade this Tome tier.",
                ephemeral=True,
            )
            return
        ok, new_val = await self.bot.database.codex.upgrade_tome(
            self.user_id, self.selected_slot
        )
        if ok:
            await self.bot.database.users.modify_currency(
                self.user_id, "codex_fragments", -cost
            )
            await self.bot.database.users.modify_gold(self.user_id, -gold_cost)
            self.fragments -= cost
            self.player.codex_tomes = await self.bot.database.codex.get_tomes(
                self.user_id
            )
        self._rebuild()
        await interaction.edit_original_response(embed=self._build_embed(), view=self)

    async def _on_reroll_value(self, interaction: Interaction):
        await interaction.response.defer()
        tome = next(
            (t for t in self.player.codex_tomes if t.slot == self.selected_slot), None
        )
        if not tome or tome.tier == 0:
            return
        cost = get_reroll_cost(tome.tier)
        gold_cost = get_reroll_gold_cost(tome.tier)
        if self.fragments < cost:
            await interaction.followup.send(
                "Not enough Codex Fragments.", ephemeral=True
            )
            return
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < gold_cost:
            await interaction.followup.send(
                f"You need **{gold_cost:,} gold** to reroll a Tome value.",
                ephemeral=True,
            )
            return
        ok, _ = await self.bot.database.codex.reroll_tome_value(
            self.user_id, self.selected_slot
        )
        if ok:
            await self.bot.database.users.modify_currency(
                self.user_id, "codex_fragments", -cost
            )
            await self.bot.database.users.modify_gold(self.user_id, -gold_cost)
            self.fragments -= cost
            self.player.codex_tomes = await self.bot.database.codex.get_tomes(
                self.user_id
            )
        self._rebuild()
        await interaction.edit_original_response(embed=self._build_embed(), view=self)

    async def _on_reroll_type(self, interaction: Interaction):
        await interaction.response.defer()
        if self.pages <= 0:
            await interaction.followup.send("No Codex Pages available.", ephemeral=True)
            return
        ok, _ = await self.bot.database.codex.reroll_tome_type(
            self.user_id, self.selected_slot
        )
        if ok:
            await self.bot.database.users.modify_currency(
                self.user_id, "codex_pages", -1
            )
            self.pages -= 1
            self.player.codex_tomes = await self.bot.database.codex.get_tomes(
                self.user_id
            )
        self._rebuild()
        await interaction.edit_original_response(embed=self._build_embed(), view=self)

    async def _on_exit(self, interaction: Interaction):
        self.stop()
        from core.codex.views.menu_view import CodexMenuView

        antique_tomes = await self.bot.database.users.get_currency(
            self.user_id, "antique_tome"
        )
        menu = CodexMenuView(
            self.bot,
            self.user_id,
            self.player,
            self.fragments,
            self.pages,
            self.rerolls,
            self.chapter_history,
            antique_tomes=antique_tomes,
        )
        await interaction.response.edit_message(embed=menu.build_embed(), view=menu)
