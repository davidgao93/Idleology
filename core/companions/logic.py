# core/companions/logic.py

import discord
import random
from collections import defaultdict
from core.companions.mechanics import CompanionMechanics
from core.items.factory import create_companion
# Import Generators
from core.combat.loot import (
    generate_weapon, generate_armor, generate_accessory, 
    generate_glove, generate_boot, generate_helmet
)
from datetime import datetime

class CompanionLogic:
    @staticmethod
    async def collect_passive_rewards(bot, user_id: str, guild_id: str) -> str:
        """
        Handles the calculation and DB updates for passive companion loot.
        """
        # 1. Fetch Data
        cursor = await bot.database.connection.execute(
            "SELECT last_companion_collect_time FROM users WHERE user_id = ?", (user_id,)
        )
        res = await cursor.fetchone()
        last_collect = res[0] if res else None

        active_rows = await bot.database.companions.get_active(user_id)
        if not active_rows:
            return "You have no active companions to gather loot."

        active_comps = [create_companion(row) for row in active_rows]

        # 2. Calculate
        results = CompanionMechanics.calculate_collection_rewards(active_comps, last_collect)
        
        if not results['can_collect']:
            return "Your companions are still gathering supplies. Check back later (30m interval)."

        # 3. Process Loot
        # results['items'] is a list of ("Type", Amount)
        
        summary = defaultdict(int)
        generated_gear_count = 0
        
        for loot_type, amount in results['items']:
            
            # --- GOLD ---
            if loot_type == "Gold":
                await bot.database.users.modify_gold(user_id, amount)
                summary["Gold"] += amount

            # --- RUNES ---
            elif loot_type == "Rune of Refinement":
                await bot.database.users.modify_currency(user_id, 'refinement_runes', 1)
                summary["Rune of Refinement"] += 1
            elif loot_type == "Rune of Potential":
                await bot.database.users.modify_currency(user_id, 'potential_runes', 1)
                summary["Rune of Potential"] += 1
            elif loot_type == "Rune of Shattering":
                await bot.database.users.modify_currency(user_id, 'shatter_runes', 1)
                summary["Rune of Shattering"] += 1

            # --- BOSS KEYS (Random Selection) ---
            elif loot_type == "Boss Key":
                # 20% Dragon, 20% Angel, 20% Soul Core, 20% Void Frag, 20% balance fragment
                key_roll = random.random()
                if key_roll < 0.20:
                    await bot.database.users.modify_currency(user_id, 'dragon_key', 1)
                    summary["Draconic Key"] += 1
                elif key_roll < 0.40:
                    await bot.database.users.modify_currency(user_id, 'angel_key', 1)
                    summary["Angelic Key"] += 1
                elif key_roll < 0.60:
                    await bot.database.users.modify_currency(user_id, 'soul_cores', 1)
                    summary["Soul Core"] += 1
                elif key_roll < 0.80:
                    await bot.database.users.modify_currency(user_id, 'void_frags', 1)
                    summary["Void Fragment"] += 1
                else:
                    await bot.database.users.modify_currency(user_id, 'balance_fragment', 1) # [NEW]
                    summary["Fragment of Balance"] += 1

            # --- EQUIPMENT (Random Generation) ---
            elif loot_type == "Equipment":
                # Pick slot
                slot = random.choice(['weapon', 'armor', 'accessory', 'glove', 'boot', 'helmet'])
                lvl = random.randint(1, 100) # Random level gear
                
                if slot == 'weapon':
                    item = await generate_weapon(user_id, lvl, drop_rune=False)
                    await bot.database.equipment.create_weapon(item)
                elif slot == 'armor':
                    item = await generate_armor(user_id, lvl, drop_rune=False)
                    await bot.database.equipment.create_armor(item)
                elif slot == 'accessory':
                    item = await generate_accessory(user_id, lvl, drop_rune=False)
                    await bot.database.equipment.create_accessory(item)
                elif slot == 'glove':
                    item = await generate_glove(user_id, lvl)
                    await bot.database.equipment.create_glove(item)
                elif slot == 'boot':
                    item = await generate_boot(user_id, lvl)
                    await bot.database.equipment.create_boot(item)
                elif slot == 'helmet':
                    item = await generate_helmet(user_id, lvl)
                    await bot.database.equipment.create_helmet(item)
                
                generated_gear_count += 1

        # 4. Update Timer

        new_time = datetime.now().isoformat()
        await bot.database.connection.execute(
            "UPDATE users SET last_companion_collect_time = ? WHERE user_id = ?", 
            (new_time, user_id)
        )
        await bot.database.connection.commit()

        # 5. Format Output
        if not summary and generated_gear_count == 0:
            return f"Your companions returned empty-handed from {results['cycles']} cycles."

        msg = f"**Companions returned after {results['cycles']} cycles!**\n"
        
        # Gold
        if summary["Gold"] > 0:
            msg += f"💰 **{summary['Gold']:,}** Gold\n"
            del summary["Gold"]
            
        # Items
        items_list = [f"{k} x{v}" for k, v in summary.items()]
        if generated_gear_count > 0:
            items_list.append(f"Unidentified Equipment x{generated_gear_count}")
            
        if items_list:
            msg += "📦 " + ", ".join(items_list)
        
        return msg