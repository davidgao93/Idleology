import discord
import json
import random
import asyncio
import os
import re
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Optional, Counter

class POETrivia(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.game_active = False
        self.items = []
        self.current_items_used = set()
    
    async def load_items(self) -> None:
        """Load items from all JSON files"""
        item_files = [
            "itemoverview.json",      # Weapons
            "flaskoverview.json",     # Flasks
            "accessoryoverview.json", # Accessories
            "armouroverview.json",    # Armour
        ]
        
        self.items = []
        
        for filename in item_files:
            file_path = f'assets/items/{filename}'
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as file:
                        data = json.load(file)
                        if "lines" in data:
                            self.items.extend(data["lines"])
                            print(f"Loaded items from {filename}")
                        else:
                            print(f"Warning: No 'lines' field in {filename}")
                else:
                    print(f"Warning: File {file_path} not found")
            except json.JSONDecodeError:
                print(f"Error: Invalid JSON format in {file_path}")
            except Exception as e:
                print(f"Error loading {file_path}: {str(e)}")
        
        print(f"Total items loaded: {len(self.items)}")
        
        # Filter out items without names
        self.items = [item for item in self.items if item.get("name")]
        print(f"Valid items (with names): {len(self.items)}")
    
    def get_random_item(self) -> Optional[Dict]:
        """Get a random item that hasn't been used in the current game"""
        available_items = [item for item in self.items 
                          if item.get("name") and item["name"] not in self.current_items_used]
        
        if not available_items:
            return None
            
        item = random.choice(available_items)
        self.current_items_used.add(item["name"])
        return item
    
    def normalize_item_name(self, name: str) -> str:
        """
        Normalize an item name for flexible matching by:
        1. Converting to lowercase
        2. Removing punctuation
        3. Removing articles and common words
        4. Removing extra whitespace
        """
        # Convert to lowercase
        name = name.lower()
        
        # Remove punctuation
        name = re.sub(r'[^\w\s]', '', name)
        
        # Remove common words that don't change meaning
        common_words = ['the', 'a', 'an', 'of', 'and', 'or']
        words = name.split()
        words = [word for word in words if word not in common_words]
        
        # Rejoin and remove extra whitespace
        name = ' '.join(words)
        name = ' '.join(name.split())
        
        return name

    @app_commands.command(name="poe", description="Start a Path of Exile unique item guessing game")
    async def poe_trivia(self, interaction: discord.Interaction) -> None:
        """Starts a Path of Exile unique item guessing game"""
        # Check if user is owner
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("This command can only be used by the bot owner.", ephemeral=True)
            return
        
        if self.game_active:
            await interaction.response.send_message("A game is already in progress!", ephemeral=True)
            return
        
        # First response to the interaction
        await interaction.response.send_message("Starting Path of Exile Unique Item Trivia! Loading items...")
        
        # Load items if not already loaded
        if not self.items:
            await self.load_items()
            
        if not self.items:
            await interaction.followup.send("Failed to load POE items. Please check the item files.")
            return
        
        # Initialize the game
        self.game_active = True
        self.current_items_used = set()
        
        # Track player scores and rewards
        score_tracker = {}
        
        channel = interaction.channel
        await interaction.followup.send(f"Get ready for 10 rounds of POE trivia! {len(self.items)} unique items in the pool.")
        
        # Run 10 rounds
        for i in range(10):
            item = self.get_random_item()
            if not item:
                await channel.send("Ran out of unique items! Game over.")
                break
            
            # Get item category
            item_category = "Unknown Type"
            if "itemType" in item:
                item_category = item["itemType"]
            
            # Create and send embed
            embed = discord.Embed(
                title=f"Round {i+1}/10: Guess the Unique {item_category}!",
                description=f"**Base Type:** {item.get('baseType', 'Unknown')}\n**Required Level:** {item.get('levelRequired', 'Unknown')}",
                color=discord.Color.gold()
            )
            
            # Add mods to the embed
            mods_text = ""
            if "explicitModifiers" in item:
                for mod in item["explicitModifiers"]:
                    if not mod.get("optional", False):  # Only show non-optional mods
                        mods_text += f"• {mod['text']}\n"
            if mods_text:
                embed.add_field(name="Properties", value=mods_text, inline=False)
            
            # Add implicit mods if available
            impl_text = ""
            if "implicitModifiers" in item and item["implicitModifiers"]:
                for mod in item["implicitModifiers"]:
                    if not mod.get("optional", False):
                        impl_text += f"• {mod['text']}\n"
                if impl_text:
                    embed.add_field(name="Implicit Modifiers", value=impl_text, inline=False)
            
            # Add flavor text if available
            if "flavourText" in item and item["flavourText"]:
                flavor = item["flavourText"].replace("\n", " ")
                embed.add_field(name="Lore", value=f"*{flavor}*", inline=False)
            
            # Add item image if available
            if "icon" in item and item["icon"]:
                embed.set_thumbnail(url=item["icon"])
                
            embed.set_footer(text="You have 30 seconds to guess the name! (Minor variations are allowed)")
            
            await channel.send(embed=embed)
            
            # Normalize the correct answer for comparison
            correct_answer_normalized = self.normalize_item_name(item["name"])
            
            def check(message):
                # Normalize the user's guess and compare
                guess_normalized = self.normalize_item_name(message.content)
                return (
                    message.channel == channel and 
                    guess_normalized == correct_answer_normalized
                )
            
            try:
                msg = await self.bot.wait_for('message', timeout=30.0, check=check)
                
                # Award the winner
                gold_amount = random.randint(5000, 10000)
                await self.bot.database.add_gold(str(msg.author.id), gold_amount)
                
                # 10% chance for a curio
                got_curio = random.random() < 0.1
                if got_curio:
                    await self.bot.database.update_curios_count(str(msg.author.id), str(interaction.guild_id), 1)
                
                # Track the winner's score
                if msg.author.id not in score_tracker:
                    score_tracker[msg.author.id] = {
                        "name": msg.author.display_name,
                        "correct": 0,
                        "gold": 0,
                        "curios": 0
                    }
                
                score_tracker[msg.author.id]["correct"] += 1
                score_tracker[msg.author.id]["gold"] += gold_amount
                if got_curio:
                    score_tracker[msg.author.id]["curios"] += 1
                
                # Send winner message
                win_embed = discord.Embed(
                    title="Correct!",
                    description=f"{msg.author.mention} guessed correctly! The answer was **{item['name']}**.",
                    color=discord.Color.green()
                )
                win_embed.add_field(name="Rewards", value=f"{gold_amount} gold" + (" + 1 Curio!" if got_curio else ""))
                win_embed.set_thumbnail(url=item["icon"])
                await channel.send(embed=win_embed)
                
            except asyncio.TimeoutError:
                # No correct answer in time
                timeout_embed = discord.Embed(
                    title="Time's up!",
                    description=f"Nobody guessed correctly. The answer was **{item['name']}**.",
                    color=discord.Color.red()
                )
                timeout_embed.set_thumbnail(url=item["icon"])
                await channel.send(embed=timeout_embed)
            
            # Brief pause between questions
            await asyncio.sleep(3)
        
        # End the game and display the leaderboard
        self.game_active = False
        
        # Create leaderboard embed
        leaderboard_embed = discord.Embed(
            title="🏆 Path of Exile Trivia - Results 🏆",
            description="Here's how everyone did in this game:",
            color=discord.Color.blue()
        )
        
        # Sort players by number of correct answers
        sorted_players = sorted(
            score_tracker.values(), 
            key=lambda x: (x["correct"], x["gold"]), 
            reverse=True
        )
        
        if sorted_players:
            # Add top players to the leaderboard
            for i, player in enumerate(sorted_players):
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                leaderboard_embed.add_field(
                    name=f"{medal} {player['name']}",
                    value=f"**Correct Answers:** {player['correct']}\n**Gold Earned:** {player['gold']}\n**Curios:** {player['curios']}",
                    inline=True
                )
            
            # Add total stats
            total_gold = sum(player["gold"] for player in score_tracker.values())
            total_curios = sum(player["curios"] for player in score_tracker.values())
            
            leaderboard_embed.add_field(
                name="Game Totals", 
                value=f"**Total Questions:** 10\n**Total Gold:** {total_gold}\n**Total Curios:** {total_curios}", 
                inline=False
            )
            
            leaderboard_embed.set_footer(text="Thanks for playing! Use /poe to start a new game.")
        else:
            leaderboard_embed.description = "Nobody answered any questions correctly! Better luck next time."
        
        await channel.send(embed=leaderboard_embed)

async def setup(bot) -> None:
    await bot.add_cog(POETrivia(bot))