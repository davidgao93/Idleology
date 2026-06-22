"""
core/settlement/views/nursery_foundry.py
Detail views for the Nursery and Idlem Foundry buildings.
Both produce their output through Development Turns (Next Turn button).
Each "activation" queues a single-turn project that produces output on completion.
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, ui

from core.images import SETTLEMENT_BUILDINGS, YUNA_PORTRAIT, YUNA_THUMBNAIL
from core.npc_voices import get_quip
from core.settlement.constants import (
    IDLEM_PER_TURN_BASE,
    WORKERS_PER_TURN_BASE,
)
from core.settlement.views.base import SettlementBaseView


class NurseryView(SettlementBaseView):
    """
    Detail view for the Nursery building.
    Each "Produce Workers" click queues a 1-turn project.
    On Next Turn, the project completes and adds workers.
    """

    def __init__(self, bot, user_id: str, server_id: str, building, parent_view):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.building = building
        self.parent = parent_view
        self._processing = False
        self._build_ui()

    def _build_ui(self) -> None:
        self.clear_items()

        produce_btn = ui.Button(
            label="Queue Worker Production",
            style=ButtonStyle.success,
            emoji="👶",
            row=0,
        )
        produce_btn.callback = self._on_queue
        self.add_item(produce_btn)

        back_btn = ui.Button(
            label="Back",
            style=ButtonStyle.secondary,
            emoji="⬅️",
            row=1,
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def _workers_per_turn(self) -> float:
        """Worker output per turn, scaling with Nursery tier and worker assignment."""
        tier = self.building.tier
        workers = max(1, self.building.workers_assigned)
        base = WORKERS_PER_TURN_BASE
        return base * tier * (1 + workers / 500)

    def build_embed(self, projects: list | None = None) -> discord.Embed:
        embed = discord.Embed(
            title="👶 Nursery",
            description=(
                f"*{get_quip('nursery')}*\n\n"
                "The Nursery produces new workers for your settlement "
                "through Development Turns. Each queued project completes "
                "in **1 turn**, adding workers to your ideology.\n\n"
                f"**Output per turn:** ~{self._workers_per_turn():.1f} workers\n"
                f"**Tier:** {self.building.tier} | "
                f"**Workers assigned:** {self.building.workers_assigned:,}"
            ),
            color=discord.Color.green(),
        )
        embed.set_author(name="Master Tamer Yuna", icon_url=YUNA_PORTRAIT)
        embed.set_thumbnail(url=YUNA_THUMBNAIL)

        if projects:
            nursery_proj = [p for p in projects if p["project_type"] == "nursery"]
            if nursery_proj:
                embed.add_field(
                    name="🏗️ Production Queue",
                    value=f"{len(nursery_proj)} batch(es) queued — advance turns to complete.",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🏗️ Production Queue",
                    value="No batches queued. Click **Queue Worker Production** to start one.",
                    inline=False,
                )

        return embed

    async def _on_queue(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            workers_this_turn = self._workers_per_turn()

            await self.bot.database.settlement.upsert_project(
                user_id=self.user_id,
                server_id=self.server_id,
                project_type="nursery",
                target_id=None,
                required_turns=1,
                data={"workers_per_turn": workers_this_turn},
            )

            projects = await self.bot.database.settlement.get_projects(
                self.user_id, self.server_id
            )
            embed = self.build_embed(projects=projects)
            embed.add_field(
                name="✅ Queued",
                value="Worker production batch queued! Advance **1 Development Turn** to collect.",
                inline=False,
            )
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            self.bot.logger.error(f"_on_queue exception: {e}", exc_info=True)
            raise
        finally:
            self._processing = False

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.parent._rebuild_ui()
        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


class IdlemFoundryView(SettlementBaseView):
    """
    Detail view for the Idlem Foundry building.
    Each "Produce Idlem" click queues a 1-turn project.
    On Next Turn, the project completes and grants Idlem.
    """

    def __init__(self, bot, user_id: str, server_id: str, building, parent_view):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.building = building
        self.parent = parent_view
        self._processing = False
        self._build_ui()

    def _build_ui(self) -> None:
        self.clear_items()

        produce_btn = ui.Button(
            label="Queue Idlem Production",
            style=ButtonStyle.blurple,
            emoji="⚗️",
            row=0,
        )
        produce_btn.callback = self._on_queue
        self.add_item(produce_btn)

        back_btn = ui.Button(
            label="Back",
            style=ButtonStyle.secondary,
            emoji="⬅️",
            row=1,
        )
        back_btn.callback = self._on_back
        self.add_item(back_btn)

    def _idlem_per_turn(self) -> float:
        """Base Idlem per turn (1–2 range, scaled by tier). Variance applied on completion."""
        tier = self.building.tier
        base = IDLEM_PER_TURN_BASE
        return (
            base * tier
        )  # stored as base; actual grant has +0/+1 variance on completion

    def build_embed(
        self, projects: list | None = None, idlem: int = 0
    ) -> discord.Embed:
        embed = discord.Embed(
            title="⚗️ Idlem Foundry",
            description=(
                "The Idlem Foundry distills the settlement's ambient energy "
                "into **Idlem** — the scarce resource powering the Black Market "
                "passive tree.\n\n"
                f"**Output per turn:** ~{self._idlem_per_turn():.1f} Idlem\n"
                f"**Tier:** {self.building.tier} | "
                f"**Your Idlem:** {idlem:,}"
            ),
            color=discord.Color.purple(),
        )
        embed.set_thumbnail(
            url=SETTLEMENT_BUILDINGS.get(
                "idlem_foundry", SETTLEMENT_BUILDINGS["foundry"]
            )
        )

        if projects:
            foundry_proj = [p for p in projects if p["project_type"] == "foundry_idlem"]
            if foundry_proj:
                embed.add_field(
                    name="🏗️ Production Queue",
                    value=f"{len(foundry_proj)} batch(es) queued — advance turns to collect.",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="🏗️ Production Queue",
                    value="No batches queued. Click **Queue Idlem Production** to start one.",
                    inline=False,
                )

        return embed

    async def _on_queue(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            idlem_this_turn = self._idlem_per_turn()

            await self.bot.database.settlement.upsert_project(
                user_id=self.user_id,
                server_id=self.server_id,
                project_type="foundry_idlem",
                target_id=None,
                required_turns=1,
                data={"idlem_per_turn": idlem_this_turn},
            )

            zeal_data = await self.bot.database.settlement.get_zeal_data(self.user_id, self.server_id)
            projects = await self.bot.database.settlement.get_projects(
                self.user_id, self.server_id
            )
            embed = self.build_embed(projects=projects, idlem=zeal_data.get("idlem", 0))
            embed.add_field(
                name="✅ Queued",
                value="Idlem production batch queued! Advance **1 Development Turn** to collect.",
                inline=False,
            )
            await interaction.edit_original_response(embed=embed, view=self)
        finally:
            self._processing = False

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.parent._rebuild_ui()
        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
