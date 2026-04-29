from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class Weapon:
    user: str
    name: str
    level: int
    attack: int
    defence: int
    rarity: int
    passive: str
    description: str
    p_passive: str
    u_passive: str
    item_id: Optional[int] = None
    is_equipped: bool = False
    forges_remaining: int = 0
    refines_remaining: int = 0
    refinement_lvl: int = 0
    infernal_passive: str = "none"
    forge_tier: int = 0


@dataclass
class Accessory:
    user: str
    name: str
    level: int
    attack: int
    defence: int
    rarity: int
    ward: int
    crit: int
    passive: str
    passive_lvl: int
    description: str
    item_id: Optional[int] = None
    is_equipped: bool = False
    potential_remaining: int = 0
    void_passive: str = "none"


@dataclass
class Armor:
    user: str
    name: str
    level: int
    block: int
    evasion: int
    ward: int
    pdr: int
    fdr: int
    passive: str
    description: str
    item_id: Optional[int] = None
    is_equipped: bool = False
    temper_remaining: int = 0
    imbue_remaining: int = 0
    celestial_passive: str = "none"


@dataclass
class Glove:
    user: str
    name: str
    level: int
    item_id: Optional[int] = None
    attack: int = 0
    defence: int = 0
    ward: int = 0  # Percentage
    pdr: int = 0  # Percentage
    fdr: int = 0  # Flat
    passive: str = "none"
    passive_lvl: int = 0
    description: str = ""
    is_equipped: bool = False
    potential_remaining: int = 0
    essence_1: str = "none"
    essence_1_val: float = 0.0
    essence_2: str = "none"
    essence_2_val: float = 0.0
    essence_3: str = "none"
    essence_3_val: float = 0.0
    corrupted_essence: str = "none"


@dataclass
class Boot:
    user: str
    name: str
    level: int
    item_id: Optional[int] = None
    attack: int = 0
    defence: int = 0
    ward: int = 0  # Percentage
    pdr: int = 0  # Percentage
    fdr: int = 0  # Flat
    passive: str = "none"
    passive_lvl: int = 0
    description: str = ""
    is_equipped: bool = False
    potential_remaining: int = 0
    essence_1: str = "none"
    essence_1_val: float = 0.0
    essence_2: str = "none"
    essence_2_val: float = 0.0
    essence_3: str = "none"
    essence_3_val: float = 0.0
    corrupted_essence: str = "none"


@dataclass
class Helmet:
    user: str
    name: str
    level: int
    item_id: Optional[int] = None
    defence: int = 0
    ward: int = 0  # Percentage
    pdr: int = 0
    fdr: int = 0
    passive: str = "none"
    passive_lvl: int = 0
    description: str = ""
    is_equipped: bool = False
    potential_remaining: int = 0
    essence_1: str = "none"
    essence_1_val: float = 0.0
    essence_2: str = "none"
    essence_2_val: float = 0.0
    essence_3: str = "none"
    essence_3_val: float = 0.0
    corrupted_essence: str = "none"


