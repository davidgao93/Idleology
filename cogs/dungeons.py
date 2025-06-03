# cogs/dungeon.py

import discord
from discord.ext import commands
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import View, Button
import random
from typing import List, Optional, Dict, Union

from core.models import Player, Weapon, Accessory, Armor, DungeonState, DungeonRoomOption

# Constants for room types
ROOM_COMBAT_NORMAL = "Combat"
ROOM_COMBAT_ELITE = "Elite Combat"
ROOM_MERCHANT = "Merchant"
ROOM_REPRIEVE = "Reprieve"
ROOM_TREASURE_CHEST = "Treasure Chest"
ROOM_MYSTERY = "Mystery" # Will resolve into Combat or Treasure
ROOM_BOSS = "BOSS"

class DungeonCog(commands.Cog, name="dungeon"):
    def __init__(self, bot):
        self.bot = bot
        self.active_dungeons: Dict[str, DungeonState] = {} # user_id: DungeonState

    async def _get_player_object_and_base_ward(self, user_id: str, user_name: str, existing_user_data) -> tuple[Player, int]:
        """
        Creates a Player object from database data and calculates base ward from equipment.
        """
        player = Player(
            id=user_id,
            name=user_name,
            level=existing_user_data[4],
            ascension=existing_user_data[15],
            exp=existing_user_data[5], # Not directly used for dungeon mechanics but part of Player model
            hp=existing_user_data[11], # Current HP from DB, for dungeons, we use max_hp
            max_hp=existing_user_data[12],
            attack=existing_user_data[9],
            defence=existing_user_data[10],
            rarity=0, crit=95, ward=0, block=0, evasion=0, 
            potions=0, # Dungeon potions are managed by DungeonState
            wep_id=0, weapon_passive="", acc_passive="", acc_lvl=0, armor_passive="",
            invulnerable=False # Default, can be affected by buffs later
        )
        
        base_ward_from_gear = 0
        
        # Armor ward & stats (only ward is used for base_ward now)
        equipped_armor = await self.bot.database.get_equipped_armor(user_id)
        if equipped_armor:
            base_ward_from_gear += int((equipped_armor[6] / 100) * player.max_hp)
            # player.block += equipped_armor[4] # For future use if needed
            # player.evasion += equipped_armor[5] # For future use if needed

        # Accessory ward & stats (only ward is used for base_ward now)
        equipped_accessory = await self.bot.database.get_equipped_accessory(user_id)
        if equipped_accessory:
            # Assuming equipped_accessory[7] is the % ward.
            # From combat.py: player.ward += max(1, int((equipped_accessory[7] / 100) * player.max_hp))
            # This suggests accessories can grant ward even if player.ward was 0.
            base_ward_from_gear += max(0, int((equipped_accessory[7] / 100) * player.max_hp)) 
            # player.crit -= equipped_accessory[8] # For future use if needed

        # Note: Player's base attack/defense/rarity will be augmented by gear in actual combat,
        # and then by dungeon multipliers. For now, this Player object holds base character stats.
        return player, base_ward_from_gear

    def _generate_room_options(self) -> List[DungeonRoomOption]:
        """
        Generates 3 room options for a regular dungeon floor.
        """
        options = []
        directions = ["Left", "Forward", "Right"]
        random.shuffle(directions) 

        possible_encounters_flavors = {
            ROOM_COMBAT_ELITE: "A menacing aura emanates from this path...",
            ROOM_MERCHANT: "A calming, mercantile presence is felt.",
            ROOM_REPRIEVE: "You sense a moment of peace and relaxation ahead.",
            ROOM_MYSTERY: "Curiosity tingles... mystery lies ahead!",
            ROOM_COMBAT_NORMAL: "The faint scent of steel and blood...",
            ROOM_TREASURE_CHEST: "You hear the gentle clinking of coins or valuables...",
        }
        
        # Weights for choosing room types
        encounter_types = list(possible_encounters_flavors.keys())
        weights = [0.10, 0.15, 0.20, 0.25, 0.20, 0.10] # Elite, Merchant, Reprieve, Mystery, Normal, Chest

        chosen_room_types_for_paths = random.choices(encounter_types, weights=weights, k=3)

        for i in range(3):
            room_type = chosen_room_types_for_paths[i]
            
            # Resolve MYSTERY type now for flavor text consistency
            actual_encounter_type = room_type
            if room_type == ROOM_MYSTERY:
                actual_encounter_type = random.choice([ROOM_COMBAT_NORMAL, ROOM_TREASURE_CHEST])
            
            flavor = possible_encounters_flavors[room_type] # Flavor text is for the "mystery" itself if applicable

            options.append(DungeonRoomOption(
                direction=directions[i],
                flavor_text=flavor,
                encounter_type=actual_encounter_type # Store the resolved type
            ))
        return options

    async def _build_dungeon_embed_and_view(self, dungeon_state: DungeonState):
        embed_title = f"{dungeon_state.player_name}'s Dungeon Run - Floor {dungeon_state.current_floor}"
        if dungeon_state.current_floor > dungeon_state.max_regular_floors:
            embed_title = f"{dungeon_state.player_name}'s Dungeon Run - BOSS FLOOR!"

        embed = discord.Embed(title=embed_title,
                              description=dungeon_state.last_action_message or "Choose your path...",
                              color=discord.Color.dark_red())

        hp_display = f"{dungeon_state.player_current_hp}/{dungeon_state.player_max_hp} ❤️"
        if dungeon_state.player_current_ward > 0:
            hp_display += f" ({dungeon_state.player_current_ward} 🔮)"
        
        embed.add_field(name="Status", value=hp_display, inline=True)
        embed.add_field(name="Potions", value=f"{dungeon_state.potions_remaining} 🧪", inline=True)
        embed.add_field(name="Dungeon Coins", value=f"{dungeon_state.dungeon_coins} 🪙", inline=True)
        
        loot_desc = "None"
        if dungeon_state.loot_gathered:
            loot_names = [item.name for item in dungeon_state.loot_gathered]
            if len(loot_names) > 5:
                loot_desc = ", ".join(loot_names[:5]) + f"... (+{len(loot_names)-5} more)"
            else:
                loot_desc = ", ".join(loot_names)
        embed.add_field(name=f"Loot Gathered ({len(dungeon_state.loot_gathered)} items)", value=loot_desc, inline=False)

        # Add buff/curse display later if needed
        # embed.add_field(name="Buffs", value=", ".join(dungeon_state.player_buffs) or "None", inline=True)
        # embed.add_field(name="Curses", value=", ".join(dungeon_state.player_curses) or "None", inline=True)

        view = DungeonView(self, dungeon_state.player_id, dungeon_state.current_room_options)
        return embed, view

    @app_commands.command(name="dungeon", description="Venture into the depths below...")
    async def dungeon_start(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id) 

        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return
        # if not await self.bot.is_maintenance(interaction, user_id): return # Uncomment if needed

        if user_id in self.active_dungeons:
            # Attempt to resend the last message if possible, or just notify
            # For now, simpler to block and ask to finish/retreat.
            await interaction.response.send_message(
                "You are already in a dungeon! Finish or retreat from your current one.",
                ephemeral=True
            )
            return

        _, base_ward = await self._get_player_object_and_base_ward(user_id, interaction.user.display_name, existing_user)
        
        # Initialize DungeonState
        num_regular_floors = 12 
        dungeon_state = DungeonState(
            player_id=user_id,
            player_name=interaction.user.display_name,
            current_floor=1,
            max_regular_floors=num_regular_floors,
            player_current_hp=existing_user[12], # Max HP from DB
            player_max_hp=existing_user[12],
            player_current_ward=base_ward,
            player_base_ward=base_ward,
            potions_remaining=10,
            dungeon_coins=0,
            # loot_gathered, buffs, curses, etc., use defaults from dataclass
        )
        dungeon_state.current_room_options = self._generate_room_options()
        
        self.active_dungeons[user_id] = dungeon_state
        self.bot.state_manager.set_active(user_id, "dungeon")

        embed, view = await self._build_dungeon_embed_and_view(dungeon_state)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response() # Store message for timeout editing


