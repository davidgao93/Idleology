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
    # Map generation
    hazards: List[str] = field(default_factory=list) # "safe", "gravel", "gas", "magma"
    revealed_indices: List[int] = field(default_factory=list)

class DelveMechanics:
    HAZARDS = ["Safe", "Gravel", "Gas Pocket", "Magma Flow"]
    
    # Mitigation per pickaxe tier (Iron -> Ideal)
    TIER_MITIGATION = {
        'iron': 0.0, 'steel': 0.10, 'gold': 0.20, 
        'platinum': 0.30, 'ideal': 0.50
    }

    @staticmethod
    def get_max_fuel(level: int) -> int:
        # Base 20, +5 per level
        return 20 + ((level - 1) * 5)

    @staticmethod
    def get_reinforce_power(level: int) -> int:
        # Base 15%, +5% per level
        return 15 + ((level - 1) * 5)

    @staticmethod
    def get_survey_range(level: int) -> int:
        # Lvl 1-3: 1 tile, Lvl 4-7: 2 tiles, Lvl 8+: 3 tiles
        if level >= 8: return 3
        if level >= 4: return 2
        return 1

    @staticmethod
    def get_upgrade_cost(current_level: int) -> int:
        # Cost in Obsidian Shards
        return current_level * 5

    @staticmethod
    def generate_layer(depth: int) -> str:
        """Generates a hazard based on depth difficulty."""
        roll = random.random()
        
        # Danger scales with depth. 
        # Depth 0-10: Mostly safe.
        # Depth 50+: High magma chance.
        danger_factor = min(0.8, depth * 0.015) 
        
        if roll > (0.7 - danger_factor):
            sub_roll = random.random()
            if sub_roll < 0.5: return "Gravel" # Low dmg
            if sub_roll < 0.8: return "Gas Pocket" # Med dmg
            return "Magma Flow" # High dmg
            
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
        """Returns (Curios, Shards) found at this specific depth."""
        curios = 0
        shards = 0
        
        # Curio Milestones
        if depth % 10 == 0: curios = 1
        if depth % 50 == 0: curios += 1 # Bonus at 50
        
        # Shard Random Drops
        if random.random() < 0.20:
            shards = random.randint(1, 3)
            
        return curios, shards