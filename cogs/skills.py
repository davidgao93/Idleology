import discord
import random
from discord.ext import commands, tasks
from discord import app_commands, Interaction
from core.skills.views import SkillDashboardView
from core.skills.mechanics import SkillMechanics

class Skills(commands.Cog, name="skills"):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.schedule_skills.start()

    async def cog_unload(self):
        self.schedule_skills.cancel()

    async def _skill_command(self, interaction: Interaction, skill_type: str):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # 1. Checks
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return
        if not await self.bot.check_is_active(interaction, user_id): return

        # 2. Fetch Data
        skill_data = await self.bot.database.skills.get_data(user_id, server_id, skill_type)
        if not skill_data:
            # Should have been initialized on register, but safe fallback
            return await interaction.response.send_message(f"Your {skill_type} stats are missing!", ephemeral=True)

        self.bot.state_manager.set_active(user_id, "skills")

        # 3. View
        view = SkillDashboardView(self.bot, user_id, skill_type, existing_user, skill_data)
        embed = view.get_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="mining", description="Check mining stats and upgrade pickaxe.")
    async def mining(self, interaction: Interaction):
        await self._skill_command(interaction, "mining")

    @app_commands.command(name="woodcutting", description="Check woodcutting stats and upgrade axe.")
    async def woodcutting(self, interaction: Interaction):
        await self._skill_command(interaction, "woodcutting")

    @app_commands.command(name="fishing", description="Check fishing stats and upgrade rod.")
    async def fishing(self, interaction: Interaction):
        await self._skill_command(interaction, "fishing")

    @app_commands.command(name="skills", description="Overview of all skills.")
    async def skills_summary(self, interaction: Interaction):
        """Displays a summary embed of all 3 skills (Read-only)."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user): return

        m_data = await self.bot.database.skills.get_data(user_id, server_id, 'mining')
        f_data = await self.bot.database.skills.get_data(user_id, server_id, 'fishing')
        w_data = await self.bot.database.skills.get_data(user_id, server_id, 'woodcutting')

        embed = discord.Embed(title=f"{existing_user[3]}'s Skills", color=0x00FF00)
        
        # Helper to format
        def fmt(data, tool_name):
            return f"**{data[2].title()}** {tool_name}" if data else "Locked"

        embed.add_field(name="⛏️ Mining", value=fmt(m_data, "Pickaxe"), inline=True)
        embed.add_field(name="🎣 Fishing", value=fmt(f_data, "Rod"), inline=True)
        embed.add_field(name="🪓 Woodcutting", value=fmt(w_data, "Axe"), inline=True)
        
        await interaction.response.send_message(embed=embed)

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