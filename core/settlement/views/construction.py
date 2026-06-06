# core/settlement/views/construction.py
import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.images import SETTLEMENT_HUB
from core.settlement.constants import (
    BUILD_MESSAGES,
    BUILDING_INFO,
    CONSTRUCTION_COSTS,
    PROJECT_CONSTRUCTION_DT,
)
from core.settlement.turn_engine import construction_dt_cost
from core.settlement.views.research import RESEARCHABLE_BUILDINGS

from .base import SettlementBaseView


class BuildConstructionView(SettlementBaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        plot_index: int,
        parent_view,
        uber_prog,
        researched: set | None = None,
        plot_bonus_type: str | None = None,
        return_to_detail=None,
    ):
        super().__init__(bot, user_id)
        self.plot_index = plot_index
        self.parent = parent_view
        self.uber_prog = uber_prog
        self.researched: set = researched or set()
        self.plot_bonus_type = plot_bonus_type
        self.return_to = return_to_detail  # PlotDetailView to return to after build
        self._processing = False

        self.setup_select()

    # -------------------------------------------------------------------------
    # Plot-discount helper
    # -------------------------------------------------------------------------

    def _apply_discounts(self, cost: dict) -> dict:
        """Return a copy of *cost* with plot-bonus discounts applied."""
        c = dict(cost)
        if self.plot_bonus_type == "gold_vein":
            c["gold"] = int(c.get("gold", 0) * 0.65)
        if self.plot_bonus_type == "ancient_foundation":
            c["timber"] = int(c.get("timber", 0) * 0.70)
            c["stone"]  = int(c.get("stone",  0) * 0.70)
        return c

    # -------------------------------------------------------------------------
    # Embed
    # -------------------------------------------------------------------------

    def build_embed(self):
        discount_note = ""
        if self.plot_bonus_type == "gold_vein":
            discount_note = "\n💛 **Gold Vein:** Construction gold cost reduced by 35%."
        elif self.plot_bonus_type == "ancient_foundation":
            discount_note = "\n🏺 **Ancient Foundation:** Timber & Stone cost reduced by 30%."

        embed = discord.Embed(
            title="🏗️ Construction Site",
            description=(
                f"Select a blueprint to begin construction.{discount_note}\n\n"
                "__**Available Blueprints**__"
            ),
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=SETTLEMENT_HUB)
        existing_types = {b.building_type for b in self.parent.settlement.buildings}

        for b_type, info in BUILDING_INFO.items():
            if b_type in existing_types:
                continue
            if not self._is_available(b_type):
                continue

            raw_cost = CONSTRUCTION_COSTS[b_type]
            cost = self._apply_discounts(raw_cost)

            cost_str = f"💰 {cost.get('gold', 0):,}"
            if cost.get("timber"):
                cost_str += f" | 🪵 {cost['timber']:,}"
            if cost.get("stone"):
                cost_str += f" | 🪨 {cost['stone']:,}"
            dt = construction_dt_cost(b_type)
            cost_str += f" | ⏭️ {dt} DT"

            embed.add_field(
                name=f"✅ {b_type.replace('_', ' ').title()}",
                value=f"{info}\n*Cost: {cost_str}*",
                inline=False,
            )

        return embed

    def _is_available(self, b_type: str) -> bool:
        """True if the building type can currently be built (blueprint checks)."""
        if (
            (b_type == "celestial_shrine"  and not self.uber_prog.get("celestial_blueprint_unlocked"))
            or (b_type == "infernal_shrine" and not self.uber_prog.get("infernal_blueprint_unlocked"))
            or (b_type == "void_shrine"     and not self.uber_prog.get("void_blueprint_unlocked"))
            or (b_type == "twin_shrine"     and not self.uber_prog.get("gemini_blueprint_unlocked"))
            or (b_type == "corruption_shrine" and not self.uber_prog.get("corruption_blueprint_unlocked"))
        ):
            return False
        if b_type in RESEARCHABLE_BUILDINGS and b_type not in self.researched:
            return False
        return True

    # -------------------------------------------------------------------------
    # Select
    # -------------------------------------------------------------------------

    def setup_select(self):
        self.clear_items()

        existing_types = {b.building_type for b in self.parent.settlement.buildings}
        options: list[SelectOption] = []

        for key, raw_cost in CONSTRUCTION_COSTS.items():
            if key in existing_types:
                continue
            if not self._is_available(key):
                continue

            cost = self._apply_discounts(raw_cost)
            lbl = key.replace("_", " ").title()
            desc = f"Cost: {cost.get('gold', 0):,}g"
            if cost.get("timber"):
                desc += f", {cost['timber']:,} Wood"
            if cost.get("stone"):
                desc += f", {cost['stone']:,} Stone"

            options.append(SelectOption(label=lbl, value=key, description=desc[:100]))

        if not options:
            self.add_item(
                ui.Button(
                    label="No New Blueprints Available",
                    style=ButtonStyle.gray,
                    disabled=True,
                )
            )
        else:
            select = ui.Select(placeholder="Select Blueprint...", options=options)
            select.callback = self.on_select
            self.add_item(select)

        cancel = ui.Button(label="Cancel", style=ButtonStyle.danger)
        cancel.callback = self.cancel
        self.add_item(cancel)

    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------

    async def on_select(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        b_type = interaction.data["values"][0]
        raw_cost = CONSTRUCTION_COSTS[b_type]
        cost = self._apply_discounts(raw_cost)

        # Resource check
        u_gold   = await self.bot.database.users.get_gold(self.user_id)
        u_timber = self.parent.settlement.timber
        u_stone  = self.parent.settlement.stone

        if (
            u_gold   < cost.get("gold",   0)
            or u_timber < cost.get("timber", 0)
            or u_stone  < cost.get("stone",  0)
        ):
            self._processing = False
            return await interaction.response.send_message(
                "Insufficient resources!", ephemeral=True
            )

        await interaction.response.defer()

        # === Queue as Development Turn project ===
        # Determine active event effects (construction DT halved, etc.)
        active_events = await self.bot.database.settlement.get_active_events(
            self.user_id, self.parent.server_id
        )
        event_effects: dict = {}
        from core.settlement.constants import SETTLEMENT_EVENTS
        for ev in active_events:
            if ev["event_type"] == "ongoing":
                ev_def = SETTLEMENT_EVENTS.get(ev["event_key"], {})
                event_effects.update(ev_def.get("effects", {}))

        dt_required = construction_dt_cost(b_type, event_effects)

        # Deduct resources immediately (reserved for the project)
        changes = {
            "timber": -cost.get("timber", 0),
            "stone":  -cost.get("stone",  0),
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -cost.get("gold", 0))

        # Create the project
        await self.bot.database.settlement.upsert_project(
            user_id=self.user_id,
            server_id=self.parent.server_id,
            project_type="construction",
            target_id=None,
            required_turns=dt_required,
            data={"building_type": b_type, "plot_index": self.plot_index},
        )

        # Show confirmation
        embed = discord.Embed(
            title="🏗️ Construction Queued!",
            description=(
                f"**{b_type.replace('_', ' ').title()}** will be built on Plot {self.plot_index} "
                f"after **{dt_required} Development Turn(s)**.\n\n"
                f"Resources have been reserved. Click **Next Turn** on the dashboard to advance construction."
            ),
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=SETTLEMENT_HUB)
        await interaction.edit_original_response(embed=embed, view=discord.ui.View())

        import asyncio
        await asyncio.sleep(2)

        # Return to plot detail or dashboard
        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )

        if self.return_to is not None:
            self.return_to._build_buttons()
            await interaction.edit_original_response(
                content=None, embed=self.return_to.build_embed(), view=self.return_to
            )
        else:
            self.parent._rebuild_ui()
            await interaction.edit_original_response(
                embed=self.parent.build_embed(), view=self.parent
            )

        self.stop()

    async def cancel(self, interaction: Interaction):
        if self.return_to is not None:
            await interaction.response.edit_message(
                content=None,
                embed=self.return_to.build_embed(),
                view=self.return_to,
            )
        else:
            self.parent._rebuild_ui()
            await interaction.response.edit_message(
                embed=self.parent.build_embed(), view=self.parent
            )
        self.stop()
