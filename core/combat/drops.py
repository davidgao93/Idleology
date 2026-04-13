import random

from core.combat import rewards
from core.combat.loot import (
    generate_accessory,
    generate_armor,
    generate_boot,
    generate_glove,
    generate_helmet,
    generate_weapon,
)
from core.models import Player
from core.skills.mechanics import SkillMechanics

# ---------------------------------------------------------------------------
# Essence Drop Tables
# ---------------------------------------------------------------------------

_REGULAR_ESSENCE_TABLE = [
    ("power", 35),
    ("protection", 30),
    ("insight", 12),
    ("evasion", 8),
    ("warding", 8),
    ("cleansing", 3),
    ("chaos", 2),
    ("annulment", 1),
]
_REGULAR_ESSENCE_POOL = [e for e, w in _REGULAR_ESSENCE_TABLE for _ in range(w)]
_CORRUPTED_ESSENCE_POOL = ["aphrodite", "lucifer", "gemini", "neet"]
_CORRUPTED_CHANCE = 0.03  # 3% of all essence drops are corrupted


def roll_essence_drop() -> str:
    """
    Returns an essence type string for an essence-infused monster kill.
    3% chance to return a corrupted essence, otherwise weighted regular table.
    """
    if random.random() < _CORRUPTED_CHANCE:
        return random.choice(_CORRUPTED_ESSENCE_POOL)
    return random.choice(_REGULAR_ESSENCE_POOL)


class DropManager:
    @staticmethod
    async def proc_skiller(
        bot, user_id: str, server_id: str, player: Player
    ) -> str | None:
        """
        Rolls the Skiller boot passive. Returns a log message string if it procs, else None.
        Shared by standard combat and ascent — do NOT call from codex.
        """
        if not (player.equipped_boot and player.equipped_boot.passive == "skiller"):
            return None
        proc_chance = player.equipped_boot.passive_lvl * 0.05
        if random.random() >= proc_chance:
            return None
        skill_type = random.choice(["mining", "woodcutting", "fishing"])
        skill_row = await bot.database.skills.get_data(user_id, server_id, skill_type)
        if not skill_row:
            return None
        tool_tier = skill_row[2]
        resources = SkillMechanics.calculate_yield(skill_type, tool_tier)
        await bot.database.skills.update_batch(
            user_id, server_id, skill_type, resources
        )
        msg_map = {"mining": "ores", "woodcutting": "logs", "fishing": "fish"}
        return f"👢 **Skiller** found extra {msg_map[skill_type]}!"

    @staticmethod
    async def process_drops(
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        monster_level: int,
        reward_data: dict,
        monster=None,
    ):
        """
        Handles DB updates for items, runes, and skill procs.
        """

        # 0. Ensure essences list exists in reward_data
        reward_data.setdefault("essences", [])

        # 1. Skiller Boot Passive (Skill Mats)
        skiller_msg = await DropManager.proc_skiller(bot, user_id, server_id, player)
        if skiller_msg:
            reward_data["msgs"].append(skiller_msg)

        # 1b. Essence Monster Drop
        if monster is not None and getattr(monster, "is_essence", False):
            essence_type = roll_essence_drop()
            await bot.database.essences.add(user_id, essence_type)
            reward_data["essences"].append(essence_type)

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
            if item_roll <= 35 and await check_limit("weapon"):
                item = await generate_weapon(user_id, monster_level, drop_rune=True)
                if item.name == "Rune of Refinement":
                    await bot.database.users.modify_currency(
                        user_id, "refinement_runes", 1
                    )
                    item_desc = f"**{item.name}**: {item.description}"
                else:
                    await bot.database.equipment.create_weapon(item)
                    item_desc = item.description

            elif item_roll <= 60 and await check_limit("accessory"):
                item = await generate_accessory(user_id, monster_level, drop_rune=True)
                if item.name == "Rune of Potential":
                    await bot.database.users.modify_currency(
                        user_id, "potential_runes", 1
                    )
                    item_desc = f"**{item.name}**: {item.description}"
                else:
                    await bot.database.equipment.create_accessory(item)
                    item_desc = item.description

            elif item_roll <= 70 and await check_limit("armor"):
                item = await generate_armor(user_id, monster_level, drop_rune=True)
                if item.name == "Rune of Imbuing":
                    await bot.database.users.modify_currency(user_id, "imbue_runes", 1)
                    item_desc = f"**{item.name}**: {item.description}"
                else:
                    await bot.database.equipment.create_armor(item)
                    item_desc = item.description

            elif item_roll <= 80 and await check_limit("glove"):
                item = await generate_glove(user_id, monster_level)
                await bot.database.equipment.create_glove(item)
                item_desc = item.description

            elif item_roll <= 90 and await check_limit("boot"):
                item = await generate_boot(user_id, monster_level)
                await bot.database.equipment.create_boot(item)
                item_desc = item.description

            elif item_roll <= 100 and await check_limit("helmet"):
                item = await generate_helmet(user_id, monster_level)
                await bot.database.equipment.create_helmet(item)
                item_desc = item.description

            if item_desc:
                reward_data["items"].append(item_desc)
