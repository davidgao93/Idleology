import math
import random

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.images import SLAYER_EMBLEM, SLAYER_MASTER, SLAYER_MASTER_AUTHOR
from core.npc_voices import get_quip
from core.slayer.mechanics import (
    BOSS_TASK_PREFIX,
    SLAYER_TREE_NODES,
    TREE_RESET_COST,
    SlayerMechanics,
)

_SKIP_BASE_COST = 15
_SKIP_PU1_COST = 10  # pu_1: 30% fewer points (15 → ~10)


class SlayerDashboardView(BaseView):
    def __init__(self, bot, user_id, server_id, profile, player_level, tree_data=None):
        super().__init__(bot, user_id, server_id)
        self.profile = profile
        self.player_level = player_level
        self.tree_nodes: dict = (tree_data or {}).get("nodes_owned", {})
        self.pts_spent: int = (tree_data or {}).get("points_spent", 0)
        self._processing = False
        self.setup_buttons()

    def build_embed(self) -> discord.Embed:
        lvl = self.profile["level"]
        pts = self.profile["points"]

        # Parse cumulative XP into normalized visual progress
        current_xp_prog, next_xp_req = SlayerMechanics.get_xp_progress(
            self.profile["xp"]
        )

        embed = discord.Embed(
            title="Slayer Records",
            description=get_quip("slayer"),
            color=discord.Color.dark_red(),
        )
        embed.set_author(name="Slayer Master Kael", icon_url=SLAYER_MASTER_AUTHOR)
        embed.set_thumbnail(url=SLAYER_MASTER)

        embed.add_field(
            name="Profile",
            value=f"**Level:** {lvl}\n**XP:** {current_xp_prog:,}/{next_xp_req:,}\n**Points:** {pts}",
            inline=True,
        )
        embed.add_field(
            name="Materials",
            value=f"🩸 **Violent Essence:** {self.profile['violent_essence']}\n❤️ **Imbued Hearts:** {self.profile['imbued_heart']}",
            inline=True,
        )

        if self.profile["active_task_species"]:
            prog = self.profile["active_task_progress"]
            req = self.profile["active_task_amount"]
            species = self.profile["active_task_species"]
            if species.startswith(BOSS_TASK_PREFIX):
                boss_name = species[len(BOSS_TASK_PREFIX) :].capitalize()
                task_line = f"Hunt **{req}× {boss_name}** *(Boss Task)*"
            else:
                task_line = f"Slay **{req} {species}**"
            embed.add_field(
                name="Current Task",
                value=f"{task_line}\n*Progress: {prog}/{req}*",
                inline=False,
            )
        else:
            embed.add_field(
                name="Current Task",
                value="No active task. Request one from the master.",
                inline=False,
            )

        return embed

    def setup_buttons(self):
        self.clear_items()

        has_task = bool(self.profile["active_task_species"])
        skip_cost = _SKIP_PU1_COST if self.tree_nodes.get("pu_1") else _SKIP_BASE_COST

        btn_task = ui.Button(
            label="Get Task", style=ButtonStyle.success, disabled=has_task, row=0
        )
        btn_task.callback = self.get_task
        self.add_item(btn_task)

        btn_skip = ui.Button(
            label=f"Skip Task ({skip_cost} pts)",
            style=ButtonStyle.danger,
            disabled=(not has_task or self.profile["points"] < skip_cost),
            row=0,
        )
        btn_skip.callback = self.skip_task
        self.add_item(btn_skip)

        btn_tree = ui.Button(
            label="Slayer Shop", style=ButtonStyle.primary, emoji="💀", row=0
        )
        btn_tree.callback = self.open_tree
        self.add_item(btn_tree)

        btn_emblem = ui.Button(
            label="Manage Emblem", style=ButtonStyle.primary, emoji="🛡️", row=1
        )
        btn_emblem.callback = self.open_emblem
        self.add_item(btn_emblem)

        if self.tree_nodes.get("pu_3") or self.tree_nodes.get("pu_4"):
            btn_shop = ui.Button(
                label="Shop", style=ButtonStyle.success, emoji="🛒", row=1
            )
            btn_shop.callback = self.open_shop
            self.add_item(btn_shop)

        btn_close = ui.Button(
            label="Close", style=ButtonStyle.secondary, emoji="✖️", row=1
        )
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    async def get_task(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # Boss task chance: base 10%, ×1.5 with Favored Target (tm_2)
        available_bosses = SlayerMechanics.available_boss_tasks(self.player_level)
        boss_chance = 0.15 if self.tree_nodes.get("tm_2") else 0.10
        if available_bosses and random.random() < boss_chance:
            boss = random.choice(available_bosses)
            task_key = f"{BOSS_TASK_PREFIX}{boss['key']}"
            modal = BossTaskAmountModal(task_key, boss["name"], self)
            # open_modal responds to the interaction — don't defer beforehand
            self._processing = False
            await interaction.response.send_modal(modal)
            return

        await interaction.response.defer()
        species, amount = SlayerMechanics.generate_task(self.player_level)
        # tm_1: task sizes +20% (rounded up, capped at 50)
        if self.tree_nodes.get("tm_1"):
            amount = min(50, math.ceil(amount * 1.2))

        await self.bot.database.slayer.assign_task(
            self.user_id, self.server_id, species, amount
        )
        self.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )

        self._processing = False
        self.setup_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def skip_task(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        skip_cost = _SKIP_PU1_COST if self.tree_nodes.get("pu_1") else _SKIP_BASE_COST
        if self.profile["points"] < skip_cost:
            self._processing = False
            return await interaction.response.send_message(
                "Not enough Slayer Points!", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.slayer.add_rewards(
            self.user_id, self.server_id, 0, -skip_cost
        )
        await self.bot.database.slayer.clear_task(self.user_id, self.server_id)

        self.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        self._processing = False
        self.setup_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def open_tree(self, interaction: Interaction):
        tree_data = await self.bot.database.slayer.get_tree(
            self.user_id, self.server_id
        )
        self.tree_nodes = tree_data["nodes_owned"]
        self.pts_spent = tree_data["points_spent"]
        # Re-fetch profile for current points
        self.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        view = SlayerTreeView(
            self.bot, self.user_id, self.server_id, self.profile, tree_data, self
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_shop(self, interaction: Interaction):
        self.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        view = SlayerShopView(
            self.bot, self.user_id, self.server_id, self.profile, self.tree_nodes, self
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_emblem(self, interaction: Interaction):
        emblem = await self.bot.database.slayer.get_emblem(self.user_id, self.server_id)
        view = EmblemView(
            self.bot, self.user_id, self.server_id, self.profile, emblem, self
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def close_view(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.delete_original_response()
        self.stop()


class BossTaskAmountModal(ui.Modal, title="Boss Hunt"):
    """Modal that lets the player choose how many boss kills to hunt (1–10)."""

    count_input = ui.TextInput(
        label="How many to hunt? (1–10)",
        placeholder="Enter a number from 1 to 10",
        min_length=1,
        max_length=2,
        required=True,
    )

    def __init__(self, task_key: str, boss_display_name: str, parent_view):
        super().__init__()
        self.title = f"Boss Hunt: {boss_display_name}"
        self.count_input.label = f"Hunt {boss_display_name} — how many? (1–10)"
        self.count_input.placeholder = "Closing this modal cancels the boss task"
        self.task_key = task_key
        self.boss_display_name = boss_display_name
        self.parent = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            count = int(self.count_input.value.strip())
            if not 1 <= count <= 10:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a number between 1 and 10.", ephemeral=True
            )

        await interaction.response.defer()
        await self.parent.bot.database.slayer.assign_task(
            self.parent.user_id, self.parent.server_id, self.task_key, count
        )
        self.parent.profile = await self.parent.bot.database.slayer.get_profile(
            self.parent.user_id, self.parent.server_id
        )
        self.parent.setup_buttons()
        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )


class EmblemView(BaseView):
    def __init__(self, bot, user_id, server_id, profile, emblem, parent_view):
        super().__init__(bot, user_id, server_id)
        self.profile = profile
        self.emblem = emblem
        self.parent = parent_view
        self.unlocked_slots = SlayerMechanics.get_unlocked_slots(self.profile["level"])
        self.setup_ui()

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="💀 Slayer Emblem",
            description="Enhance your combat prowess.",
            color=discord.Color.dark_purple(),
        )
        embed.set_thumbnail(url=SLAYER_EMBLEM)
        # Display Slots
        unlock_reqs = {1: 1, 2: 20, 3: 40, 4: 60, 5: 80}

        for slot in range(1, 6):
            if slot <= self.unlocked_slots:
                data = self.emblem.get(slot, {"type": "none", "tier": 1})
                if data["type"] == "none":
                    embed.add_field(
                        name=f"Slot {slot}",
                        value="*Empty - Needs Awakening*",
                        inline=False,
                    )
                else:
                    # FETCH DYNAMIC DESCRIPTION
                    desc = SlayerMechanics.get_passive_description(
                        data["type"], data["tier"]
                    )
                    embed.add_field(
                        name=f"Slot {slot} (Tier {data['tier']})",
                        value=f"**{desc}**",
                        inline=False,
                    )
            else:
                embed.add_field(
                    name=f"Slot {slot} 🔒",
                    value=f"Unlocks at Slayer Level {unlock_reqs[slot]}",
                    inline=False,
                )

        return embed

    def setup_ui(self):
        self.clear_items()

        # Select Menu for unlocked slots
        options = []
        for slot in range(1, self.unlocked_slots + 1):
            data = self.emblem.get(slot, {"type": "none", "tier": 1})

            if data["type"] == "none":
                lbl = f"Slot {slot} - Empty"
            else:
                # Provide a clean label for the dropdown
                desc = SlayerMechanics.get_passive_description(
                    data["type"], data["tier"]
                )
                lbl = f"Slot {slot} - {desc}"

            options.append(
                SelectOption(label=lbl[:100], value=str(slot))
            )  # Cap at 100 chars for Discord limits

        if options:
            select = ui.Select(
                placeholder="Select a slot to modify...", options=options
            )
            select.callback = self.select_slot
            self.add_item(select)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def select_slot(self, interaction: Interaction):
        slot = int(interaction.data["values"][0])
        slot_data = self.emblem.get(slot, {"type": "none", "tier": 1})

        view = SlotManageView(
            self.bot, self.user_id, self.server_id, self.profile, slot, slot_data, self
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def go_back(self, interaction: Interaction):
        # Refresh profile before going back
        self.parent.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        self.parent.setup_buttons()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


class SlotManageView(BaseView):
    def __init__(
        self, bot, user_id, server_id, profile, slot_num, slot_data, parent_view
    ):
        super().__init__(bot, user_id, server_id)
        self.profile = profile
        self.slot_num = slot_num
        self.slot_data = slot_data
        self.parent = parent_view
        self.result_msg: str = ""
        self._processing = False
        self.setup_ui()

    def build_embed(self) -> discord.Embed:
        p_type = self.slot_data["type"]
        p_tier = self.slot_data["tier"]

        embed = discord.Embed(
            title=f"Modify Slot {self.slot_num}", color=discord.Color.dark_magenta()
        )
        embed.description = f"🩸 **Violent Essence:** {self.profile['violent_essence']}\n❤️ **Imbued Hearts:** {self.profile['imbued_heart']}\n\n"
        if self.result_msg:
            embed.description += f"{self.result_msg}\n\n"

        if p_type == "none":
            embed.description += "**Status:** Empty\nUse 1 Violent Essence to Awaken a random Tier 1 passive."
        else:
            # USE DYNAMIC DESCRIPTION
            desc = SlayerMechanics.get_passive_description(p_type, p_tier)
            success_rate = max(0, int((1.0 - (p_tier * 0.20)) * 100))
            downgrade_rate = 0 if p_tier == 1 else int(((p_tier - 1) * 0.20) * 100)

            embed.add_field(name="Current Passive", value=f"**{desc}**", inline=False)
            if p_tier < 5:
                # Add a preview of what the NEXT tier looks like
                next_desc = SlayerMechanics.get_passive_description(p_type, p_tier + 1)
                embed.add_field(
                    name="Next Tier Preview", value=f"*{next_desc}*", inline=False
                )

                embed.add_field(
                    name="Upgrade Odds",
                    value=f"🟢 Success: {success_rate}%\n🔴 Downgrade: {downgrade_rate}%\n🩸 Cost: {p_tier + 1} Violent Essence",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Upgrade Status", value="🌟 Max Tier Reached!", inline=False
                )

        return embed

    def setup_ui(self):
        self.clear_items()

        essences = self.profile["violent_essence"]
        hearts = self.profile["imbued_heart"]
        p_type = self.slot_data["type"]
        p_tier = self.slot_data["tier"]

        if p_type == "none":
            btn_awaken = ui.Button(
                label="Awaken (1 Essence)",
                style=ButtonStyle.primary,
                emoji="🩸",
                disabled=(essences < 1),
            )
            btn_awaken.callback = self.awaken_slot
            self.add_item(btn_awaken)
        else:
            upgrade_cost = p_tier + 1  # T1→T2 costs 2, T2→T3 costs 3, …, T4→T5 costs 5
            btn_upgrade = ui.Button(
                label=f"Upgrade ({upgrade_cost} Essence)",
                style=ButtonStyle.success,
                emoji="🩸",
                disabled=(essences < upgrade_cost or p_tier >= 5),
            )
            btn_upgrade.callback = self.upgrade_slot
            self.add_item(btn_upgrade)

            btn_reroll = ui.Button(
                label="Reroll Type (1 Heart)",
                style=ButtonStyle.primary,
                emoji="❤️",
                disabled=(hearts < 1),
            )
            btn_reroll.callback = self.reroll_slot
            self.add_item(btn_reroll)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def awaken_slot(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        # ATOMIC DEDUCTION CHECK
        if not await self.bot.database.slayer.consume_material(
            self.user_id, self.server_id, "violent_essence", 1
        ):
            self._processing = False
            return await interaction.followup.send(
                "Not enough Violent Essence!", ephemeral=True
            )

        self.profile["violent_essence"] -= 1

        # Assign random
        new_type = random.choice(SlayerMechanics.PASSIVE_POOL)
        self.slot_data["type"] = new_type
        self.slot_data["tier"] = 1

        await self.bot.database.slayer.update_emblem_slot(
            self.user_id, self.server_id, self.slot_num, new_type, 1
        )

        new_desc = SlayerMechanics.get_passive_description(new_type, 1)
        self.result_msg = f"✅ Slot Awakened! Gained: **{new_desc}**"
        self.setup_ui()
        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def upgrade_slot(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        old_tier = self.slot_data["tier"]
        upgrade_cost = old_tier + 1  # matches setup_ui

        # ATOMIC DEDUCTION CHECK
        if not await self.bot.database.slayer.consume_material(
            self.user_id, self.server_id, "violent_essence", upgrade_cost
        ):
            self._processing = False
            return await interaction.followup.send(
                f"Not enough Violent Essence! You need {upgrade_cost}.", ephemeral=True
            )

        self.profile["violent_essence"] -= upgrade_cost
        success, new_tier = SlayerMechanics.roll_upgrade(old_tier)

        self.slot_data["tier"] = new_tier
        await self.bot.database.slayer.update_emblem_slot(
            self.user_id,
            self.server_id,
            self.slot_num,
            self.slot_data["type"],
            new_tier,
        )

        if success:
            msg = f"✨ **Success!** Upgraded to Tier {new_tier}!"
        elif new_tier < old_tier:
            msg = (
                f"💥 **Failure.** The essence corrupted. Downgraded to Tier {new_tier}."
            )
        else:
            msg = f"💨 **Failure.** The essence faded. Slot remains Tier {new_tier}."

        self.result_msg = msg
        self.setup_ui()
        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def reroll_slot(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        # ATOMIC DEDUCTION CHECK
        if not await self.bot.database.slayer.consume_material(
            self.user_id, self.server_id, "imbued_heart", 1
        ):
            self._processing = False
            return await interaction.followup.send(
                "Not enough Imbued Hearts!", ephemeral=True
            )

        self.profile["imbued_heart"] -= 1

        # Pick new random (exclude current)
        pool = [p for p in SlayerMechanics.PASSIVE_POOL if p != self.slot_data["type"]]
        new_type = random.choice(pool)

        self.slot_data["type"] = new_type
        await self.bot.database.slayer.update_emblem_slot(
            self.user_id,
            self.server_id,
            self.slot_num,
            new_type,
            self.slot_data["tier"],
        )

        new_desc = SlayerMechanics.get_passive_description(
            new_type, self.slot_data["tier"]
        )
        self.result_msg = f"❤️ **Rerolled!** New Passive: **{new_desc}**"
        self.setup_ui()
        self._processing = False
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        # Sync changes back to parent
        self.parent.emblem[self.slot_num] = self.slot_data
        self.parent.setup_ui()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


# ---------------------------------------------------------------------------
# Slayer Tree
# ---------------------------------------------------------------------------

_BRANCH_ICONS = {"taskmaster": "🎯", "hunter": "🗡️", "purveyor": "🛒"}
_BRANCH_NAMES = {"taskmaster": "Taskmaster", "hunter": "Hunter", "purveyor": "Purveyor"}
_NODE_ORDER = ["tm", "hu", "pu"]  # branch prefixes in display order


def _node_status(node_id: str, nodes_owned: dict) -> str:
    node = SLAYER_TREE_NODES[node_id]
    if nodes_owned.get(node_id):
        return "✅"
    prereq = node.get("prereq")
    if prereq and not nodes_owned.get(prereq):
        return "🔒"
    return "◻️"


def _node_value_display(node_id: str, nodes_owned: dict) -> str:
    """Shows the chosen option for Hunter choice nodes, or blank."""
    val = nodes_owned.get(node_id)
    if not val or val is True:
        return ""
    node = SLAYER_TREE_NODES[node_id]
    for key, label in node.get("choices", []):
        if key == val:
            return f" *({label.split('+')[0].strip() if '+' in label else label})*"
    return f" *({val})*"


class SlayerTreeView(BaseView):
    """Displays the Slayer Tree, handles node purchasing and resets."""

    def __init__(self, bot, user_id, server_id, profile, tree_data, parent_view):
        super().__init__(bot, user_id, server_id)
        self.profile = profile
        self.tree_nodes: dict = dict(tree_data.get("nodes_owned", {}))
        self.pts_spent: int = tree_data.get("points_spent", 0)
        self.parent = parent_view
        self._processing = False
        self._pending_node: str | None = None  # Hunter node awaiting choice
        self.result_msg = ""
        self.active_branch = "taskmaster"
        self.setup_ui()

    # --- Embed ---------------------------------------------------------------

    def build_embed(self) -> discord.Embed:
        pts = self.profile["points"]
        ess = self.profile["violent_essence"]
        branch = self.active_branch
        icon = _BRANCH_ICONS[branch]
        name = _BRANCH_NAMES[branch]
        prefix = {"taskmaster": "tm", "hunter": "hu", "purveyor": "pu"}[branch]

        embed = discord.Embed(
            title=f"💀 Slayer Shop — {icon} {name}",
            description=(
                f"**Slayer Points:** {pts} | 🩸 **Violent Essence:** {ess}\n"
                f"*Points spent: {self.pts_spent}*\n\n"
                + (f"**{self.result_msg}**\n" if self.result_msg else "")
            ),
            color=discord.Color.dark_red(),
        )

        lines = []
        for nid, node in SLAYER_TREE_NODES.items():
            if not nid.startswith(prefix):
                continue
            status = _node_status(nid, self.tree_nodes)
            cost_str = f"({node['cost']} pts)"
            if "choices" in node:
                val = self.tree_nodes.get(nid)
                if val and val is not True:
                    desc = next(
                        (label for key, label in node["choices"] if key == val),
                        "Choose one option",
                    )
                else:
                    desc = "Choose one option"
            else:
                desc = node["desc"]
            lines.append(f"{status} **{node['name']}** {cost_str}\n└ *{desc}*")
        embed.add_field(name=f"{icon} {name}", value="\n".join(lines), inline=False)

        embed.set_footer(
            text=f"Reset: costs {TREE_RESET_COST} Violent Essence | refunds 80% of points spent"
        )
        return embed

    # --- UI ------------------------------------------------------------------

    def setup_ui(self):
        self.clear_items()
        self._pending_node = None

        # Row 0: branch navigation buttons
        _prefix_map = {"taskmaster": "tm", "hunter": "hu", "purveyor": "pu"}
        for branch in ("taskmaster", "hunter", "purveyor"):
            icon = _BRANCH_ICONS[branch]
            name = _BRANCH_NAMES[branch]
            btn = ui.Button(
                label=f"{icon} {name}",
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

        # Row 1: purchasable nodes in the active branch only
        active_prefix = _prefix_map[self.active_branch]
        purchasable = [
            nid
            for nid, node in SLAYER_TREE_NODES.items()
            if nid.startswith(active_prefix)
            and not self.tree_nodes.get(nid)
            and (node["prereq"] is None or self.tree_nodes.get(node["prereq"]))
        ]
        if purchasable:
            options = []
            for nid in purchasable:
                node = SLAYER_TREE_NODES[nid]
                options.append(
                    SelectOption(
                        label=f"{node['name']} ({node['cost']} pts)",
                        value=nid,
                        description=(
                            "Choose one option"
                            if "choices" in node
                            else node.get("desc", "")
                        )[:100],
                    )
                )
            sel = ui.Select(
                placeholder="Select a node to purchase…",
                options=options,
                row=1,
            )
            sel.callback = self.on_node_select
            self.add_item(sel)

        can_reset = (
            bool(self.tree_nodes) and self.profile["violent_essence"] >= TREE_RESET_COST
        )
        btn_reset = ui.Button(
            label=f"Reset Tree ({TREE_RESET_COST} Essence)",
            style=ButtonStyle.danger,
            disabled=not can_reset,
            row=2,
        )
        btn_reset.callback = self.on_reset
        self.add_item(btn_reset)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    def _show_choice_ui(self, node_id: str):
        """Rebuilds the UI to show choice buttons for a Hunter node."""
        self.clear_items()
        node = SLAYER_TREE_NODES[node_id]
        self._pending_node = node_id
        for key, label in node["choices"]:
            btn = ui.Button(label=label[:80], style=ButtonStyle.primary, row=0)
            btn.custom_id_key = key  # stored for callback

            # Closure capture
            async def _choice_cb(interaction: Interaction, k=key):
                await self._confirm_choice(interaction, node_id, k)

            btn.callback = _choice_cb
            self.add_item(btn)
        btn_cancel = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=1)
        btn_cancel.callback = self._cancel_choice
        self.add_item(btn_cancel)

    # --- Callbacks -----------------------------------------------------------

    async def on_node_select(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        node_id = interaction.data["values"][0]
        node = SLAYER_TREE_NODES[node_id]

        if "choices" in node:
            # Show choice picker UI
            self._show_choice_ui(node_id)
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            return

        # Regular node — purchase immediately
        await self._purchase_node(interaction, node_id, choice=None)

    async def _cancel_choice(self, interaction: Interaction):
        self._pending_node = None
        self.setup_ui()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _confirm_choice(
        self, interaction: Interaction, node_id: str, choice: str
    ):
        await self._purchase_node(interaction, node_id, choice=choice)

    async def _purchase_node(
        self, interaction: Interaction, node_id: str, choice: str | None
    ):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        # Re-fetch profile to avoid stale points
        fresh = await self.bot.database.slayer.get_profile(self.user_id, self.server_id)
        node = SLAYER_TREE_NODES[node_id]
        cost = node["cost"]

        if fresh["points"] < cost:
            self._processing = False
            self.result_msg = f"❌ Not enough Slayer Points (need {cost})."
            self.setup_ui()
            return await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        self.profile = fresh
        # Deduct points
        await self.bot.database.slayer.add_rewards(
            self.user_id, self.server_id, 0, -cost
        )
        self.profile["points"] -= cost

        # Record node
        value = choice if choice is not None else True
        self.tree_nodes[node_id] = value
        new_pts_spent = self.pts_spent + cost
        await self.bot.database.slayer.upsert_tree(
            self.user_id, self.server_id, self.tree_nodes, new_pts_spent
        )
        self.pts_spent = new_pts_spent

        node_name = node["name"]
        choice_label = ""
        if choice:
            for k, label in node.get("choices", []):
                if k == choice:
                    choice_label = f" → **{label}**"
                    break
        self.result_msg = f"✅ Unlocked **{node_name}**!{choice_label}"

        # Sync parent tree state
        self.parent.tree_nodes = self.tree_nodes
        self.parent.pts_spent = self.pts_spent

        self._processing = False
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def on_reset(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        # Atomic consume Violent Essence
        if not await self.bot.database.slayer.consume_material(
            self.user_id, self.server_id, "violent_essence", TREE_RESET_COST
        ):
            self._processing = False
            self.result_msg = f"❌ Need {TREE_RESET_COST} Violent Essence to reset."
            self.setup_ui()
            return await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        refund = math.floor(self.pts_spent * 0.80)
        await self.bot.database.slayer.add_rewards(
            self.user_id, self.server_id, 0, refund
        )
        await self.bot.database.slayer.reset_tree(self.user_id, self.server_id)

        # Refresh profile
        self.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        self.tree_nodes = {}
        self.pts_spent = 0
        self.parent.tree_nodes = {}
        self.parent.pts_spent = 0

        self.result_msg = (
            f"🔄 Tree reset! Refunded **{refund}** Slayer Points "
            f"(consumed {TREE_RESET_COST} Violent Essence)."
        )
        self._processing = False
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        self.parent.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        self.parent.setup_buttons()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


# ---------------------------------------------------------------------------
# Slayer Shop (pu_3 / pu_4)
# ---------------------------------------------------------------------------


class SlayerShopView(BaseView):
    """Lets players spend Slayer Points on materials unlocked via the Purveyor branch."""

    _ESS_COST = 40
    _HEART_COST = 1200

    def __init__(self, bot, user_id, server_id, profile, tree_nodes, parent_view):
        super().__init__(bot, user_id, server_id)
        self.profile = profile
        self.tree_nodes = tree_nodes
        self.parent = parent_view
        self._processing = False
        self.result_msg = ""
        self.setup_ui()

    def build_embed(self) -> discord.Embed:
        pts = self.profile["points"]
        embed = discord.Embed(
            title="🛒 Slayer Shop",
            description=(
                f"**Slayer Points:** {pts}\n"
                f"🩸 **Violent Essence:** {self.profile['violent_essence']} | "
                f"❤️ **Imbued Hearts:** {self.profile['imbued_heart']}\n\n"
                + (f"**{self.result_msg}**\n" if self.result_msg else "")
            ),
            color=discord.Color.dark_gold(),
        )
        if self.tree_nodes.get("pu_3"):
            embed.add_field(
                name=f"🩸 Violent Essence — {self._ESS_COST} pts",
                value="Purchase 1 Violent Essence from the black market.",
                inline=False,
            )
        if self.tree_nodes.get("pu_4"):
            embed.add_field(
                name=f"❤️ Imbued Heart — {self._HEART_COST} pts",
                value="Purchase 1 Imbued Heart from the black market.",
                inline=False,
            )
        return embed

    def setup_ui(self):
        self.clear_items()
        pts = self.profile["points"]

        if self.tree_nodes.get("pu_3"):
            btn_ess = ui.Button(
                label=f"Buy Essence ({self._ESS_COST} pts)",
                style=ButtonStyle.primary,
                emoji="🩸",
                disabled=(pts < self._ESS_COST),
                row=0,
            )
            btn_ess.callback = self.buy_essence
            self.add_item(btn_ess)

        if self.tree_nodes.get("pu_4"):
            btn_heart = ui.Button(
                label=f"Buy Heart ({self._HEART_COST} pts)",
                style=ButtonStyle.danger,
                emoji="❤️",
                disabled=(pts < self._HEART_COST),
                row=0,
            )
            btn_heart.callback = self.buy_heart
            self.add_item(btn_heart)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def _buy(self, interaction: Interaction, col: str, cost: int, label: str):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        fresh = await self.bot.database.slayer.get_profile(self.user_id, self.server_id)
        if fresh["points"] < cost:
            self._processing = False
            self.result_msg = f"❌ Not enough Slayer Points (need {cost})."
            self.setup_ui()
            return await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

        await self.bot.database.slayer.add_rewards(
            self.user_id, self.server_id, 0, -cost
        )
        await self.bot.database.slayer.modify_materials(
            self.user_id, self.server_id, col, 1
        )
        self.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        self.result_msg = f"✅ Purchased 1 {label}!"
        self._processing = False
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def buy_essence(self, interaction: Interaction):
        await self._buy(
            interaction, "violent_essence", self._ESS_COST, "Violent Essence"
        )

    async def buy_heart(self, interaction: Interaction):
        await self._buy(interaction, "imbued_heart", self._HEART_COST, "Imbued Heart")

    async def go_back(self, interaction: Interaction):
        self.parent.profile = await self.bot.database.slayer.get_profile(
            self.user_id, self.server_id
        )
        self.parent.setup_buttons()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
