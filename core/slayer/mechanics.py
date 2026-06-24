import csv
import os
import random
from collections import Counter
from typing import Callable, Tuple


def _slayer_xp_threshold(lvl: int) -> int:
    """XP required to advance from level `lvl` to `lvl+1`."""
    return lvl * 500 + max(0, lvl - 70) ** 2 * 800


# Canonical display names for slayer emblem passive types.
SLAYER_PASSIVE_NAMES: dict[str, str] = {
    "slayer_dmg": "Slayer Target Damage",
    "boss_dmg": "Boss Damage",
    "combat_dmg": "Normal Monster Damage",
    "gold_find": "Gold Find",
    "xp_find": "XP Find",
    "slayer_def": "Slayer Target Defense",
    "crit_dmg": "Critical Hit Damage",
    "accuracy": "Accuracy",
    "task_progress": "Double Task Progress",
    "slayer_drops": "Slayer Material Drop Rate",
    "corrupted_find": "Corrupted Attunement",
}

# Canonical description lambdas for slayer emblem passives.
# Key: p_type string; Value: lambda(tier: int) → plain-text effect string.
SLAYER_PASSIVE_DEFS: dict[str, Callable[[int], str]] = {
    "slayer_dmg": lambda t: f"+{t * 5}% damage vs assigned slayer species",
    "boss_dmg": lambda t: f"+{t * 5}% damage vs bosses",
    "combat_dmg": lambda t: f"+{t * 2}% damage vs normal monsters",
    "slayer_def": lambda t: f"+{t * 2}% defence vs assigned slayer species",
    "crit_dmg": lambda t: f"+{t * 5}% critical hit damage multiplier",
    "accuracy": lambda t: f"+{t * 2} flat accuracy roll",
    "gold_find": lambda t: f"+{t * 3}% gold from combat",
    "xp_find": lambda t: f"+{t * 3}% XP from combat",
    "task_progress": lambda t: f"{t * 5}% chance for a task kill to count twice",
    "slayer_drops": lambda t: f"{t * 5}% chance for extra slayer material drops",
    "corrupted_find": lambda t: f"+{t * 0.2:.1f}% corrupted spawn chance",
}


BOSS_TASK_PREFIX = "BOSS:"

# ---------------------------------------------------------------------------
# Slayer Tree
# ---------------------------------------------------------------------------

TREE_RESET_COST = 20  # Violent Essence; gives back 80% of points_spent

# Node definitions: prereq is the node_id that must be owned first.
# Hunter nodes store the player's *choice* as the value (string), not True.
SLAYER_TREE_NODES: dict[str, dict] = {
    # Taskmaster branch
    "tm_1": {
        "branch": "taskmaster",
        "name": "Oversized Contract",
        "cost": 20,
        "prereq": None,
        "desc": "Task sizes +20%",
    },
    "tm_2": {
        "branch": "taskmaster",
        "name": "Favored Target",
        "cost": 35,
        "prereq": "tm_1",
        "desc": "50% increased chance of a boss task",
    },
    "tm_3": {
        "branch": "taskmaster",
        "name": "Executioner's High",
        "cost": 55,
        "prereq": "tm_2",
        "desc": "50% chance to double Slayer XP burst on task completion",
    },
    "tm_4": {
        "branch": "taskmaster",
        "name": "Relentless",
        "cost": 85,
        "prereq": "tm_3",
        "desc": "+250 flat Slayer XP per kill while on task",
    },
    # Hunter branch — choice nodes (value = chosen option string)
    "hu_1": {
        "branch": "hunter",
        "name": "Slayer's Edge",
        "cost": 20,
        "prereq": None,
        "choices": [
            ("accuracy", "+8 Accuracy vs task species"),
            ("crit", "+8 Crit Chance vs task species"),
            ("atk", "+18% ATK vs task species"),
        ],
    },
    "hu_2": {
        "branch": "hunter",
        "name": "Hunter's Resolve",
        "cost": 35,
        "prereq": "hu_1",
        "choices": [
            ("pdr", "+8% PDR vs task species"),
            ("fdr", "+24 flat FDR vs task species"),
            ("def", "+18% DEF vs task species"),
        ],
    },
    "hu_3": {
        "branch": "hunter",
        "name": "Killing Blow",
        "cost": 55,
        "prereq": "hu_2",
        "choices": [
            ("dmg", "+25% damage dealt vs task species"),
            ("tank", "+25% damage taken reduction vs task species"),
        ],
    },
    "hu_4": {
        "branch": "hunter",
        "name": "Apex Predator",
        "cost": 85,
        "prereq": "hu_3",
        "choices": [
            ("slay", "5% chance to instantly slay (non-boss)"),
            (
                "zenith",
                "5% chance next encounter spawns a Zenith monster (+100% ATK/DEF, drops guaranteed Imbued Heart)",
            ),
        ],
    },
    # Purveyor branch
    "pu_1": {
        "branch": "purveyor",
        "name": "Black Contract",
        "cost": 20,
        "prereq": None,
        "desc": "Task skips cost 30% fewer Slayer Points",
    },
    "pu_2": {
        "branch": "purveyor",
        "name": "Slayer's Fortune",
        "cost": 35,
        "prereq": "pu_1",
        "desc": "+25% bonus Slayer Points on task completion",
    },
    "pu_3": {
        "branch": "purveyor",
        "name": "Material Market",
        "cost": 55,
        "prereq": "pu_2",
        "desc": "Unlock Shop: buy 1 Violent Essence for 40 pts",
    },
    "pu_4": {
        "branch": "purveyor",
        "name": "Essence Exchange",
        "cost": 85,
        "prereq": "pu_3",
        "desc": "Unlock Shop: buy 1 Imbued Heart for 120 pts",
    },
}


