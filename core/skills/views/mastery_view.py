"""
Artisan Mastery UI

- Hub (ArtisanMasteryHubView): 4 skill buttons + Back.
- Skill view (SkillMasteryView): Shows a summary of all 3 branches and navigates to each.
- Branch view (BranchDetailView): Shows one branch in full detail with Invest + Back buttons.
- Rune mode (inline in SkillMasteryView): Craft / Respec using Runes of Nature.
"""

import json
import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.images import (
    ARTISAN_MASTERY_HUB,
    ARTISAN_MASTERY_ATTUNEMENT,
    MASTERY_MINING,
    MASTERY_FISHING,
    MASTERY_WOODCUTTING,
)
from core.skills.mastery import (
    NODE_LABELS,
    get_tree,
    get_branch_display_name,
    BRANCH_NODE_ORDERS,
    get_branch_progress,
    invest_in_branch,
    _get_unlocked_nodes_from_alloc,
    RUNE_CRAFT_COST,
    get_yield_proc_bonus,
    get_rich_base_bonus,
    get_prestige_spawn_bonus,
    get_branch_total_cost,
    has_nature_attunement_unlocked,
    get_attunement_progress,
    get_total_insight_bonuses,
    NATURE_ATTUNEMENT_TREE,
    NATURE_ATTUNEMENT_NODE_ORDER,
    invest_in_attunement,
)
from core.skills.mechanics import SkillMechanics


# =========================================================
# HUB VIEW
# =========================================================


