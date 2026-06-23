from discord import Interaction, app_commands
from discord.ext import commands, tasks

from core.first_use import TutorialGateView
from core.skills.fishing_view import FishingView
from core.skills.forestry_view import ForestryView
from core.skills.mastery import (
    compute_catchup_points,
    roll_rich_event,
    roll_remnant_generation,
    get_remnant_column,
    get_never_empty_proc_chance,
    has_nature_attunement_unlocked,
    get_attunement_progress,
    INSIGHT_CONVERSION_RATE,
    get_below_tier_chance,
)
from core.skills.mechanics import SkillMechanics
from core.skills.views import GatherView
import datetime
import random


class Skills(commands.Cog, name="skills"):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.schedule_skills.start()

    async def cog_unload(self):
        self.schedule_skills.cancel()

    @app_commands.command(
        name="gather",
        description="Manage your gathering skills (Mining, Fishing, Woodcutting).",
    )
    async def gather(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # 2. State Lock
        self.bot.state_manager.set_active(user_id, "gather")

        async def _build():
            view = GatherView(self.bot, user_id, server_id, initial_skill="mining")
            await view.refresh_state()
            return view.get_embed(), view

        if not await self.bot.database.tutorials.has_seen(user_id, "gather"):
            await self.bot.database.tutorials.mark_seen(user_id, "gather")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "gather", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="fish", description="Go fishing with your rod.")
    async def fish(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "fishing")

        view = FishingView(self.bot, user_id, server_id, interaction.user.mention)
        await view.refresh_data()
        view.setup_ui()

        await interaction.response.send_message(embed=view.get_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="chop", description="Head into the forest to chop wood.")
    async def chop(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "forestry")

        view = ForestryView(self.bot, user_id, server_id)
        await view.refresh_data()
        view.setup_ui()

        await interaction.response.send_message(embed=view.get_embed(), view=view)
        view.message = await interaction.original_response()

    # --- REGENERATION TASK (Artisan Mastery aware) ---

    @tasks.loop(hours=1)
    async def schedule_skills(self):
        """Passive resource generation + Artisan Points + Rich events + Remnants (MVP)."""
        self.bot.logger.info("Running Skill Regeneration Task (Mastery)...")

        _tool_col = {
            "mining": "pickaxe_tier",
            "fishing": "fishing_rod",
            "woodcutting": "axe_type",
        }

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Collect all unique (user_id, server_id) pairs across all skills.
        all_users: set[tuple[str, str]] = set()
        for skill in ["mining", "fishing", "woodcutting"]:
            skill_users = await self.bot.database.skills.get_all_users(skill)
            if skill_users:
                all_users.update(skill_users)

        for user_id, server_id in all_users:
            # Fetch mastery row once per user so last_point_claim is read before
            # any skill updates it. All three skills share the same claim timestamp,
            # so they must all be processed before the timestamp advances.
            try:
                mrow = await self.bot.database.skills.get_mastery(user_id, server_id)
                last_claim = mrow.get("last_point_claim")
                any_pts_awarded = False

                for skill in ["mining", "fishing", "woodcutting"]:
                    try:
                        data = await self.bot.database.skills.get_data(
                            user_id, server_id, skill
                        )
                        if not data:
                            continue

                        tool_tier = data[_tool_col[skill]]

                        # --- 1. Points (catch-up on first run or long absence) ---
                        pts = compute_catchup_points(last_claim, tool_tier, now_iso)
                        if pts > 0:
                            await self.bot.database.skills.add_mastery_points(
                                user_id, server_id, skill, pts
                            )
                            any_pts_awarded = True

                        # --- 2. Yield (with mastery multipliers) ---
                        resources = SkillMechanics.calculate_yield_with_mastery(
                            skill, tool_tier, mrow
                        )

                        # Below-tier signature resource chance (from 2pt Quality nodes)
                        below_tier_chance = get_below_tier_chance(skill, mrow)
                        if below_tier_chance > 0 and random.random() < below_tier_chance:
                            sig_map = {
                                "mining": "idea_ore",
                                "fishing": "titanium_bones",
                                "woodcutting": "idea_logs",
                            }
                            sig = sig_map.get(skill)
                            if sig:
                                resources[sig] = resources.get(sig, 0) + 1

                        # --- 3. Rich event + remnant generation (Quality investment) ---
                        is_rich = roll_rich_event(skill, mrow)
                        if is_rich:
                            for k in resources:
                                resources[k] = int(resources[k] * 2.6)

                        remnants = roll_remnant_generation(skill, mrow, is_rich)
                        if remnants > 0:
                            rem_col = get_remnant_column(skill)
                            await self.bot.database.skills.modify_remnants(
                                user_id, server_id, {rem_col: remnants}
                            )

                        # Never Empty / equivalent Yield proc
                        never_empty_chance = get_never_empty_proc_chance(skill, mrow)
                        if never_empty_chance > 0 and random.random() < never_empty_chance:
                            for k in resources:
                                resources[k] = int(resources[k] * 1.70)

                        # --- Triple tick consumption (prestige boss reward) ---
                        tick_col = f"{skill}_tripled_ticks"
                        remaining_ticks = mrow.get(tick_col, 0) or 0
                        if remaining_ticks > 0:
                            for k in resources:
                                resources[k] = int(resources[k] * 3)
                            await self.bot.database.skills.consume_tripled_tick(
                                user_id, server_id, skill
                            )

                        # Write resources
                        await self.bot.database.skills.update_batch(
                            user_id, server_id, skill, resources
                        )

                    except Exception:
                        self.bot.logger.error(
                            f"schedule_skills error for {user_id}/{server_id} ({skill})",
                            exc_info=True,
                        )

                # Advance last_point_claim once after all skills have been processed.
                # Only advance when points were actually awarded so fractional hours
                # accumulate across ticks for sub-daily rates.
                if any_pts_awarded:
                    await self.bot.database.skills.update_last_mastery_claim(
                        user_id, server_id, now_iso
                    )

                # --- Post-max Mastery Insight conversion ---
                mrow_for_insight = await self.bot.database.skills.get_mastery(
                    user_id, server_id
                )
                if has_nature_attunement_unlocked(mrow_for_insight):
                    att = get_attunement_progress(
                        mrow_for_insight.get("attunement_alloc", "{}")
                    )
                    if att.get("complete"):
                        await self.bot.database.skills.convert_excess_to_insight(
                            user_id, server_id, INSIGHT_CONVERSION_RATE
                        )
            except Exception:
                self.bot.logger.error(
                    f"schedule_skills error for {user_id}/{server_id}",
                    exc_info=True,
                )

    @schedule_skills.before_loop
    async def before_schedule_skills(self):
        await self.bot.wait_until_ready()

    @schedule_skills.error
    async def schedule_skills_error(self, error):
        self.bot.logger.error(f"schedule_skills task crashed: {error}", exc_info=True)


async def setup(bot):
    await bot.add_cog(Skills(bot))