def get_tree_bonuses(nodes_owned: dict) -> dict:
    """Converts raw nodes_owned dict into structured bonus values for combat/UI use."""
    return {
        "tm_1": bool(nodes_owned.get("tm_1")),
        "tm_2": bool(nodes_owned.get("tm_2")),
        "tm_3": bool(nodes_owned.get("tm_3")),
        "tm_4": bool(nodes_owned.get("tm_4")),
        "hu_1": nodes_owned.get("hu_1") or None,  # "accuracy", "crit", or "atk"
        "hu_2": nodes_owned.get("hu_2") or None,  # "pdr", "fdr", or "def"
        "hu_3": nodes_owned.get("hu_3") or None,  # "dmg" or "tank"
        "hu_4": nodes_owned.get("hu_4") or None,  # "slay" or "zenith"
        "pu_1": bool(nodes_owned.get("pu_1")),
        "pu_2": bool(nodes_owned.get("pu_2")),
        "pu_3": bool(nodes_owned.get("pu_3")),
        "pu_4": bool(nodes_owned.get("pu_4")),
    }


# Level-gated boss hunt targets.  ``key`` is appended to BOSS_TASK_PREFIX and
# used to match monsters in combat; ``name`` is the display name shown to the player.
BOSS_TASK_CATALOG = [
    {"key": "aphrodite", "name": "Aphrodite", "min_level": 20},
    {"key": "lucifer", "name": "Lucifer", "min_level": 30},
    {"key": "gemini", "name": "Gemini", "min_level": 40},
    {"key": "NEET", "name": "NEET", "min_level": 50},
]

# Slayer XP awarded per boss kill (10× normal kill XP of 500).
BOSS_TASK_XP_PER_KILL = 5_000
# Flat XP bonus on boss task completion.
BOSS_TASK_COMPLETION_XP = 20_000