@dataclass
class Companion:
    id: int
    user_id: str
    name: str
    species: str
    image_url: str
    level: int
    exp: int
    passive_type: str
    passive_tier: int
    is_active: bool = False
    balanced_passive: str = "none"
    balanced_passive_tier: int = 0

    @property
    def passive_value(self) -> int:
        """Calculates the numerical value based on Type and Tier."""
        # Tier scaling logic
        if self.passive_type in ["atk", "def"]:  # Percentage
            return 4 + self.passive_tier  # 5, 6, 7, 8, 9
        elif self.passive_type in ["hit", "crit"]:  # Flat
            return self.passive_tier  # 1, 2, 3, 4, 5
        elif self.passive_type == "ward":  # Percentage
            return self.passive_tier * 5  # 5, 10, 15, 20, 25
        elif self.passive_type == "rarity":  # Base Rarity
            return self.passive_tier * 3  # 3, 6, 9, 12, 15
        elif self.passive_type == "s_rarity":  # Special Rarity
            return self.passive_tier  # 1, 2, 3, 4, 5
        elif self.passive_type == "fdr":  # Flat Damage Reduction
            return 1 + self.passive_tier  # 2, 3, 4, 5, 6
        elif self.passive_type == "pdr":  # Percent Damage Reduction
            return 2 + self.passive_tier  # 3, 4, 5, 6, 7
        return 0

    @property
    def description(self) -> str:
        """Returns formatted string like '+9% Atk'"""
        val = self.passive_value
        p_map = {
            "atk": f"+{val}% Atk",
            "def": f"+{val}% Def",
            "hit": f"+{val} Hit Chance",
            "crit": f"+{val} Crit Chance",
            "ward": f"+{val}% HP as Ward",
            "rarity": f"+{val}% Rarity",
            "s_rarity": f"+{val}% Special Drop Rate",
            "fdr": f"+{val} Flat Dmg Red.",
            "pdr": f"+{val}% Dmg Red.",
        }
        return p_map.get(self.passive_type, "Unknown Effect")

    @property
    def balanced_passive_value(self) -> int:
        """Calculates the numerical value of the secondary balanced passive."""
        if self.balanced_passive == "none" or self.balanced_passive_tier == 0:
            return 0
        t = self.balanced_passive_tier
        if self.balanced_passive in ["atk", "def"]:
            return 4 + t
        elif self.balanced_passive in ["hit", "crit"]:
            return t
        elif self.balanced_passive == "ward":
            return t * 5
        elif self.balanced_passive == "rarity":
            return t * 3
        elif self.balanced_passive == "s_rarity":
            return t
        elif self.balanced_passive == "fdr":
            return 1 + t
        elif self.balanced_passive == "pdr":
            return 2 + t
        return 0

    @property
    def balanced_description(self) -> str:
        """Returns formatted string for the balanced passive."""
        if self.balanced_passive == "none" or self.balanced_passive_tier == 0:
            return "Not Awakened"
        val = self.balanced_passive_value
        p_map = {
            "atk": f"+{val}% Atk",
            "def": f"+{val}% Def",
            "hit": f"+{val} Hit Chance",
            "crit": f"+{val} Crit Chance",
            "ward": f"+{val}% Ward",
            "rarity": f"+{val}% Rarity",
            "s_rarity": f"+{val}% Special Drop Rate",
            "fdr": f"+{val} FDR",
            "pdr": f"+{val}% PDR",
        }
        return p_map.get(self.balanced_passive, "Unknown Effect")


@dataclass
class CodexTome:
    slot: int
    passive_type: str
    tier: int
    value: float  # Actual rolled stat contribution (not a fixed tier value)


_PART_SLOT_LABELS = {
    "head": "Head", "torso": "Torso",
    "right_arm": "Right Arm", "left_arm": "Left Arm",
    "right_leg": "Right Leg", "left_leg": "Left Leg",
    "cheeks": "Cheeks", "organs": "Organs",
}


@dataclass
class MonsterPart:
    id: int
    user_id: str
    slot_type: str
    monster_name: str
    ilvl: int
    hp_value: int

    @property
    def display_name(self) -> str:
        label = _PART_SLOT_LABELS.get(self.slot_type, self.slot_type.replace("_", " ").title())
        return f"{self.monster_name}'s **{label}**"


