import discord
import random
from discord.ext import commands, tasks
from discord import app_commands, Interaction
from core.skills.views import GatherView
from core.skills.mechanics import SkillMechanics

class Skills(commands.Cog, name="skills"):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.schedule_skills.start()

    async def cog_unload(self):
        self.schedule_skills.cancel()

    @app_commands.command(name="gather", description="Manage your gathering skills (Mining, Fishing, Woodcutting).")
    async def gather(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Validation
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        # 2. State Lock
        self.bot.state_manager.set_active(user_id, "gather")

        # 3. View Initialization
        # We start with Mining by default
        view = GatherView(self.bot, user_id, server_id, initial_skill="mining")
        
        # 4. Fetch Initial Data inside View
        # We manually call refresh_state here before sending so the first embed is populated
        await view.refresh_state()
        
        embed = view.get_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    # --- REGENERATION TASK ---
    
    @tasks.loop(hours=1)
    async def schedule_skills(self):
        """Passive resource generation."""
        self.bot.logger.info("Running Skill Regeneration Task...")
        
        # We iterate through the 3 types
        for skill in ['mining', 'fishing', 'woodcutting']:
            users = await self.bot.database.skills.get_all_users(skill)
            if not users: continue

            for user_id, server_id in users:
                data = await self.bot.database.skills.get_data(user_id, server_id, skill)
                if not data: continue
                
                tool_tier = data[2]
                
                resources = SkillMechanics.calculate_yield(skill, tool_tier)

                await self.bot.database.skills.update_batch(user_id, server_id, skill, resources)

    @schedule_skills.before_loop
    async def before_schedule_skills(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Skills(bot))