class SlayerMechanics:
    PASSIVE_POOL = [
        "slayer_dmg",
        "boss_dmg",
        "combat_dmg",
        "gold_find",
        "xp_find",
        "slayer_def",
        "crit_dmg",
        "accuracy",
        "task_progress",
        "slayer_drops",
        "corrupted_find",
    ]

    @staticmethod
    def calculate_level_from_xp(xp: int) -> int:
        lvl = 1
        while xp >= _slayer_xp_threshold(lvl):
            xp -= _slayer_xp_threshold(lvl)
            lvl += 1
        return lvl

    @staticmethod
    def available_boss_tasks(player_level: int) -> list[dict]:
        """Returns the boss-task catalog entries the player can currently access."""
        return [b for b in BOSS_TASK_CATALOG if player_level >= b["min_level"]]

    @staticmethod
    def generate_task(player_level: int) -> Tuple[str, int]:
        """Reads monsters.csv, weights species by frequency in bracket, returns (Species, Amount)"""
        csv_path = os.path.join(os.path.dirname(__file__), "../../assets/monsters.csv")
        bracket_min = max(1, player_level - 50)
        bracket_max = min(110, player_level + 10)

        species_pool = []
        try:
            with open(csv_path, newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    m_lvl = int(row["level"]) * 10
                    if bracket_min <= m_lvl <= bracket_max:
                        species_pool.append(row.get("species", "Humanoid"))
        except Exception:
            species_pool = ["Humanoid"]  # Fallback

        if not species_pool:
            species_pool = ["Humanoid"]

        counts = Counter(species_pool)

        # Weight species selection by how frequently each appears in the bracket pool
        chosen_species = random.choices(list(counts.keys()), weights=list(counts.values()), k=1)[0]

        # Level-banded task sizes with variance
        if player_level < 20:
            base, variance = 5, 0.20
        elif player_level < 40:
            base, variance = 10, 0.30
        else:
            base, variance = 15, 0.50

        amount = max(1, round(base * random.uniform(1 - variance, 1 + variance)))

        return chosen_species, amount

    @staticmethod
    def calculate_task_rewards(amount: int) -> Tuple[int, int]:
        """Returns (XP, Points). Linear scaling."""
        # Completion burst: 800 XP per monster in the task, +1 Point per monster.
        return (amount * 800), amount

    @staticmethod
    def roll_drops(monster_level: int) -> Tuple[int, int]:
        """Returns (ViolentEssenceFound, ImbuedHeartsFound)"""
        essence, hearts = 0, 0

        # Scales slightly with level. e.g., Lvl 100 = 20% essence, 2% heart
        e_chance = 0.10 + (monster_level * 0.001)
        h_chance = 0.01 + (monster_level * 0.0001)

        if random.random() < e_chance:
            essence = 1
        if random.random() < h_chance:
            hearts = 1
        return essence, hearts

    @staticmethod
    def roll_upgrade(current_tier: int) -> Tuple[bool, int]:
        """
        Returns (Success, NewTier).
        Implements the Korean MMO tiering logic requested.
        """
        if current_tier >= 5:
            return False, 5

        # Success Chances: T1(80%), T2(60%), T3(40%), T4(20%)
        success_chance = 1.0 - (current_tier * 0.20)

        if random.random() <= success_chance:
            return True, current_tier + 1

        # Failed - Calculate Downgrade
        # T1 (No downgrade), T2(20%), T3(40%), T4(60%)
        downgrade_chance = (current_tier - 1) * 0.20
        new_tier = current_tier
        if random.random() <= downgrade_chance and current_tier > 1:
            new_tier -= 1

        return False, new_tier

    @staticmethod
    def get_unlocked_slots(slayer_level: int) -> int:
        """1 slot every 20 levels. Max 5 at Lvl 80+"""
        if slayer_level >= 80:
            return 5
        if slayer_level >= 50:
            return 4
        if slayer_level >= 20:
            return 3
        if slayer_level >= 10:
            return 2
        return 1

    @staticmethod
    def get_xp_progress(total_xp: int) -> Tuple[int, int]:
        """
        Returns (xp_into_current_level, xp_needed_for_next_level).
        Converts cumulative DB XP into a clean UI format.
        """
        lvl = 1
        rem_xp = total_xp
        while rem_xp >= _slayer_xp_threshold(lvl):
            rem_xp -= _slayer_xp_threshold(lvl)
            lvl += 1

        return rem_xp, _slayer_xp_threshold(lvl)

    @staticmethod
    def get_passive_description(p_type: str, tier: int) -> str:
        """Returns a fully formatted string with the calculated mathematical bonus."""
        if p_type == "none" or not p_type:
            return "Empty Slot"
        name = SLAYER_PASSIVE_NAMES.get(p_type, p_type)
        fn = SLAYER_PASSIVE_DEFS.get(p_type)
        if fn:
            return f"{name} ({fn(tier)})"
        return f"{name} (Tier {tier})"