@dataclass
class Player:
    id: str
    name: str
    level: int
    ascension: int
    exp: int
    current_hp: int
    max_hp: int
    base_attack: int
    base_defence: int
    potions: int  # Moved UP: Mandatory field from DB

    # Fields with Defaults come LAST

    # Equipped Gear
    equipped_weapon: Optional[Weapon] = None
    equipped_accessory: Optional[Accessory] = None
    equipped_armor: Optional[Armor] = None
    equipped_glove: Optional[Glove] = None
    equipped_boot: Optional[Boot] = None
    equipped_helmet: Optional[Helmet] = None

    # Active Companions
    active_companions: List[Companion] = field(default_factory=list)

    # Settlement buffs
    apothecary_workers: int = 0
    barracks_workers: int = 0

    # Slayer
    slayer_emblem: dict = field(default_factory=dict)
    active_task_species: str = (
        None  # Store this so the engine knows if we are fighting a task mob
    )

    # Codex Tomes
    codex_tomes: List[CodexTome] = field(default_factory=list)

    # Alchemy — Potion Passives (loaded from DB, list of dicts)
    potion_passives: List[dict] = field(default_factory=list)

    # Alchemy — Transient combat state (reset each combat)
    alchemy_atk_boost_pct: float = (
        0.0  # Warrior's Draft: % ATK boost on next attack (resets after use)
    )
    alchemy_def_boost_pct: float = (
        0.0  # Iron Skin: % damage reduction for N monster turns
    )
    alchemy_def_boost_turns: int = 0  # Turns remaining for Iron Skin DEF boost
    alchemy_dmg_reduction_pct: float = (
        0.0  # Dulled Pain: % incoming dmg reduction (next attack only)
    )
    alchemy_dmg_reduction_turns: int = (
        0  # Turns remaining for Dulled Pain (1 = next attack)
    )
    alchemy_overcap_hp: int = 0  # Overcap Brew: temporary HP above max (lost on hit)
    alchemy_linger_hp: int = 0  # Lingering Remedy: heal per turn
    alchemy_linger_turns: int = 0  # Turns remaining for lingering heal
    alchemy_guaranteed_hit: bool = False  # Bottled Courage: next attack cannot miss

    # Transient states (reset each combat)
    combat_ward: int = 0
    is_invulnerable_this_combat: bool = False
    combat_cooldown_reduction_seconds: int = 0
    celestial_vow_used: bool = False

    # Infernal passive transients
    voracious_stacks: int = 0
    cursed_precision_active: bool = False

    # Void passive transients
    gaze_stacks: int = 0
    hunger_stacks: int = 0

    # Corrupted essence transients (reset each combat)
    lucifer_pdr_burst: int = 0  # Lucifer helmet: flat PDR added after ward breaks

    # Glove passives
    equilibrium_bonus_xp_pending: int = 0
    plundering_bonus_gold_pending: int = 0

    # Codex run transients (reset per wave)
    boon_fdr: int = 0

    # -----------------------------------------------------------------------
    # Flat stat cache  (immutable during combat)
    # Computed once by compute_flat_stats() at load time and after any
    # permanent stat change (level-up, gear swap mid-session).
    # Stores: base + all gear + essences + barracks.
    # -----------------------------------------------------------------------
    flat_atk: int = 0
    flat_def: int = 0

    # -----------------------------------------------------------------------
    # Per-combat bonus accumulators  (reset each combat / wave)
    # Zeroed by reset_combat_bonus().  All combat-start passives and chapter
    # signature modifiers write here instead of mutating base stats.
    # -----------------------------------------------------------------------
    bonus_atk: int = 0
    bonus_def: int = 0
    bonus_crit: int = (
        0  # Impenetrable, Cursed Precision, chapter signatures, crit boons
    )
    bonus_max_hp: int = 0  # Chapter signatures (Decaying, Cursed), Diabolic Pact

    # -----------------------------------------------------------------------
    # Unified stat multipliers  (reset each combat / wave)
    # Applied as  (flat + bonus) × multiplier  at the end of get_total_*.
    # Covers codex signatures/boons AND strong combat passives (diabolic_pact).
    # Reset to 1.0 by reset_combat_bonus().
    # -----------------------------------------------------------------------
    atk_multiplier: float = 1.0
    def_multiplier: float = 1.0
    crit_multiplier: float = (
        1.0  # Insight helmet passive, future multiplicative crit mods
    )

    # -----------------------------------------------------------------------
    # Ascension pinnacle unlocks  (loaded once at session start, never mutated)
    ascension_unlocks: set = field(default_factory=set)

    # Codex run permanent modifiers  (NOT reset by reset_combat_bonus)
    # Accumulated by fragment_boost downsides and max_hp_boost boon.
    # Zero for a fresh run.
    # -----------------------------------------------------------------------
    run_atk_penalty: int = 0
    run_def_penalty: int = 0
    run_crit_penalty: int = 0  # fragment_boost crit downside
    run_max_hp_bonus: int = 0  # max_hp_boost boon (+) and fragment_boost hp_penalty (−)
    bonus_rarity: int = 0  # per-wave rarity boon accumulator; reset at chapter boundary

    # Monster body parts equipped (loaded at session start)
    # {slot_type: {"hp": int, "monster_name": str}}
    equipped_parts: dict = field(default_factory=dict)

    @property
    def rarity(self) -> int:
        """Gear rarity from weapon and accessory. Use get_total_rarity() for the full total."""
        total = 0
        if self.equipped_weapon:
            total += self.equipped_weapon.rarity
        if self.equipped_accessory:
            total += self.equipped_accessory.rarity
        return total

    @property
    def total_max_hp(self) -> int:
        """Effective max HP including run bonuses, chapter penalties, vitality tome, and body parts."""
        vitality_pct = self.get_tome_bonus("vitality")
        asc_hp = self.get_ascension_bonuses()["hp"] if self.ascension_unlocks else 0
        parts_hp = sum(v["hp"] for v in self.equipped_parts.values()) if self.equipped_parts else 0
        base = self.max_hp + self.run_max_hp_bonus + self.bonus_max_hp + asc_hp + parts_hp
        if vitality_pct > 0:
            base = int(base * (1 + vitality_pct / 100))
        return max(1, base)

    def _get_companion_bonus(self, p_type: str) -> int:
        primary = sum(
            c.passive_value for c in self.active_companions if c.passive_type == p_type
        )
        balanced = sum(
            c.balanced_passive_value
            for c in self.active_companions
            if c.balanced_passive == p_type
        )
        return primary + balanced

    # -----------------------------------------------------------------------
    # Flat-total helpers (base + gear + essences + barracks, no % multipliers)
    # These are the correct multiplicand for all percentage-based bonuses
    # (companions, codex tomes, codex run multipliers) so that those bonuses
    # scale with equipped gear rather than only with the small base stat.
    # -----------------------------------------------------------------------

    def _get_flat_attack(self) -> int:
        from core.items.essence_mechanics import compute_essence_stat_bonus

        total = self.base_attack
        if self.equipped_weapon:
            total += self.equipped_weapon.attack
        if self.equipped_accessory:
            total += self.equipped_accessory.attack
        if self.equipped_glove:
            total += self.equipped_glove.attack
        if self.equipped_boot:
            total += self.equipped_boot.attack
        # Essence flat bonuses (glove + boot only — helmets have no attack)
        for item in (self.equipped_glove, self.equipped_boot):
            if item:
                total += compute_essence_stat_bonus(item).get("attack", 0)
        # Barracks: % of total gear-augmented attack
        if self.barracks_workers > 0:
            total += int(total * (self.barracks_workers * 0.0001))
        return total

    def _get_flat_defence(self) -> int:
        from core.items.essence_mechanics import compute_essence_stat_bonus

        total = self.base_defence
        if self.equipped_weapon:
            total += self.equipped_weapon.defence
        if self.equipped_accessory:
            total += self.equipped_accessory.defence
        if self.equipped_glove:
            total += self.equipped_glove.defence
        if self.equipped_boot:
            total += self.equipped_boot.defence
        if self.equipped_helmet:
            total += self.equipped_helmet.defence
        # Essence flat bonuses
        for item in (self.equipped_glove, self.equipped_boot, self.equipped_helmet):
            if item:
                total += compute_essence_stat_bonus(item).get("defence", 0)
        # Barracks: % of total gear-augmented defence
        if self.barracks_workers > 0:
            total += int(total * (self.barracks_workers * 0.0001))
        return total

    # -----------------------------------------------------------------------
    # Flat-stat cache management
    # -----------------------------------------------------------------------

    def compute_flat_stats(self) -> None:
        """
        Stores flat_atk and flat_def (base + gear + essences + barracks).
        Call after load_player() and after any permanent base-stat change
        (level-up, gear swap).  get_total_attack/defence read these cached
        values, so this must be called before combat begins.
        """
        self.flat_atk = self._get_flat_attack()
        self.flat_def = self._get_flat_defence()

    def reset_combat_bonus(self) -> None:
        """
        Zeros per-combat bonus stats and resets stat multipliers to 1.0.
        Call at the start of every combat or wave to prevent passive effects
        from compounding across fights.  Does NOT touch run_* fields
        (those are permanent within a codex run).
        """
        self.bonus_atk = 0
        self.bonus_def = 0
        self.bonus_crit = 0
        self.bonus_max_hp = 0
        self.atk_multiplier = 1.0
        self.def_multiplier = 1.0
        self.crit_multiplier = 1.0

    # -----------------------------------------------------------------------
    # Ascension pinnacle bonus helper
    # -----------------------------------------------------------------------

    def get_ascension_bonuses(self) -> dict:
        from core.ascent.mechanics import AscentMechanics

        return AscentMechanics.get_cumulative_pinnacle_bonuses(self.ascension_unlocks)

    # -----------------------------------------------------------------------
    # Total stat calculations
    # -----------------------------------------------------------------------

    def get_total_attack(self) -> int:
        flat = self.flat_atk  # pre-computed; immutable during combat

        # Layer 1: flat gear total + per-combat bonus accumulator
        total = flat + self.bonus_atk

        # Layer 2: always-on percentage bonuses (scale off flat, not base)
        comp_pct = self._get_companion_bonus("atk")
        if comp_pct > 0:
            total += int(flat * (comp_pct / 100))

        # Wrath tome: converts % of flat DEF into bonus ATK
        wrath_pct = self.get_tome_bonus("wrath")
        if wrath_pct > 0:
            total += int(self.flat_def * (wrath_pct / 100))

        # Layer 3: permanent run penalty (fragment_boost downside in codex runs)
        total -= self.run_atk_penalty

        # Layer 4: unified multiplier (codex signature/boon + diabolic_pact, etc.)
        if self.atk_multiplier != 1.0:
            total = int(total * self.atk_multiplier)

        # Layer 5: ascension pinnacle % bonus
        if self.ascension_unlocks:
            atk_pct = self.get_ascension_bonuses()["atk_pct"]
            if atk_pct:
                total = int(total * (1 + atk_pct / 100))

        return max(0, total)

    def get_total_defence(self) -> int:
        flat = self.flat_def  # pre-computed; immutable during combat

        # Layer 1: flat gear total + per-combat bonus accumulator
        total = flat + self.bonus_def

        # Layer 2: always-on percentage bonuses
        comp_pct = self._get_companion_bonus("def")
        if comp_pct > 0:
            total += int(flat * (comp_pct / 100))

        # Bastion tome: converts % of flat ATK into bonus DEF
        bastion_pct = self.get_tome_bonus("bastion")
        if bastion_pct > 0:
            total += int(self.flat_atk * (bastion_pct / 100))

        # Layer 3: permanent run penalty
        total -= self.run_def_penalty

        # Layer 4: unified multiplier
        if self.def_multiplier != 1.0:
            total = int(total * self.def_multiplier)

        # Layer 5: ascension pinnacle % bonus
        if self.ascension_unlocks:
            def_pct = self.get_ascension_bonuses()["def_pct"]
            if def_pct:
                total = int(total * (1 + def_pct / 100))

        return max(0, total)

    def get_total_pdr(self) -> int:
        from core.items.essence_mechanics import compute_essence_stat_bonus

        total = 0
        if self.equipped_armor:
            total += self.equipped_armor.pdr
        if self.equipped_glove:
            total += self.equipped_glove.pdr
        if self.equipped_boot:
            total += self.equipped_boot.pdr
        if self.equipped_helmet:
            total += self.equipped_helmet.pdr

        # Companions
        total += self._get_companion_bonus("pdr")

        # Bulwark tome: bonus PDR
        total += int(self.get_tome_bonus("bulwark"))

        # Essence bonuses
        for item in (self.equipped_glove, self.equipped_boot, self.equipped_helmet):
            if item:
                total += compute_essence_stat_bonus(item).get("pdr", 0)

        # Corrupted essence: Lucifer helmet — PDR burst on ward break (transient, persists rest of combat)
        total += self.lucifer_pdr_burst

        # Ascension pinnacle flat PDR
        if self.ascension_unlocks:
            total += self.get_ascension_bonuses()["pdr"]

        # Hard cap at 80%
        return min(80, total)

    def get_total_fdr(self) -> int:
        from core.items.essence_mechanics import compute_essence_stat_bonus

        total = 0
        if self.equipped_armor:
            total += self.equipped_armor.fdr
        if self.equipped_glove:
            total += self.equipped_glove.fdr
        if self.equipped_boot:
            total += self.equipped_boot.fdr
        if self.equipped_helmet:
            total += self.equipped_helmet.fdr

        # Companions
        total += self._get_companion_bonus("fdr")

        # Resilience tome: bonus flat damage reduction
        total += int(self.get_tome_bonus("resilience"))

        # Codex FDR boon (per-wave transient)
        total += self.boon_fdr

        # Essence bonuses
        for item in (self.equipped_glove, self.equipped_boot, self.equipped_helmet):
            if item:
                total += compute_essence_stat_bonus(item).get("fdr", 0)

        # Ascension pinnacle flat FDR
        if self.ascension_unlocks:
            total += self.get_ascension_bonuses()["fdr"]

        return total

    def get_total_ward_percentage(self) -> int:
        from core.items.essence_mechanics import compute_essence_stat_bonus

        total = 0
        if self.equipped_accessory:
            total += self.equipped_accessory.ward
        if self.equipped_armor:
            total += self.equipped_armor.ward
        if self.equipped_glove:
            total += self.equipped_glove.ward
        if self.equipped_boot:
            total += self.equipped_boot.ward
        if self.equipped_helmet:
            total += self.equipped_helmet.ward

        # Companions
        total += self._get_companion_bonus("ward")

        # Essence bonuses (ward % bonus)
        for item in (self.equipped_glove, self.equipped_boot, self.equipped_helmet):
            if item:
                total += compute_essence_stat_bonus(item).get("ward", 0)
        return total

    def get_current_crit_chance(self) -> int:
        from core.items.essence_mechanics import compute_essence_stat_bonus

        # Flat sources: gear + companions + essences + tomes
        chance = 0
        if self.equipped_accessory:
            chance += self.equipped_accessory.crit

        # Companions
        chance += self._get_companion_bonus("crit")

        # Precision tome
        chance += int(self.get_tome_bonus("precision"))

        # Essence bonuses (Insight)
        for item in (self.equipped_glove, self.equipped_boot, self.equipped_helmet):
            if item:
                chance += compute_essence_stat_bonus(item).get("crit", 0)

        # Per-combat/chapter bonus accumulator and permanent run penalty
        chance += self.bonus_crit
        chance -= self.run_crit_penalty

        # Ascension pinnacle flat crit
        if self.ascension_unlocks:
            chance += self.get_ascension_bonuses()["crit"]

        # Multiplicative layer (Insight helmet passive, future mods)
        if self.crit_multiplier != 1.0:
            chance = int(chance * self.crit_multiplier)

        return max(0, chance)

    def get_total_evasion(self) -> int:
        """Total evasion including armor base and any essence bonuses on glove/boot/helmet."""
        from core.items.essence_mechanics import compute_essence_stat_bonus

        total = self.equipped_armor.evasion if self.equipped_armor else 0
        for item in (self.equipped_glove, self.equipped_boot, self.equipped_helmet):
            if item:
                total += compute_essence_stat_bonus(item).get("evasion", 0)
        return total

    def get_total_block(self) -> int:
        """Total block including armor base and any essence bonuses on glove/boot/helmet."""
        from core.items.essence_mechanics import compute_essence_stat_bonus

        total = self.equipped_armor.block if self.equipped_armor else 0
        for item in (self.equipped_glove, self.equipped_boot, self.equipped_helmet):
            if item:
                total += compute_essence_stat_bonus(item).get("block", 0)
        return total

    def get_combat_ward_value(self) -> int:
        ward_percent = self.get_total_ward_percentage()
        return int((ward_percent / 100) * self.total_max_hp) if ward_percent > 0 else 0

    def get_total_rarity(self) -> int:
        """Full rarity total: gear + companions + tome multiplier + codex boon bonus."""
        total = self.rarity  # Gear only (weapon + accessory)
        total += self._get_companion_bonus("rarity")

        # Providence tome: % bonus to total rarity
        prov_pct = self.get_tome_bonus("providence")
        if prov_pct > 0:
            total = int(total * (1 + prov_pct / 100))

        # Codex rarity boon accumulator
        total += self.bonus_rarity
        return total

    def get_special_drop_bonus(self) -> int:
        """New method for Special Rarity calculation."""
        bonus = 0
        # Gear (Thrill Seeker Boot)
        if self.equipped_boot and self.equipped_boot.passive == "thrill-seeker":
            bonus += self.equipped_boot.passive_lvl  # 1-6%

        # Companions
        bonus += self._get_companion_bonus("s_rarity")

        # [SAFETY CAP] Hard cap special rarity bonus at 20%
        return min(20, bonus)

    def get_weapon_infernal(self) -> str:
        return self.equipped_weapon.infernal_passive if self.equipped_weapon else "none"

    def get_weapon_passive(self) -> str:
        return self.equipped_weapon.passive if self.equipped_weapon else "none"

    def get_weapon_pinnacle(self) -> str:
        return self.equipped_weapon.p_passive if self.equipped_weapon else "none"

    def get_weapon_utmost(self) -> str:
        return self.equipped_weapon.u_passive if self.equipped_weapon else "none"

    def get_armor_passive(self) -> str:
        return self.equipped_armor.passive if self.equipped_armor else "none"

    def get_celestial_armor_passive(self) -> str:
        return self.equipped_armor.celestial_passive if self.equipped_armor else "none"

    def get_accessory_passive(self) -> str:
        return self.equipped_accessory.passive if self.equipped_accessory else "none"

    def get_accessory_void_passive(self) -> str:
        return (
            self.equipped_accessory.void_passive if self.equipped_accessory else "none"
        )

    def get_glove_passive(self) -> str:
        return self.equipped_glove.passive if self.equipped_glove else "none"

    def get_boot_passive(self) -> str:
        return self.equipped_boot.passive if self.equipped_boot else "none"

    def get_helmet_passive(self) -> str:
        return self.equipped_helmet.passive if self.equipped_helmet else "none"

    def get_glove_corrupted_essence(self) -> str:
        return (
            self.equipped_glove.corrupted_essence if self.equipped_glove else "none"
        ) or "none"

    def get_boot_corrupted_essence(self) -> str:
        return (
            self.equipped_boot.corrupted_essence if self.equipped_boot else "none"
        ) or "none"

    def get_helmet_corrupted_essence(self) -> str:
        return (
            self.equipped_helmet.corrupted_essence if self.equipped_helmet else "none"
        ) or "none"

    def get_emblem_bonus(self, passive_type: str) -> int:
        """
        Calculates the total tier value for a specific emblem passive.
        e.g., Two slots with Tier 3 'boss_dmg' returns 6.
        """
        total_tiers = 0
        for slot_data in self.slayer_emblem.values():
            if slot_data["type"] == passive_type:
                total_tiers += slot_data["tier"]
        return total_tiers

    def get_tome_bonus(self, passive_type: str) -> float:
        """Returns the accumulated stat value for a given Codex tome passive type."""
        return sum(t.value for t in self.codex_tomes if t.passive_type == passive_type)

    def get_effective_max_hp(self) -> int:
        """Alias for total_max_hp — kept for display call sites."""
        return self.total_max_hp


