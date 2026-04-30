# ---------------------------------------------------------------------------
# Skill display name mapping
# ---------------------------------------------------------------------------

_SKILL_DISPLAY_NAMES = {
    # Common combat
    "co_joint_attack": "Twin Strike",
    "co_heal": "Mending Aura",
    "co_damage_reduction": "Guardian's Shield",
    "co_stat_transfer": "Synergy Bond",
    "co_monster_debuff": "Weakening Hex",
    "co_xp_boost": "Scholar's Pact",
    "co_gold_boost": "Treasure Sense",
    "co_special_rarity": "Fortune's Eye",
    "co_atk_from_def": "Iron Will",
    "co_def_from_atk": "Steadfast Vanguard",
    "co_curse_damage": "Cursed Aegis",
    "co_curse_taken": "Marked Prey",
    # Rare combat
    "co_crit_rate": "Predator's Instinct",
    "co_crit_damage": "Brutal Momentum",
    "co_execute": "Final Verdict",
    "co_ward_regen": "Arcane Barrier",
    "co_ward_leech": "Ward Leech",
    # Common dispatch
    "di_exp_boost": "Seasoned Mentor",
    "di_gold_boost": "Profiteer's Route",
    "di_extra_reward": "Scavenger's Eye",
    "di_skilling_boost": "Harvester's Touch",
    # Rare dispatch
    "di_settlement_mat": "Resource Scout",
    "di_boss_reward": "Warlord's Plunder",
    "di_contract_find": "Informant Network",
    "di_pinnacle_find": "Relic Hunter",
}


def _skill_display_name(key: str) -> str:
    return _SKILL_DISPLAY_NAMES.get(key, key)


_RARITY_COLOURS = {4: 0xA8D8EA, 5: 0xFFD700, 6: 0xFF6B6B}


def _rarity_colour(rarity: int) -> int:
    return _RARITY_COLOURS.get(rarity, 0xFFFFFF)


def _stars(rarity: int) -> str:
    return "★" * rarity
