import random
import csv
from collections import defaultdict
from typing import List, Dict, Any, Tuple

from core.models import Player
from core.combat.loot import (
    generate_weapon, generate_armor, generate_accessory, 
    generate_glove, generate_boot, generate_helmet
)
from core.skills.mechanics import SkillMechanics

class CurioManager:
    @staticmethod
    def get_drop_table() -> Dict[str, float]:
        """Returns map of Reward Name -> Probability (0.0 - 1.0)."""
        return {
            "Level 100 Weapon": 0.002,
            "Level 100 Accessory": 0.002,
            "Level 100 Armor": 0.002,
            "Level 100 Gloves": 0.002,
            "Level 100 Boots": 0.002,
            "Level 100 Helmet": 0.002,
            "Rune of Imbuing": 0.003,
            "Rune of Refinement": 0.02,
            "Rune of Potential": 0.02,
            "Rune of Shattering": 0.02,
            "100k Gold": 0.10,
            "50k Gold": 0.10,
            "10k Gold": 0.10,
            "5k Gold": 0.20,
            "1k Gold": 0.05,
            "Ore": 0.125,
            "Wood": 0.125,
            "Fish": 0.125,
        }

    @staticmethod
    async def process_open(bot, user_id: str, server_id: str, amount: int) -> Dict[str, Any]:
        """
        Opens 'amount' curios and processes all rewards.
        Returns a summary dict for the UI.
        """
        table = CurioManager.get_drop_table()
        
        # 1. Expand Table for Weighted Choice
        population = []
        weights = []
        for key, val in table.items():
            population.append(key)
            weights.append(val)

        # 2. Roll Rewards
        # random.choices is faster for bulk operations
        results = random.choices(population, weights=weights, k=amount)
        
        # 3. Aggregate Results to minimize DB calls
        summary = defaultdict(int)
        for r in results:
            summary[r] += 1

        loot_logs = []
        
        # 4. Process Aggregated Rewards
        for reward, count in summary.items():
            
            # --- GEAR ---
            if "Level 100" in reward:
                item_type = reward.split(" ")[2].lower() # Weapon, Accessory, etc.
                if item_type.endswith('s'): item_type = item_type[:-1] 
                
                for _ in range(count):
                    item = None
                    if item_type == "weapon":
                        item = await generate_weapon(user_id, 100, drop_rune=False)
                        await bot.database.equipment.create_weapon(item)
                    elif item_type == "accessory":
                        item = await generate_accessory(user_id, 100, drop_rune=False)
                        await bot.database.equipment.create_accessory(item)
                    elif item_type == "armor":
                        item = await generate_armor(user_id, 100, drop_rune=False)
                        await bot.database.equipment.create_armor(item)
                    elif item_type == "glove":
                        item = await generate_glove(user_id, 100)
                        await bot.database.equipment.create_glove(item)
                    elif item_type == "boot":
                        item = await generate_boot(user_id, 100)
                        await bot.database.equipment.create_boot(item)
                    elif item_type == "helmet":
                        item = await generate_helmet(user_id, 100)
                        await bot.database.equipment.create_helmet(item)
                    
                    if item:
                        loot_logs.append(item.description)

            # --- RUNES ---
            elif "Rune" in reward:
                col_map = {
                    "Rune of Refinement": "refinement_runes",
                    "Rune of Potential": "potential_runes",
                    "Rune of Imbuing": "imbue_runes",
                    "Rune of Shattering": "shatter_runes"
                }
                await bot.database.users.modify_currency(user_id, col_map[reward], count)

            # --- GOLD ---
            elif "Gold" in reward:
                # Extract number from string "100k Gold"
                val_str = reward.split(" ")[0].lower().replace("k", "000")
                gold_amt = int(val_str) * count
                await bot.database.users.modify_gold(user_id, gold_amt)

            # --- MATERIALS ---
            elif reward in ["Ore", "Wood", "Fish"]:
                skill_map = {
                    "Ore": ("mining", "pickaxe_tier"),
                    "Wood": ("woodcutting", "axe_type"), # Assuming DB column name
                    "Fish": ("fishing", "fishing_rod")
                }
                
                skill_name, tool_col = skill_map[reward]
                skill_data = await bot.database.skills.get_data(user_id, server_id, skill_name)
                tool_tier = skill_data[2] if skill_data else 'starter' # Fallback
                
                # Calculate Yield
                total_resources = defaultdict(int)
                for _ in range(count * 5):
                    yields = SkillMechanics.calculate_yield(skill_name, tool_tier)
                    for res, amt in yields.items():
                        total_resources[res] += amt
                
                await bot.database.skills.update_batch(user_id, server_id, skill_name, dict(total_resources))

        # Deduct Curios
        await bot.database.users.modify_currency(user_id, 'curios', -amount)
        
        return {
            "summary": dict(summary),
            "loot_logs": loot_logs
        }

    @staticmethod
    def get_image_url(reward_name: str) -> str:
        """Attempts to load image URL from CSV."""
        try:
            with open('assets/curios.csv', mode='r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['Item'] == reward_name.replace(" ", "_"):
                        return row['URL']
        except: pass
        return None