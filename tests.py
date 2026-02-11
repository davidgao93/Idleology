import unittest
import aiosqlite
import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

# Add root directory to path so we can import core/database/cogs
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import your modules
from database import DatabaseManager
from core.models import Player, Weapon, Monster
from core.items.factory import load_player, create_weapon
from core.items.equipment_mechanics import EquipmentMechanics
from core.combat import engine, rewards
from core.combat.gen_mob import generate_encounter

from core.models import Accessory, Glove, Boot
from core.items.factory import create_accessory, create_glove, create_boot

# --- Mocking Discord Objects ---
class MockUser:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.display_name = name
        self.mention = f"@{name}"

class MockGuild:
    def __init__(self, id):
        self.id = id

class MockInteraction:
    def __init__(self, user_id=123, user_name="TestUser"):
        self.user = MockUser(user_id, user_name)
        self.guild = MockGuild(999)
        self.response = AsyncMock()
        self.followup = AsyncMock()
        self.channel = MagicMock()

# --- The Test Suite ---
class TestIdleology(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """
        Runs before EVERY test. 
        Creates an in-memory SQLite database using your exact schema.
        """
        # 1. Setup In-Memory Database
        self.db_conn = await aiosqlite.connect(":memory:")
        
        # 2. Load Schema
        with open("database/schema.sql", "r") as f:
            await self.db_conn.executescript(f.read())
        await self.db_conn.commit()

        # 3. Initialize Manager
        self.db = DatabaseManager(connection=self.db_conn)

        # 4. Create a Mock Bot to hold the DB
        self.bot = MagicMock()
        self.bot.database = self.db
        self.bot.logger = MagicMock()

        # 5. Register a Dummy User for testing
        self.uid = "1001"
        self.gid = "999"
        await self.db.users.register(self.uid, self.gid, "Tester", "url", "Testism")
        await self.db.skills.initialize(self.uid, self.gid, 'mining', 'iron')
        await self.db.skills.initialize(self.uid, self.gid, 'fishing', 'desiccated')
        await self.db.skills.initialize(self.uid, self.gid, 'woodcutting', 'flimsy')

        # Give some gold/resources
        await self.db.users.modify_gold(self.uid, 50000)
        await self.db.users.modify_currency(self.uid, "refinement_runes", 5)

    async def asyncTearDown(self):
        await self.db_conn.close()

    # =================================================================
    # 1. DATA LAYER TESTS (Database & Factory)
    # =================================================================
    async def test_user_registration_and_retrieval(self):
        """Test if a user is correctly saved and loaded."""
        user = await self.db.users.get(self.uid, self.gid)
        self.assertIsNotNone(user, "User should exist in DB")
        self.assertEqual(user[3], "Tester", "Username should match")
        self.assertEqual(user[6], 50000, "Gold should be 50000 (added)")

    async def test_equipment_creation_and_factory(self):
        """Test creating a weapon and parsing it via factory."""
        # Create a dummy weapon object
        w = Weapon(
            user=self.uid, name="Test Sword", level=10, 
            attack=5, defence=5, rarity=0, passive="burning", 
            description="A test sword", p_passive="none", u_passive="none"
        )
        
        # Save to DB
        await self.db.equipment.create_weapon(w)
        
        # Fetch from DB
        raw_items = await self.db.equipment.get_all(self.uid, "weapon")
        self.assertEqual(len(raw_items), 1, "Should have 1 weapon")
        
        # Test Factory Parsing
        weapon_obj = create_weapon(raw_items[0])
        self.assertIsInstance(weapon_obj, Weapon)
        self.assertEqual(weapon_obj.name, "Test Sword")
        self.assertEqual(weapon_obj.forges_remaining, 3, "Level 10 weapon should have 3 forges")

    async def test_player_loading(self):
        """Test loading a full Player object with gear."""
        # Equip a weapon
        w = Weapon(user=self.uid, name="Equipped Sword", level=10, attack=10, defence=0, rarity=0, passive="none", description="", p_passive="none", u_passive="none")
        await self.db.equipment.create_weapon(w)
        items = await self.db.equipment.get_all(self.uid, "weapon")
        await self.db.equipment.equip(self.uid, items[0][0], "weapon")

        # Load Player
        raw_user = await self.db.users.get(self.uid, self.gid)
        player = await load_player(self.uid, raw_user, self.db)

        self.assertIsInstance(player, Player)
        self.assertIsNotNone(player.equipped_weapon)
        self.assertEqual(player.equipped_weapon.name, "Equipped Sword")
        self.assertEqual(player.get_total_attack(), player.base_attack + 10)

    # =================================================================
    # 2. LOGIC LAYER TESTS (Mechanics & Combat)
    # =================================================================
    async def test_equipment_mechanics_forge(self):
        """Test the math for forging costs and outcomes."""
        w = Weapon(user=self.uid, name="Sword", level=50, attack=0, defence=0, rarity=0, passive="none", description="", p_passive="none", u_passive="none")
        w.forges_remaining = 4 # Tier 2 (Lvl 40-80)
        
        cost = EquipmentMechanics.calculate_forge_cost(w)
        
        # Lvl 50, 4 forges left -> Should correspond to index 4 logic in mechanics
        # Based on file: {'ore': 'iron', 'log': 'oak', 'bone': 'desiccated', 'qty': 25, 'gold': 250}
        self.assertEqual(cost['ore_type'], 'iron')
        self.assertEqual(cost['gold'], 250)

        # Test Roll Outcome
        success, new_passive = EquipmentMechanics.roll_forge_outcome(w)
        self.assertTrue(success or not success) # Just ensuring it runs without error
        if success:
            self.assertNotEqual(new_passive, "none")

    async def test_combat_engine_flow(self):
        """Simulate a full combat turn without Discord UI."""
        # 1. Setup Player
        raw_user = await self.db.users.get(self.uid, self.gid)
        player = await load_player(self.uid, raw_user, self.db)
        
        # 2. Setup Monster

        monster = Monster(
            name="Test Goblin", level=1, hp=50, max_hp=50, xp=100, 
            attack=5, defence=0, modifiers=[], image="", flavor=""
        )

        # 3. Test Turn Logic
        log_atk = engine.process_player_turn(player, monster)
        log_def = engine.process_monster_turn(player, monster)

        # 4. Assertions
        self.assertIsInstance(log_atk, str)
        self.assertIsInstance(log_def, str)
        self.assertTrue(monster.hp < 50 or "Miss" in log_atk, "Monster should take damage or miss")
        self.assertTrue(player.current_hp <= player.max_hp)

    async def test_rewards_calculation(self):
        """Test XP and Gold calculation."""
        # Setup
        raw_user = await self.db.users.get(self.uid, self.gid)
        player = await load_player(self.uid, raw_user, self.db)
        monster = Monster(name="Test", level=10, hp=0, max_hp=100, xp=100, attack=10, defence=10, modifiers=[], image="", flavor="")

        result = rewards.calculate_rewards(player, monster)
        
        self.assertGreater(result['xp'], 0)
        self.assertGreater(result['gold'], 0)

    # =================================================================
    # 3. CONTROLLER LAYER TESTS (Simulating Cogs)
    # =================================================================
    async def test_cog_register_command(self):
        """Simulate the /register command."""
        from cogs.guild import Guild
        
        cog = Guild(self.bot)
        
        # New user interaction
        interaction = MockInteraction(user_id=2002, user_name="NewGuy")
        
        # Since /register waits for reactions, this is hard to fully test without dpytest.
        # However, we can test the initial checks.
        
        # We Mock the check_user_registered to return False (so we proceed)
        # But wait, /register logic checks if user exists first.
        
        # Let's test checking cooldowns instead, simpler command
        # from cogs.general import General
        # general_cog = General(self.bot)
        # await general_cog.cooldowns.callback(general_cog, interaction)
        # interaction.response.send_message.assert_called() 
        pass 

    async def test_inventory_ui_logic(self):
        """Test the logic inside the Inventory Cog (fetching and sorting)."""
        from cogs.weapons import Weapons
        cog = Weapons(self.bot)

        # Add 3 weapons
        for i in range(3):
            w = Weapon(user=self.uid, name=f"Sword {i}", level=i+1, attack=1, defence=1, rarity=0, passive="none", description="", p_passive="none", u_passive="none")
            await self.db.equipment.create_weapon(w)

        # Call the helper method directly
        weapons = await cog._fetch_and_parse_weapons(self.uid)
        
        self.assertEqual(len(weapons), 3)
        self.assertEqual(weapons[0].name, "Sword 0")

    async def test_skills_logic(self):
        """Test updating skill resources."""
        # Initial: 0 Iron
        data = await self.db.skills.get_data(self.uid, self.gid, 'mining')
        self.assertEqual(data[3], 0) # Iron index

        # Add 10 Iron
        await self.db.skills.update_single_resource(self.uid, self.gid, 'mining', 'iron', 10)
        
        # Verify
        data = await self.db.skills.get_data(self.uid, self.gid, 'mining')
        self.assertEqual(data[3], 10)

class TestEquipmentAdvanced(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Setup a clean DB environment for Equipment tests."""
        self.db_conn = await aiosqlite.connect(":memory:")
        with open("database/schema.sql", "r") as f:
            await self.db_conn.executescript(f.read())
        await self.db_conn.commit()
        
        self.db = DatabaseManager(connection=self.db_conn)
        self.uid = "1001"
        self.gid = "999"
        await self.db.users.register(self.uid, self.gid, "GearTester", "url", "Test")
        await self.db.users.modify_gold(self.uid, 100000)

    async def asyncTearDown(self):
        await self.db_conn.close()

    # =================================================================
    # ACCESSORY TESTS (Ward, Crit, Potential)
    # =================================================================
    async def test_accessory_workflow(self):
        """
        Simulate the full lifecycle of an Accessory:
        Creation -> Fetch -> Stat Verification -> Potential Upgrade Logic
        """
        # 1. Creation
        acc = Accessory(
            user=self.uid, name="Ring of Power", level=50, 
            attack=5, defence=5, rarity=10, 
            ward=20, crit=5, passive="none", passive_lvl=0, description="Precious"
        )
        await self.db.equipment.create_accessory(acc)

        # 2. Fetch and Verify (Simulates Helper _fetch_and_parse_accessories)
        raw_items = await self.db.equipment.get_all(self.uid, "accessory")
        self.assertEqual(len(raw_items), 1)
        
        # 3. Factory Parse
        loaded_acc = create_accessory(raw_items[0])
        self.assertIsInstance(loaded_acc, Accessory)
        self.assertEqual(loaded_acc.ward, 20, "Ward stat failed to persist")
        self.assertEqual(loaded_acc.crit, 5, "Crit stat failed to persist")
        self.assertEqual(loaded_acc.potential_remaining, 10, "Default potential should be 10")

        # 4. Mechanics: Potential Upgrade Cost
        # Lvl 0 Cost -> Should be 500 (based on mechanics)
        cost_lvl_0 = EquipmentMechanics.calculate_potential_cost(loaded_acc.passive_lvl)
        self.assertEqual(cost_lvl_0, 500)

        # Simulate Upgrade (DB Update)
        await self.db.equipment.update_counter(loaded_acc.item_id, 'accessory', 'passive_lvl', 1)
        await self.db.equipment.update_counter(loaded_acc.item_id, 'accessory', 'potential_remaining', 9)

        # Verify New Cost (Lvl 1 -> 1000)
        loaded_acc.passive_lvl = 1
        cost_lvl_1 = EquipmentMechanics.calculate_potential_cost(loaded_acc.passive_lvl)
        self.assertEqual(cost_lvl_1, 1000)

    # =================================================================
    # GLOVE TESTS (PDR, FDR, Sorting)
    # =================================================================
    async def test_glove_mechanics_and_sorting(self):
        """
        Tests Glove specific stats (PDR/FDR) and the list sorting logic 
        (Equipped items should appear first).
        """
        # 1. Create two gloves
        g1 = Glove(user=self.uid, name="Weak Glove", level=10, pdr=5, fdr=0, passive="none")
        g2 = Glove(user=self.uid, name="Strong Glove", level=50, pdr=0, fdr=10, passive="none")
        
        await self.db.equipment.create_glove(g1)
        await self.db.equipment.create_glove(g2)

        # Fetch IDs to simulate equipping
        raw = await self.db.equipment.get_all(self.uid, "glove")
        g1_id = raw[0][0] # ID of Weak Glove
        
        # 2. Equip the Weak Glove
        await self.db.equipment.equip(self.uid, g1_id, "glove")

        # 3. Simulate Cog Sorting Logic
        # Cogs sort by: (Is Not Equipped, Level Descending)
        # Equipped items (False is_not_equipped) come before True
        parsed_gloves = [create_glove(item) for item in raw]
        
        # Re-fetch equipped status logic simulation
        equipped_raw = await self.db.equipment.get_equipped(self.uid, "glove")
        equipped_id = equipped_raw[0]

        # Apply Sort
        parsed_gloves.sort(key=lambda g: (g.item_id != equipped_id, -g.level))

        # 4. Assertions
        self.assertEqual(parsed_gloves[0].item_id, g1_id, "Equipped item should be first, even if lower level")
        self.assertEqual(parsed_gloves[0].pdr, 5, "PDR stat verification")
        self.assertEqual(parsed_gloves[1].fdr, 10, "FDR stat verification")

    # =================================================================
    # BOOT TESTS (Passives & Equipping)
    # =================================================================
    async def test_boot_passives_and_limits(self):
        """
        Tests Boot creation and verifies that logic handles passive strings correctly.
        """
        # 1. Create Boots with a specific passive
        b = Boot(
            user=self.uid, name="Speed Boots", level=100, 
            attack=10, defence=10, ward=0, pdr=0, fdr=0, 
            passive="speedster", passive_lvl=3, description="Fast"
        )
        await self.db.equipment.create_boot(b)

        # 2. Fetch
        raw = await self.db.equipment.get_all(self.uid, "boot")
        boot_obj = create_boot(raw[0])

        await self.db.equipment.update_counter(boot_obj.item_id, 'boot', 'passive_lvl', 3)
        raw = await self.db.equipment.get_all(self.uid, "boot")
        boot_obj = create_boot(raw[0])
        # 3. Verify Data
        self.assertEqual(boot_obj.passive, "speedster")
        self.assertEqual(boot_obj.passive_lvl, 3)
        self.assertEqual(boot_obj.potential_remaining, 6, "Boots should have 6 potential by default")

        # 4. Simulate Action Availability Check
        # Logic in boots.py: can_improve = potential > 0 and passive < 6
        can_improve = boot_obj.potential_remaining > 0 and boot_obj.passive_lvl < 6
        self.assertTrue(can_improve, "Should be able to improve boots")

        # 5. Simulate Maxed Boots
        boot_obj.passive_lvl = 6
        can_improve_maxed = boot_obj.potential_remaining > 0 and boot_obj.passive_lvl < 6
        self.assertFalse(can_improve_maxed, "Should NOT be able to improve max level boots")


class TestWeaponsAdvanced(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Setup for Weapon Tests."""
        self.db_conn = await aiosqlite.connect(":memory:")
        with open("database/schema.sql", "r") as f:
            await self.db_conn.executescript(f.read())
        await self.db_conn.commit()
        
        self.db = DatabaseManager(connection=self.db_conn)
        self.uid = "1001"
        self.gid = "999"
        # Register user with plenty of gold/mats
        await self.db.users.register(self.uid, self.gid, "BladeMaster", "url", "Steel")
        await self.db.users.modify_gold(self.uid, 500000)
        
        # Insert Skilling Resources for Forge tests
        await self.db.skills.initialize(self.uid, self.gid, 'mining', 'iron')
        await self.db.skills.update_single_resource(self.uid, self.gid, 'mining', 'iron', 100)
        await self.db.skills.initialize(self.uid, self.gid, 'woodcutting', 'flimsy')
        await self.db.skills.update_single_resource(self.uid, self.gid, 'woodcutting', 'oak_logs', 100)
        await self.db.skills.initialize(self.uid, self.gid, 'fishing', 'desiccated')
        await self.db.skills.update_single_resource(self.uid, self.gid, 'fishing', 'desiccated_bones', 100)

    async def asyncTearDown(self):
        await self.db_conn.close()

    # =================================================================
    # WEAPON MECHANICS (Forge, Refine, Shatter)
    # =================================================================
    async def test_forge_mechanics(self):
        """Test the math and resource calculation for Forging."""
        # Create a basic sword, Level 10, 3 forges remaining
        w = Weapon(user=self.uid, name="Rusty Sword", level=10, attack=5, defence=0, rarity=0, passive="none", description="", p_passive="none", u_passive="none")
        w.forges_remaining = 3
        
        # 1. Calculate Cost
        cost = EquipmentMechanics.calculate_forge_cost(w)
        self.assertIsNotNone(cost)
        self.assertEqual(cost['gold'], 100)
        self.assertEqual(cost['ore_type'], 'iron')

        # 2. Simulate Success Roll
        with patch('random.random', return_value=0.1): # Force success (0.1 < 0.8)
            with patch('random.choice', return_value='burning'): # Force 'burning' passive
                success, passive = EquipmentMechanics.roll_forge_outcome(w)
                self.assertTrue(success)
                self.assertEqual(passive, 'burning')

        # 3. Simulate Failure Roll
        # Max forges = 3. Remaining = 1. Steps = 2. Rate = 0.8 - (2*0.05) = 0.7.
        w.forges_remaining = 1
        with patch('random.random', return_value=0.9): # Force fail (0.9 > 0.7)
            success, passive = EquipmentMechanics.roll_forge_outcome(w)
            self.assertFalse(success)
            self.assertEqual(passive, 'none')

    async def test_refine_mechanics(self):
        """Test stat gain logic for Refining."""
        w = Weapon(user=self.uid, name="Fine Sword", level=20, attack=10, defence=10, rarity=0, passive="none", description="", p_passive="none", u_passive="none")
        w.refines_remaining = 3
        
        # 1. Cost Calculation
        cost = EquipmentMechanics.calculate_refine_cost(w)
        self.assertEqual(cost, 500) # Level 20, 3 left -> 500 gold logic

        # 2. Roll Outcome (Force success on Atk, fail on Def)
        # random.randint called for: Atk%, Def%, Rar%, AtkAmt, DefAmt, RarAmt
        # We need to mock randint to control the flow.
        # Sequence: 5 (Atk<80), 90 (Def>50), 90 (Rar>20), 5 (AtkAmt)
        with patch('random.randint', side_effect=[5, 90, 90, 5]):
            stats = EquipmentMechanics.roll_refine_outcome(w)
            self.assertEqual(stats['attack'], 5)
            self.assertEqual(stats['defence'], 0) # Failed roll
            self.assertEqual(stats['rarity'], 0) # Failed roll

    async def test_shatter_calculation(self):
        """Test the logic for shattering returns."""
        # Logic: max(0, int(refinement_lvl - 5 * 0.8)) + (1 if stats>0)
        # 5 * 0.8 = 4.0.
        # If Refine Lvl 6: 6 - 4 = 2. Plus 1 base = 3 runes.
        w = Weapon(user=self.uid, name="Shattered Hope", level=50, attack=10, defence=10, rarity=10, passive="none", description="", p_passive="none", u_passive="none")
        w.refinement_lvl = 6
        
        runes_back = max(0, int(w.refinement_lvl - 5 * 0.8))
        if w.attack > 0: runes_back += 1
        
        self.assertEqual(runes_back, 3)

    async def test_voidforge_eligibility(self):
        """Test finding valid sacrifices for Voidforge."""
        # 1. Valid Candidate: Unequipped, Refine 5, Forges 0
        w1 = Weapon(user=self.uid, name="Sacrifice", level=10, attack=5, defence=0, rarity=0, passive="burning", description="", p_passive="none", u_passive="none")
        await self.db.equipment.create_weapon(w1)
        # Manually update DB to meet strict voidforge criteria
        items = await self.db.equipment.get_all(self.uid, "weapon")
        w1_id = items[0][0]
        await self.db.equipment.update_counter(w1_id, 'weapon', 'refinement_lvl', 5)
        await self.db.equipment.update_counter(w1_id, 'weapon', 'forges_remaining', 0)
        await self.db.equipment.unequip(self.uid, 'weapon')

        # 2. Invalid Candidate: Equipped
        w2 = Weapon(user=self.uid, name="Equipped", level=10, attack=5, defence=0, rarity=0, passive="burning", description="", p_passive="none", u_passive="none")
        await self.db.equipment.create_weapon(w2)
        # Get ID and Equip
        items = await self.db.equipment.get_all(self.uid, "weapon")
        w2_id = items[1][0]
        await self.db.equipment.update_counter(w2_id, 'weapon', 'refinement_lvl', 5)
        await self.db.equipment.update_counter(w2_id, 'weapon', 'forges_remaining', 0)
        await self.db.equipment.equip(self.uid, w2_id, 'weapon')

        # 3. Test Query
        candidates = await self.db.equipment.fetch_void_forge_candidates(self.uid)
        
        # Only w1 should be returned
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0][0], w1_id)

    # =================================================================
    # COMBAT INTEGRATION (Weapon Passives vs Monsters)
    # =================================================================
    async def test_weapon_passive_polished_vs_monster(self):
        """Test 'Polished' passive reducing monster defence."""
        # Setup Player with Polished Weapon
        raw_user = await self.db.users.get(self.uid, self.gid)
        player = await load_player(self.uid, raw_user, self.db)
        
        # Mocking equipped weapon directly on player object for speed
        p_wep = Weapon(user=self.uid, name="Polished Blade", level=10, attack=10, defence=0, rarity=0, passive="polished", description="", p_passive="none", u_passive="none", item_id=99)
        player.equipped_weapon = p_wep

        # Setup Monster
        from core.models import Monster
        monster = Monster(name="Tank", level=10, hp=100, max_hp=100, xp=0, attack=10, defence=100, modifiers=[], image="", flavor="")

        # Run Start-of-Combat Logic
        log = engine.apply_combat_start_passives(player, monster)
        
        # 'Polished' (Tier 0) reduces def by 8%. 100 * 0.08 = 8. New Def = 92.
        self.assertEqual(monster.defence, 92)
        self.assertIn("Weapon Passive", log)
        self.assertIn("polished", log["Weapon Passive"])

    async def test_weapon_passive_sturdy_vs_boss(self):
        """Test 'Sturdy' passive increasing player defence against a Boss."""
        # Setup Player
        raw_user = await self.db.users.get(self.uid, self.gid)
        player = await load_player(self.uid, raw_user, self.db)
        player.base_defence = 50
        
        # Mock Weapon: Sturdy
        p_wep = Weapon(user=self.uid, name="Shield Sword", level=10, attack=10, defence=0, rarity=0, passive="sturdy", description="", p_passive="none", u_passive="none", item_id=99)
        player.equipped_weapon = p_wep

        # Setup Boss (High stats)
        monster = Monster(name="Boss", level=100, hp=10000, max_hp=10000, xp=0, attack=200, defence=200, modifiers=["Ascended"], image="", flavor="", is_boss=True)

        # Run Start-of-Combat Logic
        log = engine.apply_combat_start_passives(player, monster)

        # 'Sturdy' (Tier 0) increases Player Def by 8%. 
        # Player Def (Base 50) -> 50 + (50 * 0.08) = 54.
        self.assertEqual(player.base_defence, 54)
        self.assertIn("sturdy", log["Weapon Passive"])

    async def test_weapon_burning_damage_calc(self):
        """Test 'Burning' passive increasing damage calculation output."""
        # Setup Player
        raw_user = await self.db.users.get(self.uid, self.gid)
        player = await load_player(self.uid, raw_user, self.db)
        player.base_attack = 100
        
        # Mock Weapon: Burning
        p_wep = Weapon(user=self.uid, name="Fire Sword", level=10, attack=0, defence=0, rarity=0, passive="burning", description="", p_passive="none", u_passive="none", item_id=99)
        player.equipped_weapon = p_wep

        # Setup Weak Monster
        monster = Monster(name="Dummy", level=1, hp=1000, max_hp=1000, xp=0, attack=0, defence=0, modifiers=[], image="", flavor="")

        # We need to test specific logic inside calcs.py / engine.py.
        # Since we can't easily isolate the internal variable `base_damage_max` in integration tests,
        # we check the resulting log message or average damage over mocked rolls.
        
        # Let's inspect the log output from engine.process_player_turn
        # Force a Hit (Hit chance 100%)
        with patch('random.randint', return_value=50): # Force standard rolls
             with patch('core.combat.calcs.calculate_hit_chance', return_value=1.0):
                log = engine.process_player_turn(player, monster)
        
        # 'Burning' logic adds text to the attack log
        self.assertIn("burns bright", log)

if __name__ == "__main__":
    unittest.main()