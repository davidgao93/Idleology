import discord
from discord import Interaction, ButtonStyle, SelectOption
from discord.ui import View, Button, Select, Modal, TextInput
import csv
import re

class RegistrationView(View):
    """
    Step 1: Gender Selection (Buttons)
    Step 2: Appearance Selection (Select Menu + Preview) -> Confirm Button
    Step 3: Ideology (Modal)
    """
    def __init__(self, bot, user_id, name):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = str(user_id)
        self.name = name
        self.gender = None
        self.appearance_url = None
        
        # NOTE: We do NOT manually add buttons here because we use decorators below.
        # This fixes the duplicate button issue.

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)

    def _load_appearances(self, gender_code: str):
        apps = []
        try:
            with open('assets/profiles.csv', mode='r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['Sex'].upper() == gender_code:
                        apps.append(row['URL'])
        except Exception: 
            pass 
        return apps

    # --- STEP 1: GENDER SELECTION ---

    @discord.ui.button(label="Male", emoji="♂️", style=ButtonStyle.primary)
    async def male_btn(self, interaction: Interaction, button: Button):
        await self.process_gender(interaction, "M")

    @discord.ui.button(label="Female", emoji="♀️", style=ButtonStyle.danger)
    async def female_btn(self, interaction: Interaction, button: Button):
        await self.process_gender(interaction, "F")

    async def process_gender(self, interaction: Interaction, gender: str):
        self.gender = gender
        urls = self._load_appearances(gender)
        
        self.clear_items() # Clear gender buttons
        
        if not urls:
            # Fallback if no images found
            self.appearance_url = "https://i.imgur.com/6pRwl0k.jpeg"
            # Skip straight to modal button if no images
            confirm_btn = Button(label="Confirm Setup", style=ButtonStyle.success)
            confirm_btn.callback = self.on_confirm_appearance
            self.add_item(confirm_btn)
            await interaction.response.edit_message(view=self)
            return

        # 1. Default to first image
        self.appearance_url = urls[0]

        # 2. Build Select Menu
        options = []
        for i, url in enumerate(urls[:25]):
            options.append(SelectOption(label=f"Portrait {i+1}", value=url))
        
        select = Select(placeholder="Preview Appearance...", options=options)
        select.callback = self.on_select_appearance # Updates preview only
        self.add_item(select)

        # 3. Build Confirm Button
        confirm_btn = Button(label="Confirm Appearance", style=ButtonStyle.success, row=1)
        confirm_btn.callback = self.on_confirm_appearance # Moves to next step
        self.add_item(confirm_btn)
        
        # 4. Update Embed to show first image immediately
        embed = interaction.message.embeds[0]
        embed.description = f"Gender: **{'Male' if gender == 'M' else 'Female'}**\nSelect an appearance from the menu to preview it."
        embed.set_image(url=self.appearance_url)
        
        await interaction.response.edit_message(embed=embed, view=self)

    # --- STEP 2: PREVIEW & CONFIRM ---

    async def on_select_appearance(self, interaction: Interaction):
        """Updates the embed image without progressing state."""
        self.appearance_url = interaction.data['values'][0]
        
        embed = interaction.message.embeds[0]
        embed.set_image(url=self.appearance_url)
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_confirm_appearance(self, interaction: Interaction):
        """Triggered when user is happy with the preview."""
        await interaction.response.send_modal(IdeologyModal(self))

    # --- FINALIZATION ---

    async def complete_registration(self, interaction: Interaction, ideology: str):
        # 1. Register User
        await self.bot.database.users.register(
            self.user_id, str(interaction.guild.id), self.name, self.appearance_url, ideology
        )
        
        # 2. Initialize Skills
        sid = str(interaction.guild.id)
        await self.bot.database.skills.initialize(self.user_id, sid, 'mining', 'iron')
        await self.bot.database.skills.initialize(self.user_id, sid, 'fishing', 'desiccated')
        await self.bot.database.skills.initialize(self.user_id, sid, 'woodcutting', 'flimsy')
        
        # 3. Starter Pack
        await self.bot.database.users.modify_gold(self.user_id, 200)
        await self.bot.database.users.modify_stat(self.user_id, 'potions', 10)
        
        # 4. Handle Ideology Logic
        ideologies = await self.bot.database.social.get_all_by_server(sid)
        
        embed = discord.Embed(title="Registration Complete! 🎉", color=0x00FF00)
        embed.set_thumbnail(url=self.appearance_url)
        
        if ideology in ideologies:
            count = await self.bot.database.social.get_follower_count(ideology)
            await self.bot.database.social.update_followers(ideology, count + 1)
            embed.description = f"Welcome, **{self.name}**!\nYou have adopted **{ideology}** (Followers: {count+1})."
        else:
            await self.bot.database.social.create_ideology(self.user_id, sid, ideology)
            await self.bot.database.social.update_followers(ideology, 1)
            embed.description = f"Welcome, **{self.name}**!\nYou have founded a new ideology: **{ideology}**!"

        # Clear buttons
        await interaction.response.edit_message(embed=embed, view=None)
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


class IdeologyModal(Modal, title="Choose Your Path"):
    ideology = TextInput(label="Ideology Name", placeholder="e.g. The Order of Code", max_length=24, required=True)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        val = self.ideology.value.strip()
        
        if not re.match(r'^[A-Za-z0-9\s]+$', val):
            return await interaction.response.send_message("Invalid characters in ideology name.", ephemeral=True)
            
        await self.parent_view.complete_registration(interaction, val)

class PassiveAllocateView(View):
    def __init__(self, bot, user_id, user_data):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.points = user_data[20] # passive_points index
        
        # Stats Cache
        self.atk = user_data[9]
        self.defn = user_data[10]
        self.hp = user_data[12]
        
        self.update_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try: await self.message.delete()
        except: pass

    def update_buttons(self):
        disabled = (self.points <= 0)
        self.atk_btn.disabled = disabled
        self.def_btn.disabled = disabled
        self.hp_btn.disabled = disabled
        
        self.atk_btn.label = f"Attack ({self.atk})"
        self.def_btn.label = f"Defense ({self.defn})"
        self.hp_btn.label = f"Max HP ({self.hp})"

    async def process_allocation(self, interaction: Interaction, stat: str):
        if self.points <= 0: return
        
        await self.bot.database.users.modify_stat(self.user_id, stat, 1)
        
        # Update local state
        if stat == 'attack': self.atk += 1
        elif stat == 'defence': self.defn += 1
        elif stat == 'max_hp': self.hp += 1
        
        self.points -= 1
        await self.bot.database.users.set_passive_points(self.user_id, str(interaction.guild.id), self.points)
        
        self.update_buttons()
        
        embed = interaction.message.embeds[0]
        embed.description = f"**Points Remaining:** {self.points}\n\nSelect a stat to upgrade."
        
        if self.points == 0:
            embed.description = "✅ All points allocated."
            self.stop()
            self.bot.state_manager.clear_active(self.user_id)
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⚔️", style=ButtonStyle.danger)
    async def atk_btn(self, interaction: Interaction, button: Button):
        await self.process_allocation(interaction, 'attack')

    @discord.ui.button(emoji="🛡️", style=ButtonStyle.primary)
    async def def_btn(self, interaction: Interaction, button: Button):
        await self.process_allocation(interaction, 'defence')

    @discord.ui.button(emoji="❤️", style=ButtonStyle.success)
    async def hp_btn(self, interaction: Interaction, button: Button):
        await self.process_allocation(interaction, 'max_hp')