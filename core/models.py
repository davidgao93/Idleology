# core/models.py
from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict
from enum import Enum

class ModifierType(Enum):
    STEEL_BORN = "Steel-born"
    ALL_SEEING = "All-seeing"
    MIRROR_IMAGE = "Mirror Image"
    VOLATILE = "Volatile"
    GLUTTON = "Glutton"
    ENFEEBLE = "Enfeeble"
    VENOMOUS = "Venomous"
    STRENGTHENED = "Strengthened"
    HELLBORN = "Hellborn"
    LUCIFER_TOUCHED = "Lucifer-touched"
    TITANIUM = "Titanium"
    ASCENDED = "Ascended"
    SUMMONER = "Summoner"
    SHIELD_BREAKER = "Shield-breaker"
    IMPENETRABLE = "Impenetrable"
    UNBLOCKABLE = "Unblockable"
    UNAVOIDABLE = "Unavoidable"

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
    description: str

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

@dataclass
class Glove: # New dataclass for Gloves
    user: str  # user_id
    name: str  # item_name
    level: int # item_level
    attack: int = 0
    defence: int = 0
    ward: int = 0    # Percentage
    pdr: int = 0     # Percentage
    fdr: int = 0     # Flat
    passive: str = "none"
    description: str = ""


@dataclass
class Boot: # New dataclass for Boots
    user: str
    name: str
    level: int
    attack: int = 0
    defence: int = 0
    ward: int = 0    # Percentage
    pdr: int = 0     # Percentage
    fdr: int = 0     # Flat
    passive: str = "none"
    description: str = ""


@dataclass
class Player:
    id: str
    name: str
    level: int
    ascension: int
    exp: int
    hp: int
    max_hp: int
    attack: int
    defence: int
    rarity: int
    crit: int
    ward: int
    block: int
    evasion: int
    pdr: int
    fdr: int
    potions: int
    wep_id: int
    weapon_passive: str
    pinnacle_passive: str
    utmost_passive: str
    acc_passive: str
    acc_lvl: int
    armor_passive: str
    glove_passive: str = ""
    glove_passive_lvl: int = 0
    boot_passive: str = ""
    boot_passive_lvl: int = 0
    combat_cooldown_reduction: int = 0 # For speedster, in seconds
    invulnerable: bool = False

@dataclass
class Monster:
    name: str
    level: int
    hp: int
    max_hp: int
    xp: int
    attack: int
    defence: int
    modifiers: List[str]
    image: str
    flavor: str
    is_boss: bool = False


@dataclass
class DungeonRoomOption:
    direction: str
    flavor_text: str
    encounter_type: str # e.g., "COMBAT_NORMAL", "MERCHANT", "BOSS_ENTRANCE"

@dataclass
class DungeonState:
    player_id: str
    player_name: str 
    current_floor: int
    max_regular_floors: int # Number of floors with choices before the boss
    
    player_current_hp: int
    player_max_hp: int
    player_current_ward: int
    player_base_ward: int 
    
    potions_remaining: int
    dungeon_coins: int
    loot_gathered: List[Union[Weapon, Accessory, Armor]] = field(default_factory=list)

    player_buffs: List[str] = field(default_factory=list)
    player_curses: List[str] = field(default_factory=list)
    player_attack_multiplier: float = 1.0
    player_defence_multiplier: float = 1.0
    player_rarity_multiplier: float = 1.0
    monster_attack_multiplier: float = 1.0
    monster_defence_multiplier: float = 1.0
    global_monster_modifiers: List[str] = field(default_factory=list)

    current_room_options: Optional[List[DungeonRoomOption]] = None
    last_action_message: Optional[str] = None