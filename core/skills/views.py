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
        self.user_data = user_data
        self.skill_data = skill_data
        
        self.current_tier = self.skill_data[2]
        self.setup_ui()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.edit(view=None)
        except: pass

    def setup_ui(self):
        self.clear_items()
        
        next_tier = SkillMechanics.get_next_tier(self.skill_type, self.current_tier)
        
        if next_tier:
            costs = SkillMechanics.get_upgrade_cost(self.skill_type, self.current_tier)
            can_afford = self._check_affordability(costs)
            
            btn = Button(
                label=f"Upgrade to {next_tier.title()}", 
                style=ButtonStyle.success if can_afford else ButtonStyle.secondary,
                disabled=not can_afford,
                emoji="⬆️",
                row=0
            )
            btn.callback = self.upgrade_callback
            self.add_item(btn)
        else:
            # Visual indicator only
            btn = Button(label="Tool Maxed Out", style=ButtonStyle.primary, disabled=True, emoji="🌟", row=0)
            self.add_item(btn)

        close_btn = Button(label="Close", style=ButtonStyle.danger, row=1)
        close_btn.callback = self.close_callback
        self.add_item(close_btn)

    async def close_callback(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    def _check_affordability(self, costs) -> bool:
        if not costs: return False
        
        res_held = [self.skill_data[3], self.skill_data[4], self.skill_data[5], self.skill_data[6]]
        gold_held = self.user_data[6]

        if res_held[0] < costs['res_1']: return False
        if res_held[1] < costs['res_2']: return False
        if res_held[2] < costs['res_3']: return False
        if res_held[3] < costs['res_4']: return False
        if gold_held < costs['gold']: return False
        
        return True

    def get_embed(self) -> discord.Embed:
        desc = ""
        
        def r_line(label, amount): return f"**{label}:** {amount:,}" if amount > 0 else ""

        # Define resource names and images
        if self.skill_type == "mining":
            tier_display = f"⛏️ **{self.current_tier.title()} Pickaxe**"
            res_labels = ["Iron Ore", "Coal", "Gold Ore", "Platinum Ore", "Idea Ore"]
            res_values = [self.skill_data[i] for i in range(3, 8)]
            img_url = "https://i.imgur.com/4OS6Blx.jpeg"
            
        elif self.skill_type == "fishing":
            tier_display = f"🎣 **{self.current_tier.title()} Rod**"
            res_labels = ["Desiccated Bones", "Regular Bones", "Sturdy Bones", "Reinforced Bones", "Titanium Bones"]
            res_values = [self.skill_data[i] for i in range(3, 8)]
            img_url = "https://i.imgur.com/JpgyGlD.jpeg"

        elif self.skill_type == "woodcutting":
            tier_display = f"🪓 **{self.current_tier.title()} Axe**"
            res_labels = ["Oak Logs", "Willow Logs", "Mahogany Logs", "Magic Logs", "Idea Logs"]
            res_values = [self.skill_data[i] for i in range(3, 8)]
            img_url = "https://i.imgur.com/X0JdvX8.jpeg"

        # Build Resource List
        resources = [r_line(l, v) for l, v in zip(res_labels, res_values)]
        desc = f"Current Tool: {tier_display}\n\n" + "\n".join(filter(None, resources))
        
        # --- Fix for Issue 2: Display Costs ---
        next_tier = SkillMechanics.get_next_tier(self.skill_type, self.current_tier)
        if next_tier:
            costs = SkillMechanics.get_upgrade_cost(self.skill_type, self.current_tier)
            
            cost_parts = []
            # Map res_1...res_4 back to labels
            for i in range(1, 5):
                qty = costs.get(f'res_{i}', 0)
                if qty > 0:
                    cost_parts.append(f"{qty} {res_labels[i-1]}")
            
            if costs['gold'] > 0:
                cost_parts.append(f"{costs['gold']:,} GP")

            desc += f"\n\n**Next Upgrade:** {next_tier.title()}\n"
            desc += f"**Costs:** {', '.join(cost_parts)}"
        else:
            desc += "\n\n**Tool is Max Level!**"
        # --------------------------------------
        
        embed = discord.Embed(title=f"{self.skill_type.title()} Skills", description=desc, color=0x00FF00)
        embed.set_thumbnail(url=self.user_data[7])
        embed.set_image(url=img_url)
        return embed

    async def upgrade_callback(self, interaction: Interaction):
        await interaction.response.defer()
        
        next_tier = SkillMechanics.get_next_tier(self.skill_type, self.current_tier)
        costs = SkillMechanics.get_upgrade_cost(self.skill_type, self.current_tier)
        
        if not costs or not next_tier: return

        cost_tuple = (costs['res_1'], costs['res_2'], costs['res_3'], costs['res_4'], costs['gold'])
        
        if self.skill_type == "mining":
            await self.bot.database.skills.upgrade_pickaxe(self.user_id, interaction.guild.id, next_tier, cost_tuple)
        elif self.skill_type == "woodcutting":
            await self.bot.database.skills.upgrade_axe(self.user_id, interaction.guild.id, next_tier, cost_tuple)
        elif self.skill_type == "fishing":
            await self.bot.database.skills.upgrade_fishing_rod(self.user_id, interaction.guild.id, next_tier, cost_tuple)

        # Refresh Data
        self.skill_data = await self.bot.database.skills.get_data(self.user_id, str(interaction.guild.id), self.skill_type)
        self.user_data = await self.bot.database.users.get(self.user_id, str(interaction.guild.id))
        self.current_tier = self.skill_data[2]

        self.setup_ui()
        embed = self.get_embed()
        
        await interaction.followup.send(f"🎉 **Upgraded to {next_tier.title()}!**", ephemeral=True)
        await interaction.edit_original_response(embed=embed, view=self)