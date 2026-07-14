import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.emojis import INNER_SANC, INNER_SANCTUM_BRANCH_EMOJI, RUNE_REGRET
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
from core.inner_sanctum.mechanics import can_purchase, get_node_cost
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


def _node_status_line(node_id: str, node: dict, nodes_owned: dict) -> str:
    if node.get("is_choice"):
        owned = nodes_owned.get(node_id)
        if owned:
            label = next((lbl for key, lbl in node["choices"] if key == owned), owned)
            return f"✅ **{node['name']}** → {label}"
        return f"⬜ **{node['name']}** ({node['cost']} pts) — *choose an affinity*"

    rank = nodes_owned.get(node_id, 0) or 0
    max_rank = node["max_rank"]
    effect = node["desc"](rank) if rank > 0 else "*not invested*"
    if rank >= max_rank:
        cost_str = "MAX"
    else:
        cost_str = f"{node['costs'][rank]} pts → rank {rank + 1}"
    return f"{'✅' if rank > 0 else '⬜'} **{node['name']}** ({rank}/{max_rank}) — {effect}\n└ Next: {cost_str}"


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
                style=ButtonStyle.primary
                if branch == self.active_branch
                else ButtonStyle.secondary,
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
                    desc = (
                        "Choose an affinity"
                        if node.get("is_choice")
                        else node["desc"](self.nodes_owned.get(nid, 0) or 0)
                    )
                    options.append(
                        SelectOption(
                            label=f"{node['name']} ({cost} pts)",
                            value=nid,
                            description=desc[:100],
                        )
                    )
                sel = ui.Select(
                    placeholder="Select a node to invest in…", options=options, row=1
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
        self.clear_items()
        node = ALL_NODES[node_id]
        self._pending_choice_node = node_id
        for key, label in node["choices"]:
            btn = ui.Button(label=label[:80], style=ButtonStyle.primary, row=0)

            async def _choice_cb(interaction: Interaction, k=key):
                await self._purchase_node(interaction, node_id, choice=k)

            btn.callback = _choice_cb
            self.add_item(btn)
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
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            return
        await self._purchase_node(interaction, node_id, choice=None)

    async def _cancel_choice(self, interaction: Interaction):
        self.setup_ui()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _purchase_node(
        self, interaction: Interaction, node_id: str, choice: str | None
    ):
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
        if node.get("is_choice"):
            value = choice
        else:
            value = (self.nodes_owned.get(node_id, 0) or 0) + 1

        await self.bot.database.inner_sanctum.purchase_node(
            self.user_id, self.server_id, node_id, cost, value
        )

        self.points_available -= cost
        self.points_spent += cost
        self.nodes_owned[node_id] = value

        choice_label = ""
        if choice:
            choice_label = " → " + next(
                (lbl for k, lbl in node["choices"] if k == choice), choice
            )
        self.result_msg = f"✅ Invested in **{node['name']}**!{choice_label}"

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
