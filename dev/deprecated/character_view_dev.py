import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, Message
import asyncio
import random
import json
from discord.ui import View, Button

"""
Index	Attribute Description
0	Unique ID
1	User ID
2	Server ID
3	Player Name
4	Level
5	Experience
6	Gold
7	Image URL (for player image)
8	Ideology
9	Attack
10	Defense
11	Current HP
12	Maximum HP
13	Last Rest Time
14	Last Propagate Time
15	Ascension Level
16	Potion Count
17	Last Checkin Time
18  Created at
19  Refinement runes
20  Passive Points
21  Potential runes
22  Curios
23  Curious purchased
24  Last Combat
25  Dragon Key
26  Angel Key
27  Imbue runes
"""

class WeaponInventoryView(View):
    def __init__(self, bot, interaction: Interaction, items, player_name: str):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.interaction = interaction
        self.user_id = str(interaction.user.id)
        self.items = items
        self.player_name = player_name
        self.items_per_page = 5
        self.current_page = 0
        self.selected_item = None
        self.total_pages = (len(items) + self.items_per_page - 1) // self.items_per_page
        self.build_view()

    def build_view(self):
        """Build or rebuild the view based on the current state."""
        self.clear_items()
        
        if self.selected_item is None:
            # Main inventory view with pagination
            start_idx = self.current_page * self.items_per_page
            items_to_display = self.items[start_idx:start_idx + self.items_per_page]

            for idx, item in enumerate(items_to_display):
                button = Button(label=f"{idx + 1}", style=discord.ButtonStyle.primary)
                button.callback = self.create_item_callback(item, idx)
                self.add_item(button)

            # Add navigation buttons
            prev_button = Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=self.current_page == 0)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)

            next_button = Button(label="Next", style=discord.ButtonStyle.secondary, disabled=self.current_page >= self.total_pages - 1)
            next_button.callback = self.next_page
            self.add_item(next_button)

            close_button = Button(label="Close", style=discord.ButtonStyle.danger)
            close_button.callback = self.close_view
            self.add_item(close_button)
        else:
            # Item detail view with action buttons
            equip_button = Button(label="Equip", style=discord.ButtonStyle.success, emoji="⚔️")
            equip_button.callback = self.equip_callback
            self.add_item(equip_button)

            forge_button = Button(label="Forge", style=discord.ButtonStyle.primary, emoji="🔨")
            forge_button.callback = self.forge_callback
            self.add_item(forge_button)

            refine_button = Button(label="Refine", style=discord.ButtonStyle.primary, emoji="⚙️")
            refine_button.callback = self.refine_callback
            self.add_item(refine_button)

            discard_button = Button(label="Discard", style=discord.ButtonStyle.danger, emoji="🗑️")
            discard_button.callback = self.discard_callback
            self.add_item(discard_button)

            back_button = Button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️")
            back_button.callback = self.back_callback
            self.add_item(back_button)

    def create_item_callback(self, item, idx):
        """Create a callback for selecting an item."""
        async def callback(interaction: Interaction):
            if interaction.user.id != self.interaction.user.id:
                await interaction.response.send_message("This inventory is not yours!", ephemeral=True)
                return
            self.selected_item = item
            embed = await self.build_embed()
            self.build_view()
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    async def previous_page(self, interaction: Interaction):
        """Go to the previous page."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This inventory is not yours!", ephemeral=True)
            return
        self.current_page -= 1
        embed = await self.build_embed()
        self.build_view()
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: Interaction):
        """Go to the next page."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This inventory is not yours!", ephemeral=True)
            return
        self.current_page += 1
        embed = await self.build_embed()
        self.build_view()
        await interaction.response.edit_message(embed=embed, view=self)

    async def close_view(self, interaction: Interaction):
        """Close the inventory view."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This inventory is not yours!", ephemeral=True)
            return
        self.bot.state_manager.clear_active(self.user_id)
        await interaction.response.defer()
        await interaction.message.delete()
        self.stop()

    async def back_callback(self, interaction: Interaction):
        """Go back to the main inventory view."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This inventory is not yours!", ephemeral=True)
            return
        self.selected_item = None
        embed = await self.build_embed()
        self.build_view()
        await interaction.response.edit_message(embed=embed, view=self)

    async def equip_callback(self, interaction: Interaction):
        """Handle equipping the selected item."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This inventory is not yours!", ephemeral=True)
            return
        embed = discord.Embed(title="Switch Weapon", color=0xFFCC00)
        equipped_item = await self.bot.database.get_equipped_item(self.user_id)
        item_name = self.selected_item[1]
        
        if equipped_item and equipped_item[0] == self.selected_item[0]:
            embed.add_field(name="But why", value=f"You already have **{item_name}** equipped! Returning to main menu...", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
            await asyncio.sleep(3)
            embed = await self.build_embed()
            self.selected_item = None
            self.build_view()
            await interaction.message.edit(embed=embed, view=self)
            return

        if equipped_item:
            current_equipped_name = equipped_item[2]
            embed.description = f"Unequip **{current_equipped_name}** and equip **{item_name}** instead?"
            view = ConfirmView(self.bot, self.interaction, self.equip_action, item_name)
        else:
            view = ConfirmView(self.bot, self.interaction, self.equip_action, item_name)
            embed.description = f"Equip **{item_name}**?"
        
        await interaction.response.edit_message(embed=embed, view=view)

    async def equip_action(self, interaction: Interaction, item_name: str):
        """Perform the equip action after confirmation."""
        item_id = self.selected_item[0]
        await self.bot.database.equip_item(self.user_id, item_id)
        embed = discord.Embed(title="Equip", color=0x00FF00)
        embed.add_field(name="Success", value=f"Equipped **{item_name}**. Returning to main menu...", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
        await asyncio.sleep(3)
        embed = await self.build_embed()
        self.selected_item = None
        self.build_view()
        await interaction.message.edit(embed=embed, view=self)

    async def forge_callback(self, interaction: Interaction):
        """Handle forging the selected item."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This inventory is not yours!", ephemeral=True)
            return
        server_id = str(self.interaction.guild.id)
        embed = await self.forge_item(interaction, self.selected_item, self.user_id, server_id)
        await interaction.response.edit_message(embed=embed, view=None)
        await asyncio.sleep(5)
        embed = await self.build_embed()
        self.selected_item = None
        self.build_view()
        await interaction.message.edit(embed=embed, view=self)

    async def refine_callback(self, interaction: Interaction):
        """Handle refining the selected item."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This inventory is not yours!", ephemeral=True)
            return
        server_id = str(self.interaction.guild.id)
        embed = await self.refine_item(interaction, self.selected_item, self.user_id, server_id)
        await interaction.response.edit_message(embed=embed, view=None)
        await asyncio.sleep(5)
        embed = await self.build_embed()
        self.selected_item = None
        self.build_view()
        await interaction.message.edit(embed=embed, view=self)

    async def discard_callback(self, interaction: Interaction):
        """Handle discarding the selected item."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This inventory is not yours!", ephemeral=True)
            return
        item_name = self.selected_item[1]
        embed = discord.Embed(title="Confirm Discard", description=f"Are you sure you want to discard **{item_name}**? This action cannot be undone.", color=0xFF0000)
        view = ConfirmView(self.bot, self.interaction, self.discard_action, item_name)
        await interaction.response.edit_message(embed=embed, view=view)

    async def discard_action(self, interaction: Interaction, item_name: str):
        """Perform the discard action after confirmation."""
        item_id = self.selected_item[0]
        await self.bot.database.discard_item(item_id)
        embed = discord.Embed(title="Discard", color=0x00FF00)
        embed.add_field(name="Success", value=f"Discarded **{item_name}**. Returning to main menu...", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
        await asyncio.sleep(3)
        self.items = await self.bot.database.fetch_user_items(self.user_id)
        self.total_pages = (len(self.items) + self.items_per_page - 1) // self.items_per_page
        self.current_page = min(self.current_page, max(0, self.total_pages - 1))
        embed = await self.build_embed()
        self.selected_item = None
        self.build_view()
        await interaction.message.edit(embed=embed, view=self)

    async def build_embed(self):
        """Build the embed for the current view state."""
        embed = discord.Embed(title="📦", description=f"{self.player_name}'s Weapons (Page {self.current_page + 1}/{self.total_pages}):", color=0x00FF00)
        embed.set_thumbnail(url="https://i.imgur.com/AnlbnbO.jpeg")
        
        if self.selected_item:
            item_name = self.selected_item[1]
            item_level = self.selected_item[2]
            item_attack = self.selected_item[3] if len(self.selected_item) > 4 else 0
            item_defence = self.selected_item[4] if len(self.selected_item) > 5 else 0
            item_rarity = self.selected_item[5] if len(self.selected_item) > 6 else 0
            item_passive = self.selected_item[6]
            embed.description = f"**{item_name}** (Level {item_level}):"
            embed.add_field(name="Attack", value=item_attack, inline=True)
            embed.add_field(name="Defence", value=item_defence, inline=True)
            embed.add_field(name="Rarity", value=item_rarity, inline=True)
            embed.add_field(name="Passive", value=item_passive, inline=False)
            if item_passive != "none":
                effect_description = self.get_passive_effect(item_passive)
                embed.add_field(name="Effect", value=effect_description, inline=False)
            embed.add_field(name="Item Guide", value="Use the buttons below to interact with the item.", inline=False)
        else:
            start_idx = self.current_page * self.items_per_page
            items_to_display = self.items[start_idx:start_idx + self.items_per_page]
            items_display_string = ""
            equipped_item = await self.bot.database.get_equipped_item(self.user_id)
            for idx, item in enumerate(items_to_display):
                is_equipped = equipped_item and (equipped_item[0] == item[0])
                items_display_string += f"{idx + 1}: {item[1]} (Level {item[2]}) {'[E]' if is_equipped else ''}\n"
            embed.add_field(name="Weapons:", value=items_display_string.strip() or "No weapons on this page.", inline=False)
            embed.add_field(name="Instructions", value="Click a number to view an item, or use navigation buttons.", inline=False)
        
        return embed
    
    def get_passive_effect(self, passive: str) -> str:
        """Return the description of a passive effect."""
        passive_messages = {
            "burning": "Increases your maximum hit (1d6).",
            "flaming": "Increases your maximum hit. (2d6)",
            "scorching": "Increases your maximum hit. (3d6)",
            "incinerating": "Increases your maximum hit. (4d6)",
            "carbonising": "Increases your maximum hit. (5d6)",
            "poisonous": "Additional damage on misses. (3d6)",
            "noxious": "Additional damage on misses. (4d6)",
            "venomous": "Additional damage on misses. (5d6)",
            "toxic": "Additional damage on misses. (6d6)",
            "lethal": "Additional damage on misses. (7d6)",
            "polished": "Reduce monster's defence. (5%)",
            "honed": "Reduce monster's defence. (10%)",
            "gleaming": "Reduce monster's defence. (15%)",
            "tempered": "Reduce monster's defence. (20%)",
            "flaring": "Reduce monster's defence. (25%)",
            "sparking": "Additional damage on normal hits. (1d6)",
            "shocking": "Additional damage on normal hits. (2d6)",
            "discharging": "Additional damage on normal hits. (3d6)",
            "electrocuting": "Additional damage on normal hits. (4d6)",
            "vapourising": "Additional damage on normal hits. (5d6)",
            "sturdy": "Additional defence. (+3)",
            "reinforced": "Additional defence. (+6)",
            "thickened": "Additional defence. (+9)",
            "impregnable": "Additional defence. (+12)",
            "impenetrable": "Additional defence. (+15)",
            "piercing": "Additional crit chance. (3%)",
            "keen": "Additional crit chance. (6%)",
            "incisive": "Additional crit chance. (9%)",
            "puncturing": "Additional crit chance. (12%)",
            "penetrating": "Additional crit chance. (15%)",
            "strengthened": "Culling strike. (5%)",
            "forceful": "Culling strike. (10%)",
            "overwhelming": "Culling strike. (15%)",
            "devastating": "Culling strike. (20%)",
            "catastrophic": "Culling strike. (25%)",
            "accurate": "Increased accuracy. (3%)",
            "precise": "Increased accuracy. (6%)",
            "sharpshooter": "Increased accuracy. (9%)",
            "deadeye": "Increased accuracy. (12%)",
            "bullseye": "Increased accuracy. (15%)",
            "echo": "Echo normal hits. (10% dmg)",
            "echoo": "Echo normal hits. (20% dmg)",
            "echooo": "Echo normal hits. (30% dmg)",
            "echoooo": "Echo normal hits. (40% dmg)",
            "echoes": "Echo normal hits. (50% dmg)"
        }
        return passive_messages.get(passive, "No effect.")

    async def upgrade_passive(self, current_passive: str) -> str:
        """Upgrade the current passive to a stronger version."""
        passive_upgrade_table = {
            "burning": "flaming",
            "flaming": "scorching",
            "scorching": "incinerating",
            "incinerating": "carbonising",
            "poisonous": "noxious",
            "noxious": "venomous",
            "venomous": "toxic",
            "toxic": "lethal",
            "polished": "honed",
            "honed": "gleaming",
            "gleaming": "tempered",
            "tempered": "flaring",
            "sparking": "shocking",
            "shocking": "discharging",
            "discharging": "electrocuting",
            "electrocuting": "vapourising",
            "sturdy": "reinforced",
            "reinforced": "thickened",
            "thickened": "impregnable",
            "impregnable": "impenetrable",
            "piercing": "keen",
            "keen": "incisive",
            "incisive": "puncturing",
            "puncturing": "penetrating",
            "strengthened": "forceful",
            "forceful": "overwhelming",
            "overwhelming": "devastating",
            "devastating": "catastrophic",
            "accurate": "precise",
            "precise": "sharpshooter",
            "sharpshooter": "deadeye",
            "deadeye": "bullseye",
            "echo": "echoo",
            "echoo": "echooo",
            "echooo": "echoooo",
            "echoooo": "echoes"
        }
        return passive_upgrade_table.get(current_passive, current_passive)

    async def on_timeout(self):
        """Handle view timeout."""
        self.bot.state_manager.clear_active(self.user_id)
        if self.interaction.message:
            await self.interaction.message.delete()
        self.stop()

class ConfirmView(View):
    def __init__(self, bot, interaction: Interaction, action_callback, item_name: str):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.interaction = interaction
        self.action_callback = action_callback
        self.item_name = item_name
        self.add_item(Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅", callback=self.confirm))
        self.add_item(Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", callback=self.cancel))

    async def confirm(self, interaction: Interaction):
        """Handle confirm button."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This action is not yours!", ephemeral=True)
            return
        await self.action_callback(interaction, self.item_name)

    async def cancel(self, interaction: Interaction):
        """Handle cancel button."""
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("This action is not yours!", ephemeral=True)
            return
        embed = discord.Embed(title="Cancelled", description="Action cancelled. Returning to main menu...", color=0xFFCC00)
        await interaction.response.edit_message(embed=embed, view=None)
        await asyncio.sleep(3)
        view = WeaponInventoryView(self.bot, self.interaction, await self.bot.database.fetch_user_items(str(self.interaction.user.id)), self.interaction.user.name)
        embed = await view.build_embed()
        await interaction.message.edit(embed=embed, view=view)

    async def on_timeout(self):
        """Handle view timeout."""
        self.bot.state_manager.clear_active(str(self.interaction.user.id))
        if self.interaction.message:
            await self.interaction.message.delete()
        self.stop()

class Character(commands.Cog, name="character"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.active_users = {}  # Dictionary to track active users
        
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_hp.is_running():
            print('Starting self heal')
            self.check_hp.start()

    @tasks.loop(minutes=5)
    async def check_hp(self):
        """Check and increment current_hp for all users every hour."""
        # Fetch all users from the database
        users = await self.bot.database.fetch_all_users()

        for user in users:
            user_id = user[1] 
            current_hp = user[11]
            max_hp = user[12]
            scaling = int(max_hp / 30)
            if current_hp < max_hp:
                # Update current_hp by incrementing it by 1
                # print(f'healing {user_id} by 1')
                new_hp = current_hp + 1 + scaling
                if (new_hp > max_hp):
                    new_hp = max_hp
                
                await self.bot.database.update_player_hp(user_id, new_hp)

    @app_commands.command(name="stats", description="Get your character's stats.")
    async def get_stats(self, interaction: Interaction) -> None:
        """Fetch and display the character's stats."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if existing_user:
            embed = discord.Embed(
                title=f"{existing_user[3]}'s Stats",
                color=0x00FF00,
            )
            embed.set_thumbnail(url=existing_user[7])
            equipped_item = await self.bot.database.get_equipped_item(user_id)
            equipped_accessory = await self.bot.database.get_equipped_accessory(user_id)
            equipped_armor = await self.bot.database.get_equipped_armor(user_id)

            # Calculate base attack and defense
            base_attack = existing_user[9]
            base_defense = existing_user[10]
            add_atk = 0
            add_def = 0
            add_rar = 0
            crit = 0
            ward = 0
            block = 0
            evasion = 0
            if equipped_item:
                add_atk += equipped_item[4]
                add_def += equipped_item[5]
                add_rar += equipped_item[6]
            if equipped_accessory:
                add_atk += equipped_accessory[4]
                add_def += equipped_accessory[5]
                add_rar += equipped_accessory[6]
                # Add crit and ward if they exist
                crit = equipped_accessory[8]
                ward = equipped_accessory[7]
            if equipped_armor:
                ward = equipped_armor[6]
                block = equipped_armor[4]
                evasion = equipped_armor[5]

            # Fetch experience table
            with open('assets/exp.json') as file:
                exp_table = json.load(file)

            current_level = existing_user[4]  # Assuming level is at index 4
            current_exp = existing_user[5]      # Current experience
            exp_needed = exp_table["levels"].get(str(current_level), 0)  # Fetch the necessary EXP for this level

            # Calculate experience percentage
            if exp_needed > 0:
                exp_percentage = (current_exp / exp_needed) * 100
            else:
                exp_percentage = 100  # Full EXP if already max level or no exp required
            # Add the character stats to the embed
            embed.add_field(name="Level ⭐", value=existing_user[4], inline=True)
            embed.add_field(name="Experience ✨", value=f"{current_exp:,} ({exp_percentage:.2f}%)", inline=True)
            attack_display = f"{base_attack} (+{add_atk})" if add_atk > 0 else f"{base_attack}"
            embed.add_field(name="Attack ⚔️", value=attack_display, inline=True)
            defense_display = f"{base_defense} (+{add_def})" if add_def > 0 else f"{base_defense}"
            embed.add_field(name="Defense 🛡️", value=defense_display, inline=True)
            if (crit > 0):
                embed.add_field(name="Crit 🗡️", value=f"{crit}%", inline=True)
            if (block > 0): 
                embed.add_field(name="Block 🧱", value=f"{block}", inline=True)
            if (evasion > 0): 
                embed.add_field(name="Evasion 🏃‍♂️", value=f"{evasion}", inline=True)
            if (ward > 0): 
                embed.add_field(name="Ward 🔮", value=f"{ward}", inline=True)
            if (add_rar > 0):
                embed.add_field(name="Rarity 🪄", value=f"{add_rar}%", inline=True)
            embed.add_field(name="Current HP ❤️", value=existing_user[11], inline=True)
            embed.add_field(name="Maximum HP ❤️", value=existing_user[12], inline=True) 
            ascension = existing_user[15]
            if (ascension > 0):
                embed.add_field(name="Ascension 🌟", value=ascension, inline=True)

            await interaction.response.send_message(embed=embed)
            message: Message = await interaction.original_response()
            await asyncio.sleep(10)
            await message.delete()
        else:
            if not await self.bot.check_user_registered(interaction, existing_user):
                return


    @app_commands.command(name="inventory", description="Check your inventory status.")
    async def inventory(self, interaction: Interaction) -> None:
        """Fetch and display the user's inventory status."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        # Fetching inventory data
        weapons_count = await self.bot.database.count_user_weapons(user_id)
        accessories_count = await self.bot.database.count_user_accessories(user_id)
        arms = await self.bot.database.fetch_user_armors(user_id)
        runes_of_potential = existing_user[21]  # index for runes of potential
        runes_of_refinement = existing_user[19]  # index for runes of refinement
        runes_of_imbuing = existing_user[27] # imbue runes
        potions_count = existing_user[16]  # index for potion count
        dragon_keys = existing_user[25] # dragon keys
        angel_keys = existing_user[26]
        curio_count = existing_user[22]
        gold_count = existing_user[6]  # index for gold

        # Create an embed to display inventory information
        embed = discord.Embed(
            title=(f"{existing_user[3]}'s Inventory\n"
            f"Gold 💰: **{gold_count:,}**"),
            color=0x00FF00,
        )
        embed.add_field(name="Weapons ⚔️", value=f"{weapons_count:,}", inline=True)
        embed.add_field(name="Accessories 📿", value=f"{accessories_count:,}", inline=True)
        embed.add_field(name="Armors 🛡️", value=f"{len(arms):,}", inline=True)
        embed.add_field(name="Runes of Potential 💎", value=f"{runes_of_potential:,}", inline=True)
        embed.add_field(name="Runes of Refinement 🔨", value=f"{runes_of_refinement:,}", inline=True)
        embed.add_field(name="Runes of Imbuing 🔅", value=f"{runes_of_imbuing:,}", inline=True)
        embed.add_field(name="Draconic Keys 🐉", value=f"{dragon_keys:,}", inline=True)
        embed.add_field(name="Angelic Keys 🪽", value=f"{angel_keys:,}", inline=True)
        embed.add_field(name="Potions 🍹", value=f"{potions_count:,}", inline=True)
        embed.add_field(name="Curios 🎁", value=f"{curio_count:,}", inline=True)
        # embed.add_field(name="Gold 💰", value=f"{gold_count:,}", inline=True)

        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        await asyncio.sleep(10)
        await message.delete()

    '''

    WEAPON HANDLING

    '''
    @app_commands.command(name="viewweps", description="View your character's weapons and modify them.")
    async def viewweapons(self, interaction: Interaction) -> None:
        """Fetch and display the character's weapons with pagination using Views."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Check if the user has any active operations
        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        items = await self.bot.database.fetch_user_items(user_id)
        if not items:
            await interaction.response.send_message("You peer into your weapon's pouch, it is empty.", ephemeral=True)
            return

        player_name = existing_user[3]
        self.bot.state_manager.set_active(user_id, "inventory")
        view = WeaponInventoryView(self.bot, interaction, items, player_name)
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)

    async def equip(self, interaction: Interaction, selected_item: tuple, new_equip: str, message, embed) -> None:
        """Equip an item."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            self.bot.state_manager.clear_active(user_id)
            return
                
        equipped_item = await self.bot.database.get_equipped_item(user_id)

        if equipped_item:
            current_equipped_id = equipped_item[0] 
            if selected_item[0] == current_equipped_id:
                embed.add_field(name="But why", value=(f"You already have **{new_equip}** equipped! "
                                                       " Returning to main menu..."), inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

            item_name = equipped_item[2]  # Assuming item_name is at index 2
            embed = discord.Embed(
                title="Switch weapon",
                description=f"Unequip **{item_name}** and equip **{new_equip}** instead?",
                color=0xFFCC00
            )
            await message.edit(embed=embed)
            await message.clear_reactions()
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def confirm_check(reaction, user):
                return (user == interaction.user and 
                        reaction.message.id == message.id 
                        and str(reaction.emoji) in ["✅", "❌"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)
                if str(reaction.emoji) == "❌":
                    return

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)  
                return

        item_id = selected_item[0]
        await self.bot.database.equip_item(user_id, item_id)
        embed.add_field(name="Equip", value=f"Equipped **{new_equip}**\nReturning to main menu...", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(3)

    async def discard(self, interaction: Interaction, selected_item: tuple, item_name: str, message, embed) -> None:
        """Discard an item."""
        item_id = selected_item[0]

        embed = discord.Embed(
            title="Confirm Discard",
            description=f"Are you sure you want to discard **{item_name}**? This action cannot be undone.",
            color=0xFF0000,
        )
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")  # Confirm discard
        await message.add_reaction("❌")  # Cancel discard

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["✅", "❌"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Cancel", value=f"Returning to main menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        await self.bot.database.discard_item(item_id)
        embed.add_field(name="Discard", 
                                     value=f"Discarded **{item_name}**. Returning to main menu...", 
                                     inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(3)


    async def forge_item(self, interaction: Interaction, selected_item: tuple, user_id: str, server_id: str, embed, message, current_page: int, selected_index: int) -> None:
        item_id = selected_item[0] # unique id of item
        item_name = selected_item[1]
        item_level = selected_item[2]
        # Fetch current item details
        item_details = await self.bot.database.fetch_item_by_id(item_id)
        
        if not item_details:
            await interaction.followup.send("Item not found.")
            return

        # Get the current state of the item
        forges_remaining = item_details[9]  # Index where `forges_remaining` is stored
        print(f'Forges remaining for item id {item_id}: {forges_remaining}')
        # Define the costs lookup based on the forges remaining
        base_success_rate = 0.8
        if item_level <= 40:
            costs = {
                3: (10, 10, 10, 100),
                2: (10, 10, 10, 400),
                1: (10, 10, 10, 1000),
            }
            cost_index = 6 - forges_remaining
            success_rate = base_success_rate - (3 - forges_remaining) * 0.05
            forges_data = {
                3: ('iron', 'oak', 'desiccated'),
                2: ('coal', 'willow', 'regular'),
                1: ('gold', 'mahogany', 'sturdy'),
            }
        elif 40 < item_level <= 80:    
            costs = {
                4: (25, 25, 25, 250),
                3: (25, 25, 25, 1000),
                2: (25, 25, 25, 2500),
                1: (25, 25, 25, 5000),
            }       
            forges_data = {
                4: ('iron', 'oak', 'desiccated'),
                3: ('coal', 'willow', 'regular'),
                2: ('gold', 'mahogany', 'sturdy'),
                1: ('platinum', 'magic', 'reinforced'),
            }
            cost_index = 7 - forges_remaining
            success_rate = base_success_rate - (4 - forges_remaining) * 0.05 
        else:
            costs = {
                5: (50, 50, 50, 500),
                4: (50, 50, 50, 2000),
                3: (50, 50, 50, 5000),
                2: (50, 50, 50, 10000),
                1: (50, 50, 50, 20000),
            }
            forges_data = {
                5: ('iron', 'oak', 'desiccated'),
                4: ('coal', 'willow', 'regular'),
                3: ('gold', 'mahogany', 'sturdy'),
                2: ('platinum', 'magic', 'reinforced'),
                1: ('idea', 'idea', 'titanium'),
            }
            cost_index = 8 - forges_remaining
            success_rate = base_success_rate - (5 - forges_remaining) * 0.05
        success_rate = max(0, min(success_rate, 1))
        # Check if there are forges remaining
        if forges_remaining == 0:
            embed.add_field(name="Forging", value=f"This item cannot be forged anymore.", inline=True)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return

        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]  # Fetch the amount of gold from existing_user

        # Resources from the mining, woodcutting, and fishing tables
        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)

        # Get the corresponding costs based on forges remaining
        ore_cost, wood_cost, bone_cost, gp_cost = costs[forges_remaining]
        print(mining_data)
        print(woodcutting_data)
        print(fishing_data)
        print(f'forge will cost {ore_cost} ore, {wood_cost} logs, {bone_cost} bones, {gp_cost} gp')
        print(f'mining_data[cost_index]: {mining_data[cost_index]}')

        if forges_remaining in forges_data:
            ore, logs, bones = forges_data[forges_remaining]
        else:
            ore, logs, bones = None, None, None
        # Check if the user has enough resources and gold
        if (mining_data[cost_index] < ore_cost or
            woodcutting_data[cost_index] < wood_cost or
            fishing_data[cost_index] < bone_cost or
            player_gp < gp_cost):
            embed.add_field(name="Forging", 
                            value=(f"You do not have enough resources to forge this item.\n"
                                   f"Forging costs:\n"
                                   f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                                   f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                                   f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                                   f"- GP cost: **{gp_cost}**\n"), 
                            inline=True)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return
        
        embed = discord.Embed(
            title="Forge",
            description=(f"You are about to forge **{item_name}**.\n"
                         f"Forging costs:\n"
                         f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                         f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                         f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                         f"- GP cost: **{gp_cost:,}**\n"
                         f"- Success rate: **{int(success_rate * 100)}%**\n"
                         "Do you want to continue?"),
            color=0xFFFF00
        )
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id 
                    and str(reaction.emoji) in ["✅", "❌"])
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Cancel", value=f"Returning to item menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        # Deduct the costs from the user's resources
        print('subtracting ore')
        if item_level <= 40:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if forges_remaining == 3 else 0,
                'coal': -ore_cost if forges_remaining == 2 else 0,
                'gold': -ore_cost if forges_remaining == 1 else 0,
                'platinum': 0,
                'idea': 0,
            })
        elif 40 < item_level <= 80:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if forges_remaining == 4 else 0,
                'coal': -ore_cost if forges_remaining == 3 else 0,
                'gold': -ore_cost if forges_remaining == 2 else 0,
                'platinum': -ore_cost if forges_remaining == 1 else 0,
                'idea': 0,
            })
        else:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if forges_remaining == 5 else 0,
                'coal': -ore_cost if forges_remaining == 4 else 0,
                'gold': -ore_cost if forges_remaining == 3 else 0,
                'platinum': -ore_cost if forges_remaining == 2 else 0,
                'idea': -ore_cost if forges_remaining == 1 else 0,
            })

        print('subtracting wood')
        if item_level <= 40:
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -ore_cost if forges_remaining == 3 else 0,
                'willow': -ore_cost if forges_remaining == 2 else 0,
                'mahogany': -ore_cost if forges_remaining == 1 else 0,
                'magic': 0,
                'idea': 0,
            })
        elif 40 < item_level <= 80:
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -ore_cost if forges_remaining == 4 else 0,
                'willow': -ore_cost if forges_remaining == 3 else 0,
                'mahogany': -ore_cost if forges_remaining == 2 else 0,
                'magic': -ore_cost if forges_remaining == 1 else 0,
                'idea': 0,
            })
        else:
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -ore_cost if forges_remaining == 5 else 0,
                'willow': -ore_cost if forges_remaining == 4 else 0,
                'mahogany': -ore_cost if forges_remaining == 3 else 0,
                'magic': -ore_cost if forges_remaining == 2 else 0,
                'idea': -ore_cost if forges_remaining == 1 else 0,
            })

        print('subtracting bones')
        if item_level <= 40:
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -ore_cost if forges_remaining == 3 else 0,
                'regular': -ore_cost if forges_remaining == 2 else 0,
                'sturdy': -ore_cost if forges_remaining == 1 else 0,
                'reinforced': 0,
                'titanium': 0,
            })
        elif 40 < item_level <= 80:
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -ore_cost if forges_remaining == 4 else 0,
                'regular': -ore_cost if forges_remaining == 3 else 0,
                'sturdy': -ore_cost if forges_remaining == 2 else 0,
                'reinforced': -ore_cost if forges_remaining == 1 else 0,
                'titanium': 0,
            })
        else:
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -ore_cost if forges_remaining == 5 else 0,
                'regular': -ore_cost if forges_remaining == 4 else 0,
                'sturdy': -ore_cost if forges_remaining == 3 else 0,
                'reinforced': -ore_cost if forges_remaining == 2 else 0,
                'titanium': -ore_cost if forges_remaining == 1 else 0,
            })
        print('subtracting gold')
        await self.bot.database.add_gold(user_id, -gp_cost)

        new_forges_remaining = forges_remaining - 1
        forge_success = random.random() <= success_rate  

        if forge_success:
            print('forge success')
            current_passive = item_details[7]  # Index where `passive` is stored
            
            if current_passive == "none":
                print('item has no passive')
                passives = [
                    "burning",
                    "poisonous",
                    "polished",
                    "sparking",
                    "sturdy",
                    "piercing",
                    "strengthened",
                    "accurate",
                    "echo"
                ]
                new_passive = random.choice(passives)
                print(f'Assigning {new_passive} to item {item_id}')
                await self.bot.database.update_item_passive(item_id, new_passive)
                embed.add_field(name="Forging success", 
                                value=(f"🎊 Congratulations! 🎊 " 
                                       f"**{item_name}** has gained the " 
                                       f"**{new_passive.capitalize()}** passive."), 
                                inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(7)
            else:
                print('item has passive, upgrade it')
                new_passive = await self.upgrade_passive(current_passive)
                print(f'new passive is {new_passive}')
                await self.bot.database.update_item_passive(item_id, new_passive)
                embed.add_field(name="Forging success", 
                                value=(f"🎊 Congratulations! 🎊 "
                                       f"**{item_name}**'s passive upgrades from **{current_passive.capitalize()}**"
                                       f" to **{new_passive.capitalize()}**."),
                                inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(7)
        else:
            print('forging failed')
            embed.add_field(name="Forging", 
                            value=(f"Forging failed! "
                                   f"Better luck next time. 🥺 \n"
                                   f"Returning to item menu..."),
                            inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
        
        await self.bot.database.update_item_forge_count(item_id, new_forges_remaining)

    def get_passive_effect(self, passive: str) -> str:
        passive_messages = {
            "burning": "Increases your maximum hit (1d6).",
            "flaming": "Increases your maximum hit. (2d6)",
            "scorching": "Increases your maximum hit. (3d6)",
            "incinerating": "Increases your maximum hit. (4d6)",
            "carbonising": "Increases your maximum hit. (5d6)",
            
            "poisonous": "Additional damage on misses. (3d6)",
            "noxious": "Additional damage on misses. (4d6)",
            "venomous": "Additional damage on misses. (5d6)",
            "toxic": "Additional damage on misses. (6d6)",
            "lethal": "Additional damage on misses. (7d6)",
            
            "polished": "Reduce monster's defence. (5%)",
            "honed": "Reduce monster's defence. (10%)",
            "gleaming": "Reduce monster's defence. (15%)",
            "tempered": "Reduce monster's defence. (20%)",
            "flaring": "Reduce monster's defence. (25%)",
            
            "sparking": "Additional damage on normal hits. (1d6)",
            "shocking": "Additional damage on normal hits. (2d6)",
            "discharging": "Additional damage on normal hits. (3d6)",
            "electrocuting": "Additional damage on normal hits. (4d6)",
            "vapourising": "Additional damage on normal hits. (5d6)",
            
            "sturdy": "Additional defence. (+3)",
            "reinforced": "Additional defence. (+6)",
            "thickened": "Additional defence. (+9)",
            "impregnable": "Additional defence. (+12)",
            "impenetrable": "Additional defence. (+15)",
            
            "piercing": "Additional crit chance. (3%)",
            "keen": "Additional crit chance. (6%)",
            "incisive": "Additional crit chance. (9%)",
            "puncturing": "Additional crit chance. (12%)",
            "penetrating": "Additional crit chance. (15%)",
            
            "strengthened": "Culling strike. (5%)",
            "forceful": "Culling strike. (10%)",
            "overwhelming": "Culling strike. (15%)",
            "devastating": "Culling strike. (20%)",
            "catastrophic": "Culling strike. (25%)",
            
            "accurate": "Increased accuracy. (3%)",
            "precise": "Increased accuracy. (6%)",
            "sharpshooter": "Increased accuracy. (9%)",
            "deadeye": "Increased accuracy. (12%)",
            "bullseye": "Increased accuracy. (15%)",
            
            "echo": "Echo normal hits. (10% dmg)",
            "echoo": "Echo normal hits. (20% dmg)",
            "echooo": "Echo normal hits. (30% dmg)",
            "echoooo": "Echo normal hits. (40% dmg)",
            "echoes": "Echo normal hits. (50% dmg)"
        }
        return passive_messages.get(passive, "No effect.")
    
    async def refine_item(self, interaction: Interaction, 
                          selected_item: tuple, 
                          user_id: str, server_id: str,
                          embed,
                          message,
                          current_page: int,
                          selected_index: int) -> None:
        item_id = selected_item[0]  # unique id of item
        item_name = selected_item[1]
        item_level = selected_item[2]
        # Fetch current item details
        item_details = await self.bot.database.fetch_item_by_id(item_id)
        
        if not item_details:
            await interaction.followup.send("Item not found.")
            return

        # Get the current state of the item
        refines_remaining = item_details[10]  # Assuming refines_remaining is at index 10
        player_gold = await self.bot.database.fetch_user_gold(user_id, server_id)
        refinement_runes = await self.bot.database.fetch_refinement_runes(user_id)

        if refines_remaining <= 0:
            if refinement_runes > 0:
                embed = discord.Embed(
                    title="Apply Rune of Refinement?",
                    description=(f"**{item_name}** has no refine attempts remaining.\n"
                                 f"Do you want to use a **Rune of Refinement** to add a refining attempt?\n"
                                 f"(You have {refinement_runes} rune(s) available)"),
                    color=0xFFCC00
                )
                await message.clear_reactions()
                await message.edit(embed=embed)

                await message.add_reaction("✅")
                await message.add_reaction("❌")

                def confirm_check(reaction, user):
                    return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

                    if str(reaction.emoji) == "✅":
                        await self.bot.database.update_refinement_runes(user_id, -1)
                        await self.bot.database.update_item_refine_count(item_id, 1)
                        embed.add_field(name="Rune of Refinement",
                                       value=(f"You have successfully applied a **Rune of Refinement**!\n"
                                              f"{item_name} now has **1** refine remaining. Returning to item menu..."),
                                       inline=False)
                        refines_remaining = 1
                        await message.edit(embed=embed)
                        await asyncio.sleep(5)
                    elif str(reaction.emoji) == "❌":
                        embed.add_field(name="Rune of Refinement",
                                        value=(f"You chose not to apply a Rune of Refinement.\nReturning to item menu..."),
                                        inline=False)
                        await message.edit(embed=embed)
                        await asyncio.sleep(5)
                        return

                except asyncio.TimeoutError:
                    self.bot.state_manager.clear_active(interaction.user.id)  
                    return
            return

        # Determine cost of the refinement
        if item_level <= 40:
            refine_costs = [1000, 6000, 10000]  
            cost = refine_costs[3 - refines_remaining]
        elif 40 < item_level <= 80:    
            refine_costs = [5000, 15000, 25000, 50000]  
            cost = refine_costs[4 - refines_remaining]
        else:
            refine_costs = [10000, 30000, 50000, 100000, 200000]
            cost = refine_costs[5 - refines_remaining]
        embed = discord.Embed(
            title="Confirm Refinement",
            description=f"You are about to refine **{item_name}**.\n"
                        f"Cost: **{cost:,} GP**\n"
                        f"Refines Remaining: **{refines_remaining}**\n"
                        f"Stats are granted randomly **with a chance to grant no stats.**\n"
                        "Do you want to proceed?",
            color=0xFFCC00
        )
        embed.set_thumbnail(url="https://i.imgur.com/AnlbnbO.jpeg")
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def confirm_check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Refining", value=f"Refinement cancelled. Returning to item menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(5)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return
        
        if player_gold < cost:
            embed.add_field(name="Refining", value=f"You do not have enough gold. Returning to item menu...", inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
            return

        await self.bot.database.update_user_gold(user_id, player_gold - cost)

        embed.add_field(name="Refining", value=f"You chose to refine {item_name}.", inline=False)
        await message.edit(embed=embed)
        
        attack_roll = random.randint(0, 100) < 80
        defense_roll = random.randint(0, 100) < 50
        rarity_roll = random.randint(0, 100) < 20

        attack_modifier = 0
        defense_modifier = 0
        rarity_modifier = 0
        max_range = int(item_level / 10) + 2
        if attack_roll:
            attack_modifier = random.randint(2, max_range)
            await self.bot.database.increase_item_attack(item_id, attack_modifier) 
        else:
            attack_modifier = 1
            await self.bot.database.increase_item_attack(item_id, attack_modifier) 
        
        if defense_roll:
            defense_modifier = random.randint(2, max_range)
            await self.bot.database.increase_item_defence(item_id, defense_modifier) 
        else:
            defense_modifier = 1
            await self.bot.database.increase_item_defence(item_id, defense_modifier)  

        if rarity_roll:
            rarity_modifier = random.randint(5, max_range * 5)
            await self.bot.database.update_item_rarity(item_id, rarity_modifier)

        await self.bot.database.update_item_refine_count(item_id, refines_remaining - 1)

        result_message = []
        if attack_modifier > 0:
            result_message.append(f"Attack increased by **{attack_modifier}**!")
        if defense_modifier > 0:
            result_message.append(f"Defense increased by **{defense_modifier}**!")
        if rarity_modifier > 0:
            result_message.append(f"Rarity increased by **{rarity_modifier}**!")

        if not result_message:
            embed.add_field(name="Refining", value=f"The refinement was successful, but no stats were upgraded. Returning to item menu...", inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
        else:
            embed.add_field(name="Refining", value=("\n".join(result_message) + "\nReturning to item menu..."), inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)

    ''' 

    ACCESSORY HANDLING

    '''            

    @app_commands.command(name="accessory", description="View your character's accessories and modify them.")
    async def accessory(self, interaction: Interaction) -> None:
        """Fetch and display the character's accessories with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        
        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        accessories = await self.bot.database.fetch_user_accessories(user_id)

        if not accessories:
            await interaction.response.send_message("You check your accessory pouch, it is empty.")
            return

        player_name = existing_user[3]
        embed = discord.Embed(
            title=f"📿",
            description=f"{player_name}'s Accessories:",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/yzQDtNg.jpeg")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")  # Set inventory as active operation

        # Pagination setup
        items_per_page = 5
        total_pages = (len(accessories) + items_per_page - 1) // items_per_page  # Ceiling division
        current_page = 0
        number_emojis = ["❌", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        while True:
            accessories = await self.bot.database.fetch_user_accessories(user_id)
            total_pages = (len(accessories) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1)  # Ensure current_page is valid
            embed.description = f"{player_name}'s Accessories (Page {current_page + 1}/{total_pages}):"
            
            if not accessories:
                await interaction.followup.send("You check your accessory pouch, it is empty.")
                break

            accessories.sort(key=lambda acc: acc[3], reverse=True)  # Sort by item_level at index 3
            start_idx = current_page * items_per_page
            accessories_to_display = accessories[start_idx:start_idx + items_per_page]
            await message.clear_reactions()
            embed.clear_fields()
            accessories_display_string = ""

            for index, accessory in enumerate(accessories_to_display):
                accessory_name = accessory[2]  # item_name is at index 2
                accessory_level = accessory[3]  # item_level is at index 3
                is_equipped = accessory[10]  # is_equipped is at index 10

                # Append accessory details to the display string
                accessories_display_string += (
                    f"{number_emojis[index + 1]}: "
                    f"{accessory_name} (Level {accessory_level})"
                    f"{' [E]' if is_equipped else ''}\n"
                )

            # Add a single field for all accessories
            embed.add_field(
                name="Accessories:",
                value=accessories_display_string.strip(),
                inline=False
            )

            # Instructions for user
            embed.add_field(
                name="Instructions",
                value=(f"[ℹ️] Select an accessory to interact with.\n"
                       f"[◀️] Previous page | [▶️] Next page | [❌] Close interface."),
                inline=False
            )
            await message.edit(embed=embed)

            # Add reactions: number emojis for items, navigation, and exit
            for i in range(len(accessories_to_display) + 1):
                await message.add_reaction(number_emojis[i])
            if current_page > 0:
                await message.add_reaction("◀️")
            if current_page < total_pages - 1:
                await message.add_reaction("▶️")

            def check(reaction, user):
                return (user == interaction.user
                        and reaction.message.id == message.id
                        and str(reaction.emoji) in number_emojis + ["◀️", "▶️"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                reaction_str = str(reaction.emoji)
                
                if reaction_str == "◀️" and current_page > 0:
                    current_page -= 1
                    continue
                elif reaction_str == "▶️" and current_page < total_pages - 1:
                    current_page += 1
                    continue
                elif reaction_str == "❌":
                    await message.delete()
                    self.bot.state_manager.clear_active(user_id)
                    break
                
                selected_index = number_emojis.index(reaction_str) - 1
                if selected_index >= 0:
                    selected_accessory = accessories_to_display[selected_index]
                    print(f'Selected accessory: {selected_accessory}')
                    # Display selected accessory details
                    accessory_name = selected_accessory[2]
                    accessory_level = selected_accessory[3]
                    accessory_attack = selected_accessory[4]
                    accessory_defence = selected_accessory[5]
                    accessory_rarity = selected_accessory[6]
                    accessory_ward = selected_accessory[7]
                    accessory_crit = selected_accessory[8]
                    accessory_passive = selected_accessory[9]
                    potential_lvl = selected_accessory[12]
                    passive_effect = self.get_accessory_passive_effect(accessory_passive, potential_lvl)

                    embed.description = f"**{accessory_name}** (Level {accessory_level}):"
                    embed.clear_fields()
                    if accessory_attack > 0:
                        embed.add_field(name="Attack", value=accessory_attack, inline=True)
                    elif accessory_defence > 0:
                        embed.add_field(name="Defense", value=accessory_defence, inline=True)
                    elif accessory_rarity > 0:
                        embed.add_field(name="Rarity", value=accessory_rarity, inline=True)
                    elif accessory_ward > 0:
                        embed.add_field(name="Ward", value=accessory_ward, inline=True)
                    elif accessory_crit > 0:
                        embed.add_field(name="Critical Chance", value=accessory_crit, inline=True)

                    if accessory_passive != "none":
                        embed.add_field(name="Passive", value=accessory_passive + f" ({potential_lvl})", inline=False)
                        embed.add_field(name="Passive Description", value=passive_effect, inline=False)
                    else:
                        embed.add_field(name="Passive", value="🪄 to unlock!", inline=False)

                    potential_guide = (
                        "💎 to equip.\n"
                        "🪄 to unlock/improve potential.\n"
                        "🗑️ to discard.\n"
                        "◀️ to go back."
                    )
                    embed.add_field(name="Accessory Guide", value=potential_guide, inline=False)
                    await message.edit(embed=embed)
                    await message.clear_reactions()

                    action_reactions = ["💎", "🪄", "🗑️", "◀️"]
                    for emoji in action_reactions:
                        await message.add_reaction(emoji)

                    def action_check(r, u):
                        return u == interaction.user and r.message.id == message.id and str(r.emoji) in action_reactions

                    try:
                        action_reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=action_check)
                        if str(action_reaction.emoji) == "💎":
                            await self.equip_accessory(interaction, selected_accessory, accessory_name, message, embed)
                            continue
                        elif str(action_reaction.emoji) == "🪄":
                            await self.improve_potential(interaction, selected_accessory, user_id, server_id, message, embed, current_page, selected_index)
                            continue
                        elif str(action_reaction.emoji) == "🗑️":
                            await self.discard_accessory(interaction, selected_accessory, accessory_name, message, embed)
                            continue
                        elif str(action_reaction.emoji) == "◀️":
                            continue

                    except asyncio.TimeoutError:
                        await message.delete()
                        self.bot.state_manager.clear_active(interaction.user.id)
                        break
                
            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)
                break
            
        self.bot.state_manager.clear_active(user_id)

    def get_accessory_passive_effect(self, passive: str, level: int) -> str:
        passive_messages = {
            "Obliterate": f"**{level * 2}%** chance to deal double damage.",
            "Absorb": f"**{level * 10}%** chance to absorb 10% of the monster's stats and add them to your own.",
            "Prosper": f"**{level * 10}%** chance to double gold earned.",
            "Infinite Wisdom": f"**{level * 5}%** chance to double experience earned.",
            "Lucky Strikes": f"**{level * 10}%** chance to roll lucky hit chance."
        }
        return passive_messages.get(passive, "No passive effect.")

    async def equip_accessory(self, interaction: Interaction, selected_item: tuple, new_equip: str, message, embed) -> None:
        """Equip an item."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        
        if not await self.bot.check_user_registered(interaction, existing_user):
            self.bot.state_manager.clear_active(user_id)
            return
                
        equipped_item = await self.bot.database.get_equipped_accessory(user_id)

        if equipped_item:
            current_equipped_id = equipped_item[0] 
            if selected_item[0] == current_equipped_id:
                embed.add_field(name="But why", value=(f"You already have **{new_equip}** equipped! "
                                                       " Returning to main menu..."), inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

            item_name = equipped_item[2]  # Assuming item_name is at index 2
            embed = discord.Embed(
                title="Switch accessory",
                description=f"Unequip **{item_name}** and equip **{new_equip}** instead?",
                color=0xFFCC00
            )
            await message.edit(embed=embed)
            await message.clear_reactions()
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def confirm_check(reaction, user):
                return (user == interaction.user and 
                        reaction.message.id == message.id 
                        and str(reaction.emoji) in ["✅", "❌"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)
                if str(reaction.emoji) == "❌":
                    await interaction.response.send_message("You put the accessory away.")
                    return

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)  
                return

        item_id = selected_item[0]
        await self.bot.database.equip_accessory(user_id, item_id)
        embed.add_field(name="Equip", value=f"Equipped **{new_equip}**\nReturning to main menu...", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(3)

    async def discard_accessory(self, interaction: Interaction, selected_accessory: tuple, accessory_name: str, message, embed) -> None:
        """Discard an accessory."""
        accessory_id = selected_accessory[0]  # Assuming item_id is at index 0

        embed = discord.Embed(
            title="Confirm Discard",
            description=f"Are you sure you want to discard **{accessory_name}**? This action cannot be undone.",
            color=0xFF0000,
        )
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")  # Confirm discard
        await message.add_reaction("❌")  # Cancel discard

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["✅", "❌"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Cancel", value=f"Returning to main menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        # Perform the actual discard operation
        await self.bot.database.discard_accessory(accessory_id)  # Assuming you have a method to discard items
        embed.add_field(name="Discard", 
                                    value=f"Discarded **{accessory_name}**. Returning to main menu...", 
                                    inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(3)


    async def improve_potential(self, interaction: Interaction, selected_accessory: tuple, 
                                user_id: str, server_id: str, message, embed,
                                current_page: int, selected_index: int) -> None:
        print('Improving accessory')
        accessory_id = selected_accessory[0]
        accessory_name = selected_accessory[2]
        current_passive = selected_accessory[9]
        potential_remaining = selected_accessory[11]
        potential_lvl = selected_accessory[12] 
        potential_passive_list = ["Obliterate", "Absorb", "Prosper", "Infinite Wisdom", "Lucky Strikes"]
        
        if potential_remaining <= 0:
            embed.add_field(name="Error", 
                            value=f"This accessory has no potential remaining. You cannot enhance it further. Returning to item menu...", 
                            inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return

        rune_of_potential_count = await self.bot.database.fetch_potential_runes(str(interaction.user.id))
        costs = [500, 1000, 2000, 3000, 4000, 5000, 10000, 20000, 30000, 40000]
        refine_cost = costs[10 - potential_remaining]
        success_rate = max(75 - (10 - potential_remaining) * 5, 35)

        if current_passive == "none":
            embed = discord.Embed(
                title="Unlock Potential Attempt",
                description=(f"Attempt to unlock *{accessory_name}*'s potential? \n"
                             f"Attempts left: **{potential_remaining}** \n"
                             f"Unlock Cost: **{refine_cost:,} GP**\n"
                             f"Success Rate: **{success_rate}%**\n"),
                color=0xFFCC00
            )       
        else:
            embed = discord.Embed(
                title="Enhance Potential Attempt",
                description=(f"Enhance **{accessory_name}**'s potential? \n"
                             f"Attempts left: **{potential_remaining}** \n"
                             f"Next Potential Level Cost: **{refine_cost:,} GP**\n"
                             f"Success Rate: **{success_rate}%**\n"),
                color=0xFFCC00
            )

        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def confirm_check(reaction, user):
            return user == interaction.user and reaction.message.id == message.id and str(reaction.emoji) in ["✅", "❌"]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Potential", value=f"Cancelling, returning to item menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(5)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return
        
        player_gold = await self.bot.database.fetch_user_gold(user_id, server_id)
        if player_gold < refine_cost:
            embed.add_field(name="Refining", value=f"You do not have enough gold. Returning to item menu...", inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
            return

        await self.bot.database.update_user_gold(user_id, player_gold - refine_cost)

        if rune_of_potential_count > 0:
            embed.add_field(name="Runes of Potential", 
                            value=(f"You have **{rune_of_potential_count}** Rune(s) of Potential available.\n"
                                   f"Do you want to use one to boost your success rate to **{success_rate + 25}%**?"),
                            inline=False)
            await message.edit(embed=embed)
            await message.clear_reactions()
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def check_reaction(r, user):
                return user == interaction.user and r.message.id == message.id and str(r.emoji) in ["✅", "❌"]

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check_reaction)

                if str(reaction.emoji) == "✅":
                    success_rate += 25
                    await self.bot.database.update_potential_runes(str(interaction.user.id), -1)

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)  
                return

        player_roll = random.random()
        chance_to_improve = success_rate / 100
        enhancement_success = player_roll <= chance_to_improve
        print(f"Enhancement was {enhancement_success}, with player rolling {player_roll} and {chance_to_improve} success rate")
        
        if enhancement_success:
            if potential_lvl == 0:
                passive_choice = random.choice(potential_passive_list)
                await self.bot.database.update_accessory_passive(accessory_id, passive_choice)
                await self.bot.database.update_accessory_passive_lvl(accessory_id, 1)
                success_message = (f"🎉 Success!\n"
                                   f"Your accessory has gained the **{passive_choice}** passive.")
            else:
                new_potential = potential_lvl + 1
                await self.bot.database.update_accessory_passive_lvl(accessory_id, new_potential)
                success_message = (f"🎉 Success!\n"
                                   f"Upgraded **{current_passive}** from level **{potential_lvl}** to **{new_potential}**.\n")
            embed.add_field(name="Enhancement Result", value=success_message + " Returning to item menu...", inline=False)
        else:
            fail_message = "💔 The enhancement failed. Unlucky. Returning to item menu..."
            embed.add_field(name="Enhancement Result", value=fail_message, inline=False)

        potential_remaining -= 1
        self.bot.state_manager.clear_active(interaction.user.id)  
        await self.bot.database.update_accessory_potential(accessory_id, potential_remaining)
        await message.edit(embed=embed)
        await asyncio.sleep(5)
        embed.clear_fields()


    '''
    
    HANDLE ARMOR
    
    '''
    @app_commands.command(name="armor", description="View your character's armor and modify them.")
    async def armor(self, interaction: Interaction) -> None:
        """Fetch and display the character's armors with pagination."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Check if the user has any active operations
        if not await self.bot.check_is_active(interaction, user_id):
            return

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        armors = await self.bot.database.fetch_user_armors(user_id)
        
        if not armors:
            await interaction.response.send_message("You peer into your armor pouch, it is empty.")
            return
        
        player_name = existing_user[3]
        embed = discord.Embed(
            title=f"🛡️",
            description=f"{player_name}'s Armors:",
            color=0x00FF00,
        )
        embed.set_thumbnail(url="https://i.imgur.com/NTVHFL8.png")
        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "inventory")  # Set inventory as active operation

        # Pagination setup
        items_per_page = 5
        total_pages = (len(armors) + items_per_page - 1) // items_per_page  # Ceiling division
        current_page = 0
        number_emojis = ["❌", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        while True:
            armors = await self.bot.database.fetch_user_armors(user_id)
            total_pages = (len(armors) + items_per_page - 1) // items_per_page
            current_page = min(current_page, total_pages - 1)  # Ensure current_page is valid
            embed.description = f"{player_name}'s Armor (Page {current_page + 1}/{total_pages}):"
            if not armors:
                await interaction.followup.send("You peer into your armor pouch, it is empty.")
                break

            armors.sort(key=lambda armor: armor[3], reverse=True)  # item_level at index 2
            start_idx = current_page * items_per_page
            armors_to_display = armors[start_idx:start_idx + items_per_page]
            await message.clear_reactions()
            embed.clear_fields()
            armors_display_string = ""

            for index, armor in enumerate(armors_to_display):
                armor_name = armor[2]  # item_name at index 1
                armor_level = armor[3]  # item_level at index 2
                equipped_armor = await self.bot.database.get_equipped_armor(user_id)
                is_equipped = equipped_armor and (equipped_armor[0] == armor[0])
                
                # Append armor details to the display string
                armors_display_string += (
                    f"{number_emojis[index + 1]}: "
                    f"{armor_name} (Level {armor_level})"
                    f"{' [E]' if is_equipped else ''}\n"
                )
            
            # Add a single field for all armors
            embed.add_field(
                name="Armors:",
                value=armors_display_string.strip(),
                inline=False
            )
                
            # Add instructions and page info
            embed.add_field(
                name="Instructions",
                value=(f"[ℹ️] Select an armor to interact with.\n"
                       f"[◀️] Previous page | [▶️] Next page | [❌] Close interface."),
                inline=False
            )
            await message.edit(embed=embed)
            
            # Add reactions: number emojis for armors, navigation, and exit
            for i in range(len(armors_to_display) + 1):
                await message.add_reaction(number_emojis[i])
            if current_page > 0:
                await message.add_reaction("◀️")
            if current_page < total_pages - 1:
                await message.add_reaction("▶️")

            def check(reaction, user):
                return (user == interaction.user
                        and reaction.message.id == message.id
                        and str(reaction.emoji) in number_emojis + ["◀️", "▶️"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                reaction_str = str(reaction.emoji)
                
                if reaction_str == "◀️" and current_page > 0:
                    current_page -= 1
                    continue
                elif reaction_str == "▶️" and current_page < total_pages - 1:
                    current_page += 1
                    continue
                elif reaction_str == "❌":
                    await message.delete()
                    self.bot.state_manager.clear_active(user_id)
                    break
                
                selected_index = number_emojis.index(reaction_str) - 1
                if selected_index >= 0:
                    selected_armor = armors_to_display[selected_index]
                    print(f'associated armor: {selected_armor}')
                    # Display selected armor details
                    armor_name = selected_armor[2]
                    armor_level = selected_armor[3]
                    armor_block = selected_armor[4]
                    armor_evasion = selected_armor[5]
                    armor_ward = selected_armor[6]
                    armor_passive = selected_armor[7]
                    embed.description = f"**{armor_name}** (Level {armor_level}):"
                    embed.clear_fields()
                    if (armor_block > 0):
                        embed.add_field(name="Block", value=armor_block, inline=True)
                    if (armor_evasion > 0):
                        embed.add_field(name="Evasion", value=armor_evasion, inline=True)
                    if (armor_ward > 0):
                        embed.add_field(name="Ward", value=f"{armor_ward}%", inline=True)
                    if armor_passive != "none":
                        effect_description = self.get_armor_passive_effect(armor_passive)
                        embed.add_field(name="Passive", value=armor_passive, inline=False)
                        embed.add_field(name="Effect", value=effect_description, inline=False)
                    armor_guide = (
                        "🛡️ to equip.\n"
                        "🔨 to temper.\n"
                        "🔅 to imbue.\n"
                        "🗑️ to discard.\n"
                        "◀️ to go back."
                    )
                    embed.add_field(name="Armor Guide", value=armor_guide, inline=False)
                    await message.edit(embed=embed)
                    await message.clear_reactions()
                    action_reactions = ["🛡️", "🔨", "🔅", "🗑️", "◀️"]
                    for emoji in action_reactions:
                        await message.add_reaction(emoji)

                    def action_check(r, u):
                        return u == interaction.user and r.message.id == message.id and str(r.emoji) in action_reactions

                    try:
                        action_reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=action_check)
                        if str(action_reaction.emoji) == "🛡️":
                            await self.equip_armor(interaction, selected_armor, armor_name, message, embed)
                            continue
                        elif str(action_reaction.emoji) == "🔨":
                            await self.temper_armor(interaction, selected_armor, user_id, server_id, embed, message, current_page, selected_index)
                            continue
                        elif str(action_reaction.emoji) == "🔅":
                            await self.imbue_armor(interaction, selected_armor, user_id, server_id, embed, message, current_page, selected_index)
                            continue
                        elif str(action_reaction.emoji) == "🗑️":
                            await self.discard_armor(interaction, selected_armor, armor_name, message, embed)
                            continue
                        elif str(action_reaction.emoji) == "◀️":
                            continue

                    except asyncio.TimeoutError:
                        await message.delete()
                        self.bot.state_manager.clear_active(interaction.user.id)
                        break

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)
                break
        self.bot.state_manager.clear_active(user_id)

    async def equip_armor(self, interaction: Interaction, selected_armor: tuple, new_equip: str, message, embed) -> None:
        """Equip an armor piece."""
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            self.bot.state_manager.clear_active(user_id)
            return
                
        equipped_armor = await self.bot.database.get_equipped_armor(user_id)

        if equipped_armor:
            current_equipped_id = equipped_armor[0] 
            if selected_armor[0] == current_equipped_id:
                embed.add_field(name="But why", value=(f"You already have **{new_equip}** equipped! "
                                                       "Returning to main menu..."), inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

            armor_name = equipped_armor[2]
            embed = discord.Embed(
                title="Switch armor",
                description=f"Unequip **{armor_name}** and equip **{new_equip}** instead?",
                color=0xFFCC00
            )
            await message.edit(embed=embed)
            await message.clear_reactions()
            await message.add_reaction("✅")
            await message.add_reaction("❌")

            def confirm_check(reaction, user):
                return (user == interaction.user and 
                        reaction.message.id == message.id 
                        and str(reaction.emoji) in ["✅", "❌"])

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)
                if str(reaction.emoji) == "❌":
                    return

            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)  
                return

        armor_id = selected_armor[0]
        await self.bot.database.equip_armor(user_id, armor_id)
        embed.add_field(name="Equip", value=f"Equipped **{new_equip}**\nReturning to main menu...", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(3)

    async def temper_armor(self, interaction: Interaction, selected_armor: tuple, user_id: str, server_id: str, embed, message, current_page: int, selected_index: int) -> None:
        """Temper an armor piece to increase its modifier."""
        armor_id = selected_armor[0]  # unique id of armor
        armor_name = selected_armor[2]
        armor_level = selected_armor[3]
        # Fetch current armor details
        armor_details = await self.bot.database.fetch_armor_by_id(armor_id)
        
        if not armor_details:
            await interaction.followup.send("Armor not found.")
            return

        # Get the current state of the armor
        tempers_remaining = armor_details[9]  # temper_remaining at index 9
        print(f'Tempers remaining for armor id {armor_id}: {tempers_remaining}')
        # Define the costs lookup based on the tempers remaining
        base_success_rate = 0.8
        if armor_level <= 40:
            costs = {
                3: (20, 20, 20, 500),
                2: (20, 20, 20, 100),
                1: (20, 20, 20, 2000),
            }
            cost_index = 6 - tempers_remaining
            success_rate = base_success_rate - (3 - tempers_remaining) * 0.05
            tempers_data = {
                3: ('iron', 'oak', 'desiccated'),
                2: ('coal', 'willow', 'regular'),
                1: ('gold', 'mahogany', 'sturdy'),
            }
        elif 40 < armor_level <= 80:    
            costs = {
                4: (50, 50, 50, 500),
                3: (50, 50, 50, 1500),
                2: (50, 50, 50, 3000),
                1: (50, 50, 50, 6000),
            }       
            tempers_data = {
                4: ('iron', 'oak', 'desiccated'),
                3: ('coal', 'willow', 'regular'),
                2: ('gold', 'mahogany', 'sturdy'),
                1: ('platinum', 'magic', 'reinforced'),
            }
            cost_index = 7 - tempers_remaining
            success_rate = base_success_rate - (4 - tempers_remaining) * 0.05 
        else:
            costs = {
                5: (100, 100, 100, 500),
                4: (100, 100, 100, 2000),
                3: (100, 100, 100, 5000),
                2: (100, 100, 100, 10000),
                1: (100, 100, 100, 20000),
            }
            tempers_data = {
                5: ('iron', 'oak', 'desiccated'),
                4: ('coal', 'willow', 'regular'),
                3: ('gold', 'mahogany', 'sturdy'),
                2: ('platinum', 'magic', 'reinforced'),
                1: ('idea', 'idea', 'titanium'),
            }
            cost_index = 8 - tempers_remaining
            success_rate = base_success_rate - (5 - tempers_remaining) * 0.05
        success_rate = max(0, min(success_rate, 1))
        # Check if there are tempers remaining
        if tempers_remaining == 0:
            embed.add_field(name="Tempering", value=f"This armor cannot be tempered anymore.", inline=True)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return

        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        player_gp = existing_user[6]  # Fetch the amount of gold from existing_user

        # Resources from the mining, woodcutting, and fishing tables
        mining_data = await self.bot.database.fetch_user_mining(user_id, server_id)
        woodcutting_data = await self.bot.database.fetch_user_woodcutting(user_id, server_id)
        fishing_data = await self.bot.database.fetch_user_fishing(user_id, server_id)

        # Get the corresponding costs based on tempers remaining
        ore_cost, wood_cost, bone_cost, gp_cost = costs[tempers_remaining]
        print(f'temper will cost {ore_cost} ore, {wood_cost} logs, {bone_cost} bones, {gp_cost} gp')

        if tempers_remaining in tempers_data:
            ore, logs, bones = tempers_data[tempers_remaining]
        else:
            ore, logs, bones = None, None, None
        # Check if the user has enough resources and gold
        if (mining_data[cost_index] < ore_cost or
            woodcutting_data[cost_index] < wood_cost or
            fishing_data[cost_index] < bone_cost or
            player_gp < gp_cost):
            embed.add_field(name="Tempering", 
                            value=(f"You do not have enough resources to temper this armor.\n"
                                   f"Tempering costs:\n"
                                   f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                                   f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                                   f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                                   f"- GP cost: **{gp_cost}**\n"), 
                            inline=True)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return
        
        embed = discord.Embed(
            title="Temper",
            description=(f"You are about to temper **{armor_name}**.\n"
                         f"Tempering costs:\n"
                         f"- **{ore.capitalize()}** {'Ore' if ore != 'coal' else ''} : **{ore_cost}**\n"
                         f"- **{logs.capitalize()}** Logs: **{wood_cost}**\n"
                         f"- **{bones.capitalize()}** Bones: **{bone_cost}**\n"
                         f"- GP cost: **{gp_cost:,}**\n"
                         f"- Success rate: **{int(success_rate * 100)}%**\n"
                         "Do you want to continue?"),
            color=0xFFFF00
        )
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id 
                    and str(reaction.emoji) in ["✅", "❌"])
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Cancel", value=f"Returning to armor menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        # Deduct the costs from the user's resources
        if armor_level <= 40:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if tempers_remaining == 3 else 0,
                'coal': -ore_cost if tempers_remaining == 2 else 0,
                'gold': -ore_cost if tempers_remaining == 1 else 0,
                'platinum': 0,
                'idea': 0,
            })
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -wood_cost if tempers_remaining == 3 else 0,
                'willow': -wood_cost if tempers_remaining == 2 else 0,
                'mahogany': -wood_cost if tempers_remaining == 1 else 0,
                'magic': 0,
                'idea': 0,
            })
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -bone_cost if tempers_remaining == 3 else 0,
                'regular': -bone_cost if tempers_remaining == 2 else 0,
                'sturdy': -bone_cost if tempers_remaining == 1 else 0,
                'reinforced': 0,
                'titanium': 0,
            })
        elif 40 < armor_level <= 80:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if tempers_remaining == 4 else 0,
                'coal': -ore_cost if tempers_remaining == 3 else 0,
                'gold': -ore_cost if tempers_remaining == 2 else 0,
                'platinum': -ore_cost if tempers_remaining == 1 else 0,
                'idea': 0,
            })
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -wood_cost if tempers_remaining == 4 else 0,
                'willow': -wood_cost if tempers_remaining == 3 else 0,
                'mahogany': -wood_cost if tempers_remaining == 2 else 0,
                'magic': -wood_cost if tempers_remaining == 1 else 0,
                'idea': 0,
            })
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -bone_cost if tempers_remaining == 4 else 0,
                'regular': -bone_cost if tempers_remaining == 3 else 0,
                'sturdy': -bone_cost if tempers_remaining == 2 else 0,
                'reinforced': -bone_cost if tempers_remaining == 1 else 0,
                'titanium': 0,
            })
        else:
            await self.bot.database.update_mining_resources(user_id, server_id, {
                'iron': -ore_cost if tempers_remaining == 5 else 0,
                'coal': -ore_cost if tempers_remaining == 4 else 0,
                'gold': -ore_cost if tempers_remaining == 3 else 0,
                'platinum': -ore_cost if tempers_remaining == 2 else 0,
                'idea': -ore_cost if tempers_remaining == 1 else 0,
            })
            await self.bot.database.update_woodcutting_resources(user_id, server_id, {
                'oak': -wood_cost if tempers_remaining == 5 else 0,
                'willow': -wood_cost if tempers_remaining == 4 else 0,
                'mahogany': -wood_cost if tempers_remaining == 3 else 0,
                'magic': -wood_cost if tempers_remaining == 2 else 0,
                'idea': -wood_cost if tempers_remaining == 1 else 0,
            })
            await self.bot.database.update_fishing_resources(user_id, server_id, {
                'desiccated': -bone_cost if tempers_remaining == 5 else 0,
                'regular': -bone_cost if tempers_remaining == 4 else 0,
                'sturdy': -bone_cost if tempers_remaining == 3 else 0,
                'reinforced': -bone_cost if tempers_remaining == 2 else 0,
                'titanium': -bone_cost if tempers_remaining == 1 else 0,
            })
        await self.bot.database.add_gold(user_id, -gp_cost)

        new_tempers_remaining = tempers_remaining - 1
        temper_success = random.random() <= success_rate  

        if temper_success:
            print('temper success')
            # Determine which stat to increase (assuming one of block, evasion, or ward is non-zero)
            if armor_details[4] > 0:  # block
                stat_to_increase = 'block'
                current_value = armor_details[4]
            elif armor_details[5] > 0:  # evasion
                stat_to_increase = 'evasion'
                current_value = armor_details[5]
            else:  # ward
                stat_to_increase = 'ward'
                current_value = armor_details[6]
                
            increase_amount = max(1, random.randint(int(armor_level // 7), int(armor_level // 5)))
            await self.bot.database.increase_armor_stat(armor_id, stat_to_increase, increase_amount)
            embed.add_field(name="Tempering success", 
                           value=(f"🎊 Congratulations! 🎊 " 
                                  f"**{armor_name}**'s {stat_to_increase.capitalize()} increased by **{increase_amount}**."),
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(7)
        else:
            print('tempering failed')
            embed.add_field(name="Tempering", 
                           value=(f"Tempering failed! "
                                  f"Better luck next time. 🥺 \n"
                                  f"Returning to armor menu..."),
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)
        
        await self.bot.database.update_armor_temper_count(armor_id, new_tempers_remaining)

    async def imbue_armor(self, interaction: Interaction, selected_armor: tuple, user_id: str, server_id: str, embed, message, current_page: int, selected_index: int) -> None:
        """Imbue an armor piece with a rune of imbuing for a chance to gain a passive."""
        armor_id = selected_armor[0]
        armor_name = selected_armor[2]
        armor_passive = selected_armor[7]
        imbues_remaining = selected_armor[10]
        if armor_passive != "none":
            embed.add_field(name="Imbuing", 
                           value=f"This armor already has a passive: **{armor_passive}**. Cannot imbue again.", 
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return
        
        if imbues_remaining < 1:
            embed.add_field(name="Imbuing", 
                           value=f"This armor can no longer be imbued.", 
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        imbue_runes = existing_user[27]
        if imbue_runes <= 0:
            embed.add_field(name="Imbuing", 
                           value=f"You do not have any Runes of Imbuing. Returning to armor menu...", 
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(3)
            return

        embed = discord.Embed(
            title="Imbue Armor",
            description=(f"Use a **Rune of Imbuing** to attempt to imbue **{armor_name}** with a passive?\n"
                         f"You have **{imbue_runes}** Rune(s) of Imbuing.\n"
                         f"Success rate: **50%**\n"
                         "Do you want to continue?"),
            color=0xFFCC00
        )
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")
        await message.add_reaction("❌")

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id 
                    and str(reaction.emoji) in ["✅", "❌"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Cancel", value=f"Returning to armor menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        # Deduct one rune of imbuing
        await self.bot.database.update_imbuing_runes(user_id, -1)
        await self.bot.database.update_armor_imbue_count(armor_id, 0)
        # 50% success rate
        imbue_success = random.random() <= 0.5
        if imbue_success:
            passives = [
                "Invulnerable",
                "Mystical Might",
                "Omnipotent",
                "Treasure Hunter",
                "Unlimited Wealth",
                "Everlasting Blessing"
            ]
            new_passive = random.choice(passives)
            await self.bot.database.update_armor_passive(armor_id, new_passive)
            embed.add_field(name="Imbuing success", 
                           value=(f"🎊 Congratulations! 🎊 "
                                  f"**{armor_name}** has been imbued with **{new_passive}**."),
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(7)
        else:
            embed.add_field(name="Imbuing", 
                           value=(f"Imbuing failed! "
                                  f"Better luck next time. 🥺 \n"
                                  f"Returning to armor menu..."),
                           inline=False)
            await message.edit(embed=embed)
            await asyncio.sleep(5)

    async def discard_armor(self, interaction: Interaction, selected_armor: tuple, armor_name: str, message, embed) -> None:
        """Discard an armor piece."""
        armor_id = selected_armor[0]

        embed = discord.Embed(
            title="Confirm Discard",
            description=f"Are you sure you want to discard **{armor_name}**? This action cannot be undone.",
            color=0xFF0000,
        )
        await message.edit(embed=embed)
        await message.clear_reactions()
        await message.add_reaction("✅")  # Confirm discard
        await message.add_reaction("❌")  # Cancel discard

        def confirm_check(reaction, user):
            return (user == interaction.user and 
                    reaction.message.id == message.id and 
                    str(reaction.emoji) in ["✅", "❌"])

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=confirm_check)

            if str(reaction.emoji) == "❌":
                embed.add_field(name="Cancel", value=f"Returning to armor menu...", inline=False)
                await message.edit(embed=embed)
                await asyncio.sleep(3)
                return

        except asyncio.TimeoutError:
            await message.delete()
            self.bot.state_manager.clear_active(interaction.user.id)  
            return

        await self.bot.database.discard_armor(armor_id)
        embed.add_field(name="Discard", 
                       value=f"Discarded **{armor_name}**. Returning to armor menu...", 
                       inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(3)

    def get_armor_passive_effect(self, passive: str) -> str:
        """Return the description of an armor passive effect."""
        passive_messages = {
            "Invulnerable": "20% chance to take no damage the entire fight.",
            "Mystical Might": "20% chance to deal 10x damage after all calculations.",
            "Omnipotent": "20% chance to set the monsters attack and defense to 0.",
            "Treasure Hunter": "5% additional chance to turn the monster into a loot encounter.",
            "Unlimited Wealth": "20% chance to 5x player rarity stat.",
            "Everlasting Blessing": "3% chance on victory to propagate your ideology."
        }
        return passive_messages.get(passive, "No effect.")

    '''
    
    MISCELLANEOUS COMMANDS
    
    '''

    @app_commands.command(name="leaderboard", description="Show the top adventurers sorted by level.")
    async def leaderboard(self, interaction: Interaction) -> None:
        """Fetch and display the top 10 adventurers sorted by level."""
        top_users = await self.bot.database.fetch_top_users_by_level(limit=10)

        if not top_users:
            await interaction.response.send_message("No adventurers found.")
            return

        # Create an embed for the leaderboard
        embed = discord.Embed(
            title="Hiscores 🏆",
            color=0x00FF00
        )

        # Construct the leaderboard information
        leaderboard_lines = []
        for idx, user in enumerate(top_users, start=1):
            user_name = user[3]  # Assuming player name is at index 3
            user_level = user[4]  # Assuming level is at index 4

            # Build leaderboard line with the appropriate emoji
            if idx == 1:
                leaderboard_lines.append(f"🥇 **{user_name}** - Level {user_level}")
            elif idx == 2:
                leaderboard_lines.append(f"🥈 **{user_name}** - Level {user_level}")
            elif idx == 3:
                leaderboard_lines.append(f"🥉 **{user_name}** - Level {user_level}")
            else:
                leaderboard_lines.append(f"**{idx}: {user_name}** - Level {user_level}")

        leaderboard_text = "\n".join(leaderboard_lines)
        embed.add_field(name="Top Adventurers:", value=leaderboard_text, inline=False)

        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()


    @app_commands.command(name="passives", description="Allocate your passive points.")
    async def passives(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        # Fetch the sender's user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        
        if not await self.bot.check_is_active(interaction, user_id):
            return

        # Fetch user's current passive points
        passive_points = await self.bot.database.fetch_passive_points(user_id, server_id)
        if passive_points <= 0:
            await interaction.response.send_message("You do not have any passive points to allocate.")
            return
        
        embed = discord.Embed(
            title="Allocate Passive Points",
            description="Choose a stat to allocate a passive point to.",
            color=0x00FF00
        )
        embed.add_field(name="Points remaining: ", value=f"{passive_points}", inline=True)
        embed.add_field(name="Current Stats", 
                value=(f"Attack: {existing_user[9]}\n"
                f"Defense: {existing_user[10]}\n"
                f"HP: {existing_user[12]}"), inline=False)
        embed.add_field(name="**WARNING**", 
                value=(f"All choices are **final**, no take-backsies! You have been warned."), inline=False)
        # embed.add_field(name="Attack", value="⚔️", inline=False)
        # embed.add_field(name="Defense", value="🛡️", inline=True)
        # embed.add_field(name="HP", value="❤️", inline=True)

        await interaction.response.send_message(embed=embed)
        message: Message = await interaction.original_response()
        self.bot.state_manager.set_active(user_id, "stats")
        def check(reaction, user):
            return (user == interaction.user and 
                    str(reaction.emoji) in ["⚔️", "🛡️", "❤️", "❌"] and 
                    reaction.message.id == message.id)
        
        while passive_points > 0:
            await message.add_reaction("⚔️")  # Attack
            await message.add_reaction("🛡️")  # Defense
            await message.add_reaction("❤️")  # HP
            await message.add_reaction("❌") # Leave
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=180.0, check=check)
                if str(reaction.emoji) == "⚔️":
                    # Increment attack and decrement passive points
                    await self.bot.database.increase_attack(user_id, 1)
                elif str(reaction.emoji) == "🛡️":
                    # Increment defense and decrement passive points
                    await self.bot.database.increase_defence(user_id, 1)
                elif str(reaction.emoji) == "❤️":
                    # Increment HP and decrement passive points
                    await self.bot.database.update_player_max_hp(user_id, 1)
                elif str(reaction.emoji) == "❌":
                    await message.delete()
                    break

                await message.remove_reaction(reaction.emoji, user)
                passive_points = await self.bot.database.fetch_passive_points(user_id, server_id)
                # Update passive points
                if passive_points > 0:
                    passive_points -= 1
                    print("-1 passive pt")
                    await self.bot.database.set_passive_points(user_id, server_id, passive_points)
                else:
                    print('Invalid passive points')
                # Edit the embed to show current allocations
                embed.clear_fields()
                existing_user = await self.bot.database.fetch_user(user_id, server_id)
                embed.add_field(name="Points remaining: ", value=f"{passive_points}", inline=True)
                embed.add_field(name="Current Stats", 
                                value=(f"Attack ⚔️: {existing_user[9]}\n"
                                f"Defense 🛡️: {existing_user[10]}\n"
                                f"HP ❤️: {existing_user[12]}"), inline=False)
                # embed.add_field(name="Attack", value="⚔️", inline=True)
                # embed.add_field(name="Defense", value="🛡️", inline=True)
                # embed.add_field(name="HP", value="❤️", inline=True)
                await message.edit(embed=embed)
            
            except asyncio.TimeoutError:
                await message.delete()
                self.bot.state_manager.clear_active(interaction.user.id)  
                break

        self.bot.state_manager.clear_active(user_id)
        # await message.clear_reactions()
        if (passive_points == 0):
            embed.add_field(name="All points allocated", value="You have allocated all your passive points.", inline=False)
            await message.edit(embed=embed)
            await message.clear_reactions()



async def setup(bot) -> None:
    await bot.add_cog(Character(bot))