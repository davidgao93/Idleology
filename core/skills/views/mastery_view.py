"""
Artisan Mastery UI (redesigned per user feedback)

- Hub (ArtisanMasteryHubView): Only 4 buttons — Mining, Woodcutting, Fishing, Back to Gather.
  No selects, no Black Market (moved to Settlement), minimal noise.

- Per-skill view (SkillMasteryView): Shows the three branches (Yield / Quality / Synergy)
  with clear unlock status and progress toward the next node.
  Primary actions are three "Invest in <Branch>" buttons.
  Every successful investment updates the embed directly.
  Ephemeral messages are **only** used for errors.

The investment model is now branch-based counters that unlock nodes sequentially.
"""

import json
import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
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
# HUB VIEW — extremely simple, only 4 buttons
# =========================================================

class ArtisanMasteryHubView(BaseView):
    """The main entry point for Artisan Mastery. Only 4 buttons as requested."""

    def __init__(self, bot, user_id: str, server_id: str, parent_view: BaseView | None = None):
        super().__init__(bot, user_id, server_id, parent=parent_view)
        self.parent_view = parent_view
        self._processing = False

    async def refresh(self):
        self.mastery_row = await self.bot.database.skills.get_mastery(self.user_id, self.server_id)
        self.setup_ui()

    def setup_ui(self):
        self.clear_items()

        skills = ["mining", "woodcutting", "fishing"]
        for idx, s in enumerate(skills):
            info = SkillMechanics.get_skill_info(s)
            btn = Button(
                label=info["display_name"],
                emoji=info["emoji"],
                style=ButtonStyle.primary,
                row=0,
            )
            btn.callback = self._make_skill_button_cb(s)
            self.add_item(btn)

        # Nature's Attunement (cross-skill) button — only visible once gate is met
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

            view = SkillMasteryView(self.bot, self.user_id, self.server_id, skill, parent_view=self)
            await view.refresh()
            await interaction.edit_original_response(embed=view.get_embed(), view=view)
            view.message = await interaction.original_response()
            self._processing = False
        return cb

    async def back_callback(self, interaction: Interaction):
        await interaction.response.defer()
        if self.parent_view:
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
                "Choose a gathering skill to view its specialization trees and begin investing Artisan Points.\n\n"
                "🌿 **Nature's Attunement** (cross-skill tree) unlocks after investing **20+ points** in *each* of Mining, Woodcutting, and Fishing (including post-capstone bonus investment)."
            ),
            color=0x2E8B57,
        )
        embed.set_footer(text="The Black Market is seeking rare gathering materials for trade.")
        return embed


# =========================================================
# SKILL-SPECIFIC VIEW — the heart of the new experience
# =========================================================

