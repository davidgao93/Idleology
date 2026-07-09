import asyncio

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.emojis import (
    HEMATURGY_ICON,
    RARITY,
    STAT_ATK,
    STAT_BLOCK,
    STAT_DEF,
    STAT_FDR,
    STAT_HP,
    STAT_PDR,
)
from core.images import CODEX_TOME, SERAPHINE_PORTRAIT, SERAPHINE_THUMBNAIL
from core.models import CodexTome, Player
from core.npc_voices import get_quip
from database.repositories.codex import (
    TOME_GOLD_COSTS,
    TOME_TIER_RANGES,
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

# Icon shown next to each passive's name — reuses existing stat/material
# emoji where the passive maps directly onto a stat; 🗡️/👑 for the two
# without an existing dedicated asset (Insight/Affluence).
_PASSIVE_EMOJI = {
    "vitality": STAT_HP,
    "wrath": STAT_ATK,
    "bastion": STAT_DEF,
    "tenacity": STAT_BLOCK,
    "bloodthirst": HEMATURGY_ICON,
    "providence": RARITY,
    "precision": "🗡️",
    "affluence": "👑",
    "bulwark": STAT_PDR,
    "resilience": STAT_FDR,
}


def _passive_display_name(passive_type: str) -> str:
    """Emoji-prefixed display name for contexts that render custom emoji
    tags inline (embed text) — NOT for SelectOption labels, which only
    show plain text and need the emoji passed via their own `emoji=` kwarg."""
    name, _ = _PASSIVE_LABELS.get(passive_type, (passive_type, ""))
    emoji = _PASSIVE_EMOJI.get(passive_type)
    return f"{emoji} {name}" if emoji else name

_PASSIVE_DESCRIPTIONS = {
    "vitality": "Hardens your body, permanently raising your maximum HP.",
    "wrath": "Channels fury, converting a portion of your Defence into Attack.",
    "bastion": "Anchors your stance, converting a portion of your Attack into Defence.",
    "tenacity": "Grit under fire — a chance to halve incoming damage.",
    "bloodthirst": "Feeds on violence, healing you on critical hits.",
    "providence": "Favour of fortune, boosting your total drop rarity.",
    "precision": "Sharpens your eye, raising your flat Crit Chance.",
    "affluence": "Draws in wealth, boosting XP and Gold earned in combat.",
    "bulwark": "Reinforces your guard, raising your Percent Damage Reduction.",
    "resilience": "Toughens your hide, raising your Flat Damage Reduction.",
}


def _tome_field(tome) -> tuple[str, str]:
    """Returns (name, value) for an embed field showing a tome slot."""
    _, val_tmpl = _PASSIVE_LABELS.get(tome.passive_type, (tome.passive_type, "{v:.1f}"))
    stat_str = val_tmpl.format(v=tome.value) if tome.value > 0 else "Not upgraded"
    return _passive_display_name(tome.passive_type), f"Tier {tome.tier}/5 — {stat_str}"


def _passive_range_text(passive_type: str) -> str:
    """Formats the tier-1 and tier-5 (max) value ranges for a passive type,
    so a freshly unlocked slot's growth potential is clear at a glance."""
    _, val_tmpl = _PASSIVE_LABELS.get(passive_type, (passive_type, "{v:.1f}"))
    ranges = TOME_TIER_RANGES.get(passive_type)
    if not ranges:
        return "Unknown"
    t1_lo, t1_hi = ranges[0]
    t5_lo, t5_hi = ranges[4]
    t1 = f"{val_tmpl.format(v=t1_lo)} – {val_tmpl.format(v=t1_hi)}"
    t5 = f"{val_tmpl.format(v=t5_lo)} – {val_tmpl.format(v=t5_hi)}"
    return f"**Tier 1:** {t1}\n**Tier 5 (max):** {t5}"


class CodexTomsView(BaseLayoutView):
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
        server_id: str = "",
        player_avatar_url: str | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.fragments = fragments
        self.pages = pages
        self.rerolls = rerolls
        self.chapter_history = chapter_history
        self.player_avatar_url = player_avatar_url
        self.selected_slot: int | None = None
        self._processing = False
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(self._build_embed()))

        tomes = self.player.codex_tomes
        slots = len(tomes)

        if slots > 0:
            options = [
                discord.SelectOption(
                    label=f"Slot {t.slot + 1}: {_PASSIVE_LABELS.get(t.passive_type, (t.passive_type, ''))[0]}",
                    value=str(t.slot),
                    description=f"Tier {t.tier}/5",
                    emoji=_PASSIVE_EMOJI.get(t.passive_type),
                )
                for t in tomes
            ]
            select_row = ui.ActionRow()
            select = ui.Select(placeholder="Select a tome slot...", options=options)
            select.callback = self._on_slot_select
            select_row.add_item(select)
            self.add_item(select_row)

        can_unlock = slots < 5 and self.pages > 0
        unlock_row = ui.ActionRow()
        unlock_btn = ui.Button(
            label=f"Unlock Slot ({self.pages} page{'s' if self.pages != 1 else ''})",
            style=ButtonStyle.success,
            disabled=not can_unlock,
        )
        unlock_btn.callback = self._on_unlock
        unlock_row.add_item(unlock_btn)
        self.add_item(unlock_row)

        if self.selected_slot is not None:
            tome = next((t for t in tomes if t.slot == self.selected_slot), None)
            if tome:
                actions_row = ui.ActionRow()

                can_upgrade = (
                    tome.tier < 5 and self.fragments >= TOME_UPGRADE_COSTS[tome.tier]
                )
                upgrade_cost = TOME_UPGRADE_COSTS[tome.tier] if tome.tier < 5 else 0
                upgrade_gold = TOME_GOLD_COSTS[tome.tier] if tome.tier < 5 else 0
                upgrade_btn = ui.Button(
                    label=f"Upgrade T{tome.tier}→T{tome.tier + 1} ({upgrade_cost}🔷 + {upgrade_gold // 1_000_000}m💰)",
                    style=ButtonStyle.primary,
                    disabled=not can_upgrade,
                )
                upgrade_btn.callback = self._on_upgrade
                actions_row.add_item(upgrade_btn)

                reroll_val_cost = get_reroll_cost(tome.tier)
                reroll_val_gold = get_reroll_gold_cost(tome.tier)
                can_reroll_val = tome.tier > 0 and self.fragments >= reroll_val_cost
                reroll_val_btn = ui.Button(
                    label=f"Reroll Value ({reroll_val_cost}🔷 + {reroll_val_gold // 1_000_000}m💰)",
                    style=ButtonStyle.secondary,
                    disabled=not can_reroll_val,
                )
                reroll_val_btn.callback = self._on_reroll_value
                actions_row.add_item(reroll_val_btn)

                can_reroll_type = self.pages > 0
                reroll_type_btn = ui.Button(
                    label="Reroll Type (1📄)",
                    style=ButtonStyle.danger,
                    disabled=not can_reroll_type,
                )
                reroll_type_btn.callback = self._on_reroll_type
                actions_row.add_item(reroll_type_btn)

                self.add_item(actions_row)

        exit_row = ui.ActionRow()
        exit_btn = ui.Button(label="Back", style=ButtonStyle.secondary, emoji="⬅️")
        exit_btn.callback = self._on_exit
        exit_row.add_item(exit_btn)
        self.add_item(exit_row)

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
                    name=f"Slot {tome.slot + 1}: {name}", value=value, inline=False
                )
            unlocked = len(tomes)
            if unlocked < 5:
                for i in range(unlocked, 5):
                    embed.add_field(
                        name=f"Slot {i + 1}: 🔒 Locked",
                        value="Requires a Codex Page",
                        inline=False,
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
        await interaction.response.edit_message(view=self)

    async def _on_slot_select(self, interaction: Interaction):
        self.selected_slot = int(interaction.data["values"][0])
        await self._refresh(interaction)

    async def _on_unlock(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        tome = await self.bot.database.codex.unlock_tome_slot(self.user_id)
        if tome is None:
            self._processing = False
            await interaction.followup.send(
                "All 5 slots are already unlocked.", ephemeral=True
            )
            return
        await self.bot.database.users.modify_currency(self.user_id, "codex_pages", -1)
        self.pages -= 1
        self.player.codex_tomes = await self.bot.database.codex.get_tomes(self.user_id)
        self.selected_slot = tome.slot

        await self._show_unlock_reveal(interaction, tome)

        self._rebuild()
        self._processing = False
        await interaction.edit_original_response(view=self)

    async def _show_unlock_reveal(self, interaction: Interaction, tome: CodexTome):
        """Brief fanfare screen shown when a new tome slot is unlocked —
        reveals the rolled passive, what it does, and its growth potential."""
        name = _passive_display_name(tome.passive_type)
        description = _PASSIVE_DESCRIPTIONS.get(
            tome.passive_type, "A new power stirs within the tome."
        )

        embed = discord.Embed(
            title=f"📖 A New Skill Awakens — {name}",
            description=(
                f"*{get_quip('codex_tome_unlock')}*\n\n**{name}** — {description}"
            ),
            color=discord.Color.gold(),
        )
        embed.set_author(name="Seraphine", icon_url=SERAPHINE_PORTRAIT)
        embed.set_thumbnail(url=SERAPHINE_THUMBNAIL)
        embed.add_field(
            name="Growth Potential", value=_passive_range_text(tome.passive_type), inline=False
        )
        embed.set_footer(
            text=f"Slot {tome.slot + 1} unlocked — upgrade it with Codex Fragments."
        )

        self.clear_items()
        self.add_item(combat_ui.embed_to_container(embed))
        await interaction.edit_original_response(view=self)
        await asyncio.sleep(3.5)

    async def _on_upgrade(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        tome = next(
            (t for t in self.player.codex_tomes if t.slot == self.selected_slot), None
        )
        if not tome or tome.tier >= 5:
            self._processing = False
            return
        cost = TOME_UPGRADE_COSTS[tome.tier]
        gold_cost = TOME_GOLD_COSTS[tome.tier]
        if self.fragments < cost:
            self._processing = False
            await interaction.followup.send(
                "Not enough Codex Fragments.", ephemeral=True
            )
            return
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < gold_cost:
            self._processing = False
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
        self._processing = False
        await interaction.edit_original_response(view=self)

    async def _on_reroll_value(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        tome = next(
            (t for t in self.player.codex_tomes if t.slot == self.selected_slot), None
        )
        if not tome or tome.tier == 0:
            self._processing = False
            return
        cost = get_reroll_cost(tome.tier)
        gold_cost = get_reroll_gold_cost(tome.tier)
        if self.fragments < cost:
            self._processing = False
            await interaction.followup.send(
                "Not enough Codex Fragments.", ephemeral=True
            )
            return
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < gold_cost:
            self._processing = False
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
        self._processing = False
        await interaction.edit_original_response(view=self)

    async def _on_reroll_type(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        if self.pages <= 0:
            self._processing = False
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
        self._processing = False
        await interaction.edit_original_response(view=self)

    async def _on_exit(self, interaction: Interaction):
        # Back navigation to CodexMenuView — no clear_active (neither view owns active state).
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
            server_id=self.server_id,
            player_avatar_url=self.player_avatar_url,
        )
        await interaction.response.edit_message(view=menu)
