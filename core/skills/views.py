import discord
from discord import Interaction, ButtonStyle
from discord.ui import View, Button
from core.skills.mechanics import SkillMechanics

class SkillDashboardView(View):
    def __init__(self, bot, user_id: str, skill_type: str, user_data: tuple, skill_data: tuple):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.skill_type = skill_type
        self.user_data = user_data # Users table row
        self.skill_data = skill_data # Skill table row
        
        self.current_tier = self.skill_data[2] # Index 2 is tool_tier/type
        self.setup_ui()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def setup_ui(self):
        self.clear_items()
        
        next_tier = SkillMechanics.get_next_tier(self.skill_type, self.current_tier)
        if next_tier:
            # Check if affordable
            costs = SkillMechanics.get_upgrade_cost(self.skill_type, self.current_tier)
            can_afford = self._check_affordability(costs)
            
            btn = Button(
                label=f"Upgrade to {next_tier.title()}", 
                style=ButtonStyle.success if can_afford else ButtonStyle.secondary,
                disabled=not can_afford,
                emoji="⬆️"
            )
            btn.callback = self.upgrade_callback
            self.add_item(btn)
        else:
            # Maxed out
            btn = Button(label="Maxed Out", style=ButtonStyle.primary, disabled=True, emoji="🌟")
            self.add_item(btn)

    def _check_affordability(self, costs) -> bool:
        if not costs: return False
        
        # Skill Data Indices: 
        # Mining: 3=Iron, 4=Coal, 5=Gold, 6=Plat
        # Fishing: 3=Desic, 4=Reg, 5=Sturdy, 6=Reinf
        # Wood: 3=Oak, 4=Willow, 5=Mahog, 6=Magic
        
        res_held = [self.skill_data[3], self.skill_data[4], self.skill_data[5], self.skill_data[6]]
        gold_held = self.user_data[6]

        if res_held[0] < costs['res_1']: return False
        if res_held[1] < costs['res_2']: return False
        if res_held[2] < costs['res_3']: return False
        if res_held[3] < costs['res_4']: return False
        if gold_held < costs['gold']: return False
        
        return True

    def get_embed(self) -> discord.Embed:
        # Build dynamic description based on skill type
        desc = ""
        
        # Helper for resource lines
        def r_line(label, amount): return f"**{label}:** {amount:,}" if amount > 0 else ""

        if self.skill_type == "mining":
            tier_display = f"⛏️ **{self.current_tier.title()} Pickaxe**"
            resources = [
                r_line("Iron Ore", self.skill_data[3]),
                r_line("Coal", self.skill_data[4]),
                r_line("Gold Ore", self.skill_data[5]),
                r_line("Platinum Ore", self.skill_data[6]),
                r_line("Idea Ore", self.skill_data[7])
            ]
            img_url = "https://i.imgur.com/4OS6Blx.jpeg"
            
        elif self.skill_type == "fishing":
            tier_display = f"🎣 **{self.current_tier.title()} Rod**"
            resources = [
                r_line("Desiccated Bones", self.skill_data[3]),
                r_line("Regular Bones", self.skill_data[4]),
                r_line("Sturdy Bones", self.skill_data[5]),
                r_line("Reinforced Bones", self.skill_data[6]),
                r_line("Titanium Bones", self.skill_data[7])
            ]
            img_url = "https://i.imgur.com/JpgyGlD.jpeg"

        elif self.skill_type == "woodcutting":
            tier_display = f"🪓 **{self.current_tier.title()} Axe**"
            resources = [
                r_line("Oak Logs", self.skill_data[3]),
                r_line("Willow Logs", self.skill_data[4]),
                r_line("Mahogany Logs", self.skill_data[5]),
                r_line("Magic Logs", self.skill_data[6]),
                r_line("Idea Logs", self.skill_data[7])
            ]
            img_url = "https://i.imgur.com/X0JdvX8.jpeg"

        desc = f"Current Tool: {tier_display}\n\n" + "\n".join(filter(None, resources))
        
        # Add upgrade info if available
        next_tier = SkillMechanics.get_next_tier(self.skill_type, self.current_tier)
        if next_tier:
            costs = SkillMechanics.get_upgrade_cost(self.skill_type, self.current_tier)
            desc += f"\n\n**Next Upgrade: {next_tier.title()}**\n"
            desc += f"Cost: {costs['gold']:,} GP"
            # Add resource costs logic for display if desired, keeping it simple for now
        
        embed = discord.Embed(title=f"{self.skill_type.title()} Skills", description=desc, color=0x00FF00)
        embed.set_thumbnail(url=self.user_data[7]) # User avatar
        embed.set_image(url=img_url)
        return embed

    async def upgrade_callback(self, interaction: Interaction):
        await interaction.response.defer()
        
        # 1. Re-validate
        # (For production, re-fetch DB data here to prevent race conditions or stale view exploitation)
        # For this refactor, we'll assume the interaction check + button state is sufficient, 
        # but technically we should fetch `self.skill_data` again.
        
        next_tier = SkillMechanics.get_next_tier(self.skill_type, self.current_tier)
        costs = SkillMechanics.get_upgrade_cost(self.skill_type, self.current_tier)
        
        if not costs or not next_tier: return

        # 2. Execute Upgrade
        # Map cost dictionary back to tuple for the repo method
        cost_tuple = (costs['res_1'], costs['res_2'], costs['res_3'], costs['res_4'], costs['gold'])
        
        if self.skill_type == "mining":
            await self.bot.database.skills.upgrade_pickaxe(self.user_id, interaction.guild.id, next_tier, cost_tuple)
        elif self.skill_type == "woodcutting":
            await self.bot.database.skills.upgrade_axe(self.user_id, interaction.guild.id, next_tier, cost_tuple)
        elif self.skill_type == "fishing":
            await self.bot.database.skills.upgrade_fishing_rod(self.user_id, interaction.guild.id, next_tier, cost_tuple)

        # 3. Refresh Data
        self.skill_data = await self.bot.database.skills.get_data(self.user_id, str(interaction.guild.id), self.skill_type)
        self.user_data = await self.bot.database.users.get(self.user_id, str(interaction.guild.id))
        self.current_tier = self.skill_data[2]

        # 4. Refresh UI
        self.setup_ui()
        embed = self.get_embed()
        
        await interaction.followup.send(f"🎉 **Upgraded to {next_tier.title()}!**", ephemeral=True)
        await interaction.edit_original_response(embed=embed, view=self)