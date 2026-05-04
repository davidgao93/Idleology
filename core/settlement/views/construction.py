# core/settlement/views/construction.py
import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.images import SETTLEMENT_HUB
from core.settlement.constants import BUILD_MESSAGES, BUILDING_INFO, CONSTRUCTION_COSTS

from .base import SettlementBaseView


class BuildConstructionView(SettlementBaseView):
    def __init__(self, bot, user_id, slot_index, parent_view, uber_prog):
        super().__init__(bot, user_id)
        self.slot_index = slot_index
        self.parent = parent_view
        self.uber_prog = uber_prog

        self.setup_select()

    def build_embed(self):
        embed = discord.Embed(
            title="🏗️ Construction Site",
            description="Select a blueprint to begin construction.\n\n__**Available Blueprints**__",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=SETTLEMENT_HUB)
        existing_types = {b.building_type for b in self.parent.settlement.buildings}

        for b_type, info in BUILDING_INFO.items():
            if b_type in existing_types:
                continue

            # Skip locked uber buildings
            if (
                (
                    b_type == "celestial_shrine"
                    and self.uber_prog.get("celestial_blueprint_unlocked", 0) == 0
                )
                or (
                    b_type == "infernal_forge"
                    and self.uber_prog.get("infernal_blueprint_unlocked", 0) == 0
                )
                or (
                    b_type == "void_sanctum"
                    and self.uber_prog.get("void_blueprint_unlocked", 0) == 0
                )
                or (
                    b_type == "twin_shrine"
                    and self.uber_prog.get("gemini_blueprint_unlocked", 0) == 0
                )
            ):
                continue

            cost = CONSTRUCTION_COSTS[b_type]

            cost_str = f"💰 {cost.get('gold', 0):,}"
            if cost.get("timber"):
                cost_str += f" | 🪵 {cost['timber']}"
            if cost.get("stone"):
                cost_str += f" | 🪨 {cost['stone']}"

            status_icon = "✅"
            embed.add_field(
                name=f"{status_icon} {b_type.replace('_', ' ').title()}",
                value=f"{info}\n*Cost: {cost_str}*",
                inline=False,
            )

        return embed

    async def on_timeout(self):
        try:
            expired_embed = discord.Embed(
                title="Construction Menu Expired",
                description="This construction selection session has timed out.\n\n"
                "Open the empty slot again from the settlement dashboard to build.",
                color=discord.Color.dark_grey(),
            )
            await self.parent.message.edit(embed=expired_embed, view=None)
        except:
            pass
        finally:
            self.stop()

    def setup_select(self):
        self.clear_items()

        existing_types = {b.building_type for b in self.parent.settlement.buildings}
        options = []

        for key, cost in CONSTRUCTION_COSTS.items():
            if key in existing_types:
                continue

            # Skip locked uber buildings
            if (
                (
                    key == "celestial_shrine"
                    and self.uber_prog.get("celestial_blueprint_unlocked", 0) == 0
                )
                or (
                    key == "infernal_forge"
                    and self.uber_prog.get("infernal_blueprint_unlocked", 0) == 0
                )
                or (
                    key == "void_sanctum"
                    and self.uber_prog.get("void_blueprint_unlocked", 0) == 0
                )
                or (
                    key == "twin_shrine"
                    and self.uber_prog.get("gemini_blueprint_unlocked", 0) == 0
                )
            ):
                continue

            lbl = key.replace("_", " ").title()
            desc = f"Cost: {cost.get('gold',0)}g"
            if cost.get("timber"):
                desc += f", {cost['timber']} Wood"
            if cost.get("stone"):
                desc += f", {cost['stone']} Stone"

            options.append(SelectOption(label=lbl, value=key, description=desc))

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

    async def on_select(self, interaction: Interaction):
        b_type = interaction.data["values"][0]
        cost = CONSTRUCTION_COSTS[b_type]

        used_slots = len(self.parent.settlement.buildings)
        max_slots = self.parent.settlement.building_slots

        if used_slots >= max_slots:
            return await interaction.response.send_message(
                "No building slots remaining! Upgrade your Town Hall to build more.",
                ephemeral=True,
            )

        # Check Funds
        u_gold = await self.bot.database.users.get_gold(self.user_id)
        u_timber = self.parent.settlement.timber
        u_stone = self.parent.settlement.stone

        if (
            u_gold < cost.get("gold", 0)
            or u_timber < cost.get("timber", 0)
            or u_stone < cost.get("stone", 0)
        ):
            return await interaction.response.send_message(
                "Insufficient resources!", ephemeral=True
            )

        await interaction.response.defer()

        # === EMBED-BASED CONSTRUCTION ANIMATION ===
        import asyncio
        import random

        chosen_messages = random.choices(
            population=[msg for msg, _ in BUILD_MESSAGES],
            weights=[w for _, w in BUILD_MESSAGES],
            k=3,
        )

        progress_embed = discord.Embed(
            title="🏗️ Construction in Progress",
            color=discord.Color.orange(),
        )
        progress_embed.set_thumbnail(url=SETTLEMENT_HUB)

        for i, msg in enumerate(chosen_messages, 1):
            progress_embed.description = f"**Step {i}/3:** {msg}"
            await interaction.edit_original_response(embed=progress_embed)
            if i < 3:
                await asyncio.sleep(2)

        # Final completion
        progress_embed.title = "✅ Construction Complete"
        progress_embed.description = (
            "**Building complete!** The new structure is now operational."
        )
        progress_embed.color = discord.Color.green()
        await interaction.edit_original_response(embed=progress_embed)
        await asyncio.sleep(1.5)

        # === Actual building logic ===
        changes = {
            "timber": -cost.get("timber", 0),
            "stone": -cost.get("stone", 0),
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -cost.get("gold", 0))

        await self.bot.database.settlement.build_structure(
            self.user_id, self.parent.server_id, b_type, self.slot_index
        )

        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )
        self.parent.update_grid()

        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()

    async def cancel(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
