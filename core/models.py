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

@dataclass
class Glove:
    user: str
    name: str
    level: int
    item_id: Optional[int] = None
    attack: int = 0
    defence: int = 0
    ward: int = 0    # Percentage
    pdr: int = 0     # Percentage
    fdr: int = 0     # Flat
    passive: str = "none"
    passive_lvl: int = 0
    description: str = ""
    is_equipped: bool = False
    potential_remaining: int = 0

@dataclass
class Boot:
    user: str
    name: str
    level: int
    item_id: Optional[int] = None
    attack: int = 0
    defence: int = 0
    ward: int = 0    # Percentage
    pdr: int = 0     # Percentage
    fdr: int = 0     # Flat
    passive: str = "none"
    passive_lvl: int = 0
    description: str = ""
    is_equipped: bool = False
    potential_remaining: int = 0

@dataclass
class Helmet:
    user: str
    name: str
    level: int
    item_id: Optional[int] = None
    defence: int = 0
    ward: int = 0    # Percentage
    pdr: int = 0     
    fdr: int = 0     
    passive: str = "none"
    passive_lvl: int = 0
    description: str = ""
    is_equipped: bool = False
    potential_remaining: int = 0


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

    @property
    def passive_value(self) -> int:
        """Calculates the numerical value based on Type and Tier."""
        # Tier scaling logic
        if self.passive_type in ['atk', 'def']: # Percentage
            return 4 + self.passive_tier # 5, 6, 7, 8, 9
        elif self.passive_type in ['hit', 'crit']: # Flat
            return self.passive_tier # 1, 2, 3, 4, 5
        elif self.passive_type == 'ward': # Percentage
            return self.passive_tier * 5 # 5, 10, 15, 20, 25
        elif self.passive_type == 'rarity': # Base Rarity
            return self.passive_tier * 3 # 3, 6, 9, 12, 15
        elif self.passive_type == 's_rarity': # Special Rarity
            return self.passive_tier # 1, 2, 3, 4, 5
        elif self.passive_type == 'fdr': # Flat Damage Reduction
            return 1 + self.passive_tier # 2, 3, 4, 5, 6
        elif self.passive_type == 'pdr': # Percent Damage Reduction
            return 2 + self.passive_tier # 3, 4, 5, 6, 7
        return 0

    @property
    def description(self) -> str:
        """Returns formatted string like '+9% Atk'"""
        val = self.passive_value
        p_map = {
            'atk': f"+{val}% Atk",
            'def': f"+{val}% Def",
            'hit': f"+{val} Hit Chance",
            'crit': f"+{val} Crit Chance",
            'ward': f"+{val}% HP as Ward",
            'rarity': f"+{val}% Rarity",
            's_rarity': f"+{val}% Special Drop Rate",
            'fdr': f"+{val} Flat Dmg Red.",
            'pdr': f"+{val}% Phys Dmg Red."
        }
        return p_map.get(self.passive_type, "Unknown Effect")


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
    base_rarity: int = 0
    base_crit_chance_target: int = 95 

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
    apothecary_tier: int = 0 

    # Transient states (reset each combat)
    combat_ward: int = 0
    is_invulnerable_this_combat: bool = False
    combat_cooldown_reduction_seconds: int = 0

    # Glove passives
    equilibrium_bonus_xp_pending: int = 0
    plundering_bonus_gold_pending: int = 0

    @property
    def rarity(self) -> int:
        """Calculates total effective rarity from base stats and equipped gear."""
        total = self.base_rarity
        if self.equipped_weapon: 
            total += self.equipped_weapon.rarity
        if self.equipped_accessory: 
            total += self.equipped_accessory.rarity
        return total
    
    def _get_companion_bonus(self, p_type: str) -> int:
        return sum(c.passive_value for c in self.active_companions if c.passive_type == p_type)

    # Methods to calculate total states
    def get_total_attack(self) -> int:
        total = self.base_attack
        if self.equipped_weapon: total += self.equipped_weapon.attack
        if self.equipped_accessory: total += self.equipped_accessory.attack
        if self.equipped_glove: total += self.equipped_glove.attack
        if self.equipped_boot: total += self.equipped_boot.attack

        comp_pct = self._get_companion_bonus('atk')
        if comp_pct > 0:
            total += int(self.base_attack * (comp_pct / 100))
        return total

    def get_total_defence(self) -> int:
        total = self.base_defence
        if self.equipped_weapon: total += self.equipped_weapon.defence
        if self.equipped_accessory: total += self.equipped_accessory.defence
        if self.equipped_glove: total += self.equipped_glove.defence
        if self.equipped_boot: total += self.equipped_boot.defence
        if self.equipped_helmet: total += self.equipped_helmet.defence

        comp_pct = self._get_companion_bonus('def')
        if comp_pct > 0:
            total += int(self.base_defence * (comp_pct / 100))
        return total
    
    def get_total_pdr(self) -> int:
        total = 0 
        if self.equipped_armor: total += self.equipped_armor.pdr
        if self.equipped_glove: total += self.equipped_glove.pdr
        if self.equipped_boot: total += self.equipped_boot.pdr
        if self.equipped_helmet: total += self.equipped_helmet.pdr

        # Companions
        total += self._get_companion_bonus('pdr')
        
        # Hard cap at 80%
        return min(80, total)

    def get_total_fdr(self) -> int:
        total = 0 
        if self.equipped_armor: total += self.equipped_armor.fdr
        if self.equipped_glove: total += self.equipped_glove.fdr
        if self.equipped_boot: total += self.equipped_boot.fdr
        if self.equipped_helmet: total += self.equipped_helmet.fdr

        # Companions
        total += self._get_companion_bonus('fdr')
        return total

    def get_total_ward_percentage(self) -> int:
        total = 0
        if self.equipped_accessory: total += self.equipped_accessory.ward
        if self.equipped_armor: total += self.equipped_armor.ward
        if self.equipped_glove: total += self.equipped_glove.ward
        if self.equipped_boot: total += self.equipped_boot.ward
        if self.equipped_helmet: total += self.equipped_helmet.ward

        # Companions
        total += self._get_companion_bonus('ward')
        return total

    def get_current_crit_target(self) -> int:
        target = self.base_crit_chance_target
        if self.equipped_accessory: target -= self.equipped_accessory.crit

        # Companions (Flat Reduction)
        target -= self._get_companion_bonus('crit')
        return max(1, target)

    def get_combat_ward_value(self) -> int:
        ward_percent = self.get_total_ward_percentage()
        return int((ward_percent / 100) * self.max_hp) if ward_percent > 0 else 0
    
    def get_total_rarity(self) -> int:
        """Helper for base rarity total."""
        total = self.rarity # Base + Gear
        total += self._get_companion_bonus('rarity')
        return total

    def get_special_drop_bonus(self) -> int:
        """New method for Special Rarity calculation."""
        bonus = 0
        # Gear (Thrill Seeker Boot)
        if self.equipped_boot and self.equipped_boot.passive == "thrill-seeker":
            bonus += self.equipped_boot.passive_lvl # 1-6%
            
        # Companions
        bonus += self._get_companion_bonus('s_rarity')
        
        # [SAFETY CAP] Hard cap special rarity bonus at 20%
        return min(20, bonus)

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
    
    def get_glove_passive(self) -> str:
        return self.equipped_glove.passive if self.equipped_glove else "none"
    
    def get_boot_passive(self) -> str:
        return self.equipped_boot.passive if self.equipped_boot else "none"
    
    def get_helmet_passive(self) -> str:
        return self.equipped_helmet.passive if self.equipped_helmet else "none"

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
    species: str = "Unknown"
    is_boss: bool = False

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
    buildings: List['Building'] = field(default_factory=list)

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