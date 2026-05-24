from discord import Interaction, app_commands
from discord.ext import commands

from core.hatchery.views import HatcheryView
from core.settlement.models import Plot
from core.settlement.views import SettlementDashboardView


class SettlementCog(commands.Cog, name="settlement"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="settlement", description="Manage your ideology's settlement."
    )
    async def settlement(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Standard Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        if existing_user["level"] < 50:
            await interaction.response.send_message(
                "Settlements can only be founded by those who have proven themselves at **Level 50**.",
                ephemeral=True,
            )
            return

        self.bot.state_manager.set_active(user_id, "settlement")

        # 2. Fetch Data
        settlement = await self.bot.database.settlement.get_settlement(
            user_id, server_id
        )
        ideology = existing_user["ideology"]

        # 3. Follower / Worker Validation
        # If player lost followers (e.g. raid/event), we must unassign workers to match cap.
        total_followers = await self.bot.database.social.get_follower_count(ideology)
        total_assigned = sum(b.workers_assigned for b in settlement.buildings)

        if total_assigned > total_followers:
            # Simple logic: Remove from buildings in reverse order until valid
            diff = total_assigned - total_followers
            for building in reversed(settlement.buildings):
                if diff <= 0:
                    break
                to_remove = min(building.workers_assigned, diff)
                building.workers_assigned -= to_remove
                diff -= to_remove
                # Commit fix immediately
                await self.bot.database.settlement.assign_workers(
                    building.id, building.workers_assigned
                )

            await interaction.channel.send(
                f"⚠️ **Workforce Shortage!** {total_assigned - total_followers} workers have abandoned their posts.",
                delete_after=10,
            )

        # 4. Load plots (ensure rows exist first)
        await self.bot.database.plots.ensure_plots(user_id, server_id)
        plot_rows = await self.bot.database.plots.get_plots(user_id, server_id)
        plots = [
            Plot(plot_index=r[0], is_developed=bool(r[1]), bonus_type=r[2])
            for r in plot_rows
        ]

        # 5. Launch Dashboard
        view = SettlementDashboardView(
            self.bot, user_id, server_id, settlement, total_followers, plots=plots
        )
        embed = view.build_embed()

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


    @app_commands.command(
        name="hatchery",
        description="Open your settlement's Hatchery to incubate monster eggs.",
    )
    async def hatchery(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        settlement = await self.bot.database.settlement.get_settlement(user_id, server_id)
        hatchery_building = next(
            (b for b in settlement.buildings if b.building_type == "hatchery"), None
        )

        if hatchery_building is None:
            return await interaction.response.send_message(
                "You don't have a **Hatchery** built yet. "
                "Construct one in your `/settlement` first!",
                ephemeral=True,
            )

        self.bot.state_manager.set_active(user_id, "settlement")
        view = HatcheryView(self.bot, user_id, server_id, hatchery_building, parent_view=None)
        await view._load()
        view._rebuild_buttons()

        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(SettlementCog(bot))