@dataclass
class MonsterModifier:
    name: str
    tier: int          # 1–5 for tiered mods; 0 for flat (no numeral shown)
    value: float       # resolved numeric value for this tier
    difficulty: float  # contribution to special_drop_chance

    @property
    def display_name(self) -> str:
        if self.tier == 0:
            return self.name
        numerals = ["I", "II", "III", "IV", "V"]
        return f"{self.name} {numerals[self.tier - 1]}"


@dataclass
class Monster:
    name: str
    level: int
    hp: int
    max_hp: int
    xp: int
    attack: int
    defence: int
    modifiers: List[MonsterModifier] = field(default_factory=list)
    image: str = ""
    flavor: str = ""
    species: str = "Unknown"
    is_boss: bool = False
    combat_round: int = 0
    is_essence: bool = False
    ward: int = 0

    def has_modifier(self, name: str) -> bool:
        return any(m.name == name for m in self.modifiers)

    def get_modifier_value(self, name: str) -> float:
        for m in self.modifiers:
            if m.name == name:
                return m.value
        return 0.0

    @property
    def display_modifiers(self) -> list:
        result = []
        for m in self.modifiers:
            if m.name == "Ascended":
                result.append(f"Ascended +{int(m.value)}")
            else:
                result.append(m.display_name)
        return result


