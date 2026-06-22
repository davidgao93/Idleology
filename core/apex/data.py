"""
core/apex/data.py — Static definitions for Apex Hunts.

Contains:
  ZoneDef           — zone metadata
  ZONE_DEFS         — 6 zones keyed by zone_key
  ApexMonsterDef    — apex monster definition
  APEX_BY_ZONE      — monsters indexed by zone_key
  PASSIVE_SHARD_MAP — passive_name → shard_type
  PASSIVE_CATEGORY_MAP — passive_name → category
  RESONANCE_TABLE   — resonance key → (name, description)
  UPGRADE_COSTS     — (tier_from, tier_to) → {matching, rift}
  UPGRADE_OUTCOMES  — (tier_from, tier_to) → (success_pct, stay_pct, downgrade_pct)
"""

from dataclasses import dataclass

from core.images import (  # Apex monster combat images
    APEX_ASHFALL_COLOSSUS,
    APEX_BASTION_WRAITH,
    APEX_CINDERBORN_DRAKE,
    APEX_CYCLONE_REVENANT,
    APEX_EMBER_TYRANT,
    APEX_ENTROPY_ENGINE,
    APEX_FORTRESS_COLOSSUS,
    APEX_FORTUNES_REAPER,
    APEX_GILDED_PREDATOR,
    APEX_GREED_INCARNATE,
    APEX_GROVE_ANCIENT,
    APEX_IRON_GOLEM_LORD,
    APEX_LIVING_CANOPY,
    APEX_MAGMA_HYDRA,
    APEX_NEXUS_ABOMINATION,
    APEX_PYROCLAST_SPECTER,
    APEX_REALITY_SHREDDER,
    APEX_RIFT_LEVIATHAN,
    APEX_ROOT_SOVEREIGN,
    APEX_SIEGE_MASTER,
    APEX_STORMCALLER_WYRM,
    APEX_TEMPEST_SOVEREIGN,
    APEX_THORNWEALD_TITAN,
    APEX_THUNDER_BEHEMOTH,
    APEX_VAULT_PHANTOM,
    APEX_VAULT_SENTINEL,
    APEX_VERDANT_DEVOURER,
    APEX_VOID_FRACTURE,
    APEX_VOLTAIC_SHADE,
    APEX_WARDEN_OF_IRON,
)

# ---------------------------------------------------------------------------
# Zone definitions
# ---------------------------------------------------------------------------


@dataclass
class ZoneDef:
    key: str
    name: str
    emoji: str
    shard_type: str
    modifier_key: str
    modifier_name: str
    modifier_desc: str
    color: int  # Discord embed color (hex int)


ZONE_DEFS: dict[str, ZoneDef] = {
    "ashen": ZoneDef(
        key="ashen",
        name="Ashen Wastes",
        emoji="🔥",
        shard_type="pyre",
        modifier_key="scorched",
        modifier_name="Scorched",
        modifier_desc=(
            "Your ATK is boosted +20%. The monster's Flashfire charges begin at 4 "
            "and their strikes deal +20% damage."
        ),
        color=0xCC4400,
    ),
    "storm": ZoneDef(
        key="storm",
        name="Storm Reach",
        emoji="⚡",
        shard_type="tempest",
        modifier_key="tempest",
        modifier_name="Tempest",
        modifier_desc=(
            "You gain +15% Crit Chance. Every 3rd monster turn, unavoidable "
            "lightning strikes for 8% of your max HP as true damage."
        ),
        color=0x4466FF,
    ),
    "citadel": ZoneDef(
        key="citadel",
        name="Iron Citadel",
        emoji="🏰",
        shard_type="bulwark",
        modifier_key="siege_grounds",
        modifier_name="Siege Grounds",
        modifier_desc=(
            "You deal +30% ATK. The monster starts with 30% max HP Ward and "
            "an additional 30% DR against your attacks."
        ),
        color=0x888888,
    ),
    "grove": ZoneDef(
        key="grove",
        name="Eternal Grove",
        emoji="🌿",
        shard_type="verdant",
        modifier_key="living_battlefield",
        modifier_name="Living Battlefield",
        modifier_desc=(
            "The monster regenerates 0.4% of max HP each monster turn. "
            "You heal 1% of your max HP on each connected hit."
        ),
        color=0x228833,
    ),
    "vault": ZoneDef(
        key="vault",
        name="Golden Vault",
        emoji="💰",
        shard_type="fortune",
        modifier_key="tempted_fate",
        modifier_name="Tempted Fate",
        modifier_desc=(
            "All XP and Gold rewards are doubled. Every 4th monster turn, "
            "all your ward is drained instantly."
        ),
        color=0xFFAA00,
    ),
    "shattered": ZoneDef(
        key="shattered",
        name="Shattered Realm",
        emoji="🌀",
        shard_type="rift",
        modifier_key="reality_fracture",
        modifier_name="Reality Fracture",
        modifier_desc=(
            "One of the monster's modifiers rerolls every 5 turns. "
            "Each of your turns has a 12% chance to force a critical hit."
        ),
        color=0x9900CC,
    ),
}