class DungeonView(View):
    def __init__(self, cog: DungeonCog, user_id: str, room_options: List[DungeonRoomOption], timeout=300): # 5 min
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_id = user_id
        self.message: Optional[discord.Message] = None # Will be set after sending

        if room_options: # Room options might be None if it's a forced encounter like BOSS
            for option in room_options:
                # Ensure button label isn't too long
                label = f"{option.direction}: {option.flavor_text}"
                if len(label) > 80:
                    label = label[:77] + "..."
                
                button = Button(label=label,
                                style=ButtonStyle.secondary,
                                custom_id=f"dungeon_path_{option.direction}_{option.encounter_type.replace(' ', '_')}")
                button.callback = self.path_callback 
                self.add_item(button)

        retreat_button = Button(label="Retreat", style=ButtonStyle.danger, custom_id="dungeon_retreat")
        retreat_button.callback = self.retreat_callback
        self.add_item(retreat_button)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This is not your dungeon run!", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        if self.user_id in self.cog.active_dungeons:
            # User might still be in dungeon state if they just AFK'd
            # Let's simulate a retreat on timeout
            dungeon_state = self.cog.active_dungeons[self.user_id]
            dungeon_state.last_action_message = "Your dungeon run timed out and you were safely extracted."
            # No interaction object here, so we can't call handle_dungeon_end directly in the same way
            # We'll just clean up the state. The message disabling happens below.
            del self.cog.active_dungeons[self.user_id]
            self.cog.bot.state_manager.clear_active(self.user_id)
        
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(content="Dungeon run timed out. Your progress (if any) was saved as if retreated.", embed=None, view=self)
            except discord.NotFound:
                pass # Message might have been deleted
            except discord.HTTPException as e:
                self.cog.bot.logger.warning(f"Failed to edit dungeon message on timeout: {e}")


    async def path_callback(self, interaction: Interaction):
        await interaction.response.defer() 
        
        dungeon_state = self.cog.active_dungeons.get(self.user_id)
        if not dungeon_state:
            await interaction.followup.send("Error: Dungeon state not found or run ended.", ephemeral=True)
            await _disable_view_and_clear_state(interaction, self.cog, self.user_id, self)
            return

        # custom_id: dungeon_path_{DIRECTION}_{ENCOUNTER_TYPE}
        parts = interaction.data['custom_id'].split('_')
        chosen_direction = parts[2]
        # Reconstruct encounter type if it had underscores
        chosen_encounter_type_from_id = "_".join(parts[3:]).replace('_', ' ') 
        
        # Find the original DungeonRoomOption based on direction; custom_id provides encounter type directly
        # This assumes that the custom_id's encounter type is the one to use.
        original_option = next((opt for opt in dungeon_state.current_room_options if opt.direction == chosen_direction), None)
        
        if not original_option: # Should not happen if view is built correctly
             await interaction.followup.send("Error: Invalid choice.", ephemeral=True)
             return
        
        actual_encounter_type = original_option.encounter_type # Use the type from the generated options

        dungeon_state.last_action_message = f"Floor {dungeon_state.current_floor}: Chose {original_option.direction} ({original_option.flavor_text}).\nEntered a **{actual_encounter_type}** room."

        # --- Simulate Encounter (Placeholders) ---
        if actual_encounter_type == ROOM_TREASURE_CHEST:
            coins_found = random.randint(50, 200)
            dungeon_state.dungeon_coins += coins_found
            dungeon_state.last_action_message += f"\nFound {coins_found} dungeon coins!"
            # Placeholder for item:
            # if random.random() < 0.1:
            #    # Generate a simple item and add to dungeon_state.loot_gathered
            #    dungeon_state.last_action_message += "\nAnd a small trinket!"
        elif actual_encounter_type == ROOM_REPRIEVE:
            heal_amount = int(dungeon_state.player_max_hp * random.uniform(0.20, 0.35)) 
            dungeon_state.player_current_hp = min(dungeon_state.player_max_hp, dungeon_state.player_current_hp + heal_amount)
            dungeon_state.last_action_message += f"\nHealed for {heal_amount} HP ({dungeon_state.player_current_hp}/{dungeon_state.player_max_hp})!"
            if dungeon_state.potions_remaining < 10 and random.random() < 0.3: # Chance to find a potion
                dungeon_state.potions_remaining +=1
                dungeon_state.last_action_message += f"\nFound a spare potion! ({dungeon_state.potions_remaining} total)"
        elif actual_encounter_type in [ROOM_COMBAT_NORMAL, ROOM_COMBAT_ELITE]:
            # Placeholder: Player takes some minor damage
            # damage_taken = random.randint(1, int(dungeon_state.player_max_hp * 0.05)) # Lose up to 5% HP
            # dungeon_state.player_current_hp -= damage_taken
            dungeon_state.last_action_message += f"\n(Placeholder: Combat Occurred)"
        # --- End Simulate Encounter ---

        # Refresh Ward (simulating end of an encounter)
        dungeon_state.player_current_ward = dungeon_state.player_base_ward
        dungeon_state.current_floor += 1 # Advance to the next floor

        # --- Check Game State ---
        if dungeon_state.player_current_hp <= 0:
            dungeon_state.last_action_message += "\n\n**You have fallen in the dungeon! All loot and coins are lost.**"
            await self.handle_dungeon_end(interaction, dungeon_state, success=False, reason="Defeated")
            return

        if dungeon_state.current_floor > dungeon_state.max_regular_floors: # Time for the BOSS
            dungeon_state.last_action_message = f"Floor {dungeon_state.max_regular_floors} cleared. **The BOSS of the dungeon appears!**"
            # For now, instant win placeholder for BOSS
            dungeon_state.last_action_message += "\n(Placeholder: You bravely fought the BOSS... and WON!)"
            # TODO: Transition to a BOSS fight view/logic
            await self.handle_dungeon_end(interaction, dungeon_state, success=True, reason="Boss Defeated")
            return
        
        # --- Generate next set of choices ---
        dungeon_state.current_room_options = self.cog._generate_room_options()
        
        new_embed, new_view = await self.cog._build_dungeon_embed_and_view(dungeon_state)
        self.message = await interaction.edit_original_response(embed=new_embed, view=new_view)


    async def retreat_callback(self, interaction: Interaction):
        await interaction.response.defer()
        dungeon_state = self.cog.active_dungeons.get(self.user_id)
        if not dungeon_state:
            await interaction.followup.send("Error: Dungeon state not found or run already ended.", ephemeral=True)
            await _disable_view_and_clear_state(interaction, self.cog, self.user_id, self)
            return
        
        await self.handle_dungeon_end(interaction, dungeon_state, success=True, reason="Retreated")

    async def handle_dungeon_end(self, interaction: Interaction, dungeon_state: DungeonState, success: bool, reason: str):
        # Disable buttons on the original message
        for item in self.children: # self.children refers to the view's items
            item.disabled = True
        
        final_embed = discord.Embed(title=f"Dungeon Run Concluded: {reason}", color=discord.Color.green() if success else discord.Color.red())
        final_embed.description = dungeon_state.last_action_message # Show the last action that led to this
        
        if success: # Success (Retreat or Boss Defeated)
            final_embed.add_field(name="Dungeon Coins Acquired", value=str(dungeon_state.dungeon_coins), inline=True)
            # TODO: Actually award coins and loot to player's main inventory
            # For now, they are just reported.
            if dungeon_state.loot_gathered:
                loot_names = [item.name for item in dungeon_state.loot_gathered]
                final_embed.add_field(name="Loot Gathered", value=", ".join(loot_names) or "None", inline=False)
            else:
                final_embed.add_field(name="Loot Gathered", value="None", inline=False)
        else: # Failed (Defeated)
            final_embed.add_field(name="Dungeon Coins Lost", value=str(dungeon_state.dungeon_coins), inline=True)
            final_embed.add_field(name="Loot Lost", value=f"{len(dungeon_state.loot_gathered)} items", inline=False)

        try:
            if interaction.response.is_done(): # If already responded (e.g. deferred)
                 await interaction.edit_original_response(embed=final_embed, view=self)
            else: # Should not happen if we defer, but as a fallback
                 await interaction.response.edit_message(embed=final_embed, view=self)
        except discord.HTTPException as e: 
            self.cog.bot.logger.error(f"Error editing dungeon end message: {e}")
            try: # Fallback to followup if edit fails
                await interaction.followup.send(embed=final_embed, view=None) # Send without view if edit failed
            except discord.HTTPException as e2:
                self.cog.bot.logger.error(f"Error sending dungeon end followup: {e2}")


        if self.user_id in self.cog.active_dungeons:
            del self.cog.active_dungeons[self.user_id]
        self.cog.bot.state_manager.clear_active(self.user_id)
        self.stop() # Stop the view


async def _disable_view_and_clear_state(interaction: Interaction, cog_instance: Optional[DungeonCog], user_id_to_clear: Optional[str], view_instance: Optional[View]):
    """Helper to disable view and clear state if an interaction failed prematurely."""
    if view_instance:
        for item in view_instance.children:
            item.disabled = True
        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(content="This dungeon run has encountered an issue or ended.", embed=None, view=view_instance)
            # else: # If not deferred, this might be problematic
            #     await interaction.response.edit_message(content="This dungeon run has encountered an issue or ended.", embed=None, view=view_instance)
        except discord.NotFound: 
            pass 
        except discord.HTTPException:
            pass # Best effort
        view_instance.stop()

    if cog_instance and user_id_to_clear:
        if user_id_to_clear in cog_instance.active_dungeons:
            del cog_instance.active_dungeons[user_id_to_clear]
        cog_instance.bot.state_manager.clear_active(user_id_to_clear)


async def setup(bot) -> None:
    await bot.add_cog(DungeonCog(bot))