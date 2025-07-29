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
    passive_lvl: int
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
    passive_lvl: int = 0
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
    passive_lvl: int = 0
    description: str = ""


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
    base_rarity: int = 0
    base_crit_chance_target: int = 95 # target to hit when rolling, 5% base crit

    potions: int

    # Equipped Gear
    equipped_weapon: Optional[Weapon] = None
    equipped_accessory: Optional[Accessory] = None
    equipped_armor: Optional[Armor] = None
    equipped_glove: Optional[Glove] = None
    equipped_boot: Optional[Boot] = None

    # Transient states (reset each combat)
    combat_ward: int = 0
    is_invulnerable_this_combat: bool = False
    combat_cooldown_reduction_seconds: int = 0

    # Glove passives
    equilibrium_bonus_xp_pending: int = 0
    plundering_bonus_gold_pending: int = 0

    # Methods to calculate total states
    def get_total_attack(self) -> int:
        total = self.base_attack
        if self.equipped_weapon: total += self.equipped_weapon.attack
        if self.equipped_accessory: total += self.equipped_accessory.attack
        if self.equipped_glove: total += self.equipped_glove.attack
        if self.equipped_boot: total += self.equipped_boot.attack
        return total

    def get_total_defence(self) -> int:
        total = self.base_defence
        if self.equipped_weapon: total += self.equipped_weapon.defence
        if self.equipped_accessory: total += self.equipped_accessory.defence
        if self.equipped_glove: total += self.equipped_glove.defence
        if self.equipped_boot: total += self.equipped_boot.defence
        return total
    
    def get_total_pdr(self) -> int:
        total = 0 # Base PDR if any
        if self.equipped_armor: total += self.equipped_armor.pdr
        if self.equipped_glove: total += self.equipped_glove.pdr
        if self.equipped_boot: total += self.equipped_boot.pdr
        return total

    def get_total_fdr(self) -> int:
        total = 0 # Base FDR if any
        if self.equipped_armor: total += self.equipped_armor.fdr
        if self.equipped_glove: total += self.equipped_glove.fdr
        if self.equipped_boot: total += self.equipped_boot.fdr
        return total

    def get_total_ward_percentage(self) -> int:
        total = 0
        if self.equipped_accessory: total += self.equipped_accessory.ward
        if self.equipped_armor: total += self.equipped_armor.ward
        if self.equipped_glove: total += self.equipped_glove.ward
        if self.equipped_boot: total += self.equipped_boot.ward
        return total

    def get_current_crit_target(self) -> int:
        target = self.base_crit_chance_target
        if self.equipped_accessory: target -= self.equipped_accessory.crit
        return max(1, target)

    # Ward from gear is % of max_hp, applied at start of combat
    def get_combat_ward_value(self) -> int:
        ward_percent = self.get_total_ward_percentage()
        return int((ward_percent / 100) * self.max_hp) if ward_percent > 0 else 0

    # Add more getter methods for block, evasion, rarity, passives etc.
    def get_weapon_passive(self) -> str:
        return self.equipped_weapon.passive if self.equipped_weapon else "none"
    
    def get_weapon_pinnacle(self) -> str:
        return self.equipped_weapon.p_passive if self.equipped_weapon else "none"
    
    def get_weapon_utmost(self) -> str:
        return self.equipped_weapon.u_passive if self.equipped_weapon else "none"
    
    def get_armor_passive(self) -> str:
        return self.equipped_armor.passive if self.equipped_armor else "none"
    
    def get_accessory_passive(self) -> str:
        return self.equipped_accessory.passive if self.equipped_accessory else "none"
    
    def get_accessory_level(self) -> str:
        return self.equipped_accessory.passive if self.equipped_accessory else "none"
    
    def get_glove_passive(self) -> str:
        return self.equipped_glove.passive if self.equipped_glove else "none"
    
    def get_glove_passive_lvl(self) -> str:
        return self.equipped_glove.passive_lvl if self.equipped_glove else "none"
    
    def get_boot_passive(self) -> str:
        return self.equipped_boot.passive if self.equipped_boot else "none"
    
    def get_boot_passive_lvl(self) -> str:
        return self.equipped_boot.passive_lvl if self.equipped_boot else "none"


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