# ---------------------------------------------------------------------------
# Apex monster definitions
# ---------------------------------------------------------------------------


@dataclass
class ApexMonsterDef:
    name: str
    zone_key: str
    flavor: str  # monster.flavor text for combat log
    modifiers: list  # list of modifier name strings (applied at build time)
    image: str = ""  # URL or asset key


# Apex monster pool (module-private; only used to populate the zone index below)
_apex_pool: list[ApexMonsterDef] = [
    # ----- Ashen Wastes (pyre) -----
    ApexMonsterDef(
        "Cinderborn Drake",
        "ashen",
        "breathes scorching flame",
        ["Flashfire", "Savage", "Enraged"],
    ),
    ApexMonsterDef(
        "Ember Tyrant",
        "ashen",
        "bellows a volcanic roar",
        ["Flashfire", "Lethal", "Overwhelming"],
    ),
    ApexMonsterDef(
        "Ashfall Colossus",
        "ashen",
        "shakes the earth with blazing fists",
        ["Flashfire", "Ironclad", "Titanic"],
    ),
    ApexMonsterDef(
        "Magma Hydra",
        "ashen",
        "strikes with molten heads",
        ["Flashfire", "Mending", "Multistrike"],
    ),
    ApexMonsterDef(
        "Pyroclast Specter",
        "ashen",
        "surges through waves of fire",
        ["Flashfire", "Spectral", "Venomous"],
    ),
    # ----- Storm Reach (tempest) -----
    ApexMonsterDef(
        "Stormcaller Wyrm",
        "storm",
        "crackles with electric fury",
        ["Keen", "Lethal", "Savage"],
    ),
    ApexMonsterDef(
        "Tempest Sovereign",
        "storm",
        "commands the winds to strike",
        ["Devastating", "Keen", "Blinding"],
    ),
    ApexMonsterDef(
        "Cyclone Revenant",
        "storm",
        "spins in a vortex of lightning",
        ["Multistrike", "Keen", "Lethal"],
    ),
    ApexMonsterDef(
        "Thunder Behemoth",
        "storm",
        "stomps with crackling force",
        ["Overwhelming", "Lethal", "Ironclad"],
    ),
    ApexMonsterDef(
        "Voltaic Shade",
        "storm",
        "phases through lightning",
        ["Spectral", "Keen", "Venomous"],
    ),
    # ----- Iron Citadel (bulwark) -----
    ApexMonsterDef(
        "Siege Master",
        "citadel",
        "marches with impenetrable armour",
        ["Ironclad", "Stalwart", "Crushing"],
    ),
    ApexMonsterDef(
        "Iron Golem Lord",
        "citadel",
        "pummels with titanium fists",
        ["Ironclad", "Titanic", "Devastating"],
    ),
    ApexMonsterDef(
        "Warden of Iron",
        "citadel",
        "deflects all but the mightiest blows",
        ["Ironclad", "Stalwart", "Savage"],
    ),
    ApexMonsterDef(
        "Fortress Colossus",
        "citadel",
        "absorbs your strikes with layered plate",
        ["Ironclad", "Mending", "Ironclad"],
    ),
    ApexMonsterDef(
        "Bastion Wraith",
        "citadel",
        "warps through impenetrable steel",
        ["Stalwart", "Spectral", "Crushing"],
    ),
    # ----- Eternal Grove (verdant) -----
    ApexMonsterDef(
        "Grove Ancient",
        "grove",
        "channels the forest's endless vitality",
        ["Mending", "Vampiric", "Thorned"],
    ),
    ApexMonsterDef(
        "Thornweald Titan",
        "grove",
        "lashes with living vines",
        ["Thorned", "Mending", "Venomous"],
    ),
    ApexMonsterDef(
        "Verdant Devourer",
        "grove",
        "consumes your life force",
        ["Vampiric", "Hemorrhage", "Mending"],
    ),
    ApexMonsterDef(
        "Living Canopy",
        "grove",
        "rains life-draining spores",
        ["Mending", "Parching", "Vampiric"],
    ),
    ApexMonsterDef(
        "Root Sovereign",
        "grove",
        "binds you with ancient roots",
        ["Mending", "Enraged", "Thorned"],
    ),
    # ----- Golden Vault (fortune) -----
    ApexMonsterDef(
        "Vault Sentinel",
        "vault",
        "guards untold wealth with deadly precision",
        ["Lethal", "Savage", "Keen"],
    ),
    ApexMonsterDef(
        "Gilded Predator",
        "vault",
        "hunts with razor instinct",
        ["Lethal", "Blinding", "Devastating"],
    ),
    ApexMonsterDef(
        "Fortune's Reaper",
        "vault",
        "claims bounty with every strike",
        ["Lethal", "Multistrike", "Keen"],
    ),
    ApexMonsterDef(
        "Greed Incarnate",
        "vault",
        "feeds on your accumulated power",
        ["Vampiric", "Lethal", "Savage"],
    ),
    ApexMonsterDef(
        "Vault Phantom",
        "vault",
        "phases through defences with gilded blades",
        ["Spectral", "Lethal", "Savage"],
    ),
    # ----- Shattered Realm (rift) -----
    ApexMonsterDef(
        "Reality Shredder",
        "shattered",
        "tears apart the fabric of combat",
        ["Spectral", "Devastating", "Lethal"],
    ),
    ApexMonsterDef(
        "Void Fracture",
        "shattered",
        "bends causality to its will",
        ["Spectral", "Nullifying", "Savage"],
    ),
    ApexMonsterDef(
        "Entropy Engine",
        "shattered",
        "accelerates entropy around you",
        ["Temporal Collapse", "Spectral", "Lethal"],
    ),
    ApexMonsterDef(
        "Nexus Abomination",
        "shattered",
        "converges all realities into a killing blow",
        ["Multistrike", "Devastating", "Spectral"],
    ),
    ApexMonsterDef(
        "Rift Leviathan",
        "shattered",
        "swallows you in cascading reality breaks",
        ["Overwhelming", "Spectral", "Devastating"],
    ),
]

