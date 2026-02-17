import discord
from discord import ui, ButtonStyle, Interaction, SelectOption
from core.companions.mechanics import CompanionMechanics

class FusionWizardView(ui.View):
    def __init__(self, bot, user_id: str, companions: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.all_companions = companions
        
        # State
        self.parent_a = None
        self.parent_b = None
        self.FUSION_COST = 50000

        self.setup_step_one()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.edit(content="Fusion session timed out.", view=None, embed=None)
        except: pass

    # --- STEP 1: Select First ---
    def setup_step_one(self):
        self.clear_items()
        
        options = []
        # Discord select limit is 25. If user has > 25 (cap is 20), we are safe.
        for comp in self.all_companions:
            options.append(SelectOption(
                label=f"Lv.{comp.level} {comp.name}",
                description=f"T{comp.passive_tier} {comp.passive_type.upper()} | {comp.species}",
                value=str(comp.id)
            ))

        select = ui.Select(placeholder="Select Primary Companion...", options=options)
        select.callback = self.step_one_callback
        self.add_item(select)
        
        btn_cancel = ui.Button(label="Cancel", style=ButtonStyle.danger, row=1)
        btn_cancel.callback = self.cancel_callback
        self.add_item(btn_cancel)

    async def step_one_callback(self, interaction: Interaction):
        comp_id = int(interaction.data['values'][0])
        self.parent_a = next(c for c in self.all_companions if c.id == comp_id)
        
        self.setup_step_two()
        
        embed = discord.Embed(title="🧬 Companion Fusion", color=discord.Color.purple())
        embed.description = f"**Selected:** {self.parent_a.name}\nSelect the second companion to fuse."
        await interaction.response.edit_message(embed=embed, view=self)

    # --- STEP 2: Select Second ---
    def setup_step_two(self):
        self.clear_items()
        
        options = []
        for comp in self.all_companions:
            # Cannot fuse with self
            if comp.id == self.parent_a.id: continue
            
            options.append(SelectOption(
                label=f"Lv.{comp.level} {comp.name}",
                description=f"T{comp.passive_tier} {comp.passive_type.upper()} | {comp.species}",
                value=str(comp.id)
            ))

        select = ui.Select(placeholder="Select Partner Companion...", options=options)
        select.callback = self.step_two_callback
        self.add_item(select)
        
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.back_to_one
        self.add_item(btn_back)

    async def back_to_one(self, interaction: Interaction):
        self.parent_a = None
        self.setup_step_one()
        embed = discord.Embed(title="🧬 Companion Fusion", description="Select your first companion.", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=self)

    async def step_two_callback(self, interaction: Interaction):
        comp_id = int(interaction.data['values'][0])
        self.parent_b = next(c for c in self.all_companions if c.id == comp_id)
        
        self.setup_confirmation()
        
        # Calculate Preview
        xp_a = CompanionMechanics.calculate_cumulative_xp(self.parent_a.level, self.parent_a.exp)
        xp_b = CompanionMechanics.calculate_cumulative_xp(self.parent_b.level, self.parent_b.exp)
        new_lvl, _ = CompanionMechanics.calculate_level_from_xp(xp_a + xp_b)
        
        embed = discord.Embed(title="⚠️ Confirm Fusion", color=discord.Color.gold())
        embed.description = (
            f"**Parent 1:** {self.parent_a.name} (T{self.parent_a.passive_tier} {self.parent_a.passive_type})\n"
            f"**Parent 2:** {self.parent_b.name} (T{self.parent_b.passive_tier} {self.parent_b.passive_type})\n\n"
            f"**Results:**\n"
            f"• Level: **{new_lvl}** (Merged XP)\n"
            f"• Appearance: Random (50/50)\n"
            f"• Passive: Random (50/50)\n"
            f"• Tier: Random (50/50)\n\n"
            f"**Cost:** {self.FUSION_COST:,} Gold"
        )
        embed.set_footer(text="This action is irreversible. Parents will be consumed.")
        
        await interaction.response.edit_message(embed=embed, view=self)

    # --- STEP 3: Confirm ---
    def setup_confirmation(self):
        self.clear_items()
        
        btn_confirm = ui.Button(label="FUSE (50k Gold)", style=ButtonStyle.success, emoji="🧬")
        btn_confirm.callback = self.confirm_fusion
        self.add_item(btn_confirm)
        
        btn_cancel = ui.Button(label="Cancel", style=ButtonStyle.danger)
        btn_cancel.callback = self.cancel_callback
        self.add_item(btn_cancel)

    async def confirm_fusion(self, interaction: Interaction):
        # 1. Final Gold Check
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < self.FUSION_COST:
            return await interaction.response.send_message("Insufficient gold!", ephemeral=True)

        await interaction.response.defer()

        # 2. Logic
        # Stats
        new_attrs = CompanionMechanics.fuse_attributes(self.parent_a, self.parent_b)
        
        # XP
        xp_a = CompanionMechanics.calculate_cumulative_xp(self.parent_a.level, self.parent_a.exp)
        xp_b = CompanionMechanics.calculate_cumulative_xp(self.parent_b.level, self.parent_b.exp)
        total_xp = xp_a + xp_b
        lvl, rem_xp = CompanionMechanics.calculate_level_from_xp(total_xp)
        
        new_attrs['level'] = lvl
        new_attrs['exp'] = rem_xp

        # 3. DB Transaction
        await self.bot.database.companions.fuse_companions(
            self.user_id, 
            self.parent_a.id, 
            self.parent_b.id, 
            new_attrs, 
            self.FUSION_COST
        )

        # 4. Result
        embed = discord.Embed(title="🧬 Fusion Complete!", color=discord.Color.green())
        embed.set_thumbnail(url=new_attrs['image_url'])
        embed.description = (
            f"A new companion is born: **{new_attrs['name']}**!\n"
            f"**Level:** {lvl}\n"
            f"**Passive:** T{new_attrs['passive_tier']} {new_attrs['passive_type'].upper()}"
        )
        
        await interaction.edit_original_response(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def cancel_callback(self, interaction: Interaction):
        await interaction.response.edit_message(content="Fusion cancelled.", embed=None, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()