class SkillMasteryView(BaseView):
    """
    Dedicated view for one skill.
    Shows the three branches + investment progress.
    Primary actions: Invest in Yield / Quality / Synergy (1 point each).
    Success always updates the embed. Only errors are ephemeral.
    """

    def __init__(self, bot, user_id: str, server_id: str, skill: str, parent_view: BaseView | None = None):
        super().__init__(bot, user_id, server_id, parent=parent_view)
        self.parent_view = parent_view
        self.skill = skill
        self._processing = False

        self.mastery_row = None
        self.user_row = None
        self.rune_mode = False  # When True, show rune crafting + respec options instead of investment buttons

    async def refresh(self):
        self.mastery_row = await self.bot.database.skills.get_mastery(self.user_id, self.server_id)
        self.user_row = await self.bot.database.users.get(self.user_id, self.server_id)

        # Note: Robust unlock reconciliation now happens on every investment action
        # inside invest_in_branch(). The improved get_branch_progress() also prevents
        # the UI from showing misleading "0 pts to go" states even on legacy/stuck data.
        # Viewing the page will show correct progress; the next invest click will
        # claim any pending unlocks the current invested total qualifies for.

        self.setup_ui()

    def _safe_get(self, row, key, default=0):
        """Safely get a value from a sqlite3.Row or dict (or None)."""
        if row is None:
            return default
        try:
            return row[key]
        except (KeyError, IndexError, TypeError):
            return default

    def setup_ui(self):
        self.clear_items()

        info = SkillMechanics.get_skill_info(self.skill)
        pts = self._safe_get(self.mastery_row, f"{self.skill}_points", 0)
        runes = self._safe_get(self.user_row, "runes_of_nature", 0)

        if not self.rune_mode:
            # === Normal Investment Mode ===

            # Three investment buttons (row 0)
            for branch in ["yield", "quality", "synergy"]:
                btn = Button(
                    label=f"Invest in {get_branch_display_name(branch)}",
                    style=ButtonStyle.success,
                    row=0,
                )
                btn.callback = self._make_invest_cb(branch)
                self.add_item(btn)

            # Row 1: Rune of Nature button + Back
            rune_btn = Button(
                label=f"Rune of Nature ({runes})",
                style=ButtonStyle.blurple,
                row=1,
            )
            rune_btn.callback = self._make_rune_mode_cb
            self.add_item(rune_btn)

            back_btn = Button(label="Back to Mastery Hub", style=ButtonStyle.secondary, row=1)
            back_btn.callback = self.back_to_hub_callback
            self.add_item(back_btn)

        else:
            # === Rune of Nature Management Mode ===

            # Row 0: Craft + Respec
            craft_btn = Button(
                label="Craft Rune of Nature",
                style=ButtonStyle.success,
                row=0,
            )
            craft_btn.callback = self.craft_rune_callback
            self.add_item(craft_btn)

            respec_btn = Button(
                label="Respec This Skill (1 Rune)",
                style=ButtonStyle.danger,
                row=0,
            )
            respec_btn.callback = self.respec_callback
            self.add_item(respec_btn)

            # Row 1: Back to investments
            back_invest_btn = Button(
                label="Back to Investments",
                style=ButtonStyle.secondary,
                row=1,
            )
            back_invest_btn.callback = self._make_exit_rune_mode_cb
            self.add_item(back_invest_btn)

    # --- Rune mode switching ---
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

    def _make_invest_cb(self, branch: str):
        async def cb(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            pts = self._safe_get(self.mastery_row, f"{self.skill}_points", 0)
            alloc_json = self._safe_get(self.mastery_row, f"{self.skill}_alloc", "{}") or "{}"

            if pts < 1:
                await interaction.followup.send("You have no unspent Artisan Points to invest.", ephemeral=True)
                self._processing = False
                return

            new_alloc_json, spent, newly_unlocked = invest_in_branch(
                self.skill, branch, alloc_json, pts, amount=1
            )

            if spent <= 0:
                await interaction.followup.send("Could not invest (branch may be complete).", ephemeral=True)
                self._processing = False
                return

            # Persist
            new_total = self._safe_get(self.mastery_row, "total_mastery_invested", 0) + spent
            await self.bot.database.skills.update_mastery_alloc(
                self.user_id, self.server_id, self.skill, new_alloc_json, new_total
            )
            await self.bot.database.skills.deduct_mastery_points(
                self.user_id, self.server_id, self.skill, spent
            )

            # Refresh and update embed (no success ephemeral)
            await self.refresh()
            await interaction.edit_original_response(embed=self.get_embed(), view=self)

            self._processing = False
        return cb

    async def back_to_hub_callback(self, interaction: Interaction):
        await interaction.response.defer()
        if self.parent_view:
            await self.parent_view.refresh()
            await interaction.edit_original_response(
                embed=self.parent_view.get_embed() if hasattr(self.parent_view, "get_embed") else None,
                view=self.parent_view
            )
        else:
            await interaction.delete_original_response()
        self.stop()

    # --- Rune of Nature actions ---
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
            await interaction.followup.send("Not enough remnants (need 68 of each type).", ephemeral=True)
            self._processing = False
            return
        if gold < cost["gold"]:
            await interaction.followup.send("Not enough gold (350,000 required).", ephemeral=True)
            self._processing = False
            return
        if spirit < cost["spirit_stones"]:
            await interaction.followup.send("Not enough Spirit Stones (2 required).", ephemeral=True)
            self._processing = False
            return

        # Deduct resources
        await self.bot.database.skills.modify_remnants(
            self.user_id, self.server_id,
            {k: -v for k, v in cost.items() if k in have}
        )
        await self.bot.database.users.modify_gold(self.user_id, -cost["gold"])
        await self.bot.database.users.modify_spirit_stones(self.user_id, -cost["spirit_stones"])
        await self.bot.database.skills.add_runes_of_nature(self.user_id, 1)

        await self.refresh()
        await interaction.edit_original_response(embed=self.get_embed(), view=self)
        # Success is communicated purely by the updated embed showing new material/rune counts.
        self._processing = False

    async def respec_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        runes = self._safe_get(self.user_row, "runes_of_nature", 0)
        if runes < 1:
            await interaction.followup.send("You need at least 1 Rune of Nature to respec a skill.", ephemeral=True)
            self._processing = False
            return

        # Spend the rune
        await self.bot.database.skills.spend_runes_of_nature(self.user_id, 1)

        # Refund points and clear this skill's investments
        alloc = json.loads(self._safe_get(self.mastery_row, f"{self.skill}_alloc", "{}") or "{}")
        spent = 0
        tree = get_tree(self.skill)
        for bdata in alloc.values():
            if isinstance(bdata, dict):
                for nk in bdata.get("unlocked", []):
                    if nk in tree:
                        spent += tree[nk].get("cost", 0)

        await self.bot.database.skills.respec_mastery(self.user_id, self.server_id, self.skill, spent)

        # Exit rune mode after respec
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

        if self.rune_mode:
            # Rune management embed — show current holdings so player knows what they have
            geodes   = self._safe_get(m, "geode_cores", 0)
            tides    = self._safe_get(m, "tide_relics", 0)
            heartwood = self._safe_get(m, "heartwood_shards", 0)

            desc = (
                f"**Current Runes of Nature:** {runes}\n\n"
                f"**Your Current Materials:**\n"
                f"• Geode Cores: **{geodes}**\n"
                f"• Tide Relics: **{tides}**\n"
                f"• Heartwood Shards: **{heartwood}**\n\n"
                f"**Crafting Cost (per Rune):**\n"
                f"• 68 Geode Cores\n"
                f"• 68 Tide Relics\n"
                f"• 68 Heartwood Shards\n"
                f"• 350,000 Gold\n"
                f"• 2 Spirit Stones\n\n"
                "Crafting a Rune allows you to fully respec one skill's investment choices."
            )
            embed = discord.Embed(
                title=f"{info['display_name']} — Rune of Nature",
                description=desc,
                color=0x8A2BE2,
            )
            embed.set_footer(text="Use Runes to respec or craft more from remnants.")
            return embed

        # Normal investment embed
        alloc = json.loads(m.get(f"{self.skill}_alloc", "{}") or "{}")

        lines = []
        tree = get_tree(self.skill)
        order_map = BRANCH_NODE_ORDERS.get(self.skill, {})

        for branch in ["yield", "quality", "synergy"]:
            progress = get_branch_progress(self.skill, branch, alloc)
            unlocked = progress["unlocked"]
            next_node = progress["next_node"]

            branch_lines = [f"**{get_branch_display_name(branch)}** — invested **{progress['invested']}**"]

            for node_key in order_map.get(branch, []):
                label = NODE_LABELS.get(node_key, node_key)
                effect = tree.get(node_key, {}).get("desc", "")
                if node_key in unlocked:
                    branch_lines.append(f"  ✅ **{label}** — {effect}")
                else:
                    # Show full description even for locked nodes so players know what they're investing toward
                    branch_lines.append(f"  🔒 **{label}** — {effect}")

            if next_node == "bonus":
                bonus_inv = progress.get("bonus_invested", 0)
                branch_lines.append(f"  → Bonus Investment: **{bonus_inv}/10**")
            elif next_node:
                pct = 0
                if progress.get("total_for_next"):
                    pct = int((progress.get("progress_toward_next", 0) / progress["total_for_next"]) * 100)
                branch_lines.append(f"  → Next: **{NODE_LABELS.get(next_node, next_node)}** ({progress['next_cost']} pts to go)")

            # Show Bonus Investment section (with full explanation) once the normal nodes are unlocked.
            # This appears even at 0/10 so players know what the extra points do.
            total_cost = get_branch_total_cost(self.skill, branch)
            if progress["invested"] >= total_cost:
                bonus_inv = progress.get("bonus_invested", 0)
                branch_lines.append(f"  → Bonus Investment: **{bonus_inv}/10**")

                if branch == "yield":
                    current = get_yield_proc_bonus(self.skill, m) * 100
                    branch_lines.append(f"    +0.4% Never Empty proc chance per point (current +{current:.1f}%, max +4.0%)")
                elif branch == "quality":
                    current = get_rich_base_bonus(self.skill, m) * 100
                    branch_lines.append(f"    +0.5% Rich event base chance per point (current +{current:.1f}%, max +5.0%)")
                elif branch == "synergy":
                    current = get_prestige_spawn_bonus(self.skill, m) * 100
                    branch_lines.append(f"    +0.2% Prestige boss spawn chance per point (current +{current:.1f}%, max +2.0%)")

            lines.append("\n".join(branch_lines))

        desc = (
            f"Unspent Artisan Points: **{pts}**\n\n"
            + "\n\n".join(lines)
        )

        embed = discord.Embed(
            title=f"{info['display_name']} Mastery",
            description=desc,
            color=0x2E8B57,
        )
        embed.set_footer(text="Invest in a branch to progress the tree. Nodes unlock automatically at thresholds.")
        return embed


# =========================================================
# NATURE'S ATTUNEMENT VIEW — cross-skill free investment tree
# =========================================================

class AttunementView(BaseView):
    """
    Dedicated view for the Nature's Attunement (cross-skill) tree.
    Shows the 3 nodes with current investment (0-5).
    Players may freely invest in any node once the 20-pt gate is passed.
    Also displays Mastery Insight and the three global bonuses.
    """

    def __init__(self, bot, user_id: str, server_id: str, parent_view: BaseView | None = None):
        super().__init__(bot, user_id, server_id, parent=parent_view)
        self.parent_view = parent_view
        self._processing = False
        self.mastery_row = None
        self.user_row = None

    async def refresh(self):
        self.mastery_row = await self.bot.database.skills.get_mastery(self.user_id, self.server_id)
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
        att_progress = get_attunement_progress(self.mastery_row.get("attunement_alloc", "{}") if self.mastery_row else "{}")
        insight_data = get_total_insight_bonuses(self.mastery_row or {})

        # Three node investment buttons (free choice)
        for i, node_key in enumerate(NATURE_ATTUNEMENT_NODE_ORDER):
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

        # Insight summary button (informational)
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
                await interaction.followup.send("You have no unspent Artisan Points to invest.", ephemeral=True)
                self._processing = False
                return

            alloc_json = self._safe_get(self.mastery_row, "attunement_alloc", "{}") or "{}"
            new_alloc, spent, maxed = invest_in_attunement(alloc_json, total_pts, node_key, amount=1)

            if spent <= 0:
                await interaction.followup.send("Could not invest (node maxed or no points).", ephemeral=True)
                self._processing = False
                return

            # Deduct 1 point from the skill with the most unspent points (cleaner UX)
            candidates = [
                ("mining", self._safe_get(self.mastery_row, "mining_points", 0)),
                ("fishing", self._safe_get(self.mastery_row, "fishing_points", 0)),
                ("woodcutting", self._safe_get(self.mastery_row, "woodcutting_points", 0)),
            ]
            candidates.sort(key=lambda x: x[1], reverse=True)
            chosen_skill = candidates[0][0] if candidates[0][1] > 0 else "mining"
            await self.bot.database.skills.deduct_mastery_points(self.user_id, self.server_id, chosen_skill, 1)

            await self.bot.database.skills.update_attunement_alloc(self.user_id, self.server_id, new_alloc)

            # Refresh and update embed (no success ephemeral)
            await self.refresh()
            await interaction.edit_original_response(embed=self.get_embed(), view=self)

            self._processing = False
        return cb

    async def back_callback(self, interaction: Interaction):
        await interaction.response.defer()
        if self.parent_view:
            await self.parent_view.refresh()
            await interaction.edit_original_response(
                embed=self.parent_view.get_embed() if hasattr(self.parent_view, "get_embed") else None,
                view=self.parent_view
            )
        else:
            await interaction.delete_original_response()
        self._processing = False

    def get_embed(self) -> discord.Embed:
        if not self.mastery_row:
            return discord.Embed(title="Nature's Attunement", description="Loading...")

        gate_met = has_nature_attunement_unlocked(self.mastery_row)
        att_progress = get_attunement_progress(self.mastery_row.get("attunement_alloc", "{}"))
        insight = get_total_insight_bonuses(self.mastery_row)

        if not gate_met:
            desc = "This cross-skill tree unlocks after you invest at least **20 points** in *each* of the three main gathering trees (Mining, Woodcutting, and Fishing, including bonus investment)."
            embed = discord.Embed(title="🌿 Nature's Attunement — Locked", description=desc, color=0x555555)
            return embed

        lines = []
        for node_key in NATURE_ATTUNEMENT_NODE_ORDER:
            node = NATURE_ATTUNEMENT_TREE[node_key]
            inv = att_progress.get(node_key, 0)
            status = "MAX" if inv >= 5 else f"{inv}/5"
            lines.append(f"**{node['label']}** ({status})\n{node['desc']}")

        insight_lines = (
            f"**Mastery Insight:** {insight['count']}\n"
            f"• Global Yield: +{insight['global_yield']*100:.1f}%\n"
            f"• Remnant Chance: +{insight['remnant']*100:.1f}%\n"
            f"• Elemental Rune Drop: +{insight['rune']*100:.1f}%"
        )

        desc = (
            "Freely invest in any node (max 5 per node). Bonuses are global.\n\n"
            + "\n\n".join(lines)
            + "\n\n"
            + insight_lines
        )

        embed = discord.Embed(
            title="🌿 Nature's Attunement",
            description=desc,
            color=0x2E8B57,
        )
        embed.set_footer(text="Excess points after full mastery convert into Insight (5 pts = 1 Insight).")
        return embed