@dataclass
class DungeonRoomOption:
    direction: str
    flavor_text: str
    encounter_type: str


@dataclass
class DungeonState:
    player_id: str
    player_name: str
    current_floor: int
    max_regular_floors: int

    player_current_hp: int
    player_max_hp: int
    player_current_ward: int
    player_base_ward: int

    potions_remaining: int
    dungeon_coins: int
    loot_gathered: List[Union[Weapon, Accessory, Armor]] = field(default_factory=list)

    player_buffs: List[str] = field(default_factory=list)
    player_curses: List[str] = field(default_factory=list)

    current_room_options: Optional[List[DungeonRoomOption]] = None
    last_action_message: Optional[str] = None


@dataclass
class Settlement:
    user_id: str
    server_id: str
    town_hall_tier: int
    building_slots: int
    timber: int
    stone: int
    last_collection_time: str
    # Helper to hold building objects after fetching
    buildings: List["Building"] = field(default_factory=list)


@dataclass
class Building:
    id: int
    user_id: str
    server_id: str
    building_type: str
    tier: int
    slot_index: int
    workers_assigned: int

    @property
    def name(self) -> str:
        return self.building_type.replace("_", " ").title()


_SIG_COMBAT_KEYS = {
    1: "sig_co_skol",
    2: "sig_co_eve",
    3: "sig_co_kay",
    4: "sig_co_sigmund",
    5: "sig_co_velour",
    6: "sig_co_flora",
    7: "sig_co_yvenn",
}

