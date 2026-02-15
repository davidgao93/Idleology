import random
from core.models import Player
from core.combat import rewards
from core.combat.loot import generate_weapon, generate_armor, generate_accessory, generate_glove, generate_boot, generate_helmet
from core.skills.mechanics import SkillMechanics

class DropManager:
    @staticmethod
    async def process_drops(bot, user_id: str, server_id: str, player: Player, monster_level: int, reward_data: dict):
        """
        Handles DB updates for items, runes, and skill procs.
        """
        
        # 1. Skiller Boot Passive (Skill Mats)
        if player.equipped_boot and player.equipped_boot.passive == "skiller":
            proc_chance = player.equipped_boot.passive_lvl * 0.05
            if random.random() < proc_chance:
                skill_type = random.choice(['mining', 'woodcutting', 'fishing'])
                
                # Fetch tool tier
                skill_row = await bot.database.skills.get_data(user_id, server_id, skill_type)
                
                if skill_row:
                    tool_tier = skill_row[2] # Index 2 is usually the tool column based on repositories
                    # Calculate Yield
                    resources = SkillMechanics.calculate_yield(skill_type, tool_tier)
                    
                    # Update DB
                    await bot.database.skills.update_batch(user_id, server_id, skill_type, resources)
                    
                    # Log message
                    msg_map = {'mining': "ores", 'woodcutting': "logs", 'fishing': "fish"}
                    reward_data['msgs'].append(f"👢 **Skiller** found extra {msg_map[skill_type]}!")
                
        # 2. Gear Drops
        drop_roll = random.randint(1, 100)
        drop_threshold = rewards.calculate_item_drop_chance(player)
        
        if drop_roll <= drop_threshold:
            item_roll = random.randint(1, 100)
            
            # Helper to check inventory limit
            async def check_limit(itype):
                return await bot.database.equipment.get_count(user_id, itype) < 60

            item_desc = None
            
            # Adjusted Logic to prevent huge nesting
            if item_roll <= 35 and await check_limit('weapon'):
                item = await generate_weapon(user_id, monster_level, drop_rune=True)
                if item.name == "Rune of Refinement":
                    await bot.database.users.modify_currency(user_id, 'refinement_runes', 1)
                    item_desc = f"**{item.name}**: {item.description}"
                else:
                    await bot.database.equipment.create_weapon(item)
                    item_desc = item.description

            elif item_roll <= 60 and await check_limit('accessory'):
                item = await generate_accessory(user_id, monster_level, drop_rune=True)
                if item.name == "Rune of Potential":
                    await bot.database.users.modify_currency(user_id, 'potential_runes', 1)
                    item_desc = f"**{item.name}**: {item.description}"
                else:
                    await bot.database.equipment.create_accessory(item)
                    item_desc = item.description

            elif item_roll <= 70 and await check_limit('armor'):
                item = await generate_armor(user_id, monster_level, drop_rune=True)
                if item.name == "Rune of Imbuing":
                    await bot.database.users.modify_currency(user_id, 'imbue_runes', 1)
                    item_desc = f"**{item.name}**: {item.description}"
                else:
                    await bot.database.equipment.create_armor(item)
                    item_desc = item.description

            elif item_roll <= 80 and await check_limit('glove'):
                item = await generate_glove(user_id, monster_level)
                await bot.database.equipment.create_glove(item)
                item_desc = item.description

            elif item_roll <= 90 and await check_limit('boot'):
                item = await generate_boot(user_id, monster_level)
                await bot.database.equipment.create_boot(item)
                item_desc = item.description

            elif item_roll <= 100 and await check_limit('helmet'):
                item = await generate_helmet(user_id, monster_level)
                await bot.database.equipment.create_helmet(item)
                item_desc = item.description

            if item_desc:
                reward_data['items'].append(item_desc)

    @staticmethod
    async def handle_level_up(bot, user_id: str, player: Player, reward_data: dict, exp_table: dict):
        """Calculates level ups and commits stat changes."""
        exp_threshold = exp_table["levels"].get(str(player.level), 999999999)
        
        # Ascension
        if player.level >= 100 and player.exp >= exp_threshold:
            player.ascension += 1
            player.exp -= exp_threshold
            await bot.database.users.modify_currency(user_id, 'passive_points', 2)
            reward_data['msgs'].append(f"🌟 **ASCENSION LEVEL UP!** ({player.ascension})")
            reward_data['msgs'].append("✨ Gained **2** Passive Points!")
            
        # Normal Level Up
        elif player.level < 100 and player.exp >= exp_threshold:
            player.level += 1
            player.exp -= exp_threshold
            
            atk_inc = random.randint(1, 5)
            def_inc = random.randint(1, 5)
            hp_inc = random.randint(1, 5)
            
            player.base_attack += atk_inc
            player.base_defence += def_inc
            player.max_hp += hp_inc
            player.current_hp = player.max_hp # Full heal on level up
            
            await bot.database.users.modify_stat(user_id, 'attack', atk_inc)
            await bot.database.users.modify_stat(user_id, 'defence', def_inc)
            await bot.database.users.modify_stat(user_id, 'max_hp', hp_inc)
            
            reward_data['msgs'].append(f"🎉 **LEVEL UP!** ({player.level})")
            reward_data['msgs'].append(f"📈 +{atk_inc} Atk, +{def_inc} Def, +{hp_inc} HP")
            
            if player.level % 10 == 0:
                await bot.database.users.modify_currency(user_id, 'passive_points', 2)
                reward_data['msgs'].append("✨ **Milestone!** Gained **2** Passive Points!")