# Build lookup by zone
APEX_BY_ZONE: dict[str, list[ApexMonsterDef]] = {}
for _m in _apex_pool:
    APEX_BY_ZONE.setdefault(_m.zone_key, []).append(_m)

# ---------------------------------------------------------------------------
# Passive → Shard mapping
# ---------------------------------------------------------------------------

PASSIVE_SHARD_MAP: dict[str, str] = {
    # Pyre — fire / damage / damage-over-time
    "burning": "pyre",
    "shocking": "pyre",
    "echo": "pyre",
    "cull": "pyre",
    "frenzy": "pyre",
    "piety": "pyre",
    "poison": "pyre",
    # Tempest — accuracy / crit / mobility
    "piercing": "tempest",
    "debilitate": "tempest",
    "deadeye": "tempest",
    "deftness": "tempest",
    "adroit": "tempest",
    "insight": "tempest",
    "obliterate": "tempest",
    "lucky strikes": "tempest",
    # Bulwark — defence / sustain
    "sturdy": "bulwark",
    "impregnable": "bulwark",
    "arcane": "bulwark",
    "hearty": "bulwark",
    "cleric": "bulwark",
    "ward-touched": "bulwark",
    "ward-fused": "bulwark",
    "ghosted": "bulwark",
    # Verdant — lifesteal / healing / nature
    "transcendence": "verdant",
    "absorb": "verdant",
    "juggernaut": "verdant",
    "leeching": "verdant",
    "thorns": "verdant",
    "volatile": "verdant",
    "divine": "verdant",
    "instability": "verdant",
    # Fortune — wealth / utility / gathering
    "prosper": "fortune",
    "infinite wisdom": "fortune",
    "treasure hunter": "fortune",
    "unlimited wealth": "fortune",
    "alchemist": "fortune",
    "speedster": "fortune",
    "skiller": "fortune",
    "treasure-tracker": "fortune",
    "thrill-seeker": "fortune",
    "plundering": "fortune",
    "equilibrium": "fortune",
    # Rift — no exclusive family; rift shards are the T3+ co-cost
}