_SIG_DISPATCH_KEYS = {
    1: "sig_di_skol",
    2: "sig_di_eve",
    3: "sig_di_kay",
    4: "sig_di_sigmund",
    5: "sig_di_velour",
    6: "sig_di_flora",
    7: "sig_di_yvenn",
}


@dataclass
class Partner:
    # --- DB row fields ---
    row_id: int
    user_id: str
    partner_id: int
    level: int
    exp: int

    combat_slot_1: Optional[str]
    combat_slot_1_lvl: int
    combat_slot_2: Optional[str]
    combat_slot_2_lvl: int
    combat_slot_3: Optional[str]
    combat_slot_3_lvl: int
    sig_combat_lvl: int

    dispatch_slot_1: Optional[str]
    dispatch_slot_1_lvl: int
    dispatch_slot_2: Optional[str]
    dispatch_slot_2_lvl: int
    dispatch_slot_3: Optional[str]
    dispatch_slot_3_lvl: int
    sig_dispatch_lvl: int

    dispatch_task: Optional[str]
    dispatch_start_time: Optional[str]
    dispatch_task_2: Optional[str]
    dispatch_start_time_2: Optional[str]

    is_active_combat: bool
    is_dispatched: bool

    affinity_encounters: int
    affinity_story_seen: int
    portrait_variant: int

    # --- Static data from CSV ---
    name: str
    title: str
    rarity: int
    pull_message: str
    base_attack: int
    base_defence: int
    base_hp: int
    image_url: str
    affinity_image_url: str

    # --- Computed stats ---

    @property
    def total_attack(self) -> int:
        return self.base_attack + (self.level - 1) * self.rarity

    @property
    def total_defence(self) -> int:
        return self.base_defence + (self.level - 1) * self.rarity

    @property
    def total_hp(self) -> int:
        return self.base_hp + (self.level - 1) * self.rarity

    @property
    def num_slots(self) -> int:
        """Number of regular skill slots (same for combat and dispatch): 4★=1, 5★=2, 6★=3."""
        return self.rarity - 3

    @property
    def combat_skills(self) -> List[tuple]:
        """Active combat skill slots as (key, level) pairs."""
        all_slots = [
            (self.combat_slot_1, self.combat_slot_1_lvl),
            (self.combat_slot_2, self.combat_slot_2_lvl),
            (self.combat_slot_3, self.combat_slot_3_lvl),
        ]
        return all_slots[: self.num_slots]

    @property
    def dispatch_skills(self) -> List[tuple]:
        """Active dispatch skill slots as (key, level) pairs."""
        all_slots = [
            (self.dispatch_slot_1, self.dispatch_slot_1_lvl),
            (self.dispatch_slot_2, self.dispatch_slot_2_lvl),
            (self.dispatch_slot_3, self.dispatch_slot_3_lvl),
        ]
        return all_slots[: self.num_slots]

    @property
    def sig_combat_key(self) -> Optional[str]:
        return _SIG_COMBAT_KEYS.get(self.partner_id) if self.rarity >= 6 else None

    @property
    def sig_dispatch_key(self) -> Optional[str]:
        return _SIG_DISPATCH_KEYS.get(self.partner_id) if self.rarity >= 6 else None

    @property
    def display_image(self) -> str:
        if self.portrait_variant == 1 and self.affinity_image_url:
            return self.affinity_image_url
        return self.image_url

    @property
    def stars(self) -> str:
        return "★" * self.rarity

    @classmethod
    def from_row(cls, row: tuple, static: dict) -> "Partner":
        return cls(
            row_id=row[0],
            user_id=row[1],
            partner_id=row[2],
            level=row[3],
            exp=row[4],
            combat_slot_1=row[5],
            combat_slot_1_lvl=row[6],
            combat_slot_2=row[7],
            combat_slot_2_lvl=row[8],
            combat_slot_3=row[9],
            combat_slot_3_lvl=row[10],
            sig_combat_lvl=row[11],
            dispatch_slot_1=row[12],
            dispatch_slot_1_lvl=row[13],
            dispatch_slot_2=row[14],
            dispatch_slot_2_lvl=row[15],
            dispatch_slot_3=row[16],
            dispatch_slot_3_lvl=row[17],
            sig_dispatch_lvl=row[18],
            dispatch_task=row[19],
            dispatch_start_time=row[20],
            dispatch_task_2=row[21],
            dispatch_start_time_2=row[22],
            is_active_combat=bool(row[23]),
            is_dispatched=bool(row[24]),
            affinity_encounters=row[25],
            affinity_story_seen=row[26],
            portrait_variant=row[27],
            name=static["name"],
            title=static["title"],
            rarity=static["rarity"],
            pull_message=static["pull_message"],
            base_attack=static["base_attack"],
            base_defence=static["base_defence"],
            base_hp=static["base_hp"],
            image_url=static["image_url"],
            affinity_image_url=static["affinity_image_url"],
        )
