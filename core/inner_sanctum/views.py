import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.emojis import INNER_SANC, INNER_SANCTUM_BRANCH_EMOJI, RUNE_REGRET, SOUL_SLOT
from core.images import INNER_SANCTUM_THUMBNAIL
from core.inner_sanctum.data import (
    ALL_NODES,
    DEICIDE_NODES,
    DEICIDE_UNLOCK_LEVEL,
    RECOVERY_NODES,
    RECOVERY_UNLOCK_LEVEL,
    RESET_RUNE_COST,
    VICE_NODES,
    VICE_UNLOCK_LEVEL,
)
from core.inner_sanctum.mechanics import (
    can_purchase,
    can_purchase_ranks,
    get_node_cost,
    get_ranks_cost,
    owned_rank,
)
from core.npc_voices import get_quip

_BRANCH_NODES = {
    "vice": VICE_NODES,
    "recovery": RECOVERY_NODES,
    "deicide": DEICIDE_NODES,
}
_BRANCH_ICONS = INNER_SANCTUM_BRANCH_EMOJI
_BRANCH_NAMES = {"vice": "Vice", "recovery": "Recovery", "deicide": "Deicide"}
_BRANCH_UNLOCK = {
    "vice": VICE_UNLOCK_LEVEL,
    "recovery": RECOVERY_UNLOCK_LEVEL,
    "deicide": DEICIDE_UNLOCK_LEVEL,
}


def _plural(n: int) -> str:
    return "" if n == 1 else "s"


def _node_status_line(node_id: str, node: dict, nodes_owned: dict) -> str:
    if node.get("is_choice"):
        owned = nodes_owned.get(node_id)
        if owned:
            label = next((lbl for key, lbl in node["choices"] if key == owned), owned)
            return f"✅ {label}"
        return f"{SOUL_SLOT} Choose an affinity ({node['cost']} pts)"

    if node.get("is_choice_ranked"):
        owned_val = nodes_owned.get(node_id)
        rank = owned_rank(node, owned_val)
        max_rank = node["max_rank"]
        if rank == 0:
            return f"{SOUL_SLOT} Pick an affinity to begin ({node['costs'][0]} pt(s) for rank 1)"
        choice = owned_val["choice"]
        label = next((lbl for key, lbl in node["choices"] if key == choice), choice)
        status_icon = "✅"
        if rank >= max_rank:
            return f"{status_icon} {label} — {node['desc'](rank)} **(MAXED {rank}/{max_rank})**"
        cost = node["costs"][rank]
        return (
            f"{status_icon} {label} — {node['desc'](rank)} *(affinity locked in)*\n"
            f"└ {rank}/{max_rank} invested · next rank costs {cost} pt{_plural(cost)}"
        )

    rank = nodes_owned.get(node_id, 0) or 0
    max_rank = node["max_rank"]
    per_rank_effect = node["desc"](1)  # flat per-rank amount, not cumulative
    status_icon = "✅" if rank > 0 else f"{SOUL_SLOT}"

    if rank >= max_rank:
        return f"{status_icon} {node['desc'](rank)} **(MAXED {rank}/{max_rank})**"

    current = f" — currently: {node['desc'](rank)}" if rank > 0 else ""
    cost = node["costs"][rank]
    return (
        f"{status_icon} {per_rank_effect} *(per rank)*{current}\n"
        f"└ {rank}/{max_rank} invested · next rank costs {cost} pt{_plural(cost)}"
    )


class RankAmountModal(ui.Modal):
    """Custom-amount entry for investing multiple ranks in one node at once."""

    def __init__(
        self, parent_view: "InnerSanctumHubView", node_id: str, max_amount: int
    ):
        super().__init__(title="Invest Inner Sanctum Points")
        self.parent_view = parent_view
        self.node_id = node_id
        self.max_amount = max_amount
        self.amount_input = ui.TextInput(
            label=f"How many ranks? (max {max_amount})",
            placeholder=f"1 – {max_amount}",
            min_length=1,
            max_length=3,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: Interaction) -> None:
        try:
            amount = int(self.amount_input.value.strip())
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            await interaction.response.send_message(
                "Please enter a positive whole number.", ephemeral=True
            )
            return
        if amount > self.max_amount:
            await interaction.response.send_message(
                f"You can invest at most **{self.max_amount}** more rank"
                f"{_plural(self.max_amount)} here.",
                ephemeral=True,
            )
            return
        await self.parent_view._purchase_ranks(interaction, self.node_id, amount)


