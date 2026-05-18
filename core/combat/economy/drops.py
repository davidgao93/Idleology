import random

from core.combat import rewards
from core.combat.economy.loot import (
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
    ("insight", 8),
    ("evasion", 6),
    ("blocking", 6),
    ("deftness", 4),
    ("precision", 4),
    ("gluttony", 4),
    ("cleansing", 3),
    ("chaos", 2),
    ("annulment", 1),
]
_REGULAR_ESSENCE_POOL = [e for e, w in _REGULAR_ESSENCE_TABLE for _ in range(w)]
_CORRUPTED_ESSENCE_POOL = ["aphrodite", "lucifer", "gemini", "neet"]
_CORRUPTED_CHANCE = 0.03  # 3% of all essence drops are corrupted

# ---------------------------------------------------------------------------
# Monster Body Part Drop Tables
# ---------------------------------------------------------------------------

_BODY_PART_BASE_CHANCE = 0.02  # 2% base; special rarity adds on top

# ---------------------------------------------------------------------------
# Monster Egg Drop Tables
# ---------------------------------------------------------------------------

_EGG_BASE_CHANCE = 0.02  # same 2% + special rarity as body parts

_EGG_TIER_WEIGHTS = [
    ("normal", 75),
    ("rare",   20),
    ("giga",    5),
]
_EGG_TIERS, _EGG_WEIGHTS = zip(*_EGG_TIER_WEIGHTS)

_PART_SLOT_WEIGHTS = [
    ("head", 0.400),
    ("torso", 0.400),
    ("right_arm", 0.045),
    ("left_arm", 0.045),
    ("right_leg", 0.045),
    ("left_leg", 0.045),
    ("cheeks", 0.010),
    ("organs", 0.010),
]
_PART_SLOTS, _PART_WEIGHTS = zip(*_PART_SLOT_WEIGHTS)


def roll_monster_part(monster_name: str, ilvl: int) -> tuple:
    """
    Randomly selects a slot and rolls HP using a triangular distribution peaked at ilvl.
    Returns (slot_type, hp_value).
    """
    slot = random.choices(_PART_SLOTS, weights=_PART_WEIGHTS, k=1)[0]
    hp = max(1, int(random.triangular(ilvl * 0.5, ilvl * 1.5, ilvl)))
    return slot, hp


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
        # NEET boot: Void Echo doubles skilling resource yield on proc
        neet_suffix = ""
        if player.get_boot_corrupted_essence() == "neet":
            await bot.database.skills.update_batch(
                user_id, server_id, skill_type, resources
            )
            neet_suffix = " (**Void Echo** doubled the yield!)"
        msg_map = {"mining": "ores", "woodcutting": "logs", "fishing": "fish"}
        return f"👢 **Skiller** found extra {msg_map[skill_type]}!{neet_suffix}"

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

        # 1c. Monster Body Part Drop (normal, non-essence monsters only)
        if monster is not None and not getattr(monster, "is_essence", False):
            part_chance = _BODY_PART_BASE_CHANCE + (
                player.get_special_drop_bonus() / 100
            )
            _part_roll = random.random()
            reward_data.setdefault("rolls", {})
            reward_data["rolls"]["part_chance_pct"] = round(part_chance * 100, 3)
            reward_data["rolls"]["part_roll_pct"] = round(_part_roll * 100, 3)
            reward_data["rolls"]["part_hit"] = _part_roll < part_chance
            if _part_roll < part_chance:
                slot, hp = roll_monster_part(monster.name, monster_level)
                await bot.database.monster_parts.add_part(
                    user_id, slot, monster.name, monster_level, hp
                )
                reward_data["body_part"] = (slot, monster.name, hp)

        # 1d. Monster Egg Drop (normal, non-essence monsters only)
        if monster is not None and not getattr(monster, "is_essence", False):
            egg_chance = _EGG_BASE_CHANCE + (player.get_special_drop_bonus() / 100)
            if random.random() < egg_chance:
                egg_tier = random.choices(_EGG_TIERS, weights=_EGG_WEIGHTS, k=1)[0]
                added = await bot.database.eggs.add_egg(
                    user_id, egg_tier, monster_level, monster.name
                )
                if added:
                    reward_data["egg"] = egg_tier

        # 2. Gear Drops
        # Aphrodite boot: lucky gear drops — roll twice, take the lower (more likely to beat threshold)
        drop_roll = random.randint(1, 100)
        if player.get_boot_corrupted_essence() == "aphrodite":
            drop_roll = min(drop_roll, random.randint(1, 100))
        drop_threshold = rewards.calculate_item_drop_chance(player)

        reward_data.setdefault("rolls", {})
        reward_data["rolls"]["gear_roll"] = drop_roll
        reward_data["rolls"]["gear_threshold"] = drop_threshold
        reward_data["rolls"]["gear_hit"] = drop_roll <= drop_threshold

        if drop_roll <= drop_threshold:
            item_roll = random.randint(1, 100)
            reward_data["rolls"]["item_roll"] = item_roll

            # Helper to check inventory limit
            async def check_limit(itype):
                return await bot.database.equipment.get_count(user_id, itype) < 60

            item_desc = None
            chosen_slot = None

            # Adjusted Logic to prevent huge nesting
            if item_roll <= 35 and await check_limit("weapon"):
                chosen_slot = "weapon"
                item = await generate_weapon(user_id, monster_level, drop_rune=True)
                if item.name == "Rune of Refinement":
                    await bot.database.users.modify_currency(
                        user_id, "refinement_runes", 1
                    )
                    item_desc = f"**{item.name}**"
                else:
                    await bot.database.equipment.create_weapon(item)
                    item_desc = item.description

            elif item_roll <= 60 and await check_limit("accessory"):
                chosen_slot = "accessory"
                item = await generate_accessory(user_id, monster_level, drop_rune=True)
                if item.name == "Rune of Potential":
                    await bot.database.users.modify_currency(
                        user_id, "potential_runes", 1
                    )
                    item_desc = f"**{item.name}**"
                else:
                    await bot.database.equipment.create_accessory(item)
                    item_desc = item.description

            elif item_roll <= 70 and await check_limit("armor"):
                chosen_slot = "armor"
                item = await generate_armor(user_id, monster_level, drop_rune=True)
                if item.name == "Rune of Imbuing":
                    await bot.database.users.modify_currency(user_id, "imbue_runes", 1)
                    item_desc = f"**{item.name}**"
                else:
                    await bot.database.equipment.create_armor(item)
                    item_desc = item.description

            elif item_roll <= 80 and await check_limit("glove"):
                chosen_slot = "glove"
                item = await generate_glove(user_id, monster_level)
                await bot.database.equipment.create_glove(item)
                item_desc = item.description

            elif item_roll <= 90 and await check_limit("boot"):
                chosen_slot = "boot"
                item = await generate_boot(user_id, monster_level)
                await bot.database.equipment.create_boot(item)
                item_desc = item.description

            elif item_roll <= 100 and await check_limit("helmet"):
                chosen_slot = "helmet"
                item = await generate_helmet(user_id, monster_level)
                await bot.database.equipment.create_helmet(item)
                item_desc = item.description

            reward_data["rolls"]["item_slot"] = chosen_slot

            if item_desc:
                reward_data["items"].append(item_desc)


