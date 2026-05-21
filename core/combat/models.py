"""
core/combat/models.py — Combat-related dataclasses.

Contains:
  CombatState       — per-fight transient state, reset between every fight
  CodexRunState     — state that persists across Codex waves within one run
  MonsterModifier   — a single modifier applied to a monster instance
  Monster           — monster entity used during combat
  DungeonRoomOption — one branching option in a dungeon room
  DungeonState      — full dungeon-crawl session state
  Player            — player character with all stats, gear, and combat helpers
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union

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
    hema_momentum_stacks: int = 0       # Iron Momentum ATK stacks (max 5), resets on miss
    hema_bleed_total: int = 0           # Haemorrhage accumulated bleed pool
    hema_chain_stacks: int = 0          # Chain Reaction crit-dmg stacks (max 5), resets on non-crit
    hema_phantom_stacks: int = 0        # Phantom Reflex evasion stacks (max 2), consumed by hits
    hema_fevered_count: int = 0         # Fevered Strike: potions consumed this fight
    hema_predators_mark: bool = False   # Predator's Mark active on monster
    hema_tenacity_triggered: bool = False  # Tenacity one-shot flag
    hema_hp_lost_combat: int = 0        # Soul Fracture: HP lost during this combat only
    hema_blade_count: int = 0           # Spectral Waltz blade count
    hema_puncture_bleed: int = 0        # Puncture accumulated crit-bleed pool
    hema_frost_misses: int = 0          # Flash Frost consecutive miss counter
    hema_ward_inoculation: bool = False # Ward Inoculation active (no ward regen, ward→damage)
    hema_ward_dmg_buffer: int = 0       # Ward Inoculation: accumulated ward→damage pending apply
    hema_serrated_total: int = 0        # Serrated: cumulative ATK drained from monster this fight


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


# ---------------------------------------------------------------------------
# Dungeon models
# ---------------------------------------------------------------------------


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
        return max(1, base)

    def _get_companion_bonus(self, p_type: str) -> float:
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
        """Zeros bonus accumulators and stat multipliers only. Use reset_combat_state() for a full reset."""
        self.cs.bonus_atk = 0
        self.cs.bonus_def = 0
        self.cs.bonus_crit = 0
        self.cs.bonus_max_hp = 0
        self.cs.atk_multiplier = 1.0
        self.cs.def_multiplier = 1.0
        self.cs.crit_multiplier = 1.0
        self.cs.partner_special_rarity = 0.0

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

        # Hard cap: 90% with Impregnable armor passive, otherwise 80%
        cap = (
            90
            if (self.equipped_armor and self.equipped_armor.passive == "Impregnable")
            else 80
        )
        return min(cap, total)

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

        # Armor (Treasure Hunter)
        if self.equipped_armor and self.equipped_armor.passive == "Treasure Hunter":
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

    def get_weapon_crit_multi(self) -> float:
        """Returns the total crit damage multiplier.

        Additive sources (all stacked into a single multiplier):
        - Weapon base crit_multi (from DB template)
        - Deftness essence bonuses (glove / boot / helmet essence slots)
        - Insight helmet passive (+lvl × 0.1)
        - Slayer crit_dmg emblem (+tier × 0.05 per total tier)
        - Active partner co_crit_damage skill (+lvl × 0.10)
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
