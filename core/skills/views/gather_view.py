import datetime

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView
from core.combat.views.views_elemental import ElementalEncounterView
from core.images import MASTERY_FISHING, MASTERY_MINING, MASTERY_WOODCUTTING
from core.items.factory import load_player
from core.skills.mastery import get_tool_cost_reduction
from core.skills.mechanics import SkillMechanics
from core.skills.views.mastery_view import ArtisanMasteryHubView


class GatherView(BaseView):
    def __init__(
        self, bot, user_id: str, server_id: str, initial_skill: str = "mining"
    ):
        super().__init__(bot, user_id, server_id)
        self.current_skill = initial_skill

        # Re-entry guard — prevents concurrent button callbacks
        self._processing = False

        # Data cache
        self.user_data = None
        self.skill_data = None
        self.refined_data = None  # refined amounts parallel to skill resources
        self.mastery_row = None

        # Familiarization gate cache (populated in refresh_state)
        self.fam_end_iso: str | None = None
        self.fam_momentum: int = 0

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
        refined_cols = SkillMechanics.get_refined_columns(self.current_skill)
        if refined_cols:
            self.refined_data = await self.bot.database.skills.get_multi_resource(
                self.user_id, self.server_id, self.current_skill, refined_cols
            )
        else:
            self.refined_data = None
        self.mastery_row = await self.bot.database.skills.get_mastery(
            self.user_id, self.server_id
        )
        # Familiarization gate for the current tool tier
        (
            self.fam_end_iso,
            self.fam_momentum,
        ) = await self.bot.database.skills.get_familiarization_state(
            self.user_id, self.server_id, self.current_skill
        )
        self.setup_ui()

    async def refresh_and_resume(
        self, interaction: Interaction, session_summary: str = ""
    ):
        """Called by child activity views when the player returns to the hub."""
        self._processing = False
        await self.refresh_state()
        embed = self.get_embed()
        if session_summary:
            embed.description = session_summary + "\n\n" + (embed.description or "")
        await interaction.response.edit_message(embed=embed, view=self)

    def _get_tool_cost_reduction(self) -> float:
        if not self.mastery_row:
            return 0.0
        return get_tool_cost_reduction(self.mastery_row, self.current_skill)

    def _gate_remaining(self) -> int:
        """Seconds remaining on the familiarization gate (0 = no gate / lifted)."""
        return SkillMechanics.get_familiarization_remaining_seconds(
            self.fam_end_iso, self.fam_momentum
        )

    def setup_ui(self):
        self.clear_items()

        # --- ROW 0: SKILL TABS ---
        for s in ("mining", "woodcutting", "fishing"):
            info = SkillMechanics.get_skill_info(s)
            is_active = s == self.current_skill
            btn = Button(
                label=info["display_name"],
                emoji=info["emoji"],
                style=ButtonStyle.primary if is_active else ButtonStyle.secondary,
                row=0,
            )
            btn.callback = self._make_tab_callback(s)
            self.add_item(btn)

        # --- ROW 1: ACTIVITY LAUNCH BUTTON (tab-specific) ---
        if self.current_skill == "mining":
            delve_btn = Button(
                label="Deep Delve",
                emoji="⛏️",
                style=ButtonStyle.secondary,
                row=1,
            )
            delve_btn.callback = self.go_delve_callback
            self.add_item(delve_btn)
        elif self.current_skill == "fishing":
            fish_btn = Button(
                label="Go Fishing",
                emoji="🎣",
                style=ButtonStyle.secondary,
                row=1,
            )
            fish_btn.callback = self.go_fishing_callback
            self.add_item(fish_btn)
        elif self.current_skill == "woodcutting":
            chop_btn = Button(
                label="Go Chopping",
                emoji="🪓",
                style=ButtonStyle.secondary,
                row=1,
            )
            chop_btn.callback = self.go_chopping_callback
            self.add_item(chop_btn)

        # --- ROW 2: ARTISAN MASTERY + ELEMENTAL RESONANCE ---
        mastery_btn = Button(
            label="Artisan Mastery",
            emoji="🛠️",
            style=ButtonStyle.success,
            row=2,
        )
        mastery_btn.callback = self.mastery_callback
        self.add_item(mastery_btn)

        if self.mastery_row and all(
            self.mastery_row.get(k, 0) >= 1
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

        # --- ROW 3: UPGRADE / MAXED + CLOSE ---
        if self.skill_data:
            current_tier = SkillMechanics.get_tool_tier(
                self.current_skill, self.skill_data
            )
            next_tier = SkillMechanics.get_next_tier(self.current_skill, current_tier)

            if next_tier:
                costs = SkillMechanics.get_upgrade_cost(
                    self.current_skill, current_tier, self._get_tool_cost_reduction()
                )
                can_afford = self._check_affordability(costs)
                gate_secs = self._gate_remaining()

                if gate_secs > 0:
                    h, m = divmod(gate_secs // 60, 60)
                    label = f"Familiarizing… ({h}h {m}m)"
                    up_btn = Button(
                        label=label,
                        style=ButtonStyle.secondary,
                        disabled=True,
                        emoji="⏳",
                        row=3,
                    )
                else:
                    up_btn = Button(
                        label=f"Upgrade {next_tier.title()}",
                        style=(
                            ButtonStyle.success if can_afford else ButtonStyle.secondary
                        ),
                        disabled=not can_afford,
                        emoji="⬆️",
                        row=3,
                    )
                    up_btn.callback = self.upgrade_callback
                self.add_item(up_btn)
            else:
                max_btn = Button(
                    label="Maxed Out",
                    style=ButtonStyle.primary,
                    disabled=True,
                    emoji="🌟",
                    row=3,
                )
                self.add_item(max_btn)

        close_btn = Button(label="Close", style=ButtonStyle.secondary, row=3)
        close_btn.callback = self.close_callback
        self.add_item(close_btn)

    def _make_tab_callback(self, skill: str):
        async def callback(interaction: Interaction):
            await self.switch_tab(interaction, skill)

        return callback

    async def switch_tab(self, interaction: Interaction, skill: str):
        if skill == self.current_skill:
            return await interaction.response.defer()

        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        new_view = GatherView(
            self.bot, self.user_id, self.server_id, initial_skill=skill
        )
        await interaction.response.defer()
        await new_view.refresh_state()
        await interaction.edit_original_response(
            embed=new_view.get_embed(), view=new_view
        )
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

        resources = SkillMechanics.map_db_row_to_resources(
            self.current_skill, self.skill_data
        )
        refined_names = SkillMechanics.get_refined_names(self.current_skill)
        ref = self.refined_data or ()
        res_lines = []
        for i, (raw_name, raw_amt) in enumerate(resources):
            ref_amt = ref[i] if i < len(ref) else 0
            ref_name = refined_names[i] if i < len(refined_names) else ""
            if raw_amt > 0 and ref_amt > 0:
                res_lines.append(
                    f"**{raw_name}:** {raw_amt:,}  ·  **{ref_name}:** {ref_amt:,}"
                )
            elif raw_amt > 0:
                res_lines.append(f"**{raw_name}:** {raw_amt:,}")
            elif ref_amt > 0:
                res_lines.append(f"**{ref_name}:** {ref_amt:,}")
        res_text = "\n".join(res_lines) or "No resources gathered."

        artisan_pts = 0
        if self.mastery_row:
            artisan_pts = self.mastery_row.get(f"{self.current_skill}_points", 0) or 0

        desc = f"Current Tool: {tier_display}\n🛠️ **Artisan Points:** {artisan_pts}\n\n{res_text}"

        # Upgrade costs or max level
        next_tier = SkillMechanics.get_next_tier(self.current_skill, current_tier)
        if next_tier:
            costs = SkillMechanics.get_upgrade_cost(
                self.current_skill, current_tier, self._get_tool_cost_reduction()
            )
            ref = self.refined_data or ()
            cost_parts = []
            for i in range(1, 5):
                qty = costs.get(f"res_{i}", 0)
                if qty > 0:
                    raw_name = info["resources"][i - 1][1]
                    raw_held = self.skill_data[i + 2] if self.skill_data else 0
                    ref_held = ref[i - 1] if i - 1 < len(ref) else 0
                    total_held = raw_held + ref_held
                    cost_parts.append(f"{qty:,} {raw_name} (have: {total_held:,})")
            if costs["gold"] > 0:
                cost_parts.append(f"{costs['gold']:,} GP")
            desc += f"\n\n**Next Upgrade:** {next_tier.title()}\n**Costs:** {', '.join(cost_parts)}\n*Raw and refined materials are both accepted.*"

            # Familiarization gate status
            gate_secs = self._gate_remaining()
            if gate_secs > 0:
                h, m = divmod(gate_secs // 60, 60)
                gate_line = f"\n⏳ **Familiarization:** {h}h {m}m remaining"
                if self.fam_momentum > 0:
                    gate_line += f" *(−{self.fam_momentum} min from Momentum)*"
                gate_line += "\n*Tip: Participating actively in the mini-game earns Momentum, which reduces your Familiarization time.*"
                desc += gate_line
            elif self.fam_momentum > 0:
                desc += "\n✅ You feel familiarized with the tool!"
        else:
            desc += "\n\n**Tool is Max Level!**"

        embed = discord.Embed(
            title=f"{info['display_name']} Station", description=desc, color=0x00FF00
        )

        if self.current_skill == "mining":
            thumb_url = MASTERY_MINING
        elif self.current_skill == "fishing":
            thumb_url = MASTERY_FISHING
        elif self.current_skill == "woodcutting":
            thumb_url = MASTERY_WOODCUTTING
        else:
            thumb_url = info.get("image")
        embed.set_thumbnail(url=thumb_url)
        return embed

    def _check_affordability(self, costs) -> bool:
        if not costs:
            return False
        ref = self.refined_data or (0, 0, 0, 0, 0)
        res_cols = [
            col
            for col, _ in SkillMechanics.SKILL_CONFIG.get(self.current_skill, {}).get(
                "resources", []
            )
        ][:4]
        res_held = [self.skill_data[res_cols[i]] + ref[i] for i in range(len(res_cols))]
        gold_held = self.user_data["gold"]
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
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        current_tier = self.skill_data[2]
        next_tier = SkillMechanics.get_next_tier(self.current_skill, current_tier)
        costs = SkillMechanics.get_upgrade_cost(
            self.current_skill, current_tier, self._get_tool_cost_reduction()
        )

        if not costs or not next_tier:
            self._processing = False
            return

        # Gate check (double-safety; button should be disabled but guard anyway)
        if self._gate_remaining() > 0:
            self._processing = False
            return

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

        # Award 1 artisan point
        await self.bot.database.skills.add_mastery_points(
            self.user_id, self.server_id, self.current_skill, 1
        )

        # Start familiarization gate for the new tier
        fam_hours = SkillMechanics.get_familiarization_hours(
            self.current_skill, next_tier
        )
        if fam_hours > 0:
            end = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                hours=fam_hours
            )
            await self.bot.database.skills.set_familiarization_end(
                self.user_id, self.server_id, self.current_skill, end.isoformat()
            )

        await self.refresh_state()
        embed = self.get_embed()
        embed.description = f"✅ **Upgraded to {next_tier.title()}!**\n\n" + (
            embed.description or ""
        )
        await interaction.edit_original_response(embed=embed, view=self)
        self._processing = False

    # ------------------------------------------------------------------
    # Activity Launch Callbacks
    # ------------------------------------------------------------------

    async def go_fishing_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        from core.skills.fishing_view import FishingView

        view = FishingView(
            self.bot,
            self.user_id,
            self.server_id,
            interaction.user.mention,
            parent_gather_view=self,
        )
        await view.refresh_data()
        view.setup_ui()
        await interaction.edit_original_response(embed=view.get_embed(), view=view)
        view.message = await interaction.original_response()

    async def go_chopping_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        from core.skills.forestry_view import ForestryView

        view = ForestryView(
            self.bot, self.user_id, self.server_id, parent_gather_view=self
        )
        await view.refresh_data()
        view.setup_ui()
        await interaction.edit_original_response(embed=view.get_embed(), view=view)
        view.message = await interaction.original_response()

    async def go_delve_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        from core.delve.delve_views import DelveEntryView, DelveView
        from core.delve.mechanics import DelveMechanics, DelveState

        mining_data = await self.bot.database.skills.get_data(
            self.user_id, self.server_id, "mining"
        )
        pickaxe = mining_data["pickaxe_tier"] if mining_data else "iron"
        delve_stats = await self.bot.database.delve.get_profile(
            self.user_id, self.server_id
        )
        entry_cost = DelveMechanics.get_entry_cost(delve_stats["fuel_lvl"])

        if self.user_data["gold"] < entry_cost:
            self._processing = False
            await interaction.followup.send(
                f"You need **{entry_cost:,} Gold** to purchase a mining permit.",
                ephemeral=True,
            )
            return

        gather_parent = self

        async def start_delve(inter: Interaction):
            state = DelveState(
                max_fuel=DelveMechanics.get_max_fuel(delve_stats["fuel_lvl"]),
                current_fuel=DelveMechanics.get_max_fuel(delve_stats["fuel_lvl"]),
                pickaxe_tier=pickaxe,
            )
            view = DelveView(
                self.bot,
                self.user_id,
                self.server_id,
                state,
                delve_stats,
                parent_gather_view=gather_parent,
            )
            embed = view.build_embed("Systems online. Permit verified.")
            await inter.edit_original_response(embed=embed, view=view)
            view.message = await inter.original_response()

        entry_view = DelveEntryView(
            self.bot,
            self.user_id,
            self.server_id,
            entry_cost,
            start_delve,
            delve_stats,
            parent_gather_view=gather_parent,
        )
        await interaction.edit_original_response(embed=entry_view.build_embed(), view=entry_view)
        entry_view.message = await interaction.original_response()

    # ------------------------------------------------------------------
    # Other Callbacks
    # ------------------------------------------------------------------

    async def resonance_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        await self.bot.database.skills.consume_elemental_keys(
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
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def mastery_callback(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        hub = ArtisanMasteryHubView(
            self.bot, self.user_id, self.server_id, parent_view=self
        )
        await hub.refresh()
        await interaction.edit_original_response(
            embed=hub.get_embed() if hasattr(hub, "get_embed") else None, view=hub
        )
        hub.message = await interaction.original_response()