class ArtisanMasteryHubView(BaseView):
    """Entry point for Artisan Mastery. Only 4+1 buttons."""

    def __init__(
        self, bot, user_id: str, server_id: str, parent_view: BaseView | None = None
    ):
        super().__init__(bot, user_id, server_id, parent=parent_view)
        self.parent_view = parent_view
        self._processing = False

    async def refresh(self):
        self.mastery_row = await self.bot.database.skills.get_mastery(
            self.user_id, self.server_id
        )
        self.setup_ui()

    def setup_ui(self):
        self.clear_items()

        for s in ["mining", "woodcutting", "fishing"]:
            info = SkillMechanics.get_skill_info(s)
            btn = Button(
                label=info["display_name"],
                emoji=info["emoji"],
                style=ButtonStyle.primary,
                row=0,
            )
            btn.callback = self._make_skill_button_cb(s)
            self.add_item(btn)

        gate_met = has_nature_attunement_unlocked(self.mastery_row or {})
        att_btn = Button(
            label="Nature's Attunement",
            emoji="🌿",
            style=ButtonStyle.success if gate_met else ButtonStyle.secondary,
            row=0,
            disabled=not gate_met,
        )
        att_btn.callback = self._open_attunement_cb
        self.add_item(att_btn)

        back_btn = Button(label="Back to Gather", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    async def _open_attunement_cb(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        view = AttunementView(self.bot, self.user_id, self.server_id, parent_view=self)
        await view.refresh()
        await interaction.edit_original_response(embed=view.get_embed(), view=view)
        view.message = await interaction.original_response()
        self._processing = False

    def _make_skill_button_cb(self, skill: str):
        async def cb(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()
            view = SkillMasteryView(
                self.bot, self.user_id, self.server_id, skill, parent_view=self
            )
            await view.refresh()
            await interaction.edit_original_response(embed=view.get_embed(), view=view)
            view.message = await interaction.original_response()
            self._processing = False

        return cb

    async def back_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        if self.parent_view:
            self.parent_view._processing = False
            await self.parent_view.refresh_state()
            await interaction.edit_original_response(
                embed=self.parent_view.get_embed(), view=self.parent_view
            )
        else:
            await interaction.delete_original_response()
            self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Artisan Mastery",
            description=(
                "Choose a gathering skill to view its specialization trees and invest Artisan Points.\n\n"
                "🌿 **Nature's Attunement** unlocks after investing **20+ points** in each of the three skills."
            ),
            color=0x2E8B57,
        )
        embed.set_thumbnail(url=ARTISAN_MASTERY_HUB)
        embed.set_footer(
            text="The Black Market is seeking rare gathering materials for trade."
        )
        return embed


# =========================================================
# SKILL-SPECIFIC VIEW — summary of all 3 branches
# =========================================================


class SkillMasteryView(BaseView):
    """Summary view for one skill. Navigate into each branch for details and investing."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        skill: str,
        parent_view: BaseView | None = None,
    ):
        super().__init__(bot, user_id, server_id, parent=parent_view)
        self.parent_view = parent_view
        self.skill = skill
        self._processing = False
        self.mastery_row = None
        self.user_row = None
        self.rune_mode = False

    async def refresh(self):
        self.mastery_row = await self.bot.database.skills.get_mastery(
            self.user_id, self.server_id
        )
        self.user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        self.setup_ui()

    def _safe_get(self, row, key, default=0):
        if row is None:
            return default
        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            return default

    def setup_ui(self):
        self.clear_items()
        runes = self._safe_get(self.user_row, "runes_of_nature", 0)

        if not self.rune_mode:
            for branch in ["yield", "quality", "synergy"]:
                btn = Button(
                    label=f"View {get_branch_display_name(branch)}",
                    style=ButtonStyle.primary,
                    row=0,
                )
                btn.callback = self._make_branch_cb(branch)
                self.add_item(btn)

            reset_btn = Button(
                label=f"Reset Tree ({runes} Runes)", style=ButtonStyle.blurple, row=1
            )
            reset_btn.callback = self._make_rune_mode_cb
            self.add_item(reset_btn)

            back_btn = Button(
                label="Back to Mastery Hub", style=ButtonStyle.secondary, row=1
            )
            back_btn.callback = self.back_to_hub_callback
            self.add_item(back_btn)

        else:
            craft_btn = Button(
                label="Craft Rune of Nature", style=ButtonStyle.success, row=0
            )
            craft_btn.callback = self.craft_rune_callback
            self.add_item(craft_btn)

            respec_btn = Button(
                label="Respec This Skill (1 Rune)", style=ButtonStyle.danger, row=0
            )
            respec_btn.callback = self.respec_callback
            self.add_item(respec_btn)

            back_invest_btn = Button(
                label="Back to Skill Overview", style=ButtonStyle.secondary, row=1
            )
            back_invest_btn.callback = self._make_exit_rune_mode_cb
            self.add_item(back_invest_btn)

    def _make_branch_cb(self, branch: str):
        async def cb(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()
            view = BranchDetailView(
                self.bot,
                self.user_id,
                self.server_id,
                self.skill,
                branch,
                parent_view=self,
            )
            await view.refresh()
            await interaction.edit_original_response(embed=view.get_embed(), view=view)
            view.message = await interaction.original_response()
            self._processing = False

        return cb

    async def _make_rune_mode_cb(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        self.rune_mode = True
        await self.refresh()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)
        self._processing = False

    async def _make_exit_rune_mode_cb(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        self.rune_mode = False
        await self.refresh()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)
        self._processing = False

    async def back_to_hub_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        if self.parent_view:
            await self.parent_view.refresh()
            await interaction.edit_original_response(
                embed=self.parent_view.get_embed()
                if hasattr(self.parent_view, "get_embed")
                else None,
                view=self.parent_view,
            )
        else:
            await interaction.delete_original_response()
        self.stop()

    async def craft_rune_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        m = self.mastery_row or {}
        u = self.user_row or {}
        have = {
            "geode_cores": self._safe_get(m, "geode_cores", 0),
            "tide_relics": self._safe_get(m, "tide_relics", 0),
            "heartwood_shards": self._safe_get(m, "heartwood_shards", 0),
        }
        cost = RUNE_CRAFT_COST
        gold = self._safe_get(u, "gold", 0)
        spirit = self._safe_get(u, "spirit_stones", 0)

        if any(have[k] < cost[k] for k in cost if k in have):
            await interaction.followup.send(
                "Not enough remnants (need 68 of each type).", ephemeral=True
            )
            self._processing = False
            return
        if gold < cost["gold"]:
            await interaction.followup.send(
                "Not enough gold (350,000 required).", ephemeral=True
            )
            self._processing = False
            return
        if spirit < cost["spirit_stones"]:
            await interaction.followup.send(
                "Not enough Spirit Stones (2 required).", ephemeral=True
            )
            self._processing = False
            return

        await self.bot.database.skills.modify_remnants(
            self.user_id, self.server_id, {k: -v for k, v in cost.items() if k in have}
        )
        await self.bot.database.users.modify_gold(self.user_id, -cost["gold"])
        await self.bot.database.users.modify_spirit_stones(
            self.user_id, -cost["spirit_stones"]
        )
        await self.bot.database.skills.add_runes_of_nature(self.user_id, 1)

        await self.refresh()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)
        self._processing = False

    async def respec_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        runes = self._safe_get(self.user_row, "runes_of_nature", 0)
        if runes < 1:
            await interaction.followup.send(
                "You need at least 1 Rune of Nature to respec a skill.", ephemeral=True
            )
            self._processing = False
            return

        await self.bot.database.skills.spend_runes_of_nature(self.user_id, 1)

        alloc = json.loads(
            self._safe_get(self.mastery_row, f"{self.skill}_alloc", "{}") or "{}"
        )
        spent = 0
        tree = get_tree(self.skill)
        for bdata in alloc.values():
            if isinstance(bdata, dict):
                for nk in bdata.get("unlocked", []):
                    if nk in tree:
                        spent += tree[nk].get("cost", 0)

        await self.bot.database.skills.respec_mastery(
            self.user_id, self.server_id, self.skill, spent
        )

        self.rune_mode = False
        await self.refresh()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)
        skill_info = SkillMechanics.get_skill_info(self.skill)
        await interaction.followup.send(
            f"Respec complete for **{skill_info['display_name']}**. You recovered **{spent}** points.",
            ephemeral=True,
        )
        self._processing = False

    def get_embed(self) -> discord.Embed:
        info = SkillMechanics.get_skill_info(self.skill)
        m = self.mastery_row or {}
        pts = self._safe_get(m, f"{self.skill}_points", 0)
        runes = self._safe_get(self.user_row, "runes_of_nature", 0)

        skill_img = {
            "mining": MASTERY_MINING,
            "fishing": MASTERY_FISHING,
            "woodcutting": MASTERY_WOODCUTTING,
        }.get(self.skill)

        if self.rune_mode:
            geodes = self._safe_get(m, "geode_cores", 0)
            tides = self._safe_get(m, "tide_relics", 0)
            heartwood = self._safe_get(m, "heartwood_shards", 0)
            desc = (
                f"**Current Runes of Nature:** {runes}\n\n"
                f"**Your Materials:**\n"
                f"• Geode Cores: **{geodes}**\n"
                f"• Tide Relics: **{tides}**\n"
                f"• Heartwood Shards: **{heartwood}**\n\n"
                f"**Crafting Cost (per Rune):**\n"
                f"• 68 Geode Cores, 68 Tide Relics, 68 Heartwood Shards\n"
                f"• 350,000 Gold, 2 Spirit Stones\n\n"
                "A Rune allows you to fully reset one skill's investments and reclaim all spent points."
            )
            embed = discord.Embed(
                title=f"{info['display_name']} — Reset Tree",
                description=desc,
                color=0x8A2BE2,
            )
            embed.set_footer(
                text="Craft more Runes from remnants, or use one to respec."
            )
            if skill_img:
                embed.set_thumbnail(url=skill_img)
            return embed

        alloc = json.loads(m.get(f"{self.skill}_alloc", "{}") or "{}")
        lines = []
        for branch in ["yield", "quality", "synergy"]:
            progress = get_branch_progress(self.skill, branch, alloc)
            order = BRANCH_NODE_ORDERS.get(self.skill, {}).get(branch, [])
            total_nodes = len(order)
            invested = progress["invested"]
            nodes_unlocked = len(progress["unlocked"])
            total_cost = get_branch_total_cost(self.skill, branch)
            bonus_inv = progress.get("bonus_invested", 0)
            is_complete = progress.get("complete") and bonus_inv >= 10

            if is_complete:
                status = "✅ Maxed"
            elif nodes_unlocked > 0:
                status = (
                    f"{nodes_unlocked}/{total_nodes} nodes · {invested} pts invested"
                )
            else:
                status = "Not started"

            bonus_txt = (
                f" · Bonus {bonus_inv}/10"
                if invested >= total_cost and not is_complete
                else ""
            )
            lines.append(f"**{get_branch_display_name(branch)}:** {status}{bonus_txt}")

        desc = (
            f"Unspent Artisan Points: **{pts}**\n\n"
            + "\n".join(lines)
            + "\n\nSelect a branch to view its nodes and invest."
        )
        embed = discord.Embed(
            title=f"{info['display_name']} Mastery", description=desc, color=0x2E8B57
        )
        if skill_img:
            embed.set_thumbnail(url=skill_img)
        embed.set_footer(
            text="Nodes unlock automatically as you invest points into a branch."
        )
        return embed


# =========================================================
# BRANCH DETAIL VIEW — one branch with full node info
# =========================================================


class BranchDetailView(BaseView):
    """Dedicated view for one mastery branch. Shows all nodes with clean descriptions."""

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        skill: str,
        branch: str,
        parent_view: BaseView | None = None,
    ):
        super().__init__(bot, user_id, server_id, parent=parent_view)
        self.parent_view = parent_view
        self.skill = skill
        self.branch = branch
        self._processing = False
        self.mastery_row = None
        self.user_row = None

    async def refresh(self):
        self.mastery_row = await self.bot.database.skills.get_mastery(
            self.user_id, self.server_id
        )
        self.user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        self.setup_ui()

    def _safe_get(self, row, key, default=0):
        if row is None:
            return default
        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            return default

    def setup_ui(self):
        self.clear_items()

        pts = self._safe_get(self.mastery_row, f"{self.skill}_points", 0)
        alloc_json = (
            self._safe_get(self.mastery_row, f"{self.skill}_alloc", "{}") or "{}"
        )
        alloc = json.loads(alloc_json)
        progress = get_branch_progress(self.skill, self.branch, alloc)
        total_cost = get_branch_total_cost(self.skill, self.branch)
        bonus_inv = progress.get("bonus_invested", 0)
        is_complete = progress.get("complete") and bonus_inv >= 10
        can_invest = pts > 0 and not is_complete

        invest_btn = Button(
            label="Invest 1 Point",
            style=ButtonStyle.success if can_invest else ButtonStyle.secondary,
            disabled=not can_invest,
            row=0,
        )
        invest_btn.callback = self._invest_callback
        self.add_item(invest_btn)

        back_btn = Button(label="← Back", style=ButtonStyle.secondary, row=0)
        back_btn.callback = self._back_callback
        self.add_item(back_btn)

    async def _invest_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        pts = self._safe_get(self.mastery_row, f"{self.skill}_points", 0)
        alloc_json = (
            self._safe_get(self.mastery_row, f"{self.skill}_alloc", "{}") or "{}"
        )

        if pts < 1:
            await interaction.followup.send(
                "You have no unspent Artisan Points to invest.", ephemeral=True
            )
            self._processing = False
            return

        new_alloc_json, spent, newly_unlocked = invest_in_branch(
            self.skill, self.branch, alloc_json, pts, amount=1
        )
        if spent <= 0:
            await interaction.followup.send(
                "Could not invest (branch may be complete).", ephemeral=True
            )
            self._processing = False
            return

        new_total = (
            self._safe_get(self.mastery_row, "total_mastery_invested", 0) + spent
        )
        await self.bot.database.skills.update_mastery_alloc(
            self.user_id, self.server_id, self.skill, new_alloc_json, new_total
        )
        await self.bot.database.skills.deduct_mastery_points(
            self.user_id, self.server_id, self.skill, spent
        )

        await self.refresh()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)
        self._processing = False

    async def _back_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        if self.parent_view:
            await self.parent_view.refresh()
            await interaction.edit_original_response(
                embed=self.parent_view.get_embed()
                if hasattr(self.parent_view, "get_embed")
                else None,
                view=self.parent_view,
            )
        else:
            await interaction.delete_original_response()
        self.stop()

    def get_embed(self) -> discord.Embed:
        info = SkillMechanics.get_skill_info(self.skill)
        m = self.mastery_row or {}
        pts = self._safe_get(m, f"{self.skill}_points", 0)

        alloc = json.loads(m.get(f"{self.skill}_alloc", "{}") or "{}")
        progress = get_branch_progress(self.skill, self.branch, alloc)
        unlocked = set(progress["unlocked"])
        invested = progress["invested"]

        tree = get_tree(self.skill)
        order = BRANCH_NODE_ORDERS.get(self.skill, {}).get(self.branch, [])
        branch_name = get_branch_display_name(self.branch)

        lines = [f"Unspent Points: **{pts}**  ·  Invested in branch: **{invested}**\n"]

        for node_key in order:
            node = tree.get(node_key, {})
            label = NODE_LABELS.get(node_key, node_key)
            desc = node.get("desc", "")
            cost = node.get("cost", 1)
            status = "✅" if node_key in unlocked else "🔒"
            lines.append(f"{status} **{label}** *({cost} pt)*\n{desc}")

        # Bonus investment section
        total_cost = get_branch_total_cost(self.skill, self.branch)
        bonus_inv = progress.get("bonus_invested", 0)
        if invested >= total_cost:
            lines.append(f"\n**Bonus Investment: {bonus_inv}/10**")
            if self.branch == "yield":
                current_pct = get_yield_proc_bonus(self.skill, m) * 100
                lines.append(
                    f"Each bonus point adds +0.4% to the proc chance of the last Yield node. (Current: +{current_pct:.1f}%, max +4.0%)"
                )
            elif self.branch == "quality":
                current_pct = get_rich_base_bonus(self.skill, m) * 100
                lines.append(
                    f"Each bonus point adds +0.5% to the Rich event base chance. (Current: +{current_pct:.1f}%, max +5.0%)"
                )
            elif self.branch == "synergy":
                current_pct = get_prestige_spawn_bonus(self.skill, m) * 100
                lines.append(
                    f"Each bonus point adds +0.2% to the Prestige boss spawn chance. (Current: +{current_pct:.1f}%, max +2.0%)"
                )
        elif progress.get("next_node") and progress["next_node"] != "bonus":
            next_label = NODE_LABELS.get(progress["next_node"], progress["next_node"])
            lines.append(
                f"\n→ Next unlock: **{next_label}** — {progress['next_cost']} more pt(s) needed"
            )

        embed = discord.Embed(
            title=f"{info['display_name']} — {branch_name}",
            description="\n".join(lines),
            color=0x2E8B57,
        )
        skill_img = {
            "mining": MASTERY_MINING,
            "fishing": MASTERY_FISHING,
            "woodcutting": MASTERY_WOODCUTTING,
        }.get(self.skill)
        if skill_img:
            embed.set_thumbnail(url=skill_img)
        embed.set_footer(text="Click 'Invest 1 Point' to advance this branch.")
        return embed


# =========================================================
# NATURE'S ATTUNEMENT VIEW
# =========================================================


class AttunementView(BaseView):
    """Cross-skill free investment tree. Unlocks after 20pts invested in each main tree."""

    def __init__(
        self, bot, user_id: str, server_id: str, parent_view: BaseView | None = None
    ):
        super().__init__(bot, user_id, server_id, parent=parent_view)
        self.parent_view = parent_view
        self._processing = False
        self.mastery_row = None
        self.user_row = None

    async def refresh(self):
        self.mastery_row = await self.bot.database.skills.get_mastery(
            self.user_id, self.server_id
        )
        self.user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        self.setup_ui()

    def _safe_get(self, row, key, default=0):
        if row is None:
            return default
        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            return default

    def setup_ui(self):
        self.clear_items()

        gate_met = has_nature_attunement_unlocked(self.mastery_row or {})
        att_progress = get_attunement_progress(
            self.mastery_row.get("attunement_alloc", "{}") if self.mastery_row else "{}"
        )

        for node_key in NATURE_ATTUNEMENT_NODE_ORDER:
            node = NATURE_ATTUNEMENT_TREE[node_key]
            invested = att_progress.get(node_key, 0)
            label = f"{node['label']} ({invested}/5)"
            btn = Button(
                label=label,
                style=ButtonStyle.primary if invested < 5 else ButtonStyle.success,
                row=0,
                disabled=not gate_met or invested >= 5,
            )
            btn.callback = self._make_invest_cb(node_key)
            self.add_item(btn)

        insight_data = get_total_insight_bonuses(self.mastery_row or {})
        insight_btn = Button(
            label=f"Insight: {insight_data['count']}",
            style=ButtonStyle.secondary,
            row=1,
            disabled=True,
        )
        self.add_item(insight_btn)

        back_btn = Button(label="Back", style=ButtonStyle.secondary, row=1)
        back_btn.callback = self.back_callback
        self.add_item(back_btn)

    def _make_invest_cb(self, node_key: str):
        async def cb(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            pts_m = self._safe_get(self.mastery_row, "mining_points", 0)
            pts_f = self._safe_get(self.mastery_row, "fishing_points", 0)
            pts_w = self._safe_get(self.mastery_row, "woodcutting_points", 0)
            total_pts = pts_m + pts_f + pts_w

            if total_pts < 1:
                await interaction.followup.send(
                    "You have no unspent Artisan Points to invest.", ephemeral=True
                )
                self._processing = False
                return

            alloc_json = (
                self._safe_get(self.mastery_row, "attunement_alloc", "{}") or "{}"
            )
            new_alloc, spent, maxed = invest_in_attunement(
                alloc_json, total_pts, node_key, amount=1
            )

            if spent <= 0:
                await interaction.followup.send(
                    "Could not invest (node maxed or no points).", ephemeral=True
                )
                self._processing = False
                return

            candidates = [
                ("mining", self._safe_get(self.mastery_row, "mining_points", 0)),
                ("fishing", self._safe_get(self.mastery_row, "fishing_points", 0)),
                (
                    "woodcutting",
                    self._safe_get(self.mastery_row, "woodcutting_points", 0),
                ),
            ]
            candidates.sort(key=lambda x: x[1], reverse=True)
            chosen_skill = candidates[0][0] if candidates[0][1] > 0 else "mining"
            await self.bot.database.skills.deduct_mastery_points(
                self.user_id, self.server_id, chosen_skill, 1
            )
            await self.bot.database.skills.update_attunement_alloc(
                self.user_id, self.server_id, new_alloc
            )

            await self.refresh()
            await interaction.edit_original_response(embed=self.get_embed(), view=self)
            self._processing = False

        return cb

    async def back_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        if self.parent_view:
            await self.parent_view.refresh()
            await interaction.edit_original_response(
                embed=self.parent_view.get_embed()
                if hasattr(self.parent_view, "get_embed")
                else None,
                view=self.parent_view,
            )
        else:
            await interaction.delete_original_response()
        self.stop()

    def get_embed(self) -> discord.Embed:
        if not self.mastery_row:
            return discord.Embed(title="Nature's Attunement", description="Loading...")

        gate_met = has_nature_attunement_unlocked(self.mastery_row)
        att_progress = get_attunement_progress(
            self.mastery_row.get("attunement_alloc", "{}")
        )
        insight = get_total_insight_bonuses(self.mastery_row)

        if not gate_met:
            desc = "This cross-skill tree unlocks after you invest at least **20 points** in each of the three main trees (Mining, Woodcutting, and Fishing, including bonus investment)."
            return discord.Embed(
                title="🌿 Nature's Attunement — Locked",
                description=desc,
                color=0x555555,
            )

        lines = []
        for node_key in NATURE_ATTUNEMENT_NODE_ORDER:
            node = NATURE_ATTUNEMENT_TREE[node_key]
            inv = att_progress.get(node_key, 0)
            status = "MAX" if inv >= 5 else f"{inv}/5"
            lines.append(f"**{node['label']}** ({status})\n{node['desc']}")

        insight_lines = (
            f"**Mastery Insight:** {insight['count']}\n"
            f"• Global Yield: +{insight['global_yield'] * 100:.1f}%\n"
            f"• Remnant Chance: +{insight['remnant'] * 100:.1f}%\n"
            f"• Elemental Rune Drop: +{insight['rune'] * 100:.1f}%"
        )

        desc = (
            "Freely invest in any node (max 5 per node). Bonuses apply globally to all gathering.\n\n"
            + "\n\n".join(lines)
            + "\n\n"
            + insight_lines
        )

        embed = discord.Embed(
            title="🌿 Nature's Attunement", description=desc, color=0x2E8B57
        )
        embed.set_thumbnail(url=ARTISAN_MASTERY_ATTUNEMENT)
        embed.set_footer(
            text="Excess points after full mastery convert to Insight (5 pts = 1 Insight)."
        )
        return embed
