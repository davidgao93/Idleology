# core/models.py
from dataclasses import dataclass
from typing import List, Optional
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
    name: str
    level: int
    attack_modifier: int = 0
    defence_modifier: int = 0
    rarity_modifier: int = 0
    passive: str = ""

@dataclass
class Accessory:
    name: str
    level: int
    attack_modifier: int = 0
    defence_modifier: int = 0
    rarity_modifier: int = 0
    ward_modifier: int = 0
    crit_modifier: int = 0
    passive: str = ""

@dataclass
class Armor:
    name: str
    level: int
    block_modifier: int = 0
    evasion_modifier: int = 0
    ward_modifier: int = 0
    passive: str = ""        

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
    potions: int
    wep_id: int
    weapon_passive: str
    acc_passive: str
    acc_lvl: int
    armor_passive: str
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