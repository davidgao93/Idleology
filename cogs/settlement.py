from discord import Interaction, app_commands
from discord.ext import commands

from core.first_use import TutorialGateView
from core.hatchery.views import HatcheryView
from core.settlement.models import Plot
from core.settlement.views import BlackMarketView, SettlementDashboardView


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

        if existing_user["level"] < 10:
            await interaction.response.send_message(
                "Settlements can only be founded by those who have reached **Level 10**.",
                ephemeral=True,
            )
            return

        self.bot.state_manager.set_active(user_id, "settlement")

        async def _build():
            settlement = await self.bot.database.settlement.get_settlement(
                user_id, server_id
            )
            ideology = existing_user["ideology"]
            total_followers = await self.bot.database.social.get_follower_count(
                ideology
            )
            total_assigned = sum(b.workers_assigned for b in settlement.buildings)
            if total_assigned > total_followers:
                diff = total_assigned - total_followers
                for building in reversed(settlement.buildings):
                    if diff <= 0:
                        break
                    to_remove = min(building.workers_assigned, diff)
                    building.workers_assigned -= to_remove
                    diff -= to_remove
                    await self.bot.database.settlement.assign_workers(
                        building.id, building.workers_assigned
                    )
                await interaction.channel.send(
                    f"⚠️ **Workforce Shortage!** {total_assigned - total_followers} workers have abandoned their posts.",
                    delete_after=10,
                )
            await self.bot.database.plots.ensure_plots(user_id, server_id)
            plot_rows = await self.bot.database.plots.get_plots(user_id, server_id)
            plots = [
                Plot(plot_index=r[0], is_developed=bool(r[1]), bonus_type=r[2])
                for r in plot_rows
            ]
            player_name = (
                existing_user["prestige_display_name"]
                or existing_user["name"]
                or interaction.user.display_name
            )
            view = SettlementDashboardView(
                self.bot,
                user_id,
                server_id,
                settlement,
                total_followers,
                plots=plots,
                player_name=player_name,
            )
            turns_data = await self.bot.database.settlement.get_turns_data(
                user_id, server_id
            )
            zeal_data = await self.bot.database.settlement.get_zeal_data(user_id, server_id)
            active_events = await self.bot.database.settlement.get_active_events(
                user_id, server_id
            )
            projects = await self.bot.database.settlement.get_projects(
                user_id, server_id
            )
            pending_deal = await self.bot.database.settlement.get_pending_deal(
                user_id, server_id
            )
            embed = view.build_embed(
                turns_data=turns_data,
                zeal_data=zeal_data,
                active_events=active_events,
                projects=projects,
                pending_deal=pending_deal,
            )
            return embed, view

        if not await self.bot.database.tutorials.has_seen(user_id, "settlement"):
            await self.bot.database.tutorials.mark_seen(user_id, "settlement")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "settlement", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
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

        settlement = await self.bot.database.settlement.get_settlement(
            user_id, server_id
        )
        hatchery_building = next(
            (b for b in settlement.buildings if b.building_type == "hatchery"), None
        )

        if user_data["level"] < 50:
            return await interaction.response.send_message(
                "The **Hatchery** requires **Level 50** to access.",
                ephemeral=True,
            )

        if hatchery_building is None:
            return await interaction.response.send_message(
                "You don't have a **Hatchery** built yet. "
                "Construct one in your `/settlement` first!",
                ephemeral=True,
            )

        self.bot.state_manager.set_active(user_id, "settlement")
        view = HatcheryView(
            self.bot, user_id, server_id, hatchery_building, parent_view=None
        )
        await view._load()
        view._rebuild_buttons()

        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="black_market",
        description="Open your settlement's Black Market directly.",
    )
    async def black_market(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        settlement = await self.bot.database.settlement.get_settlement(
            user_id, server_id
        )
        bm_building = next(
            (b for b in settlement.buildings if b.building_type == "black_market"),
            None,
        )
        if bm_building is None:
            return await interaction.response.send_message(
                "You don't have a **Black Market** built yet. "
                "Construct one in your `/settlement` first!",
                ephemeral=True,
            )

        self.bot.state_manager.set_active(user_id, "settlement")
        pending = await self.bot.database.settlement.get_pending_deal(
            user_id, server_id
        )
        zeal_data = await self.bot.database.settlement.get_zeal_data(user_id, server_id)
        view = BlackMarketView(
            self.bot,
            user_id,
            parent_view=None,
            building=bm_building,
            has_pending_deal=bool(pending),
            server_id=server_id,
        )
        await interaction.response.send_message(
            embed=view.build_embed(pending_deal=pending, zeal_data=zeal_data), view=view
        )
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(SettlementCog(bot))
