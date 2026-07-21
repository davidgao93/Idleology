from discord import Interaction, app_commands
from discord.ext import commands

from core.delve.delve_views import DelveEntryView, DelveView
from core.delve.mechanics import DelveMechanics, DelveState
from core.first_use import TutorialGateView
from core.skills import mastery as Mastery


class Delve(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="delve", description="Start a tactical mining expedition."
    )
    async def delve(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Checks
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # 2. Get Mining Tool & Delve Stats
        mining_data = await self.bot.database.skills.get_data(
            user_id, server_id, "mining"
        )
        pickaxe = mining_data["pickaxe_tier"] if mining_data else "iron"
        delve_stats = await self.bot.database.delve.get_profile(user_id, server_id)
        mastery_row = await self.bot.database.skills.get_mastery(user_id, server_id)

        # 3. Calculate Entry Cost
        entry_cost = DelveMechanics.get_entry_cost(delve_stats["fuel_lvl"])
        entry_reduction = Mastery.get_entry_pass_reduction(mastery_row)
        if entry_reduction:
            entry_cost = int(entry_cost * (1 - entry_reduction))

        # Pre-check gold
        if existing_user["gold"] < entry_cost:
            return await interaction.response.send_message(
                f"You need **{entry_cost:,} Gold** to purchase a mining permit.",
                ephemeral=True,
            )

        self.bot.state_manager.set_active(user_id, "delve")

        # 3a. First-use tutorial (fires before the entry view on the very first visit)
        if not await self.bot.database.tutorials.has_seen(user_id, "delve"):
            await self.bot.database.tutorials.mark_seen(user_id, "delve")

            async def _build_entry():
                async def start_game(inter: Interaction):
                    state = DelveState(
                        max_fuel=DelveMechanics.get_max_fuel(delve_stats["fuel_lvl"]),
                        current_fuel=DelveMechanics.get_max_fuel(
                            delve_stats["fuel_lvl"]
                        ),
                        pickaxe_tier=pickaxe,
                    )
                    view = DelveView(
                        self.bot,
                        user_id,
                        server_id,
                        state,
                        delve_stats,
                        mastery_row=mastery_row,
                    )
                    embed = view.build_embed("Systems online. Permit verified.")
                    await inter.edit_original_response(embed=embed, view=view)
                    view.message = await inter.original_response()

                entry_view = DelveEntryView(
                    self.bot, user_id, server_id, entry_cost, start_game, delve_stats
                )
                return entry_view.build_embed(), entry_view

            gate = TutorialGateView(
                self.bot, user_id, server_id, "delve", build_main=_build_entry
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        # Callback invoked by entry view after permit cost is paid.
        async def start_game(inter: Interaction):
            state = DelveState(
                max_fuel=DelveMechanics.get_max_fuel(delve_stats["fuel_lvl"]),
                current_fuel=DelveMechanics.get_max_fuel(delve_stats["fuel_lvl"]),
                pickaxe_tier=pickaxe,
            )

            view = DelveView(
                self.bot,
                user_id,
                server_id,
                state,
                delve_stats,
                mastery_row=mastery_row,
            )
            embed = view.build_embed("Systems online. Permit verified.")

            await inter.response.edit_message(embed=embed, view=view)
            view.message = await inter.original_response()

        # 5. Show Entry View
        view = DelveEntryView(
            self.bot, user_id, server_id, entry_cost, start_game, delve_stats
        )
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Delve(bot))
