# core/companions/mastery_views.py

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.companions.mastery import (
    MASTERY_BRANCHES,
    can_purchase,
    get_all_nodes,
    get_node_by_id,
)


def _branch_for_node(node_id: str) -> str | None:
    for branch_key, branch in MASTERY_BRANCHES.items():
        for n in branch["nodes"]:
            if n["id"] == node_id:
                return branch_key
    return None


class CompanionMasteryView(BaseView):
    def __init__(
        self, bot, user_id: str, server_id: str, mastery: dict, *, parent: BaseView
    ):
        super().__init__(bot, parent=parent)
        self.user_id = user_id
        self.server_id = server_id
        self.mastery = mastery  # {nodes_owned, points_spent, kinship_points}
        self.parent_view = parent
        self._processing = False
        self.active_branch = "forager"
        self._build_select()

    def _build_select(self):
        self.clear_items()
        nodes_owned = self.mastery.get("nodes_owned", {})
        kp = self.mastery.get("kinship_points", 0)

        # Row 0: branch navigation buttons
        for branch_key, branch in MASTERY_BRANCHES.items():
            btn = ui.Button(
                label=branch["label"],
                style=ButtonStyle.primary
                if branch_key == self.active_branch
                else ButtonStyle.secondary,
                row=0,
            )

            async def _branch_cb(interaction: Interaction, b=branch_key):
                self.active_branch = b
                self._build_select()
                await interaction.response.edit_message(
                    embed=self.get_embed(), view=self
                )

            btn.callback = _branch_cb
            self.add_item(btn)

        # Row 1: nodes from the active branch only
        active_nodes = MASTERY_BRANCHES[self.active_branch]["nodes"]
        options = []
        for node in active_nodes:
            owned = node["id"] in nodes_owned
            ok, _ = can_purchase(node["id"], nodes_owned, kp)
            icon = "✅" if owned else ("🔓" if ok else "🔒")
            label = f"{icon} {node['name']} ({node['cost']} KP)"
            options.append(
                SelectOption(
                    label=label[:100],
                    description=node["desc"][:100],
                    value=node["id"],
                )
            )

        select = ui.Select(
            placeholder="Select a node to view or purchase…",
            options=options,
            row=1,
        )
        select.callback = self._on_select
        self.add_item(select)

        # Once every node is unlocked, further KP have nothing left to buy —
        # offer to convert them into rolls of the companion loot table.
        if len(nodes_owned) >= len(get_all_nodes()):
            loot_btn = ui.Button(
                label=f"Loot Roll (KP: {kp:,})",
                style=ButtonStyle.success,
                emoji="🎁",
                row=2,
            )
            loot_btn.callback = self._open_loot_roll
            self.add_item(loot_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self._go_back
        self.add_item(back_btn)

    def get_embed(self) -> discord.Embed:
        nodes_owned = self.mastery.get("nodes_owned", {})
        kp = self.mastery.get("kinship_points", 0)
        spent = self.mastery.get("points_spent", 0)

        branch = MASTERY_BRANCHES[self.active_branch]
        embed = discord.Embed(
            title=f"✨ Forged Bonds — {branch['label']}",
            color=discord.Color.purple(),
        )
        embed.set_footer(text=f"Kinship Points: {kp:,} | Total Spent: {spent:,} KP")

        lines = []
        for node in branch["nodes"]:
            owned = node["id"] in nodes_owned
            ok, reason = can_purchase(node["id"], nodes_owned, kp)
            if owned:
                val = nodes_owned[node["id"]]
                extra = f" **[{val}]**" if isinstance(val, str) else ""
                icon = "✅"
            else:
                icon = "🔓" if ok else "🔒"
                extra = ""
            lines.append(
                f"{icon} **{node['name']}** — {node['cost']} KP{extra}\n"
                f"> {node['desc']}"
            )
        embed.add_field(name=branch["label"], value="\n".join(lines), inline=False)

        return embed

    async def _on_select(self, interaction: Interaction):
        node_id = interaction.data["values"][0]
        node = get_node_by_id(node_id)
        nodes_owned = self.mastery.get("nodes_owned", {})
        kp = self.mastery.get("kinship_points", 0)

        if node["id"] in nodes_owned:
            if "choice" in node:
                view = _ChoiceSelectView(
                    self.bot, self, node, parent=self, is_change=True
                )
                embed = discord.Embed(
                    title=f"🎯 Change Focus — {node['name']}",
                    description=(
                        f"{node['desc']}\n\n"
                        f"**Current Focus:** {nodes_owned[node['id']]}\n\n"
                        "Choose a new loot focus below (free):"
                    ),
                    color=discord.Color.blurple(),
                )
                return await interaction.response.edit_message(
                    embed=embed, view=view
                )
            return await interaction.response.send_message(
                f"**{node['name']}** is already unlocked.", ephemeral=True
            )

        ok, reason = can_purchase(node_id, nodes_owned, kp)
        if not ok:
            return await interaction.response.send_message(reason, ephemeral=True)

        if "choice" in node:
            # Need secondary choice selection
            view = _ChoiceSelectView(self.bot, self, node, parent=self)
            embed = discord.Embed(
                title=f"🎯 {node['name']}",
                description=(
                    f"{node['desc']}\n\n"
                    f"**Cost:** {node['cost']} KP\n\n"
                    "Choose your loot focus below:"
                ),
                color=discord.Color.blurple(),
            )
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            view = _ConfirmPurchaseView(self.bot, self, node, choice=None, parent=self)
            embed = discord.Embed(
                title=f"Unlock **{node['name']}**?",
                description=f"{node['desc']}\n\n**Cost:** {node['cost']} KP",
                color=discord.Color.blurple(),
            )
            await interaction.response.edit_message(embed=embed, view=view)

    async def _open_loot_roll(self, interaction: Interaction):
        kp = self.mastery.get("kinship_points", 0)
        if kp <= 0:
            return await interaction.response.send_message(
                "You have no Kinship Points to spend.", ephemeral=True
            )
        view = _LootRollConfirmView(self.bot, self, kp, parent=self)
        embed = discord.Embed(
            title="🎁 Loot Roll",
            description=(
                f"Spend all **{kp:,}** Kinship Points for **{kp:,}** roll(s) of the "
                "companion loot table (Gold, Runes, Boss Keys — respecting your "
                "Loot Affinity focus)."
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def _go_back(self, interaction: Interaction):
        if hasattr(self.parent_view, "set_mastery_nodes"):
            self.parent_view.set_mastery_nodes(self.mastery.get("nodes_owned", {}))
        embed = self.parent_view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

    async def _refresh(self, interaction: Interaction):
        """Reload mastery from DB and redraw."""
        self.mastery = await self.bot.database.companions.get_mastery(
            self.user_id, self.server_id
        )
        self._build_select()
        embed = self.get_embed()
        await interaction.edit_original_response(embed=embed, view=self)


class _ChoiceSelectView(BaseView):
    """Secondary view for nodes that require a choice (prey_instinct / fine_palate).
    Also reused to let a player change their focus on an already-owned node —
    pass is_change=True in that case (skips the KP cost on confirm)."""

    def __init__(
        self,
        bot,
        mastery_view: CompanionMasteryView,
        node: dict,
        *,
        parent: BaseView,
        is_change: bool = False,
    ):
        super().__init__(bot, parent=parent)
        self.mastery_view = mastery_view
        self.node = node
        self.is_change = is_change
        self._build(node)

    def _build(self, node: dict):
        self.clear_items()
        nodes_owned = self.mastery_view.mastery.get("nodes_owned", {})
        prey_pick = nodes_owned.get("prey_instinct")
        fine_pick = nodes_owned.get("fine_palate")

        all_choices = node.get("choice", [])
        # prey_instinct and fine_palate can never share the same category
        if node["id"] == "fine_palate" and prey_pick:
            all_choices = [c for c in all_choices if c != prey_pick]
        elif node["id"] == "prey_instinct" and fine_pick:
            all_choices = [c for c in all_choices if c != fine_pick]

        options = [SelectOption(label=c, value=c) for c in all_choices]
        select = ui.Select(
            placeholder="Choose your loot focus…", options=options, row=0
        )
        select.callback = self._on_choice
        self.add_item(select)

        cancel = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=1)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _on_choice(self, interaction: Interaction):
        choice = interaction.data["values"][0]
        view = _ConfirmPurchaseView(
            self.bot,
            self.mastery_view,
            self.node,
            choice=choice,
            parent=self,
            is_change=self.is_change,
        )
        if self.is_change:
            embed = discord.Embed(
                title=f"Change Focus — **{self.node['name']}**?",
                description=f"{self.node['desc']}\n\n**New Focus:** {choice}\n**Cost:** Free",
                color=discord.Color.blurple(),
            )
        else:
            embed = discord.Embed(
                title=f"Unlock **{self.node['name']}**?",
                description=(
                    f"{self.node['desc']}\n\n"
                    f"**Focus:** {choice}\n"
                    f"**Cost:** {self.node['cost']} KP"
                ),
                color=discord.Color.blurple(),
            )
        await interaction.response.edit_message(embed=embed, view=view)

    async def _cancel(self, interaction: Interaction):
        self.mastery_view._build_select()
        embed = self.mastery_view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.mastery_view)


class _ConfirmPurchaseView(BaseView):
    def __init__(
        self,
        bot,
        mastery_view: CompanionMasteryView,
        node: dict,
        choice: str | None,
        *,
        parent: BaseView,
        is_change: bool = False,
    ):
        super().__init__(bot, parent=parent)
        self.mastery_view = mastery_view
        self.node = node
        self.choice = choice
        self.is_change = is_change
        self._processing = False
        self._add_buttons()

    def _add_buttons(self):
        confirm = ui.Button(label="Confirm", style=ButtonStyle.success, row=0)
        confirm.callback = self._confirm
        self.add_item(confirm)

        cancel = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=0)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        uid = self.mastery_view.user_id
        sid = self.mastery_view.server_id

        if self.is_change:
            success = await self.bot.database.companions.update_mastery_node_choice(
                uid, sid, self.node["id"], self.choice
            )
            if not success:
                self._processing = False
                return await interaction.followup.send(
                    "Failed to change focus — try again.", ephemeral=True
                )
            return await self.mastery_view._refresh(interaction)

        nodes_owned = self.mastery_view.mastery.get("nodes_owned", {})
        kp = self.mastery_view.mastery.get("kinship_points", 0)

        ok, reason = can_purchase(self.node["id"], nodes_owned, kp)
        if not ok:
            self._processing = False
            return await interaction.followup.send(reason, ephemeral=True)

        success = await self.bot.database.companions.purchase_mastery_node(
            uid, sid, self.node["id"], self.node["cost"], self.choice
        )
        if not success:
            self._processing = False
            return await interaction.followup.send(
                "Purchase failed — insufficient Kinship Points.", ephemeral=True
            )

        await self.mastery_view._refresh(interaction)

    async def _cancel(self, interaction: Interaction):
        self.mastery_view._build_select()
        embed = self.mastery_view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.mastery_view)


class _LootRollConfirmView(BaseView):
    """Confirms spending all current Kinship Points on loot-table rolls."""

    def __init__(
        self,
        bot,
        mastery_view: CompanionMasteryView,
        kp: int,
        *,
        parent: BaseView,
    ):
        super().__init__(bot, parent=parent)
        self.mastery_view = mastery_view
        self.kp = kp
        self._processing = False
        self._add_buttons()

    def _add_buttons(self):
        confirm = ui.Button(
            label=f"Roll {self.kp}x", style=ButtonStyle.success, emoji="🎁", row=0
        )
        confirm.callback = self._confirm
        self.add_item(confirm)

        cancel = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=0)
        cancel.callback = self._cancel
        self.add_item(cancel)

    async def _confirm(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        from core.companions.logic import CompanionLogic

        uid = self.mastery_view.user_id
        sid = self.mastery_view.server_id
        result_msg = await CompanionLogic.spend_kp_for_loot(self.bot, uid, sid)

        await self.mastery_view._refresh(interaction)
        await interaction.followup.send(result_msg, ephemeral=True)

    async def _cancel(self, interaction: Interaction):
        self.mastery_view._build_select()
        embed = self.mastery_view.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.mastery_view)
