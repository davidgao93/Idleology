"""
core/nether_market/views/mastery_view.py — Cutpurse / Strongbox mastery tree,
plus the shared Stash branch (holdings cap / market read). Pattern mirrors
core/companions/mastery_views.py (branch buttons + node select + confirm step).
"""

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.images import VEX_PORTRAIT, VEX_THUMBNAIL
from core.nether_market.data import NETHER_MARKET_NODES
from core.nether_market.mechanics import NetherMarketMechanics as M
from core.npc_voices import get_quip

_BRANCH_LABELS = {
    "trunk": "\U0001f45b Stash",
    "cutpurse": "\U0001f5e1️ Cutpurse",
    "strongbox": "\U0001f6e1️ Strongbox",
}
_BRANCH_ORDER = ("trunk", "cutpurse", "strongbox")


def _nodes_for_branch(branch_key: str) -> list[tuple[str, dict]]:
    return [(nid, n) for nid, n in NETHER_MARKET_NODES.items() if n["branch"] == branch_key]


async def build_mastery_view(bot, user_id: str, server_id: str) -> "MasteryView":
    profile = await bot.database.nether_market.get_or_create_profile(user_id, server_id)
    return MasteryView(bot, user_id, server_id, profile)


class MasteryView(BaseView):
    def __init__(self, bot, user_id, server_id, profile: dict, active_branch: str = "trunk"):
        super().__init__(bot, user_id, server_id)
        self.profile = profile
        self.active_branch = active_branch
        self._processing = False
        self._build_items()

    def build_embed(self) -> discord.Embed:
        nodes_owned = self.profile["mastery_nodes"]
        marks = self.profile["nether_marks"]

        embed = discord.Embed(
            title=f"\U0001f3ad Tricks of the Trade — {_BRANCH_LABELS[self.active_branch]}",
            color=discord.Color.dark_purple(),
        )
        embed.set_author(name="Vex, the Fence", icon_url=VEX_PORTRAIT)
        if VEX_THUMBNAIL:
            embed.set_thumbnail(url=VEX_THUMBNAIL)
        embed.set_footer(text=f"{get_quip('nether_market_mastery')}\nNether Marks: {marks:,}")

        lines = []
        for node_id, node in _nodes_for_branch(self.active_branch):
            owned = node_id in nodes_owned
            ok, _ = M.can_purchase(node_id, nodes_owned, marks)
            icon = "✅" if owned else ("\U0001f513" if ok else "\U0001f512")
            lines.append(f"{icon} **{node['name']}** — {node['cost']} Marks\n> {node['desc']}")
        embed.description = "\n\n".join(lines)
        return embed

    def _build_items(self):
        self.clear_items()
        nodes_owned = self.profile["mastery_nodes"]
        marks = self.profile["nether_marks"]

        for branch_key in _BRANCH_ORDER:
            btn = ui.Button(
                label=_BRANCH_LABELS[branch_key].split(" ", 1)[-1],
                style=ButtonStyle.primary if branch_key == self.active_branch else ButtonStyle.secondary,
                row=0,
            )
            btn.callback = self._make_branch_callback(branch_key)
            self.add_item(btn)

        options = []
        for node_id, node in _nodes_for_branch(self.active_branch):
            owned = node_id in nodes_owned
            ok, _ = M.can_purchase(node_id, nodes_owned, marks)
            icon = "✅" if owned else ("\U0001f513" if ok else "\U0001f512")
            options.append(
                SelectOption(
                    label=f"{icon} {node['name']} ({node['cost']} Marks)"[:100],
                    description=node["desc"][:100],
                    value=node_id,
                )
            )
        select = ui.Select(placeholder="Select a node to view or purchase...", options=options, row=1)
        select.callback = self._on_select
        self.add_item(select)

        back_btn = ui.Button(label="Back to Market", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self.go_back
        self.add_item(back_btn)

    def _make_branch_callback(self, branch_key: str):
        async def _callback(interaction: Interaction):
            if self._processing:
                return await interaction.response.defer()
            self.active_branch = branch_key
            self._build_items()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

        return _callback

    async def _on_select(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        node_id = interaction.data["values"][0]
        node = NETHER_MARKET_NODES[node_id]
        nodes_owned = self.profile["mastery_nodes"]
        marks = self.profile["nether_marks"]

        if node_id in nodes_owned:
            return await interaction.response.send_message(
                f"**{node['name']}** is already unlocked.", ephemeral=True
            )
        ok, reason = M.can_purchase(node_id, nodes_owned, marks)
        if not ok:
            return await interaction.response.send_message(reason, ephemeral=True)

        confirm_view = _ConfirmPurchaseView(self.bot, self, node_id, node)
        embed = discord.Embed(
            title=f"Unlock **{node['name']}**?",
            description=f"{node['desc']}\n\n**Cost:** {node['cost']} Nether Marks",
            color=discord.Color.blurple(),
        )
        embed.set_author(name="Vex, the Fence", icon_url=VEX_PORTRAIT)
        await interaction.response.edit_message(embed=embed, view=confirm_view)

    async def refresh(self, interaction: Interaction):
        self.profile = await self.bot.database.nether_market.get_or_create_profile(self.user_id, self.server_id)
        self._build_items()
        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.hub_view import build_hub_view

        view = await build_hub_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(embed=view.build_embed(), view=view)
        view.message = msg
        self.stop()


class _ConfirmPurchaseView(BaseView):
    def __init__(self, bot, mastery_view: MasteryView, node_id: str, node: dict):
        super().__init__(bot, parent=mastery_view)
        self.mastery_view = mastery_view
        self.node_id = node_id
        self.node = node
        self._processing = False

    @ui.button(label="Confirm", style=ButtonStyle.green)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()

        success = await self.bot.database.nether_market.purchase_node(
            self.user_id, self.server_id, self.node_id, self.node["cost"]
        )
        if not success:
            await interaction.followup.send("Purchase failed — not enough Nether Marks.", ephemeral=True)
        await self.mastery_view.refresh(interaction)

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        self.mastery_view._processing = False
        await interaction.edit_original_response(embed=self.mastery_view.build_embed(), view=self.mastery_view)
