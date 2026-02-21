import discord
from discord import ui, ButtonStyle, Interaction, SelectOption
import random
from core.slayer.mechanics import SlayerMechanics

PASSIVE_DISPLAY_NAMES = {
    "none": "Empty Slot",
    "slayer_dmg": "Slayer Damage",
    "boss_dmg": "Boss Damage",
    "combat_dmg": "Base Damage",
    "gold_find": "Gold Find",
    "xp_find": "XP Find"
}

class SlayerDashboardView(ui.View):
    def __init__(self, bot, user_id, server_id, profile, player_level):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.profile = profile
        self.player_level = player_level
        self.setup_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.edit(view=None)
        except: pass

    def build_embed(self) -> discord.Embed:
        lvl = self.profile['level']
        xp = self.profile['xp']
        pts = self.profile['points']
        next_xp = lvl * 1000

        embed = discord.Embed(title="💀 Slayer Master", color=discord.Color.dark_red())
        embed.set_thumbnail(url="https://i.imgur.com/oMkaM34.jpeg") # slayer master image
        
        embed.add_field(name="Profile", value=f"**Level:** {lvl}\n**XP:** {xp:,}/{next_xp:,}\n**Points:** {pts}", inline=True)
        embed.add_field(name="Materials", value=f"🩸 **Violent Essence:** {self.profile['violent_essence']}\n❤️ **Imbued Hearts:** {self.profile['imbued_heart']}", inline=True)

        if self.profile['active_task_species']:
            prog = self.profile['active_task_progress']
            req = self.profile['active_task_amount']
            species = self.profile['active_task_species']
            embed.add_field(name="Current Task", value=f"Slay **{req} {species}**\n*Progress: {prog}/{req}*", inline=False)
        else:
            embed.add_field(name="Current Task", value="No active task. Request one from the master.", inline=False)

        return embed

    def setup_buttons(self):
        self.clear_items()
        
        has_task = bool(self.profile['active_task_species'])
        
        btn_task = ui.Button(label="Get Task", style=ButtonStyle.success, disabled=has_task, row=0)
        btn_task.callback = self.get_task
        self.add_item(btn_task)

        btn_skip = ui.Button(label="Skip Task (15 pts)", style=ButtonStyle.danger, disabled=(not has_task or self.profile['points'] < 15), row=0)
        btn_skip.callback = self.skip_task
        self.add_item(btn_skip)

        btn_emblem = ui.Button(label="Manage Emblem", style=ButtonStyle.primary, emoji="🛡️", row=1)
        btn_emblem.callback = self.open_emblem
        self.add_item(btn_emblem)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    async def get_task(self, interaction: Interaction):
        await interaction.response.defer()
        species, amount = SlayerMechanics.generate_task(self.player_level)
        
        await self.bot.database.slayer.assign_task(self.user_id, self.server_id, species, amount)
        self.profile = await self.bot.database.slayer.get_profile(self.user_id, self.server_id)
        
        self.setup_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def skip_task(self, interaction: Interaction):
        if self.profile['points'] < 15:
            return await interaction.response.send_message("Not enough Slayer Points!", ephemeral=True)
            
        await interaction.response.defer()
        await self.bot.database.slayer.add_rewards(self.user_id, self.server_id, 0, -15) # Deduct 15 pts
        await self.bot.database.slayer.clear_task(self.user_id, self.server_id)
        
        self.profile = await self.bot.database.slayer.get_profile(self.user_id, self.server_id)
        self.setup_buttons()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def open_emblem(self, interaction: Interaction):
        emblem = await self.bot.database.slayer.get_emblem(self.user_id, self.server_id)
        view = EmblemView(self.bot, self.user_id, self.server_id, self.profile, emblem, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


class EmblemView(ui.View):
    def __init__(self, bot, user_id, server_id, profile, emblem, parent_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.profile = profile
        self.emblem = emblem
        self.parent = parent_view
        
        self.unlocked_slots = SlayerMechanics.get_unlocked_slots(self.profile['level'])
        self.setup_ui()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="💀 Slayer Emblem", description="Enhance your combat prowess.", color=discord.Color.dark_purple())
        embed.set_thumbnail(url="https://i.imgur.com/sEbbos9.png")
        # Display Slots
        unlock_reqs = {1: 1, 2: 20, 3: 40, 4: 60, 5: 80}
        
        for slot in range(1, 6):
            if slot <= self.unlocked_slots:
                data = self.emblem.get(slot, {'type': 'none', 'tier': 1})
                if data['type'] == 'none':
                    embed.add_field(name=f"Slot {slot}", value="*Empty - Needs Awakening*", inline=False)
                else:
                    name = PASSIVE_DISPLAY_NAMES.get(data['type'], data['type'])
                    embed.add_field(name=f"Slot {slot} (Tier {data['tier']})", value=f"**{name}**", inline=False)
            else:
                embed.add_field(name=f"Slot {slot} 🔒", value=f"Unlocks at Slayer Level {unlock_reqs[slot]}", inline=False)
                
        return embed

    def setup_ui(self):
        self.clear_items()
        
        # Select Menu for unlocked slots
        options = []
        for slot in range(1, self.unlocked_slots + 1):
            data = self.emblem.get(slot, {'type': 'none', 'tier': 1})
            lbl = f"Slot {slot} - {PASSIVE_DISPLAY_NAMES.get(data['type'], 'Empty')}"
            options.append(SelectOption(label=lbl, value=str(slot)))
            
        if options:
            select = ui.Select(placeholder="Select a slot to modify...", options=options)
            select.callback = self.select_slot
            self.add_item(select)
            
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def select_slot(self, interaction: Interaction):
        slot = int(interaction.data['values'][0])
        slot_data = self.emblem.get(slot, {'type': 'none', 'tier': 1})
        
        view = SlotManageView(self.bot, self.user_id, self.server_id, self.profile, slot, slot_data, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def go_back(self, interaction: Interaction):
        # Refresh profile before going back
        self.parent.profile = await self.bot.database.slayer.get_profile(self.user_id, self.server_id)
        self.parent.setup_buttons()
        await interaction.response.edit_message(embed=self.parent.build_embed(), view=self.parent)
        self.stop()


class SlotManageView(ui.View):
    def __init__(self, bot, user_id, server_id, profile, slot_num, slot_data, parent_view):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.profile = profile
        self.slot_num = slot_num
        self.slot_data = slot_data
        self.parent = parent_view
        
        self.setup_ui()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def build_embed(self) -> discord.Embed:
        p_type = self.slot_data['type']
        p_tier = self.slot_data['tier']
        
        embed = discord.Embed(title=f"Modify Slot {self.slot_num}", color=discord.Color.dark_magenta())
        embed.description = f"🩸 **Violent Essence:** {self.profile['violent_essence']}\n❤️ **Imbued Hearts:** {self.profile['imbued_heart']}\n\n"
        
        if p_type == 'none':
            embed.description += "**Status:** Empty\nUse 1 Violent Essence to Awaken a random Tier 1 passive."
        else:
            name = PASSIVE_DISPLAY_NAMES.get(p_type, p_type)
            success_rate = max(0, int((1.0 - (p_tier * 0.20)) * 100))
            downgrade_rate = 0 if p_tier == 1 else int(((p_tier - 1) * 0.20) * 100)
            
            embed.add_field(name="Current Passive", value=f"**{name}** (Tier {p_tier})", inline=False)
            if p_tier < 5:
                embed.add_field(name="Upgrade Odds", value=f"🟢 Success: {success_rate}%\n🔴 Downgrade: {downgrade_rate}%", inline=False)
            else:
                embed.add_field(name="Upgrade Status", value="🌟 Max Tier Reached!", inline=False)
                
        return embed

    def setup_ui(self):
        self.clear_items()
        
        essences = self.profile['violent_essence']
        hearts = self.profile['imbued_heart']
        p_type = self.slot_data['type']
        p_tier = self.slot_data['tier']
        
        if p_type == 'none':
            btn_awaken = ui.Button(label="Awaken (1 Essence)", style=ButtonStyle.primary, emoji="🩸", disabled=(essences < 1))
            btn_awaken.callback = self.awaken_slot
            self.add_item(btn_awaken)
        else:
            btn_upgrade = ui.Button(label="Upgrade (1 Essence)", style=ButtonStyle.success, emoji="🩸", disabled=(essences < 1 or p_tier >= 5))
            btn_upgrade.callback = self.upgrade_slot
            self.add_item(btn_upgrade)
            
            btn_reroll = ui.Button(label="Reroll Type (1 Heart)", style=ButtonStyle.primary, emoji="❤️", disabled=(hearts < 1))
            btn_reroll.callback = self.reroll_slot
            self.add_item(btn_reroll)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def awaken_slot(self, interaction: Interaction):
        await interaction.response.defer()
        
        # Deduct
        await self.bot.database.slayer.modify_materials(self.user_id, self.server_id, 'violent_essence', -1)
        self.profile['violent_essence'] -= 1
        
        # Assign random
        new_type = random.choice(SlayerMechanics.PASSIVE_POOL)
        self.slot_data['type'] = new_type
        self.slot_data['tier'] = 1
        
        await self.bot.database.slayer.update_emblem_slot(self.user_id, self.server_id, self.slot_num, new_type, 1)
        
        self.setup_ui()
        await interaction.followup.send(f"Slot Awakened! Gained: **{PASSIVE_DISPLAY_NAMES[new_type]}**", ephemeral=True)
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def upgrade_slot(self, interaction: Interaction):
        await interaction.response.defer()
        
        await self.bot.database.slayer.modify_materials(self.user_id, self.server_id, 'violent_essence', -1)
        self.profile['violent_essence'] -= 1
        
        old_tier = self.slot_data['tier']
        success, new_tier = SlayerMechanics.roll_upgrade(old_tier)
        
        self.slot_data['tier'] = new_tier
        await self.bot.database.slayer.update_emblem_slot(self.user_id, self.server_id, self.slot_num, self.slot_data['type'], new_tier)
        
        if success:
            msg = f"✨ **Success!** Upgraded to Tier {new_tier}!"
        elif new_tier < old_tier:
            msg = f"💥 **Failure.** The essence corrupted. Downgraded to Tier {new_tier}."
        else:
            msg = f"💨 **Failure.** The essence faded. Slot remains Tier {new_tier}."
            
        self.setup_ui()
        await interaction.followup.send(msg, ephemeral=True)
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def reroll_slot(self, interaction: Interaction):
        await interaction.response.defer()
        
        await self.bot.database.slayer.modify_materials(self.user_id, self.server_id, 'imbued_heart', -1)
        self.profile['imbued_heart'] -= 1
        
        # Pick new random (exclude current)
        pool = [p for p in SlayerMechanics.PASSIVE_POOL if p != self.slot_data['type']]
        new_type = random.choice(pool)
        
        self.slot_data['type'] = new_type
        await self.bot.database.slayer.update_emblem_slot(self.user_id, self.server_id, self.slot_num, new_type, self.slot_data['tier'])
        
        self.setup_ui()
        await interaction.followup.send(f"❤️ **Rerolled!** New Passive: {PASSIVE_DISPLAY_NAMES[new_type]}", ephemeral=True)
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        # Sync changes back to parent
        self.parent.emblem[self.slot_num] = self.slot_data
        self.parent.setup_ui()
        await interaction.response.edit_message(embed=self.parent.build_embed(), view=self.parent)
        self.stop()