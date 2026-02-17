import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict

@dataclass
class DelveState:
    depth: int = 0
    current_fuel: int = 0
    max_fuel: int = 0
    stability: int = 100
    pickaxe_tier: str = "iron"
    shards_found: int = 0
    curios_found: int = 0
    hazards: List[str] = field(default_factory=list)
    revealed_indices: List[int] = field(default_factory=list)

class DelveMechanics:
    HAZARDS = ["Safe", "Gravel", "Gas Pocket", "Magma Flow"]
    
    TIER_MITIGATION = {
        'iron': 0.0, 'steel': 0.10, 'gold': 0.20, 
        'platinum': 0.30, 'ideal': 0.50
    }

    @staticmethod
    def get_max_fuel(level: int) -> int:
        return 20 + ((level - 1) * 5)

    @staticmethod
    def get_reinforce_power(level: int) -> int:
        return 15 + ((level - 1) * 5)

    @staticmethod
    def get_survey_range(level: int) -> int:
        if level >= 8: return 3
        if level >= 4: return 2
        return 1

    @staticmethod
    def get_upgrade_cost(current_level: int) -> int:
        return current_level * 5

    @staticmethod
    def get_entry_cost(fuel_level: int) -> int:
        return 1000 + (fuel_level * 500)

    @staticmethod
    def calculate_level_from_xp(total_xp: int) -> int:
        if total_xp <= 0: return 1
        return int((total_xp / 50) ** 0.5) + 1

    @staticmethod
    def get_level_reward(level: int) -> int:
        return 5 + (level * 2)

    @staticmethod
    def generate_layer(depth: int) -> str:
        roll = random.random()
        danger_factor = min(0.90, depth * 0.03) 
        safe_threshold = max(0.1, 0.8 - danger_factor)

        if roll > safe_threshold:
            sub_roll = random.random()
            magma_chance = min(0.6, depth * 0.02)
            if sub_roll < magma_chance: return "Magma Flow"
            if sub_roll < 0.6: return "Gas Pocket"
            return "Gravel"
            
        return "Safe"

    @staticmethod
    def calculate_damage(hazard: str, pickaxe_tier: str) -> int:
        base_dmg = 0
        if hazard == "Gravel": base_dmg = 15
        elif hazard == "Gas Pocket": base_dmg = 30
        elif hazard == "Magma Flow": base_dmg = 50
        
        if base_dmg == 0: return 0
        
        mitigation = DelveMechanics.TIER_MITIGATION.get(pickaxe_tier, 0.0)
        return int(base_dmg * (1 - mitigation))

    @staticmethod
    def check_rewards(depth: int) -> Tuple[int, int]:
        curios = 0
        shards = 0
        
        if depth > 0 and depth % 25 == 0: 
            curios = 1
            if depth >= 50: curios = 2 
        
        if depth > 15:
            chance = min(0.30, (depth - 10) * 0.005)
            if random.random() < chance:
                shards = random.randint(1, 2)
            
        return curios, shards