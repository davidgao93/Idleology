"""
core/apex/mechanics.py — Pure business logic for Apex Hunts.

No I/O, no Discord, no DB — everything here is deterministic given inputs.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

from core.apex.data import (
    APEX_BY_ZONE,
    APEX_MONSTER_IMAGES,
    META_SHARD_DROP_CHANCES,
    PASSIVE_CATEGORY_MAP,
    PASSIVE_SHARD_MAP,
    RESONANCE_TABLE,
    UPGRADE_OUTCOMES,
    ZONE_DEFS,
)
from core.apex.models import ApexHuntProfile

if TYPE_CHECKING:
    from core.apex.models import SoulStone


CHARGE_REGEN_SECONDS: float = 2 * 3600  # 2 hours per charge
MAX_CHARGES: int = 5


class ApexMechanics:
    # ------------------------------------------------------------------
    # Charge management
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_charges(profile: ApexHuntProfile) -> tuple[int, float | None]:
        """
        Applies elapsed-time charge regeneration and returns
        (new_charge_count, new_last_charge_time).

        Call this before any hunt operation; persist the returned values if changed.
        """
        charges = profile.hunt_charges
        last_ts = profile.last_charge_time

        if charges >= MAX_CHARGES:
            return MAX_CHARGES, None  # Full — clear the timestamp

        if last_ts is None:
            # No regen timer running yet
            return charges, None

        now = time.time()
        elapsed = now - last_ts
        regen_count = int(elapsed // CHARGE_REGEN_SECONDS)

        if regen_count <= 0:
            return charges, last_ts

        new_charges = min(MAX_CHARGES, charges + regen_count)
        if new_charges >= MAX_CHARGES:
            return MAX_CHARGES, None

        # Advance timestamp by the consumed regen intervals
        new_ts = last_ts + regen_count * CHARGE_REGEN_SECONDS
        return new_charges, new_ts

    @staticmethod
    def seconds_until_next_charge(profile: ApexHuntProfile) -> int:
        """Returns seconds until the next charge regenerates (0 if already full)."""
        charges, _ = ApexMechanics.calculate_charges(profile)
        if charges >= MAX_CHARGES:
            return 0
        last_ts = profile.last_charge_time
        if last_ts is None:
            return 0
        now = time.time()
        elapsed = now - last_ts
        remaining = CHARGE_REGEN_SECONDS - (elapsed % CHARGE_REGEN_SECONDS)
        return max(0, int(remaining))

    # ------------------------------------------------------------------
    # Monster selection and construction
    # ------------------------------------------------------------------

    @staticmethod
    def select_apex(zone_key: str):
        """Randomly selects an ApexMonsterDef from the given zone."""
        pool = APEX_BY_ZONE.get(zone_key, [])
        if not pool:
            raise ValueError(f"No apex monsters defined for zone: {zone_key}")
        return random.choice(pool)

    @staticmethod
    def build_apex_monster(apex_def, player_level: int):
        """
        Constructs a Monster from an ApexMonsterDef scaled to the player's level.
        Returns a fully populated Monster instance.
        """
        from core.combat.mobgen.modifier_data import make_modifier
        from core.combat.models import Monster

        # Apex hunts are endgame content (unlock at 90): monsters sit well above the player
        monster_level = max(100, player_level + random.randint(30, 50))

        # Stats: noticeably stronger than normal mobs at the same level.
        # ATK/DEF carry a +20% difficulty tuning pass on top of the base multiplier.
        hp_base = int(monster_level * 140 * random.uniform(0.9, 1.1))
        atk_base = int(monster_level * 8.5 * 1.2 * random.uniform(0.9, 1.1))
        def_base = int(monster_level * 4.5 * 1.2 * random.uniform(0.9, 1.1))
        xp_base = int(monster_level * 55)

        # Build modifiers — use the monster's defined modifier names
        modifiers = []
        for mod_name in set(apex_def.modifiers):  # deduplicate
            try:
                mod = make_modifier(mod_name, monster_level)
                if mod:
                    modifiers.append(mod)
            except Exception:
                pass  # Silently skip unknown/invalid modifiers

        return Monster(
            name=apex_def.name,
            level=monster_level,
            hp=hp_base,
            max_hp=hp_base,
            xp=xp_base,
            attack=atk_base,
            defence=def_base,
            modifiers=modifiers,
            image=APEX_MONSTER_IMAGES.get(apex_def.name, apex_def.image),
            flavor=apex_def.flavor,
            species="Apex",
            is_boss=True,
            is_apex=True,
        )

    # ------------------------------------------------------------------
    # Zone modifier application
    # ------------------------------------------------------------------

    @staticmethod
    def apply_zone_modifier(player, monster, zone_key: str) -> str:
        """
        Mutates player CombatState and monster fields to apply the zone's
        signature effect at combat start.  Returns a log message.
        """
        zone = ZONE_DEFS.get(zone_key)
        if not zone:
            return ""

        # Tag both player and monster with the active zone
        player.cs.apex_zone = zone_key
        monster.apex_zone = zone_key

        if zone.modifier_key == "scorched":
            player.cs.atk_multiplier += 0.20
            monster.flashfire_charges = 5  # Start at 5 instead of 0
            monster.zone_dmg_boost = 0.25
            return (
                "🔥 **Scorched Zone** — Your ATK is boosted +20%. "
                f"{monster.name}'s Flashfire charges start at 5 and deal +25% damage!"
            )

        elif zone.modifier_key == "tempest":
            player.cs.bonus_crit += 15
            return (
                "⚡ **Tempest Zone** — Crit Chance +15%. "
                "Every 3rd monster turn, unavoidable lightning strikes for 10% max HP true damage!"
            )

        elif zone.modifier_key == "siege_grounds":
            player.cs.atk_multiplier += 0.30
            monster.ward = int(monster.max_hp * 0.35)
            monster.zone_dr = 0.35
            return (
                "🏰 **Siege Grounds** — Your ATK +30%. "
                f"{monster.name} starts with 35% max HP Ward and gains +35% DR!"
            )

        elif zone.modifier_key == "living_battlefield":
            return (
                "🌿 **Living Battlefield** — "
                f"{monster.name} regenerates 0.5%/turn. You heal 1% max HP on each connected hit!"
            )

        elif zone.modifier_key == "tempted_fate":
            return (
                "💰 **Tempted Fate** — All XP and Gold doubled! "
                "Every 3rd monster turn, your ward is fully drained!"
            )

        elif zone.modifier_key == "reality_fracture":
            return (
                "🌀 **Reality Fracture** — "
                "One of the monster's modifiers rerolls every 4 turns. "
                "You have a 12% chance each turn to force a critical hit!"
            )

        return ""

    # ------------------------------------------------------------------
    # Extraction mechanics
    # ------------------------------------------------------------------

    @staticmethod
    def extraction_chance(
        passive_count: int,
        has_corrupted: bool,
        primal_essence_count: int = 0,
    ) -> float:
        """
        Returns the base extraction success probability (0–1).

        Formula:
          passive_count_effective = passive_count + primal_essence_count (max 4 effective passives)
          base = min(0.10 + 0.15 * effective_passives, 0.55)
          corrupted essence adds +0.10 bonus
        """
        effective = min(4, passive_count + primal_essence_count)
        base = min(0.10 + 0.15 * effective, 0.55)
        if has_corrupted:
            base = min(1.0, base + 0.10)
        return base

    @staticmethod
    def roll_extraction(base_chance: float, sharpened_fang: bool = False) -> bool:
        """
        Rolls for extraction success.
        With Sharpened Fang: P = 1 − (1 − base)² (lucky mechanic).
        """
        if sharpened_fang:
            p = 1.0 - (1.0 - base_chance) ** 2
        else:
            p = base_chance
        return random.random() < p

    # ------------------------------------------------------------------
    # Upgrade mechanics
    # ------------------------------------------------------------------

    @staticmethod
    def upgrade_outcomes_display(
        tier: int, engorged_heart: bool = False, condensed_blood: bool = False
    ) -> tuple[float, float, float]:
        """
        Returns (success%, stay%, downgrade%) as display percentages (0–100).
        Adjustments:
          Engorged Heart: lucky success → P_suc = 1 − (1 − base_suc)²
          Condensed Blood: downgrade → 0, remainder added to stay
        """
        if tier < 1 or tier > 4:
            raise ValueError(f"Cannot upgrade from tier {tier}")
        base_suc, base_stay, base_down = UPGRADE_OUTCOMES[tier]

        if condensed_blood:
            base_stay = base_stay + base_down
            base_down = 0.0

        if engorged_heart:
            lucky_suc = 1.0 - (1.0 - base_suc) ** 2
            delta = lucky_suc - base_suc
            base_suc = lucky_suc
            # Redistribute delta from stay (can't exceed 1.0 total)
            base_stay = max(0.0, base_stay - delta)
            base_down = max(0.0, 1.0 - base_suc - base_stay)

        return (
            round(base_suc * 100, 1),
            round(base_stay * 100, 1),
            round(base_down * 100, 1),
        )

    @staticmethod
    def roll_upgrade(
        tier: int, engorged_heart: bool = False, condensed_blood: bool = False
    ) -> str:
        """Returns 'success', 'stay', or 'downgrade'."""
        suc_pct, stay_pct, _ = ApexMechanics.upgrade_outcomes_display(
            tier, engorged_heart, condensed_blood
        )
        roll = random.random() * 100
        if roll < suc_pct:
            return "success"
        elif roll < suc_pct + stay_pct:
            return "stay"
        return "downgrade"

    # ------------------------------------------------------------------
    # Victory / defeat drop rolls
    # ------------------------------------------------------------------

    @staticmethod
    def roll_victory_drops(zone_key: str) -> dict:
        """
        Rolls loot for a successful apex hunt.
        Returns {
            'shard_type': str,
            'shard_amount': int,     # 15-25, avg 20
            'meta': dict             # meta shard type → count (0 or 1 each)
        }
        """
        zone = ZONE_DEFS.get(zone_key)
        shard_type = zone.shard_type if zone else "rift"
        shard_amount = random.randint(15, 25)

        meta: dict[str, int] = {}
        for meta_name, chance in META_SHARD_DROP_CHANCES.items():
            if random.random() < chance:
                meta[meta_name] = 1

        return {
            "shard_type": shard_type,
            "shard_amount": shard_amount,
            "meta": meta,
        }

    @staticmethod
    def roll_defeat_drops() -> int:
        """Returns 1–3 soul fragments as consolation for a defeat."""
        return random.randint(1, 3)

    # ------------------------------------------------------------------
    # Resonance helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_resonance(soul_stone: "SoulStone") -> tuple[str, str] | None:
        """Returns (name, description) of active resonance, or None."""
        key = soul_stone.resonance_key
        if key:
            return RESONANCE_TABLE.get(key)
        return None

    @staticmethod
    def get_resonance_multipliers(soul_stone: "SoulStone") -> dict:
        """
        Returns a dict of resonance combat multipliers.
        Keys: 'atk_mult', 'def_mult', 'xp_bonus_pct', 'gold_bonus_pct', 'tyr_pct'
        """
        result = {
            "atk_mult": 1.0,
            "def_mult": 1.0,
            "xp_bonus_pct": 0.0,
            "gold_bonus_pct": 0.0,
            "tyr_pct": 0.0,
        }
        key = soul_stone.resonance_key if soul_stone else None
        if not key:
            return result
        if key == "offensive_2":
            result["atk_mult"] = 1.10
        elif key == "offensive_3":
            result["atk_mult"] = 1.25
        elif key == "defensive_2":
            result["def_mult"] = 1.08
        elif key == "defensive_3":
            result["def_mult"] = 1.15
        elif key == "mixed_2":
            result["tyr_pct"] = 0.05
        elif key == "mixed_3":
            result["tyr_pct"] = 0.20
        elif key == "utility_2":
            result["xp_bonus_pct"] = 20.0
        elif key == "utility_3":
            result["gold_bonus_pct"] = 20.0
        return result

    # ------------------------------------------------------------------
    # Passive eligibility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_extractable_passives(item) -> list[str]:
        """
        Returns passives eligible for soul stone extraction — only at max rank.

        Rank requirements per item type:
          Weapon     — tier 5 suffix (e.g. "burning_5"); infernal passive has no tier → always eligible
          Armor      — any rank (only 1 tier exists)
          Accessory  — passive_lvl >= 10
          Glove      — passive_lvl >= 5
          Boot       — passive_lvl >= 6
          Helmet     — passive_lvl >= 5
        """
        candidates: list[str] = []
        item_type_name = type(item).__name__  # "Weapon", "Armor", etc.

        def _add_if_eligible(passive_str: str | None) -> None:
            if not passive_str or passive_str in ("none", ""):
                return
            # Strip tier suffix to get the base lookup key
            if "_" in passive_str:
                base = passive_str.rsplit("_", 1)[0]
            else:
                base = passive_str
            key = (
                base.lower()
                if base.lower() in PASSIVE_SHARD_MAP
                else passive_str.lower()
            )
            if key in PASSIVE_SHARD_MAP and key not in candidates:
                candidates.append(key)

        if item_type_name == "Weapon":
            for attr in ("passive", "p_passive", "u_passive"):
                ps = getattr(item, attr, None)
                if not ps or ps in ("none", ""):
                    continue
                # Weapon passives have a tier suffix — only accept tier 5
                if "_" in ps:
                    try:
                        tier = int(ps.rsplit("_", 1)[1])
                        if tier >= 5:
                            _add_if_eligible(ps)
                    except (ValueError, IndexError):
                        pass
            # Infernal passive has no tier suffix — always eligible if present
            inf = getattr(item, "infernal_passive", None)
            if inf and inf not in ("none", ""):
                _add_if_eligible(inf)

        elif item_type_name == "Armor":
            # Armor passives have only one tier — always eligible
            _add_if_eligible(getattr(item, "passive", None))

        elif item_type_name == "Accessory":
            if (getattr(item, "passive_lvl", 0) or 0) >= 10:
                _add_if_eligible(getattr(item, "passive", None))

        elif item_type_name == "Glove":
            if (getattr(item, "passive_lvl", 0) or 0) >= 5:
                _add_if_eligible(getattr(item, "passive", None))

        elif item_type_name == "Boot":
            if (getattr(item, "passive_lvl", 0) or 0) >= 6:
                _add_if_eligible(getattr(item, "passive", None))

        elif item_type_name == "Helmet":
            if (getattr(item, "passive_lvl", 0) or 0) >= 5:
                _add_if_eligible(getattr(item, "passive", None))

        return candidates

    @staticmethod
    def get_passive_shard_type(passive_key: str) -> str:
        """Returns the shard type for a given passive (defaults to 'fortune')."""
        return PASSIVE_SHARD_MAP.get(passive_key, "fortune")

    @staticmethod
    def get_passive_category(passive_key: str) -> str:
        """Returns the combat category for a given passive (defaults to 'utility')."""
        return PASSIVE_CATEGORY_MAP.get(passive_key, "utility")

    @staticmethod
    def get_soul_stone_passive_description(passive_key: str, tier: int) -> str | None:
        """
        Returns what the given passive grants at the specified Soul Stone tier (1-5),
        using the exact formula the combat engine applies for that passive — sourced
        from core/character/passive_data.py wherever a gear-side formula exists.

        Returns None if the passive has no combat effect wired yet (it can still be
        imprinted, but currently does nothing in combat).
        """
        from core.apex.data import SOUL_STONE_TIER_VALUES as _SST
        from core.character.passive_data import (
            _ACCESSORY_PASSIVE_FUNCS,
            _BOOT_PASSIVE_FUNCS,
            _GLOVE_PASSIVE_FUNCS,
            _HELMET_PASSIVE_FUNCS,
            _WEAPON_PASSIVE_DESC,
        )

        tier = max(1, min(5, tier or 1))

        # Weapon-family — 1:1 tier match, described verbatim in passive_data.
        weapon_key = f"{passive_key}_{tier}"
        if weapon_key in _WEAPON_PASSIVE_DESC:
            return _WEAPON_PASSIVE_DESC[weapon_key]

        # Boot-family: most map tier directly to the gear lvl param. speedster/
        # skiller instead use the "6 gear tiers condensed to 5" ratio, matching
        # their explicit SOUL_STONE_TIER_VALUES entries.
        _boot_1to1 = ("hearty", "thrill-seeker", "cleric", "treasure-tracker")
        if passive_key in _boot_1to1 and passive_key in _BOOT_PASSIVE_FUNCS:
            return _BOOT_PASSIVE_FUNCS[passive_key](tier)
        if passive_key in ("speedster", "skiller") and passive_key in _BOOT_PASSIVE_FUNCS:
            return _BOOT_PASSIVE_FUNCS[passive_key](tier * 6 / 5)

        # Helmet-family — 1:1 tier match.
        _helmet_1to1 = (
            "juggernaut",
            "leeching",
            "frenzy",
            "insight",
            "ghosted",
            "thorns",
            "volatile",
            "divine",
        )
        if passive_key in _helmet_1to1 and passive_key in _HELMET_PASSIVE_FUNCS:
            return _HELMET_PASSIVE_FUNCS[passive_key](tier)

        # Glove-family — 1:1 tier match.
        _glove_1to1 = (
            "deftness",
            "adroit",
            "ward-touched",
            "ward-fused",
            "instability",
            "plundering",
            "equilibrium",
        )
        if passive_key in _glove_1to1 and passive_key in _GLOVE_PASSIVE_FUNCS:
            return _GLOVE_PASSIVE_FUNCS[passive_key](tier)

        # Accessory-family — 2:1 tier mapping (soul stone tier x2 = equivalent lvl).
        _accessory_2to1 = ("absorb", "obliterate", "lucky strikes", "prosper", "infinite wisdom")
        if passive_key in _accessory_2to1 and passive_key in _ACCESSORY_PASSIVE_FUNCS:
            return _ACCESSORY_PASSIVE_FUNCS[passive_key](tier * 2)

        # Armor-family (Imbue passives): the gear item itself has no tiers, so
        # there's no lvl-parameterized template to reuse — hand-templated against
        # the SOUL_STONE_TIER_VALUES table instead, mirroring _ARMOR_PASSIVE_DESC wording.
        if passive_key == "impregnable":
            v = _SST["impregnable"][tier - 1]
            return f"During combat: Your PDR cap is increased by {v}% ({80 + v}% cap)"
        if passive_key == "piety":
            v = _SST["piety"][tier - 1]
            return f"On hit: 10% chance to deal {v}% increased damage"
        if passive_key == "transcendence":
            v = _SST["transcendence"][tier - 1]
            return f"Combat start: Gain {v}% of your total ATK and DEF as bonus ATK"
        if passive_key == "treasure hunter":
            v = _SST["treasure hunter"][tier - 1]
            return (
                f"Combat start: +{v:.1f}% bonus Rarity "
                "(also grants the standard +3% Special Rarity on victory)"
            )
        if passive_key == "unlimited wealth":
            v = _SST["unlimited wealth"][tier - 1]
            return f"Combat start: 20% chance to gain {v}% more Rarity as bonus rarity"
        if passive_key == "alchemist":
            v = _SST["alchemist"][tier - 1]
            return f"During combat: {v}% chance to not consume a potion on use"

        return None  # not yet wired into combat
