"""
core/combat/models.py — Combat-related dataclasses.

Contains:
  CombatState       — per-fight transient state, reset between every fight
  CodexRunState     — state that persists across Codex waves within one run
  MonsterModifier   — a single modifier applied to a monster instance
  Monster           — monster entity used during combat
  Player            — player character with all stats, gear, and combat helpers
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional

from core.items.models import (
    Accessory,
    Armor,
    Boot,
    CodexTome,
    Companion,
    Glove,
    Helmet,
    Weapon,
)
from core.partners.models import Partner

# ---------------------------------------------------------------------------
# Per-combat transient state
# ---------------------------------------------------------------------------


@dataclass
class CombatState:
    """Per-combat transient state. Reset to defaults between every fight via Player.reset_combat_state()."""

    ward: int = 0
    is_invulnerable: bool = False
    cooldown_reduction_seconds: int = 0
    celestial_vow_used: bool = False
    voracious_stacks: int = 0
    cursed_precision_active: bool = False
    gaze_stacks: int = 0
    hunger_stacks: int = 0
    lucifer_pdr_burst: int = 0
    equilibrium_bonus_xp_pending: int = 0
    plundering_bonus_gold_pending: int = 0
    # Alchemy potion transients
    alchemy_atk_boost_pct: float = 0.0
    alchemy_def_boost_pct: float = 0.0
    alchemy_def_boost_turns: int = 0
    alchemy_dmg_reduction_pct: float = 0.0
    alchemy_dmg_reduction_turns: int = 0
    alchemy_overcap_hp: int = 0
    alchemy_linger_hp: int = 0
    alchemy_linger_turns: int = 0
    alchemy_guaranteed_hit: bool = False
    alchemy_hit_boost_pct: float = 0.0
    alchemy_hit_boost_turns: int = 0
    # Powerful distilled potion transients (11-passive system)
    alchemy_ailment_immunity_turns: int = 0
    alchemy_eclipse_strikes: int = 0
    alchemy_eclipse_bonus: float = 0.0
    alchemy_shield_hp: int = 0
    alchemy_shield_turns: int = 0
    alchemy_enfeeble_pct: float = 0.0
    alchemy_enfeeble_turns: int = 0
    alchemy_blood_tithe_leech: float = 0.0
    alchemy_blood_tithe_hits: int = 0
    alchemy_barrier_ward_per_turn: int = 0
    alchemy_barrier_turns: int = 0
    alchemy_viper_dot_dmg: int = 0
    alchemy_viper_dot_turns: int = 0
    # Per-combat bonus accumulators and multipliers
    bonus_atk: int = 0
    bonus_def: int = 0
    bonus_crit: int = 0
    bonus_max_hp: int = 0
    atk_multiplier: float = 1.0
    def_multiplier: float = 1.0
    crit_multiplier: float = 1.0
    partner_special_rarity: float = 0.0
    # Paradise Jewel unleash transients
    jewel_cataclysm_primed: bool = False
    jewel_cataclysm_bonus_multi: float = 0.0
    jewel_onslaught_primed: bool = False
    jewel_onslaught_bonus_pct: float = 0.0
    jewel_wardforge_bonus_dmg: int = 0
    jewel_acrimony_dot: int = 0
    jewel_acrimony_dot_dmg: int = 0
    # Hematurgy passive transients
    hema_momentum_stacks: int = 0  # Iron Momentum ATK stacks (max 5), resets on miss
    hema_bleed_total: int = 0  # Haemorrhage accumulated bleed pool
    hema_chain_stacks: int = (
        0  # Chain Reaction crit-dmg stacks (max 5), resets on non-crit
    )
    hema_phantom_stacks: int = (
        0  # Phantom Reflex evasion stacks (max 2), consumed by hits
    )
    hema_fevered_count: int = 0  # Fevered Strike: potions consumed this fight
    hema_predators_mark: bool = False  # Predator's Mark active on monster
    hema_defiance_triggered: bool = False  # Defiance one-shot flag
    hema_hp_lost_combat: int = 0  # Soul Fracture: HP lost during this combat only
    hema_blade_count: int = 0  # Spectral Waltz blade count
    hema_puncture_bleed: int = 0  # Puncture accumulated crit-bleed pool
    hema_frost_misses: int = 0  # Flash Frost consecutive miss counter
    hema_ward_inoculation: bool = (
        False  # Ward Inoculation active (no ward regen, ward→damage)
    )
    hema_ward_dmg_buffer: int = (
        0  # Ward Inoculation: accumulated ward→damage pending apply
    )
    hema_serrated_total: int = (
        0  # Serrated: cumulative ATK drained from monster this fight
    )
    # Codex chapter-level penalties (persist across all 7 waves of a chapter)
    chapter_hit_penalty: int = 0  # flat subtraction from acc_bonus in hit rolls
    chapter_pdr_reduction: float = (
        0.0  # multiplicative PDR reduction (0.30 = 30% less PDR)
    )
    chapter_ward_gen_mult: float = (
        1.0  # multiplier on all ward generation (1.0 = no reduction)
    )
    chapter_crit_dmg_reduction: float = (
        0.0  # multiplier reduction on player crit damage
    )
    chapter_hp_entry_pct: float = (
        0.0  # fraction of max HP the player may not exceed on wave entry
    )
    # Apex zone state (set at combat start by ApexMechanics.apply_zone_modifier)
    apex_zone: Optional[str] = None  # active zone key, or None for normal combat
    # Prestige gathering boss (Artisan Mastery) transient
    is_snared: bool = False  # Verdant Colossus snare effect


# ---------------------------------------------------------------------------
# Per-codex-run state
# ---------------------------------------------------------------------------


@dataclass
class CodexRunState:
    """State that persists across waves within a single Codex run. Reset when the run ends."""

    atk_penalty: int = 0
    def_penalty: int = 0
    crit_penalty: int = 0
    max_hp_bonus: int = 0
    bonus_rarity: int = 0
    boon_fdr: int = 0


# ---------------------------------------------------------------------------
# Monster models
# ---------------------------------------------------------------------------


@dataclass
class MonsterModifier:
    name: str
    tier: int  # 1–5 for tiered mods; 0 for flat (no numeral shown)
    value: float  # resolved numeric value for this tier
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
    image2: str = ""
    flavor: str = ""
    species: str = "Unknown"
    is_boss: bool = False
    combat_round: int = 0
    is_essence: bool = False
    is_corrupted: bool = False
    is_incubated: bool = False
    incubated_encounter_id: int = 0
    incubated_egg_tier: str = ""
    ward: int = 0

    # --- Apex zone fields ---
    is_apex: bool = False  # True for apex hunt encounters
    apex_zone: Optional[str] = None  # active zone key
    zone_dr: float = 0.0  # siege_grounds extra DR against player hits
    zone_dmg_boost: float = 0.0  # scorched extra multiplier on monster damage

    # --- New modifier transient state ---
    # Flashfire: charges accumulate each monster turn; at 8 → true damage burst
    flashfire_charges: int = 0
    # Hemorrhage: +1 per monster hit; true DoT at start of each monster turn
    bleed_stacks: int = 0
    # Volatile Spikes: +1 per monster hit (cap 10), resets on player evade/block; boosts monster crit
    spike_stacks: int = 0
    # Onslaught: cumulative ATK% bonus per consecutive hit; resets on player evade/block
    onslaught_bonus_atk: float = 0.0
    # Pressure Surge: +1 if player didn't crit last turn (cap 10); true dmg at 10
    pressure_stacks: int = 0
    pressure_player_critted: bool = False  # written by player_turn each turn
    # Corrosion: +1 every 3 monster turns; each stack -5 player effective PDR
    corrode_stacks: int = 0
    # Death Rattle: triggers once when HP < 25%; countdown to heal
    death_rattle_triggered: bool = False
    death_rattle_countdown: int = -1
    # Impending Doom: +1 per monster hit; instant kill at 44
    doom_stacks: int = 0
    # Wrathful Retaliation: +1 per player crit; boosts monster ATK multiplicatively
    wrathful_stacks: int = 0
    # Colossus Protocol: triggers once at <50% HP; negates first hit per turn
    colossus_active: bool = False
    colossus_hit_negated: bool = False  # reset each monster turn
    colossus_dr: float = 0.0  # flat damage reduction applied to player hits
    # Temporal Collapse: accumulates player damage over 6-turn window; burst true dmg
    temporal_window_damage: int = 0
    # Undying Resolve: triggers once on first death; immune + ATK burst for 2 turns
    undying_resolve_triggered: bool = False
    undying_immune_turns: int = 0
    undying_atk_boost_turns: int = 0
    # Frenzied Hunger: each potion use boosts monster ATK multiplicatively
    potion_uses_tracked: int = 0

    # Difficulty level: 0=off, 1=hard, 2=extreme, 3=nightmarish, 4=delirious.
    # Set by _execute_combat; drives scaled stat boosts and combat behaviour.
    difficulty_level: int = 0
    # Flat damage reduction against player hits from Nightmarish/Delirious modes.
    difficulty_dr: float = 0.0

    # =====================================================================
    # New clean combat stat model (Phase 1+)
    # =====================================================================

    # Base values captured once after monster generation + all spawn-time modifiers.
    # These should not change during a combat encounter.
    base_attack: int = 0
    base_defence: int = 0
    base_max_hp: int = 0

    # Additive percentage bonuses applied on top of base stats.
    # These are the correct place for spawn-time % boosts (Empowered, Fortified,
    # difficulty scaling, uber setup adjustments, etc.).
    bonus_attack_pct: float = 0.0
    bonus_defence_pct: float = 0.0
    bonus_max_hp_pct: float = 0.0

    # Flat bonuses (used for spawn-time flat additions like +level*X in uber generators).
    # These are added to base *before* the percentage multiplier.
    flat_attack_bonus: int = 0
    flat_defence_bonus: int = 0

    # Flat reductions (used by various debuffs that subtract a flat amount).
    # effective_* properties combine flat + percentage.
    flat_attack_reduction: int = 0
    flat_defence_reduction: int = 0

    # Damage modification pools (outgoing damage only)
    # All "% increased damage" and "% decreased damage" sources accumulate here.
    # Positive values = increased, negative values = decreased.
    damage_increased_pct: float = 0.0

    # Separate multiplicative layer for "% more damage" / "% less damage" effects.
    # Applied AFTER the increased/decreased pool.
    # 1.0 = normal. Example: 0.5 = 50% less damage.
    damage_more_mult: float = 1.0

    @property
    def hard_mode(self) -> bool:
        """True when any difficulty mode is active. Keeps legacy callers working."""
        return self.difficulty_level > 0

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

    # ------------------------------------------------------------------
    # Effective stat helpers (respect base + bonuses + flat reductions)
    # ------------------------------------------------------------------

    @property
    def effective_attack(self) -> int:
        """Returns the monster's current effective attack.
        Formula: (base + flat_bonus) * (1 + bonus_pct) - flat_reduction
        """
        base = self.base_attack if self.base_attack > 0 else self.attack
        val = base + self.flat_attack_bonus
        val = int(val * (1 + self.bonus_attack_pct))
        val = max(0, val - self.flat_attack_reduction)
        return val

    @property
    def effective_defence(self) -> int:
        """Returns the monster's current effective defence.
        Formula: (base + flat_bonus) * (1 + bonus_pct) - flat_reduction
        """
        base = self.base_defence if self.base_defence > 0 else self.defence
        val = base + self.flat_defence_bonus
        val = int(val * (1 + self.bonus_defence_pct))
        val = max(0, val - self.flat_defence_reduction)
        return val

    @property
    def effective_max_hp(self) -> int:
        """Returns the monster's effective max HP after bonuses."""
        base = self.base_max_hp if self.base_max_hp > 0 else self.max_hp
        val = int(base * (1 + self.bonus_max_hp_pct))
        return max(1, val)

    def get_total_damage_mult(self) -> float:
        """
        Returns the final multiplier to apply to monster outgoing damage rolls.

        All sources of "% increased damage" / "% decreased damage" should
        accumulate into damage_increased_pct.

        "% more" / "% less" effects go into damage_more_mult and are applied
        after the increased pool.
        """
        increased = 1.0 + self.damage_increased_pct
        return increased * self.damage_more_mult

    def reset_combat_bonuses(self) -> None:
        """
        Resets transient combat-only bonuses and damage pools.
        Spawn-established bonuses (Empowered, difficulty, etc.) should generally
        survive this call. Only combat-dynamic fields are cleared.
        """
        # Clear combat-dynamic damage modification
        self.damage_increased_pct = 0.0
        self.damage_more_mult = 1.0

        # Clear combat-accumulated flat reductions (but not spawn flat bonuses)
        self.flat_attack_reduction = 0
        self.flat_defence_reduction = 0

        # Reset common per-fight transient stacks
        self.onslaught_bonus_atk = 0.0
        self.wrathful_stacks = 0
        self.colossus_active = False
        self.colossus_dr = 0.0
        self.undying_atk_boost_turns = 0
        self.potion_uses_tracked = 0

        # Note: We do NOT clear bonus_*_pct or flat_*_bonus here,
        # as those may contain spawn-time or persistent bonuses.
        # Only clear things that are purely per-fight accumulations.


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------


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
    potions: int

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
    companion_passive_mult: float = 1.0  # from Companion Mastery (Bonded branch)
    companion_elite_bond: bool = False  # elite_bond node: balanced passives +1 tier

    # Settlement buffs
    apothecary_workers: int = 0
    barracks_workers: int = 0
    apothecary_boost_pct: float = 0.0  # from adjacent Apothecary Annex
    shrine_effectiveness: dict = field(
        default_factory=dict
    )  # btype → drop-rate multiplier

    # Slayer
    slayer_emblem: dict = field(default_factory=dict)
    slayer_tree_nodes: dict = field(
        default_factory=dict
    )  # nodes_owned from slayer_tree table
    active_task_species: str = (
        None  # Store this so the engine knows if we are fighting a task mob
    )

    # Codex Tomes
    codex_tomes: List[CodexTome] = field(default_factory=list)

    # Alchemy — Potion Passives (loaded from DB, list of dicts)
    potion_passives: List[dict] = field(default_factory=list)

    # Flat stat cache (immutable during combat; computed by compute_flat_stats())
    flat_atk: int = 0
    flat_def: int = 0

    # Ascension pinnacle unlocks (loaded once at session start, never mutated)
    ascension_unlocks: set = field(default_factory=set)

    # Monster body parts equipped (loaded at session start)
    equipped_parts: dict = field(default_factory=dict)

    # Active combat partner (loaded at session start, not reset per combat)
    active_partner: Optional[Partner] = None

    # Paradise Jewel system — loaded at session start, persisted after combat
    jewel_of_paradise: dict = field(
        default_factory=lambda: {
            "unlocked_skills": [],
            "equipped_skill": None,
            "skill_levels": {},
            "skill_charges": {},
            "passive_slots": [],
            "passive_jewels_invested": 0,
            "total_jewels_obtained": 0,
            "total_jewels_consumed": 0,
        }
    )

    # Hematurgy passives — loaded at session start, maps passive_id → tier (1-5)
    hematurgy_passives: dict = field(default_factory=dict)

    # Soul Stone — loaded at session start, None if not yet created
    soul_stone: Optional[Any] = None  # core.apex.models.SoulStone | None

    # Stat investments (passive_point allocations, 0.1% bonus per point)
    stat_invest_atk: int = 0
    stat_invest_def: int = 0
    stat_invest_hp: int = 0
    stat_invest_gold: int = 0

    # Per-combat transient state — reset via reset_combat_state()
    cs: CombatState = field(default_factory=CombatState)

    # Per-codex-run state — persists across waves, reset when a run ends
    run: CodexRunState = field(default_factory=CodexRunState)

    # -----------------------------------------------------------------------
    # Property forwarders — expose CombatState fields under their original names
    # so all existing callsites continue to work unchanged.
    # -----------------------------------------------------------------------

    @property
    def combat_ward(self) -> int:
        return self.cs.ward

    @combat_ward.setter
    def combat_ward(self, v: int) -> None:
        self.cs.ward = v

    @property
    def is_invulnerable_this_combat(self) -> bool:
        return self.cs.is_invulnerable

    @is_invulnerable_this_combat.setter
    def is_invulnerable_this_combat(self, v: bool) -> None:
        self.cs.is_invulnerable = v

    @property
    def combat_cooldown_reduction_seconds(self) -> int:
        return self.cs.cooldown_reduction_seconds

    @combat_cooldown_reduction_seconds.setter
    def combat_cooldown_reduction_seconds(self, v: int) -> None:
        self.cs.cooldown_reduction_seconds = v

    @property
    def celestial_vow_used(self) -> bool:
        return self.cs.celestial_vow_used

    @celestial_vow_used.setter
    def celestial_vow_used(self, v: bool) -> None:
        self.cs.celestial_vow_used = v

    @property
    def voracious_stacks(self) -> int:
        return self.cs.voracious_stacks

    @voracious_stacks.setter
    def voracious_stacks(self, v: int) -> None:
        self.cs.voracious_stacks = v

    @property
    def cursed_precision_active(self) -> bool:
        return self.cs.cursed_precision_active

    @cursed_precision_active.setter
    def cursed_precision_active(self, v: bool) -> None:
        self.cs.cursed_precision_active = v

    @property
    def gaze_stacks(self) -> int:
        return self.cs.gaze_stacks

    @gaze_stacks.setter
    def gaze_stacks(self, v: int) -> None:
        self.cs.gaze_stacks = v

    @property
    def hunger_stacks(self) -> int:
        return self.cs.hunger_stacks

    @hunger_stacks.setter
    def hunger_stacks(self, v: int) -> None:
        self.cs.hunger_stacks = v

    @property
    def lucifer_pdr_burst(self) -> int:
        return self.cs.lucifer_pdr_burst

    @lucifer_pdr_burst.setter
    def lucifer_pdr_burst(self, v: int) -> None:
        self.cs.lucifer_pdr_burst = v

    @property
    def equilibrium_bonus_xp_pending(self) -> int:
        return self.cs.equilibrium_bonus_xp_pending

    @equilibrium_bonus_xp_pending.setter
    def equilibrium_bonus_xp_pending(self, v: int) -> None:
        self.cs.equilibrium_bonus_xp_pending = v

    @property
    def plundering_bonus_gold_pending(self) -> int:
        return self.cs.plundering_bonus_gold_pending

    @plundering_bonus_gold_pending.setter
    def plundering_bonus_gold_pending(self, v: int) -> None:
        self.cs.plundering_bonus_gold_pending = v

    @property
    def alchemy_atk_boost_pct(self) -> float:
        return self.cs.alchemy_atk_boost_pct

    @alchemy_atk_boost_pct.setter
    def alchemy_atk_boost_pct(self, v: float) -> None:
        self.cs.alchemy_atk_boost_pct = v

    @property
    def alchemy_def_boost_pct(self) -> float:
        return self.cs.alchemy_def_boost_pct

    @alchemy_def_boost_pct.setter
    def alchemy_def_boost_pct(self, v: float) -> None:
        self.cs.alchemy_def_boost_pct = v

    @property
    def alchemy_def_boost_turns(self) -> int:
        return self.cs.alchemy_def_boost_turns

    @alchemy_def_boost_turns.setter
    def alchemy_def_boost_turns(self, v: int) -> None:
        self.cs.alchemy_def_boost_turns = v

    @property
    def alchemy_dmg_reduction_pct(self) -> float:
        return self.cs.alchemy_dmg_reduction_pct

    @alchemy_dmg_reduction_pct.setter
    def alchemy_dmg_reduction_pct(self, v: float) -> None:
        self.cs.alchemy_dmg_reduction_pct = v

    @property
    def alchemy_dmg_reduction_turns(self) -> int:
        return self.cs.alchemy_dmg_reduction_turns

    @alchemy_dmg_reduction_turns.setter
    def alchemy_dmg_reduction_turns(self, v: int) -> None:
        self.cs.alchemy_dmg_reduction_turns = v

    @property
    def alchemy_overcap_hp(self) -> int:
        return self.cs.alchemy_overcap_hp

    @alchemy_overcap_hp.setter
    def alchemy_overcap_hp(self, v: int) -> None:
        self.cs.alchemy_overcap_hp = v

    @property
    def alchemy_linger_hp(self) -> int:
        return self.cs.alchemy_linger_hp

    @alchemy_linger_hp.setter
    def alchemy_linger_hp(self, v: int) -> None:
        self.cs.alchemy_linger_hp = v

    @property
    def alchemy_linger_turns(self) -> int:
        return self.cs.alchemy_linger_turns

    @alchemy_linger_turns.setter
    def alchemy_linger_turns(self, v: int) -> None:
        self.cs.alchemy_linger_turns = v

    @property
    def alchemy_guaranteed_hit(self) -> bool:
        return self.cs.alchemy_guaranteed_hit

    @alchemy_guaranteed_hit.setter
    def alchemy_guaranteed_hit(self, v: bool) -> None:
        self.cs.alchemy_guaranteed_hit = v

    @property
    def alchemy_hit_boost_pct(self) -> float:
        return self.cs.alchemy_hit_boost_pct

    @alchemy_hit_boost_pct.setter
    def alchemy_hit_boost_pct(self, v: float) -> None:
        self.cs.alchemy_hit_boost_pct = v

    @property
    def alchemy_hit_boost_turns(self) -> int:
        return self.cs.alchemy_hit_boost_turns

    @alchemy_hit_boost_turns.setter
    def alchemy_hit_boost_turns(self, v: int) -> None:
        self.cs.alchemy_hit_boost_turns = v

    # New powerful distilled potion passives (from distillation system)
    @property
    def alchemy_ailment_immunity_turns(self) -> int:
        return self.cs.alchemy_ailment_immunity_turns

    @alchemy_ailment_immunity_turns.setter
    def alchemy_ailment_immunity_turns(self, v: int) -> None:
        self.cs.alchemy_ailment_immunity_turns = v

    @property
    def alchemy_eclipse_strikes(self) -> int:
        return self.cs.alchemy_eclipse_strikes

    @alchemy_eclipse_strikes.setter
    def alchemy_eclipse_strikes(self, v: int) -> None:
        self.cs.alchemy_eclipse_strikes = v

    @property
    def alchemy_eclipse_bonus(self) -> float:
        return self.cs.alchemy_eclipse_bonus

    @alchemy_eclipse_bonus.setter
    def alchemy_eclipse_bonus(self, v: float) -> None:
        self.cs.alchemy_eclipse_bonus = v

    @property
    def alchemy_shield_hp(self) -> int:
        return self.cs.alchemy_shield_hp

    @alchemy_shield_hp.setter
    def alchemy_shield_hp(self, v: int) -> None:
        self.cs.alchemy_shield_hp = v

    @property
    def alchemy_shield_turns(self) -> int:
        return self.cs.alchemy_shield_turns

    @alchemy_shield_turns.setter
    def alchemy_shield_turns(self, v: int) -> None:
        self.cs.alchemy_shield_turns = v

    @property
    def alchemy_enfeeble_pct(self) -> float:
        return self.cs.alchemy_enfeeble_pct

    @alchemy_enfeeble_pct.setter
    def alchemy_enfeeble_pct(self, v: float) -> None:
        self.cs.alchemy_enfeeble_pct = v

    @property
    def alchemy_enfeeble_turns(self) -> int:
        return self.cs.alchemy_enfeeble_turns

    @alchemy_enfeeble_turns.setter
    def alchemy_enfeeble_turns(self, v: int) -> None:
        self.cs.alchemy_enfeeble_turns = v

    @property
    def alchemy_blood_tithe_leech(self) -> float:
        return self.cs.alchemy_blood_tithe_leech

    @alchemy_blood_tithe_leech.setter
    def alchemy_blood_tithe_leech(self, v: float) -> None:
        self.cs.alchemy_blood_tithe_leech = v

    @property
    def alchemy_blood_tithe_hits(self) -> int:
        return self.cs.alchemy_blood_tithe_hits

    @alchemy_blood_tithe_hits.setter
    def alchemy_blood_tithe_hits(self, v: int) -> None:
        self.cs.alchemy_blood_tithe_hits = v

    @property
    def alchemy_barrier_ward_per_turn(self) -> int:
        return self.cs.alchemy_barrier_ward_per_turn

    @alchemy_barrier_ward_per_turn.setter
    def alchemy_barrier_ward_per_turn(self, v: int) -> None:
        self.cs.alchemy_barrier_ward_per_turn = v

    @property
    def alchemy_barrier_turns(self) -> int:
        return self.cs.alchemy_barrier_turns

    @alchemy_barrier_turns.setter
    def alchemy_barrier_turns(self, v: int) -> None:
        self.cs.alchemy_barrier_turns = v

    @property
    def alchemy_viper_dot_dmg(self) -> int:
        return self.cs.alchemy_viper_dot_dmg

    @alchemy_viper_dot_dmg.setter
    def alchemy_viper_dot_dmg(self, v: int) -> None:
        self.cs.alchemy_viper_dot_dmg = v

    @property
    def alchemy_viper_dot_turns(self) -> int:
        return self.cs.alchemy_viper_dot_turns

    @alchemy_viper_dot_turns.setter
    def alchemy_viper_dot_turns(self, v: int) -> None:
        self.cs.alchemy_viper_dot_turns = v

    @property
    def bonus_atk(self) -> int:
        return self.cs.bonus_atk

    @bonus_atk.setter
    def bonus_atk(self, v: int) -> None:
        self.cs.bonus_atk = v

    @property
    def bonus_def(self) -> int:
        return self.cs.bonus_def

    @bonus_def.setter
    def bonus_def(self, v: int) -> None:
        self.cs.bonus_def = v

    @property
    def bonus_crit(self) -> int:
        return self.cs.bonus_crit

    @bonus_crit.setter
    def bonus_crit(self, v: int) -> None:
        self.cs.bonus_crit = v

    @property
    def bonus_max_hp(self) -> int:
        return self.cs.bonus_max_hp

    @bonus_max_hp.setter
    def bonus_max_hp(self, v: int) -> None:
        self.cs.bonus_max_hp = v

    @property
    def atk_multiplier(self) -> float:
        return self.cs.atk_multiplier

    @atk_multiplier.setter
    def atk_multiplier(self, v: float) -> None:
        self.cs.atk_multiplier = v

    @property
    def def_multiplier(self) -> float:
        return self.cs.def_multiplier

    @def_multiplier.setter
    def def_multiplier(self, v: float) -> None:
        self.cs.def_multiplier = v

    @property
    def crit_multiplier(self) -> float:
        return self.cs.crit_multiplier

    @crit_multiplier.setter
    def crit_multiplier(self, v: float) -> None:
        self.cs.crit_multiplier = v

    @property
    def partner_special_rarity(self) -> float:
        return self.cs.partner_special_rarity

    @partner_special_rarity.setter
    def partner_special_rarity(self, v: float) -> None:
        self.cs.partner_special_rarity = v

    @property
    def chapter_hit_penalty(self) -> int:
        return self.cs.chapter_hit_penalty

    @chapter_hit_penalty.setter
    def chapter_hit_penalty(self, v: int) -> None:
        self.cs.chapter_hit_penalty = v

    @property
    def chapter_pdr_reduction(self) -> float:
        return self.cs.chapter_pdr_reduction

    @chapter_pdr_reduction.setter
    def chapter_pdr_reduction(self, v: float) -> None:
        self.cs.chapter_pdr_reduction = v

    @property
    def chapter_ward_gen_mult(self) -> float:
        return self.cs.chapter_ward_gen_mult

    @chapter_ward_gen_mult.setter
    def chapter_ward_gen_mult(self, v: float) -> None:
        self.cs.chapter_ward_gen_mult = v

    @property
    def chapter_crit_dmg_reduction(self) -> float:
        return self.cs.chapter_crit_dmg_reduction

    @chapter_crit_dmg_reduction.setter
    def chapter_crit_dmg_reduction(self, v: float) -> None:
        self.cs.chapter_crit_dmg_reduction = v

    @property
    def chapter_hp_entry_pct(self) -> float:
        return self.cs.chapter_hp_entry_pct

    @chapter_hp_entry_pct.setter
    def chapter_hp_entry_pct(self, v: float) -> None:
        self.cs.chapter_hp_entry_pct = v

    @property
    def apex_zone(self) -> Optional[str]:
        return self.cs.apex_zone

    @apex_zone.setter
    def apex_zone(self, v: Optional[str]) -> None:
        self.cs.apex_zone = v

    # -----------------------------------------------------------------------
    # Soul Stone helper
    # -----------------------------------------------------------------------

    def get_soul_stone_passive(self, key: str) -> Optional[int]:
        """Returns the tier (1–5) of the given passive in any soul stone slot, or None."""
        if not self.soul_stone:
            return None
        return self.soul_stone.get_passive_tier(key)

    @property
    def jewel_cataclysm_primed(self) -> bool:
        return self.cs.jewel_cataclysm_primed

    @jewel_cataclysm_primed.setter
    def jewel_cataclysm_primed(self, v: bool) -> None:
        self.cs.jewel_cataclysm_primed = v

    @property
    def jewel_cataclysm_bonus_multi(self) -> float:
        return self.cs.jewel_cataclysm_bonus_multi

    @jewel_cataclysm_bonus_multi.setter
    def jewel_cataclysm_bonus_multi(self, v: float) -> None:
        self.cs.jewel_cataclysm_bonus_multi = v

    @property
    def jewel_onslaught_primed(self) -> bool:
        return self.cs.jewel_onslaught_primed

    @jewel_onslaught_primed.setter
    def jewel_onslaught_primed(self, v: bool) -> None:
        self.cs.jewel_onslaught_primed = v

    @property
    def jewel_onslaught_bonus_pct(self) -> float:
        return self.cs.jewel_onslaught_bonus_pct

    @jewel_onslaught_bonus_pct.setter
    def jewel_onslaught_bonus_pct(self, v: float) -> None:
        self.cs.jewel_onslaught_bonus_pct = v

    @property
    def jewel_wardforge_bonus_dmg(self) -> int:
        return self.cs.jewel_wardforge_bonus_dmg

    @jewel_wardforge_bonus_dmg.setter
    def jewel_wardforge_bonus_dmg(self, v: int) -> None:
        self.cs.jewel_wardforge_bonus_dmg = v

    @property
    def jewel_acrimony_dot(self) -> int:
        return self.cs.jewel_acrimony_dot

    @jewel_acrimony_dot.setter
    def jewel_acrimony_dot(self, v: int) -> None:
        self.cs.jewel_acrimony_dot = v

    @property
    def jewel_acrimony_dot_dmg(self) -> int:
        return self.cs.jewel_acrimony_dot_dmg

    @jewel_acrimony_dot_dmg.setter
    def jewel_acrimony_dot_dmg(self, v: int) -> None:
        self.cs.jewel_acrimony_dot_dmg = v

    # CodexRunState forwarders
    @property
    def run_atk_penalty(self) -> int:
        return self.run.atk_penalty

    @run_atk_penalty.setter
    def run_atk_penalty(self, v: int) -> None:
        self.run.atk_penalty = v

    @property
    def run_def_penalty(self) -> int:
        return self.run.def_penalty

    @run_def_penalty.setter
    def run_def_penalty(self, v: int) -> None:
        self.run.def_penalty = v

    @property
    def run_crit_penalty(self) -> int:
        return self.run.crit_penalty

    @run_crit_penalty.setter
    def run_crit_penalty(self, v: int) -> None:
        self.run.crit_penalty = v

    @property
    def run_max_hp_bonus(self) -> int:
        return self.run.max_hp_bonus

    @run_max_hp_bonus.setter
    def run_max_hp_bonus(self, v: int) -> None:
        self.run.max_hp_bonus = v

    @property
    def bonus_rarity(self) -> int:
        return self.run.bonus_rarity

    @bonus_rarity.setter
    def bonus_rarity(self, v: int) -> None:
        self.run.bonus_rarity = v

    @property
    def boon_fdr(self) -> int:
        return self.run.boon_fdr

    @boon_fdr.setter
    def boon_fdr(self, v: int) -> None:
        self.run.boon_fdr = v

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
        """Effective max HP including run bonuses, Hearty boot, Vitality tome, body parts, and Gluttony essences.

        Percentage sources (Hearty + Vitality) are ADDITIVE with each other: their
        percentages are summed and applied once to the flat base. Gluttony essence
        is a separate multiplicative layer applied afterwards (different item slot).
        """
        from core.items.essence_mechanics import compute_essence_stat_bonus

        vitality_pct = self.get_tome_bonus("vitality")

        # Hearty boot passive: additive with Vitality (+5% per level)
        hearty_pct = 0
        if self.equipped_boot and self.equipped_boot.passive == "hearty":
            hearty_pct = self.equipped_boot.passive_lvl * 5
        # Soul Stone: hearty tier adds +5% per tier
        ss_hearty = self.get_soul_stone_passive("hearty")
        if ss_hearty:
            hearty_pct += ss_hearty * 5

        asc_hp = self.get_ascension_bonuses()["hp"] if self.ascension_unlocks else 0
        parts_hp = (
            sum(v["hp"] for v in self.equipped_parts.values())
            if self.equipped_parts
            else 0
        )
        base = (
            self.max_hp + self.run_max_hp_bonus + self.bonus_max_hp + asc_hp + parts_hp
        )
        total_pct = vitality_pct + hearty_pct
        if total_pct > 0:
            base = int(base * (1 + total_pct / 100))
        gluttony_pct = sum(
            compute_essence_stat_bonus(item).get("max_hp_pct", 0)
            for item in (self.equipped_glove, self.equipped_boot, self.equipped_helmet)
            if item
        )
        if gluttony_pct > 0:
            base = int(base * (1 + gluttony_pct / 100))
        # Stat investment bonus (0.1% per point)
        if self.stat_invest_hp > 0:
            base = int(base * (1 + self.stat_invest_hp * 0.001))
        return max(1, base)

    def _get_companion_bonus(self, p_type: str) -> float:
        primary = sum(
            c.passive_value for c in self.active_companions if c.passive_type == p_type
        )
        if self.companion_elite_bond:
            from core.companions.mastery import passive_value_for_type

            balanced = sum(
                passive_value_for_type(
                    c.balanced_passive, min(5, c.balanced_passive_tier + 1)
                )
                for c in self.active_companions
                if c.balanced_passive == p_type and c.balanced_passive != "none"
            )
        else:
            balanced = sum(
                c.balanced_passive_value
                for c in self.active_companions
                if c.balanced_passive == p_type
            )
        return (primary + balanced) * self.companion_passive_mult

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
        """Zeros bonus accumulators and stat multipliers only. Use reset_combat_state() for a full reset."""
        self.cs.bonus_atk = 0
        self.cs.bonus_def = 0
        self.cs.bonus_crit = 0
        self.cs.bonus_max_hp = 0
        self.cs.atk_multiplier = 1.0
        self.cs.def_multiplier = 1.0
        self.cs.crit_multiplier = 1.0
        self.cs.partner_special_rarity = 0.0
        self.cs.chapter_hit_penalty = 0
        self.cs.chapter_pdr_reduction = 0.0
        self.cs.chapter_ward_gen_mult = 1.0
        self.cs.chapter_crit_dmg_reduction = 0.0
        self.cs.chapter_hp_entry_pct = 0.0

    def reset_combat_state(self) -> None:
        """
        Fully resets all per-combat transient state (CombatState).
        Ward is zeroed here; callers must re-initialize it via get_combat_ward_value().
        Does NOT touch self.run (CodexRunState) — that persists for the whole run.
        """
        self.cs = CombatState()

    # -----------------------------------------------------------------------
    # Ascension pinnacle bonus helper
    # -----------------------------------------------------------------------

    def get_ascension_bonuses(self) -> dict:
        from core.ascent.mechanics import AscentMechanics

        return AscentMechanics.get_cumulative_pinnacle_bonuses(self.ascension_unlocks)

    # -----------------------------------------------------------------------
    # Total stat calculations
    #
    # Stat stacking model (applies to both get_total_attack and get_total_defence):
    #
    #   total = flat (Base + Equipment) + bonus_pool + int(flat * pct_pool)
    #
    # `flat` is the anchor (gear stats only, immutable during combat). Everything
    # else the player can gain — flat additions (companion %, stat investment,
    # tome conversions, void engram bonus_atk, gilded hunger bonus_atk, etc.) and
    # percentage-of-flat bonuses (ascension pinnacle %, soul stone resonance,
    # codex atk/def_multiplier, Alchemy Enrage, ...) — all accumulate into ONE
    # additive pool. They do NOT compound on top of each other or on top of
    # already-applied bonuses: a +50% source and a +20% source combine to +70%
    # of flat, never 1.5 * 1.2 = +80%. Every percentage source must be scaled off
    # `flat` specifically (not off `total`) to keep this true. When adding a new
    # ATK/DEF source, add it to bonus_pool (flat amount) or pct_pool (fraction of
    # flat) — never multiply `total` directly.
    # -----------------------------------------------------------------------

    def get_total_attack(self, monster: "Monster | None" = None) -> int:
        """monster is optional — only needed for the conditional Hematurgy
        Executioner's Rite bonus (which reads monster HP%). Every other caller
        can omit it."""
        flat = self.flat_atk  # Base + Equipment; pre-computed, immutable during combat

        # ---- Flat bonus pool (gear/companion/tome sources) ----
        bonus_pool = self.bonus_atk

        comp_pct = self._get_companion_bonus("atk")
        if comp_pct > 0:
            bonus_pool += int(flat * (comp_pct / 100))

        # Stat investment bonus (0.1% per point, scales off flat)
        if self.stat_invest_atk > 0:
            bonus_pool += int(flat * (self.stat_invest_atk * 0.001))

        # Wrath tome: converts % of flat DEF into bonus ATK
        wrath_pct = self.get_tome_bonus("wrath")
        if wrath_pct > 0:
            bonus_pool += int(self.flat_def * (wrath_pct / 100))

        # Hematurgy Counterforce: converts % of total DEF into flat bonus ATK —
        # same shape as Wrath tome above, just scaled off the full DEF stat
        # (including DEF buffs) instead of flat_def.
        if self.hematurgy_passives:
            from core.hematurgy.engine import get_counterforce_bonus

            bonus_pool += get_counterforce_bonus(self)

        # ---- Percentage-of-flat pool (every "+X% ATK" source sums here) ----
        pct_pool = 0.0

        # Unified multiplier (codex signature/boon + diabolic_pact, etc.)
        if self.atk_multiplier != 1.0:
            pct_pool += self.atk_multiplier - 1.0

        # Ascension pinnacle % bonus
        if self.ascension_unlocks:
            atk_pct = self.get_ascension_bonuses()["atk_pct"]
            if atk_pct:
                pct_pool += atk_pct / 100

        # Soul Stone Vulcan Resonance (offensive_2 / offensive_3)
        if self.soul_stone:
            from core.apex.mechanics import ApexMechanics

            res = ApexMechanics.get_resonance_multipliers(self.soul_stone)
            if res["atk_mult"] != 1.0:
                pct_pool += res["atk_mult"] - 1.0

        # Alchemy Enrage (temporary potion % ATK boost) — applies only to Base +
        # Equipment, same as every other pct_pool source, and expires on its own
        # turn timer (see monster_turn.py).
        if self.alchemy_atk_boost_pct > 0:
            pct_pool += self.alchemy_atk_boost_pct

        # Hematurgy: Iron Momentum (stacking) + Soul Fracture (HP-lost scaling) +
        # Executioner's Rite (conditional on monster < 30% HP, needs monster arg).
        if self.hematurgy_passives:
            from core.hematurgy.engine import (
                get_executioners_rite_bonus,
                get_iron_momentum_factor,
                get_soul_fracture_factor,
            )

            pct_pool += get_iron_momentum_factor(self)
            pct_pool += get_soul_fracture_factor(self)
            if monster is not None:
                pct_pool += get_executioners_rite_bonus(self, monster)

        total = flat + bonus_pool
        if pct_pool:
            total += int(flat * pct_pool)

        # Permanent run penalty (fragment_boost downside in codex runs) — a flat
        # deduction, not part of the pct_pool base.
        total -= self.run_atk_penalty

        return max(0, total)

    def get_total_defence(self) -> int:
        flat = self.flat_def  # Base + Equipment; pre-computed, immutable during combat

        # ---- Flat bonus pool ----
        bonus_pool = self.bonus_def

        comp_pct = self._get_companion_bonus("def")
        if comp_pct > 0:
            bonus_pool += int(flat * (comp_pct / 100))

        # Stat investment bonus (0.1% per point, scales off flat)
        if self.stat_invest_def > 0:
            bonus_pool += int(flat * (self.stat_invest_def * 0.001))

        # Bastion tome: converts % of flat ATK into bonus DEF
        bastion_pct = self.get_tome_bonus("bastion")
        if bastion_pct > 0:
            bonus_pool += int(self.flat_atk * (bastion_pct / 100))

        # ---- Percentage-of-flat pool ----
        pct_pool = 0.0

        # Unified multiplier
        if self.def_multiplier != 1.0:
            pct_pool += self.def_multiplier - 1.0

        # Ascension pinnacle % bonus
        if self.ascension_unlocks:
            def_pct = self.get_ascension_bonuses()["def_pct"]
            if def_pct:
                pct_pool += def_pct / 100

        # Soul Stone Athena Resonance (defensive_2 / defensive_3)
        if self.soul_stone:
            from core.apex.mechanics import ApexMechanics

            res = ApexMechanics.get_resonance_multipliers(self.soul_stone)
            if res["def_mult"] != 1.0:
                pct_pool += res["def_mult"] - 1.0

        # Alchemy Enrage (temporary potion % DEF boost) — same pct_pool treatment
        # as ATK; expires on its own turn timer (see monster_turn.py).
        if self.alchemy_def_boost_pct > 0:
            pct_pool += self.alchemy_def_boost_pct

        total = flat + bonus_pool
        if pct_pool:
            total += int(flat * pct_pool)

        # Permanent run penalty — a flat deduction, not part of the pct_pool base.
        total -= self.run_def_penalty

        return max(0, total)

    def _calc_raw_pdr(self) -> tuple[int, int]:
        """Returns (raw_pdr, pdr_cap) before the hard cap is applied."""
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

        # Codex chapter PDR reduction (applied before hard cap)
        if self.chapter_pdr_reduction > 0:
            total = int(total * (1 - self.chapter_pdr_reduction))

        # Soul stone: impregnable — T1=+2% → T5=+10% PDR (skipped if armor passive active)
        ss_impregnable = self.get_soul_stone_passive("impregnable")
        if ss_impregnable and not (
            self.equipped_armor and self.equipped_armor.passive == "Impregnable"
        ):
            total += ss_impregnable * 2

        # Hard cap: 90% with Impregnable armor passive OR soul stone impregnable, otherwise 80%
        has_impregnable = (
            self.equipped_armor and self.equipped_armor.passive == "Impregnable"
        ) or bool(ss_impregnable)
        cap = 90 if has_impregnable else 80
        return int(max(0, total)), cap

    def get_total_pdr(self) -> int:
        raw, cap = self._calc_raw_pdr()
        return min(cap, raw)

    def get_raw_pdr(self) -> int:
        """PDR total before the hard cap — excess acts as a buffer against Corrosion."""
        raw, _ = self._calc_raw_pdr()
        return raw

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

        return int(total)

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
        # Weapon base crit (from drop template, stored as e.g. 0.05 → 5)
        if self.equipped_weapon:
            chance += int(self.equipped_weapon.crit_chance * 100)
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
        """Full rarity total: gear + (companion + Providence % more, additive) + codex boon bonus."""
        total = self.rarity  # Gear only (weapon + accessory)

        # Companion rarity and Providence tome both provide "% more rarity" and sum additively
        # before being applied as a single multiplier to gear rarity.
        comp_rarity_pct = self._get_companion_bonus("rarity")
        prov_pct = self.get_tome_bonus("providence")
        combined_more_pct = comp_rarity_pct + prov_pct
        if combined_more_pct > 0 and total > 0:
            total = int(total * (1 + combined_more_pct / 100))

        # Codex rarity boon accumulator
        total += self.bonus_rarity
        return total

    def get_special_drop_bonus(self) -> float:
        """Returns total Special Rarity bonus in %, capped at 20%."""
        bonus = 0.0
        # Gear (Thrill-Seeker Boot): 0.5% per level, max 3% at rank 6
        if self.equipped_boot and self.equipped_boot.passive == "thrill-seeker":
            bonus += self.equipped_boot.passive_lvl * 0.5
        # Soul Stone: thrill-seeker tier adds 0.5% per tier
        ss_ts = self.get_soul_stone_passive("thrill-seeker")
        if ss_ts:
            bonus += ss_ts * 0.5

        # Armor (Treasure Hunter)
        if self.equipped_armor and self.equipped_armor.passive == "Treasure Hunter":
            bonus += 3
        # Soul Stone: treasure hunter adds flat 3% bonus
        if self.get_soul_stone_passive("treasure hunter"):
            bonus += 3

        # Companions
        bonus += self._get_companion_bonus("s_rarity")

        # Partner co_special_rarity (set at combat start by passives.py)
        bonus += int(self.partner_special_rarity)

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

    def get_weapon_crit_multi(self, monster: "Monster | None" = None) -> float:
        """Returns the total crit damage multiplier.

        Additive sources (all stacked into a single multiplier, never compounded):
        - Weapon base crit_multi (from DB template)
        - Deftness essence bonuses (glove / boot / helmet essence slots)
        - Insight helmet passive (+lvl × 0.1)
        - Slayer crit_dmg emblem (+tier × 0.05 per total tier)
        - Active partner co_crit_damage skill (+lvl × 0.10)
        - Hematurgy Chain Reaction (+per consecutive crit stack)
        - Hematurgy Executioner's Rite (conditional on monster < 30% HP, needs
          monster arg — omit to get the stat without it, e.g. profile displays)

        One-shot/consumed bonuses (Jewel of Paradise Cataclysm) are NOT included
        here since they must be consumed exactly once per crit resolution — see
        calc_crit_damage() in damage_calc.py, which adds them on top of this.
        Debuffs (Nullifying, chapter_crit_dmg_reduction) are also handled there,
        as multiplicative dampeners applied to the fully-summed total.
        """
        from core.items.essence_mechanics import compute_essence_stat_bonus

        base = self.equipped_weapon.crit_multi if self.equipped_weapon else 2.0

        # Deftness essence (glove, boot, helmet)
        for item in (self.equipped_glove, self.equipped_boot, self.equipped_helmet):
            if item:
                base += compute_essence_stat_bonus(item).get("crit_multi", 0.0)

        # Insight helmet passive
        if self.equipped_helmet and self.get_helmet_passive() == "insight":
            base += self.equipped_helmet.passive_lvl * 0.1

        # Slayer crit_dmg emblem
        crit_dmg_tiers = self.get_emblem_bonus("crit_dmg")
        if crit_dmg_tiers > 0:
            base += crit_dmg_tiers * 0.05

        # Active partner co_crit_damage
        if self.active_partner:
            for key, lvl in self.active_partner.combat_skills:
                if key == "co_crit_damage":
                    base += lvl * 0.10

        # Hematurgy: Chain Reaction + Executioner's Rite (crit damage half)
        if self.hematurgy_passives:
            from core.hematurgy.engine import (
                get_chain_reaction_crit_bonus,
                get_executioners_rite_bonus,
            )

            base += get_chain_reaction_crit_bonus(self)
            if monster is not None:
                base += get_executioners_rite_bonus(self, monster)

        return base

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
