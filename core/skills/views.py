import asyncio

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.combat.views_elemental import ElementalEncounterView
from core.items.factory import load_player
from core.skills.mechanics import SkillMechanics


class GatherView(BaseView):
    def __init__(
        self, bot, user_id: str, server_id: str, initial_skill: str = "mining"
    ):
        super().__init__(bot, user_id, server_id)
        self.current_skill = initial_skill

        # Data Cache
        self.user_data = None
        self.skill_data = None
        self.uber_data = None

        # Prevent overlapping updates
        self._lock = asyncio.Lock()

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

    async def refresh_state(self):
        """Fetches fresh data for the CURRENT skill."""
        self.user_data = await self.bot.database.users.get(self.user_id, self.server_id)
        self.skill_data = await self.bot.database.skills.get_data(
            self.user_id, self.server_id, self.current_skill
        )
        self.uber_data = await self.bot.database.uber.get_uber_progress(
            self.user_id, self.server_id
        )
        self.setup_ui()

    def setup_ui(self):
        self.clear_items()

        # --- ROW 0: TABS ---
        skills = ["mining", "woodcutting", "fishing"]
        for s in skills:
            info = SkillMechanics.get_skill_info(s)
            is_active = s == self.current_skill
            style = ButtonStyle.primary if is_active else ButtonStyle.secondary

            btn = Button(
                label=info["display_name"],
                emoji=info["emoji"],
                style=style,
                row=0,
            )
            # Proper async callback (no lambda issues)
            btn.callback = self._make_tab_callback(s)
            self.add_item(btn)

        # --- ROW 1: ACTIONS ---
        if self.skill_data:
            current_tier = self.skill_data[2]
            next_tier = SkillMechanics.get_next_tier(self.current_skill, current_tier)

            if next_tier:
                costs = SkillMechanics.get_upgrade_cost(
                    self.current_skill, current_tier
                )
                can_afford = self._check_affordability(costs)

                up_btn = Button(
                    label=f"Upgrade {next_tier.title()}",
                    style=ButtonStyle.success if can_afford else ButtonStyle.secondary,
                    disabled=not can_afford,
                    emoji="⬆️",
                    row=1,
                )
                up_btn.callback = self.upgrade_callback
                self.add_item(up_btn)
            else:
                max_btn = Button(
                    label="Maxed Out",
                    style=ButtonStyle.primary,
                    disabled=True,
                    emoji="🌟",
                    row=1,
                )
                self.add_item(max_btn)

        close_btn = Button(label="Close", style=ButtonStyle.danger, row=1)
        close_btn.callback = self.close_callback
        self.add_item(close_btn)

        # --- ROW 2: ELEMENTAL RESONANCE ---
        if self.uber_data and all(
            self.uber_data.get(k, 0) >= 1
            for k in ("blessed_bismuth", "sparkling_sprig", "capricious_carp")
        ):
            resonance_btn = Button(
                label="Elemental Resonance",
                emoji="🌀",
                style=ButtonStyle.blurple,
                row=2,
            )
            resonance_btn.callback = self.resonance_callback
            self.add_item(resonance_btn)

    def _make_tab_callback(self, skill: str):
        """Creates a proper async callback for tabs (avoids lambda pitfalls)."""

        async def callback(interaction: Interaction):
            await self.switch_tab(interaction, skill)

        return callback

    async def switch_tab(self, interaction: Interaction, skill: str):
        if skill == self.current_skill:
            return await interaction.response.defer()

        # Create a completely fresh view instead of mutating this one
        new_view = GatherView(
            self.bot, self.user_id, self.server_id, initial_skill=skill
        )

        await interaction.response.defer()
        await new_view.refresh_state()

        await interaction.edit_original_response(
            embed=new_view.get_embed(), view=new_view
        )

        # Clean up old view
        self.stop()

    def get_embed(self) -> discord.Embed:
        info = SkillMechanics.get_skill_info(self.current_skill)

        if not self.skill_data:
            return discord.Embed(
                title="Error",
                description="Skill data not found.",
                color=discord.Color.red(),
            )

        current_tier = self.skill_data[2]
        tier_display = f"{info['emoji']} **{current_tier.title()} {info['tool_name']}**"

        # Build Resource List
        resources = SkillMechanics.map_db_row_to_resources(
            self.current_skill, self.skill_data
        )
        res_text = (
            "\n".join([f"**{name}:** {amt:,}" for name, amt in resources if amt > 0])
            or "No resources gathered."
        )

        desc = f"Current Tool: {tier_display}\n\n{res_text}"

        # Upgrade Costs
        next_tier = SkillMechanics.get_next_tier(self.current_skill, current_tier)
        if next_tier:
            costs = SkillMechanics.get_upgrade_cost(self.current_skill, current_tier)
            cost_parts = []

            # Map cost keys (res_1..4) to display names
            # We assume cost keys map to resources indices 0..3
            for i in range(1, 5):
                qty = costs.get(f"res_{i}", 0)
                if qty > 0:
                    # Look up name in config. resources[i-1][0] is internal name, [1] is display
                    res_name = info["resources"][i - 1][1]
                    cost_parts.append(f"{qty} {res_name}")

            if costs["gold"] > 0:
                cost_parts.append(f"{costs['gold']:,} GP")

            desc += f"\n\n**Next Upgrade:** {next_tier.title()}\n**Costs:** {', '.join(cost_parts)}"
        else:
            desc += "\n\n**Tool is Max Level!**"

        embed = discord.Embed(
            title=f"{info['display_name']} Station", description=desc, color=0x00FF00
        )
        embed.set_thumbnail(url=self.user_data[7])  # User PFP
        embed.set_image(url=info["image"])
        return embed

    def _check_affordability(self, costs) -> bool:
        if not costs:
            return False

        # Indices 3,4,5,6 in DB row are the first 4 resources used for upgrades
        res_held = [
            self.skill_data[3],
            self.skill_data[4],
            self.skill_data[5],
            self.skill_data[6],
        ]
        gold_held = self.user_data[6]

        if res_held[0] < costs["res_1"]:
            return False
        if res_held[1] < costs["res_2"]:
            return False
        if res_held[2] < costs["res_3"]:
            return False
        if res_held[3] < costs["res_4"]:
            return False
        if gold_held < costs["gold"]:
            return False

        return True

    async def upgrade_callback(self, interaction: Interaction):
        await interaction.response.defer()

        current_tier = self.skill_data[2]
        next_tier = SkillMechanics.get_next_tier(self.current_skill, current_tier)
        costs = SkillMechanics.get_upgrade_cost(self.current_skill, current_tier)

        if not costs or not next_tier:
            return

        # Execute Transaction
        cost_tuple = (
            costs["res_1"],
            costs["res_2"],
            costs["res_3"],
            costs["res_4"],
            costs["gold"],
        )

        if self.current_skill == "mining":
            await self.bot.database.skills.upgrade_pickaxe(
                self.user_id, self.server_id, next_tier, cost_tuple
            )
        elif self.current_skill == "woodcutting":
            await self.bot.database.skills.upgrade_axe(
                self.user_id, self.server_id, next_tier, cost_tuple
            )
        elif self.current_skill == "fishing":
            await self.bot.database.skills.upgrade_fishing_rod(
                self.user_id, self.server_id, next_tier, cost_tuple
            )

        # Refresh State
        await self.refresh_state()

        await interaction.followup.send(
            f"🎉 **Upgraded to {next_tier.title()}!**", ephemeral=True
        )
        await interaction.edit_original_response(embed=self.get_embed(), view=self)

    async def resonance_callback(self, interaction: Interaction):
        await interaction.response.defer()
        await self.bot.database.uber.consume_elemental_keys(
            self.user_id, self.server_id
        )
        self.bot.state_manager.set_active(self.user_id, "elemental_boss")
        self.stop()

        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        player = await load_player(self.user_id, user_row, self.bot.database)

        elemental_view = ElementalEncounterView(
            self.bot, player, self.user_id, self.server_id
        )
        await interaction.edit_original_response(
            embed=elemental_view.build_embed(), view=elemental_view
        )
        elemental_view.message = await interaction.original_response()

    async def close_callback(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