class InnerSanctumHubView(BaseView):
    """Displays the Inner Sanctum tree, handles node purchasing and resets."""

    def __init__(self, bot, user_id, server_id, player_level, tree_data, rune_count):
        super().__init__(bot, user_id, server_id)
        self.player_level = player_level
        self.points_available: int = tree_data.get("points_available", 0)
        self.points_spent: int = tree_data.get("points_spent", 0)
        self.nodes_owned: dict = dict(tree_data.get("nodes_owned", {}))
        self.rune_count: int = rune_count
        self.active_branch = "vice"
        self.result_msg = ""
        self._pending_choice_node: str | None = None
        self.setup_ui()

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        branch = self.active_branch
        icon = _BRANCH_ICONS[branch]
        name = _BRANCH_NAMES[branch]
        unlock_lvl = _BRANCH_UNLOCK[branch]

        embed = discord.Embed(
            title=f"{INNER_SANC} Inner Sanctum — {icon} {name}",
            description=(
                f"**Inner Sanctum Points:** {self.points_available} "
                f"| *Spent: {self.points_spent}*\n"
                f"{RUNE_REGRET} **Rune of Regret:** {self.rune_count}\n\n"
                + (f"**{self.result_msg}**\n\n" if self.result_msg else "")
                + get_quip("inner_sanctum")
            ),
            color=discord.Color.dark_purple(),
        )
        if INNER_SANCTUM_THUMBNAIL:
            embed.set_thumbnail(url=INNER_SANCTUM_THUMBNAIL)

        if self.player_level < unlock_lvl:
            embed.add_field(
                name=f"{icon} {name} — 🔒 Locked",
                value=f"Unlocks at level {unlock_lvl}.",
                inline=False,
            )
            return embed

        branch_nodes = _BRANCH_NODES[branch]
        groups: dict[str, list[str]] = {}
        for nid, node in branch_nodes.items():
            group = node.get("group", name)
            groups.setdefault(group, []).append(
                _node_status_line(nid, node, self.nodes_owned)
            )

        if len(groups) > 1:
            for group_name, lines in groups.items():
                embed.add_field(
                    name=f"{icon} {group_name}", value="\n".join(lines), inline=False
                )
        else:
            lines = next(iter(groups.values()))
            embed.add_field(name=f"{icon} {name}", value="\n".join(lines), inline=False)
        embed.set_footer(
            text=f"Reset Tree: costs {RESET_RUNE_COST} Rune(s) of Regret | refunds 100% of points spent"
        )
        return embed

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def setup_ui(self):
        self.clear_items()
        self._pending_choice_node = None

        # Row 0: branch navigation
        for branch in ("vice", "recovery", "deicide"):
            locked = self.player_level < _BRANCH_UNLOCK[branch]
            btn = ui.Button(
                label=_BRANCH_NAMES[branch] + (" 🔒" if locked else ""),
                emoji=_BRANCH_ICONS[branch],
                style=(
                    ButtonStyle.primary
                    if branch == self.active_branch
                    else ButtonStyle.secondary
                ),
                row=0,
            )

            async def _branch_cb(interaction: Interaction, b=branch):
                self.active_branch = b
                self.result_msg = ""
                self.setup_ui()
                await interaction.response.edit_message(
                    embed=self.build_embed(), view=self
                )

            btn.callback = _branch_cb
            self.add_item(btn)

        if self.player_level >= _BRANCH_UNLOCK[self.active_branch]:
            # Row 1: purchasable nodes in the active branch
            purchasable = []
            for nid, node in _BRANCH_NODES[self.active_branch].items():
                cost = get_node_cost(nid, self.nodes_owned)
                if cost is None:
                    continue
                purchasable.append((nid, node, cost))

            if purchasable:
                options = []
                for nid, node, cost in purchasable:
                    rank = owned_rank(node, self.nodes_owned.get(nid))
                    if node.get("is_choice"):
                        label = "Choose an affinity"
                        desc = f"{cost} pts"
                    elif node.get("is_choice_ranked") and rank == 0:
                        label = "Choose an affinity"
                        desc = f"{cost} pt{_plural(cost)} for rank 1"
                    else:
                        label = node["desc"](1)  # flat per-rank amount
                        desc = f"{rank}/{node['max_rank']} invested · {cost} pt{_plural(cost)}/rank"
                    options.append(
                        SelectOption(
                            label=label[:100],
                            value=nid,
                            description=desc[:100],
                        )
                    )
                sel = ui.Select(
                    placeholder="Select an effect to invest in…", options=options, row=1
                )
                sel.callback = self.on_node_select
                self.add_item(sel)

            can_reset = bool(self.nodes_owned) and self.rune_count >= RESET_RUNE_COST
            btn_reset = ui.Button(
                label=f"Reset Tree ({RESET_RUNE_COST} Rune of Regret)",
                emoji=RUNE_REGRET,
                style=ButtonStyle.danger,
                disabled=not can_reset,
                row=2,
            )
            btn_reset.callback = self.on_reset
            self.add_item(btn_reset)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=2)
        btn_close.callback = self.on_close
        self.add_item(btn_close)

    def _show_choice_ui(self, node_id: str):
        """Single-purchase choice nodes (e.g. Deicide's Marked Prey) — pick one
        option. Ranked-choice nodes (`is_choice_ranked`) route through here only
        for their first purchase (rank 0 -> 1); the pick is permanent."""
        self.clear_items()
        node = ALL_NODES[node_id]
        self._pending_choice_node = node_id
        is_ranked_choice = node.get("is_choice_ranked")
        for key, label in node["choices"]:
            btn = ui.Button(label=label[:80], style=ButtonStyle.primary, row=0)

            async def _choice_cb(interaction: Interaction, k=key):
                if is_ranked_choice:
                    await self._purchase_choice_rank1(interaction, node_id, choice=k)
                else:
                    await self._purchase_node(interaction, node_id, choice=k)

            btn.callback = _choice_cb
            self.add_item(btn)
        btn_cancel = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=1)
        btn_cancel.callback = self._cancel_choice
        self.add_item(btn_cancel)

    def _show_quantity_ui(self, node_id: str):
        """Ranked nodes — quick-amount buttons + a custom-amount modal, so a
        10-rank node doesn't require 10 separate select-menu round trips."""
        self.clear_items()
        node = ALL_NODES[node_id]
        self._pending_choice_node = node_id
        rank = owned_rank(node, self.nodes_owned.get(node_id))
        remaining = node["max_rank"] - rank

        quick_amounts = sorted({a for a in (1, 5, remaining) if 0 < a <= remaining})
        for amt in quick_amounts:
            cost = get_ranks_cost(node_id, self.nodes_owned, amt)
            prefix = "Max " if amt == remaining else ""
            label = f"{prefix}+{amt} ({cost} pt{_plural(cost)})"
            btn = ui.Button(label=label[:80], style=ButtonStyle.primary, row=0)

            async def _amt_cb(interaction: Interaction, a=amt):
                await self._purchase_ranks(interaction, node_id, a)

            btn.callback = _amt_cb
            self.add_item(btn)

        btn_custom = ui.Button(
            label="Custom Amount…", style=ButtonStyle.secondary, row=1
        )

        async def _custom_cb(interaction: Interaction):
            await interaction.response.send_modal(
                RankAmountModal(self, node_id, remaining)
            )

        btn_custom.callback = _custom_cb
        self.add_item(btn_custom)

        btn_cancel = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=1)
        btn_cancel.callback = self._cancel_choice
        self.add_item(btn_cancel)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def on_node_select(self, interaction: Interaction):
        node_id = interaction.data["values"][0]
        node = ALL_NODES[node_id]
        if node.get("is_choice"):
            self._show_choice_ui(node_id)
        elif node.get("is_choice_ranked"):
            if owned_rank(node, self.nodes_owned.get(node_id)) == 0:
                self._show_choice_ui(node_id)
            else:
                self._show_quantity_ui(node_id)
        else:
            self._show_quantity_ui(node_id)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _cancel_choice(self, interaction: Interaction):
        self.setup_ui()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _purchase_node(self, interaction: Interaction, node_id: str, choice: str):
        """Purchases a single-purchase choice node."""
        await interaction.response.defer()

        # Re-fetch to avoid acting on stale points if the tree changed elsewhere.
        fresh = await self.bot.database.inner_sanctum.get(self.user_id, self.server_id)
        self.points_available = fresh["points_available"]
        self.points_spent = fresh["points_spent"]
        self.nodes_owned = fresh["nodes_owned"]

        ok, cost, reason = can_purchase(
            node_id, self.nodes_owned, self.player_level, self.points_available
        )
        if not ok:
            self.result_msg = f"❌ {reason}"
            self.setup_ui()
            return await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        node = ALL_NODES[node_id]
        await self.bot.database.inner_sanctum.purchase_node(
            self.user_id, self.server_id, node_id, cost, choice
        )

        self.points_available -= cost
        self.points_spent += cost
        self.nodes_owned[node_id] = choice

        choice_label = next((lbl for k, lbl in node["choices"] if k == choice), choice)
        self.result_msg = f"✅ {choice_label}"

        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _purchase_choice_rank1(
        self, interaction: Interaction, node_id: str, choice: str
    ):
        """First purchase of a ranked-choice node (e.g. Deicide's Marked Prey) —
        locks in `choice` and buys rank 1 in the same action. The choice is
        permanent from here on; later ranks go through `_purchase_ranks`."""
        await interaction.response.defer()

        # Re-fetch to avoid acting on stale points if the tree changed elsewhere.
        fresh = await self.bot.database.inner_sanctum.get(self.user_id, self.server_id)
        self.points_available = fresh["points_available"]
        self.points_spent = fresh["points_spent"]
        self.nodes_owned = fresh["nodes_owned"]

        ok, cost, reason = can_purchase_ranks(
            node_id, self.nodes_owned, self.player_level, self.points_available, 1
        )
        if not ok:
            self.result_msg = f"❌ {reason}"
            self.setup_ui()
            return await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        node = ALL_NODES[node_id]
        new_value = {"choice": choice, "rank": 1}
        await self.bot.database.inner_sanctum.purchase_node(
            self.user_id, self.server_id, node_id, cost, new_value
        )

        self.points_available -= cost
        self.points_spent += cost
        self.nodes_owned[node_id] = new_value

        choice_label = next((lbl for k, lbl in node["choices"] if k == choice), choice)
        self.result_msg = f"✅ {choice_label} — {node['desc'](1)}"

        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _purchase_ranks(self, interaction: Interaction, node_id: str, count: int):
        """Purchases `count` ranks of a ranked node in a single transaction."""
        await interaction.response.defer()

        # Re-fetch to avoid acting on stale points if the tree changed elsewhere.
        fresh = await self.bot.database.inner_sanctum.get(self.user_id, self.server_id)
        self.points_available = fresh["points_available"]
        self.points_spent = fresh["points_spent"]
        self.nodes_owned = fresh["nodes_owned"]

        ok, cost, reason = can_purchase_ranks(
            node_id, self.nodes_owned, self.player_level, self.points_available, count
        )
        if not ok:
            self.result_msg = f"❌ {reason}"
            self.setup_ui()
            return await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        node = ALL_NODES[node_id]
        owned_val = self.nodes_owned.get(node_id)
        is_ranked_choice = node.get("is_choice_ranked")
        rank = owned_rank(node, owned_val)
        new_rank = rank + count
        new_value = (
            {"choice": owned_val["choice"], "rank": new_rank}
            if is_ranked_choice
            else new_rank
        )
        await self.bot.database.inner_sanctum.purchase_node(
            self.user_id, self.server_id, node_id, cost, new_value
        )

        self.points_available -= cost
        self.points_spent += cost
        self.nodes_owned[node_id] = new_value

        # Ranked-choice nodes use a rank-indexed lookup table, not a linear
        # per-rank formula, so the result message reports the new absolute
        # value at new_rank rather than the count-sized increment.
        desc_value = node["desc"](new_rank) if is_ranked_choice else node["desc"](count)
        self.result_msg = (
            f"✅ +{count} rank{_plural(count)} ({cost} pt{_plural(cost)}): "
            f"{desc_value}"
        )

        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def on_reset(self, interaction: Interaction):
        await interaction.response.defer()

        async with self.bot.database.transaction():
            deducted = await self.bot.database.users.deduct_currency_atomic(
                self.user_id, "rune_of_regret", RESET_RUNE_COST
            )
            if not deducted:
                refunded = None
            else:
                refunded = await self.bot.database.inner_sanctum.reset_tree(
                    self.user_id, self.server_id
                )

        if refunded is None:
            self.result_msg = (
                f"❌ Need {RESET_RUNE_COST} Rune(s) of Regret to reset the tree."
            )
            self.setup_ui()
            return await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        self.points_available += refunded
        self.points_spent = 0
        self.nodes_owned = {}
        self.rune_count -= RESET_RUNE_COST

        self.result_msg = (
            f"🔄 Tree reset! Refunded **{refunded}** Inner Sanctum Points "
            f"(consumed {RESET_RUNE_COST} Rune of Regret)."
        )
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def on_close(self, interaction: Interaction):
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()