# ---------------------------------------------------------------------------
# Passive → Combat category
# ---------------------------------------------------------------------------

PASSIVE_CATEGORY_MAP: dict[str, str] = {
    # Offensive
    "burning": "offensive",
    "shocking": "offensive",
    "echo": "offensive",
    "cull": "offensive",
    "poison": "offensive",
    "obliterate": "offensive",
    "lucky strikes": "offensive",
    "debilitate": "offensive",
    "frenzy": "offensive",
    "instability": "offensive",
    "volatile": "offensive",
    "thorns": "offensive",
    # Defensive
    "sturdy": "defensive",
    "impregnable": "defensive",
    "ward-touched": "defensive",
    "ward-fused": "defensive",
    "ghosted": "defensive",
    "transcendence": "defensive",
    "absorb": "defensive",
    "divine": "defensive",
    "hearty": "defensive",
    "cleric": "defensive",
    # Mixed (offensive-defensive hybrid)
    "arcane": "mixed",
    "juggernaut": "mixed",
    "piety": "mixed",
    "leeching": "mixed",
    "deftness": "mixed",
    "adroit": "mixed",
    "piercing": "mixed",
    "deadeye": "mixed",
    "insight": "mixed",
    # Utility
    "prosper": "utility",
    "infinite wisdom": "utility",
    "treasure hunter": "utility",
    "unlimited wealth": "utility",
    "alchemist": "utility",
    "speedster": "utility",
    "skiller": "utility",
    "treasure-tracker": "utility",
    "thrill-seeker": "utility",
    "plundering": "utility",
    "equilibrium": "utility",
}

# ---------------------------------------------------------------------------
# Resonance table
# ---------------------------------------------------------------------------

RESONANCE_TABLE: dict[str, tuple[str, str]] = {
    "offensive_2": ("Vulcan's Rage", "+10% ATK (final multiplier)"),
    "offensive_3": ("Vulcan's Fury", "+25% ATK (final multiplier)"),
    "defensive_2": ("Athena's Stratagem", "+8% DEF (final multiplier)"),
    "defensive_3": ("Athena's Grand Design", "+15% DEF (final multiplier)"),
    "mixed_2": (
        "Tyr's Ruling",
        "Sum ATK+DEF +5%, redistributed equally at combat start",
    ),
    "mixed_3": (
        "Tyr's Adjudication",
        "Sum ATK+DEF +20%, redistributed equally at combat start",
    ),
    "utility_2": ("Midas's Wisdom", "+20% XP (additive)"),
    "utility_3": ("Midas's Blessing", "+20% Gold (additive)"),
}

# ---------------------------------------------------------------------------
# Upgrade cost table: (tier_from) → {matching_cost, rift_cost}
# ---------------------------------------------------------------------------

UPGRADE_COSTS: dict[int, dict] = {
    1: {"matching": 3, "rift": 0},
    2: {"matching": 5, "rift": 0},
    3: {"matching": 8, "rift": 2},
    4: {"matching": 12, "rift": 5},
}

# ---------------------------------------------------------------------------
# Upgrade outcome probabilities: tier_from → (success%, stay%, downgrade%)
# ---------------------------------------------------------------------------

UPGRADE_OUTCOMES: dict[int, tuple[float, float, float]] = {
    1: (0.85, 0.15, 0.00),
    2: (0.70, 0.30, 0.00),
    3: (0.55, 0.35, 0.10),
    4: (0.40, 0.35, 0.25),
}

# ---------------------------------------------------------------------------
# Meta shard drop chances per hunt victory (independent rolls)
# ---------------------------------------------------------------------------

META_SHARD_DROP_CHANCES: dict[str, float] = {
    "sharpened_fang": 0.12,
    "engorged_heart": 0.10,
    "condensed_blood": 0.06,
    "primal_essence": 0.03,
    "soul_vessel": 0.015,
}

# ---------------------------------------------------------------------------
# Soul Stone passive tier value table
#
# Indexed [T1, T2, T3, T4, T5] (0-based, use `ss_tier - 1`).
# Weapons / Gloves / Helmets use 1:1 tier→passive_lvl equivalence and need no
# explicit table — the engine already scales those by passive_lvl.
# Boots: 6 gear tiers condensed to 5 (max_tier_value / 5 per step).
# Accessories: 2:1 mapping (soul stone tier × 2 = equivalent passive_lvl).
# Armor: gear has 1 effective tier; soul stone introduces 5 explicit steps.
# ---------------------------------------------------------------------------