# ---------------------------------------------------------------------------
# Boss sigil & corrupted-monster drops (shared by CombatView and ascent)
# ---------------------------------------------------------------------------

# (name_fragment, building_key, uber_db_method, sigil_display)
_BOSS_SIGIL_CONFIGS = [
    ("Lucifer", "infernal_forge", "increment_infernal_sigils", "Infernal Sigil"),
    ("NEET", "void_sanctum", "increment_void_shards", "Void Sigil"),
    ("Aphrodite", "celestial_shrine", "increment_sigils", "Celestial Sigil"),
    ("Gemini", "twin_shrine", "increment_gemini_sigils", "Gemini Sigil"),
]


async def apply_incubated_monster_drops(
    bot,
    user_id: str,
    monster,
    reward_data: dict,
) -> None:
    """Awards blood and cleans up the incubated encounter queue entry on victory.

    No-ops if the monster is not incubated.
    """
    if not getattr(monster, "is_incubated", False):
        return

    from core.hatchery.mechanics import HatcheryMechanics

    blood_amount = HatcheryMechanics.blood_reward(monster.incubated_egg_tier, monster.level)
    blood_type   = random.choice(["primordial", "evolutionary", "mutative"])

    await bot.database.hematurgy.modify_blood(user_id, blood_type, blood_amount)
    await bot.database.eggs.consume_incubated_encounter(monster.incubated_encounter_id)

    blood_names = {"primordial": "Primordial 🩸", "evolutionary": "Evolutionary 🧬", "mutative": "Mutative ☣️"}
    reward_data.setdefault("special", [])
    reward_data["special"].append(
        f"🩸 Incubated monster dropped **{blood_amount:,}x {blood_names[blood_type]}** blood!"
    )


async def apply_boss_sigil_drops(
    bot,
    user_id: str,
    server_id: str,
    monster,
    reward_data: dict,
) -> None:
    """
    Rolls boss sigil drops for Lucifer / NEET / Aphrodite / Gemini.
    Skips uber variants. Mutates reward_data['special'] in-place.

    Drop formula: 50% base + building_workers * 0.01% for a bonus second drop.
    """
    if getattr(monster, "is_uber", False):
        return

    for name_frag, building_key, incr_fn_name, sigil_name in _BOSS_SIGIL_CONFIGS:
        if name_frag not in monster.name:
            continue
        _, building_workers = await bot.database.settlement.get_building_details(
            user_id, server_id, building_key
        )
        sigils_dropped = 0
        if random.random() < 0.5:
            sigils_dropped += 1
        if random.random() < (building_workers * 0.0001):
            sigils_dropped += 1
        incr_fn = getattr(bot.database.uber, incr_fn_name)
        await incr_fn(user_id, server_id, sigils_dropped)
        reward_data["special"].extend([sigil_name] * sigils_dropped)
        break  # Only one boss type can match


async def apply_corrupted_monster_drops(
    bot,
    user_id: str,
    server_id: str,
    monster,
    reward_data: dict,
) -> None:
    """
    Handles drops from corrupted monsters. No-ops if monster is not corrupted.
    Mutates reward_data['special'] in-place.

    Drops:
      - Guaranteed: Sigil of Corruption
      - 25%: Uncut Paradise Jewel
      - 0.01%: Rune of Mirage (Imperfect)
    """
    if not getattr(monster, "is_corrupted", False):
        return

    await bot.database.uber.increment_corruption_sigils(user_id, server_id, 1)
    reward_data["special"].append("☠️ Sigil of Corruption")

    if random.random() < 0.25:
        await bot.database.uber.increment_paradise_jewels(user_id, server_id, 1)
        reward_data["special"].append("💎 Uncut Paradise Jewel")

    if random.random() < 0.0001:
        await bot.database.users.modify_currency(user_id, "mirage_runes_imperfect", 1)
        reward_data["special"].append("🪞 Rune of Mirage (Imperfect)")
