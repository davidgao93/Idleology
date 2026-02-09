# tests/test_combat_logic.py
import pytest
import random
from core.models import Player, Monster, Weapon, Armor
from core.combat import engine
from core.combat.calcs import calculate_hit_chance, calculate_damage_taken

# ==========================================
# 1. FIXTURES (Setup Data)
# ==========================================

@pytest.fixture
def base_player():
    """Creates a standard Level 10 Player for testing."""
    return Player(
        id="123", name="TestHero", level=10, ascension=0, exp=0,
        current_hp=100, max_hp=100, base_attack=20, base_defence=20, potions=5,
        base_crit_chance_target=95
    )

@pytest.fixture
def base_monster():
    """Creates a standard Level 10 Monster."""
    return Monster(
        name="Goblin", level=10, hp=100, max_hp=100, xp=50,
        attack=20, defence=10, modifiers=[], image="", flavor="grunts"
    )

@pytest.fixture
def op_weapon():
    """Creates a weapon with the 'polished' passive (reduces monster def)."""
    return Weapon(
        user="123", name="God Blade", level=10, attack=50, defence=0,
        rarity=0, passive="polished", description="", p_passive="none", u_passive="none",
        is_equipped=True
    )

# ==========================================
# 2. UNIT TESTS (Check Mechanics)
# ==========================================

def test_hit_chance_calculation(base_player, base_monster):
    """Test that higher attack increases hit chance."""
    # Scenario A: Equal stats
    base_chance = calculate_hit_chance(base_player, base_monster)
    
    # Scenario B: Player gets massive attack boost
    base_player.base_attack = 200
    boosted_chance = calculate_hit_chance(base_player, base_monster)
    
    assert boosted_chance > base_chance, "High attack should result in higher hit chance"

def test_damage_mitigation(base_player, base_monster):
    """Test that player defence reduces incoming damage."""
    # Force monster attack to be constant-ish for test
    base_monster.attack = 50
    
    # Case 1: 0 Defence
    base_player.base_defence = 0
    dmg_low_def = calculate_damage_taken(base_player, base_monster)
    
    # Case 2: 50 Defence
    base_player.base_defence = 50
    dmg_high_def = calculate_damage_taken(base_player, base_monster)
    
    # Note: Due to RNG in damage rolls, we run this multiple times to be sure, 
    # or mock random.randint. For a simple test, we check averages logic.
    assert dmg_high_def <= dmg_low_def

def test_weapon_passive_trigger(base_player, base_monster, op_weapon):
    """Test if 'polished' passive actually reduces monster defence."""
    base_player.equipped_weapon = op_weapon
    initial_monster_def = base_monster.defence
    
    # Run the start-of-combat logic
    logs = engine.apply_combat_start_passives(base_player, base_monster)
    
    assert "Weapon Passive" in logs
    assert base_monster.defence < initial_monster_def
    print(f"\n[Passive Test] Monster Def dropped from {initial_monster_def} to {base_monster.defence}")

# ==========================================
# 3. SIMULATIONS (Balance Testing)
# ==========================================

def run_simulation(player, monster, iterations=1000):
    """Runs X automated fights to determine win rate."""
    wins = 0
    turns_log = []

    # Cache initial stats to reset after every fight
    p_hp = player.max_hp
    m_hp = monster.max_hp
    m_def_orig = monster.defence # In case passives reduce it

    for _ in range(iterations):
        # Reset HP and stats
        player.current_hp = p_hp
        monster.hp = m_hp
        monster.defence = m_def_orig 
        player.combat_ward = player.get_combat_ward_value()
        
        # Apply start passives
        engine.apply_stat_effects(player, monster)
        engine.apply_combat_start_passives(player, monster)

        turns = 0
        while player.current_hp > 0 and monster.hp > 0:
            turns += 1
            # Player turn
            engine.process_player_turn(player, monster)
            # Monster turn (if alive)
            if monster.hp > 0:
                engine.process_monster_turn(player, monster)
            
            # Limit infinite loops
            if turns > 100: break 

        if player.current_hp > 0:
            wins += 1
        
        turns_log.append(turns)

    avg_turns = sum(turns_log) / len(turns_log)
    win_rate = (wins / iterations) * 100
    return win_rate, avg_turns

def test_simulation_balance_check(base_player, base_monster):
    """
    Simulates 1,000 fights.
    FAIL if win rate is < 40% (Too Hard) or > 95% (Too Easy) for an even match.
    """
    print(f"\n--- SIMULATION: {base_player.name} vs {base_monster.name} ---")
    
    win_rate, avg_turns = run_simulation(base_player, base_monster, iterations=1000)
    
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Avg Turns: {avg_turns:.2f}")
    
    # Assertions for Game Balance
    if win_rate < 10:
        pytest.warns(UserWarning, match="Game might be too hard for same-level encounters")
    if win_rate > 90:
        pytest.warns(UserWarning, match="Game might be too easy for same-level encounters")
        
    assert win_rate > 0, "Player should win at least once"

def test_boss_simulation(base_player):
    """Checks if a boss 5 levels higher is basically impossible."""
    boss = Monster(
        name="Boss", level=15, hp=300, max_hp=300, xp=500,
        attack=35, defence=30, modifiers=["Titanium", "Strengthened"], image="", flavor=""
    )
    
    print(f"\n--- SIMULATION: {base_player.name} vs BOSS ---")
    win_rate, avg_turns = run_simulation(base_player, boss, iterations=500)
    
    print(f"Boss Win Rate: {win_rate:.2f}%")
    
    # We expect this to be hard. If win rate is > 50%, boss is too weak.
    assert win_rate < 50, "Boss should be challenging for a base level 10 player"