SOUL_STONE_TIER_VALUES: dict[str, list] = {
    # --- Armor passives (1 → 5 tiers) ---
    "impregnable": [2, 4, 6, 8, 10],  # flat % PDR added
    "piety": [120, 240, 360, 480, 600],  # % bonus damage on 10% chance
    "transcendence": [4, 8, 12, 16, 20],  # % of (ATK+DEF) added as bonus ATK
    "treasure hunter": [0.6, 1.2, 1.8, 2.4, 3.0],  # flat special-rarity bonus
    "unlimited wealth": [40, 80, 120, 160, 200],  # % rarity bonus on 20% proc
    "alchemist": [6, 12, 18, 24, 30],  # % not-consume chance on potion use
    # --- Boot passives (6 gear tiers → 5 soul stone tiers, max_value / 5) ---
    "speedster": [72, 144, 216, 288, 360],  # seconds of combat cooldown reduction
    "skiller": [6, 12, 18, 24, 30],  # % proc chance for skill-mat drop
    # Accessories use a 2:1 tier mapping (soul stone T × 2 = effective passive_lvl)
    # and are handled inline in the engine — no explicit table entry needed.
}

META_SHARD_DISPLAY: dict[str, tuple[str, str]] = {
    "sharpened_fang": ("🦷 Sharpened Fang", "Lucky extraction chance (25% → ~44%)"),
    "engorged_heart": ("❤️ Engorged Heart", "Lucky upgrade chance (better odds)"),
    "condensed_blood": (
        "🩸 Condensed Blood",
        "Prevents tier downgrade on failed upgrade",
    ),
    "primal_essence": (
        "✨ Primal Essence",
        "Counts extracted passives as +1 (improves extraction chance)",
    ),
    "soul_vessel": ("🏺 Soul Vessel", "Extract a passive without destroying the item"),
}

# Map Apex monster name → combat image constant
APEX_MONSTER_IMAGES: dict[str, str] = {
    "Cinderborn Drake": APEX_CINDERBORN_DRAKE,
    "Ember Tyrant": APEX_EMBER_TYRANT,
    "Ashfall Colossus": APEX_ASHFALL_COLOSSUS,
    "Magma Hydra": APEX_MAGMA_HYDRA,
    "Pyroclast Specter": APEX_PYROCLAST_SPECTER,
    "Stormcaller Wyrm": APEX_STORMCALLER_WYRM,
    "Tempest Sovereign": APEX_TEMPEST_SOVEREIGN,
    "Cyclone Revenant": APEX_CYCLONE_REVENANT,
    "Thunder Behemoth": APEX_THUNDER_BEHEMOTH,
    "Voltaic Shade": APEX_VOLTAIC_SHADE,
    "Siege Master": APEX_SIEGE_MASTER,
    "Iron Golem Lord": APEX_IRON_GOLEM_LORD,
    "Warden of Iron": APEX_WARDEN_OF_IRON,
    "Fortress Colossus": APEX_FORTRESS_COLOSSUS,
    "Bastion Wraith": APEX_BASTION_WRAITH,
    "Grove Ancient": APEX_GROVE_ANCIENT,
    "Thornweald Titan": APEX_THORNWEALD_TITAN,
    "Verdant Devourer": APEX_VERDANT_DEVOURER,
    "Living Canopy": APEX_LIVING_CANOPY,
    "Root Sovereign": APEX_ROOT_SOVEREIGN,
    "Vault Sentinel": APEX_VAULT_SENTINEL,
    "Gilded Predator": APEX_GILDED_PREDATOR,
    "Fortune's Reaper": APEX_FORTUNES_REAPER,
    "Greed Incarnate": APEX_GREED_INCARNATE,
    "Vault Phantom": APEX_VAULT_PHANTOM,
    "Reality Shredder": APEX_REALITY_SHREDDER,
    "Void Fracture": APEX_VOID_FRACTURE,
    "Entropy Engine": APEX_ENTROPY_ENGINE,
    "Nexus Abomination": APEX_NEXUS_ABOMINATION,
    "Rift Leviathan": APEX_RIFT_LEVIATHAN,
}
