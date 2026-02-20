from core.models import Player, Weapon, Accessory, Armor, Glove, Boot, Helmet, Companion

def create_weapon(data: tuple) -> Weapon:
    """
    Maps a database tuple from table `items` to a Weapon object.
    Schema: item_id(0), user_id(1), item_name(2), item_level(3), attack(4), defence(5), 
            rarity(6), passive(7), is_equipped(8), forges_remaining(9), 
            refines_remaining(10), refinement_lvl(11), pinnacle_passive(12), utmost_passive(13)
    """
    if not data: 
        return None
    
    return Weapon(
        item_id=data[0],
        user=data[1],
        name=data[2],
        level=data[3],
        attack=data[4],
        defence=data[5],
        rarity=data[6],
        passive=data[7],
        is_equipped=bool(data[8]),
        forges_remaining=data[9],
        refines_remaining=data[10],
        refinement_lvl=data[11],
        p_passive=data[12] if len(data) > 12 else "none",
        u_passive=data[13] if len(data) > 13 else "none",
        description="" # Description is typically generated dynamically in views
    )

def create_accessory(data: tuple) -> Accessory:
    """
    Maps a database tuple from table `accessories` to an Accessory object.
    Schema: item_id(0), user_id(1), item_name(2), item_level(3), attack(4), defence(5), 
            rarity(6), ward(7), crit(8), passive(9), is_equipped(10), 
            potential_remaining(11), passive_lvl(12)
    """
    if not data: 
        return None

    return Accessory(
        item_id=data[0],
        user=data[1],
        name=data[2],
        level=data[3],
        attack=data[4],
        defence=data[5],
        rarity=data[6],
        ward=data[7],
        crit=data[8],
        passive=data[9],
        is_equipped=bool(data[10]),
        potential_remaining=data[11],
        passive_lvl=data[12],
        description=""
    )

def create_armor(data: tuple) -> Armor:
    """
    Maps a database tuple from table `armor` to an Armor object.
    Schema: item_id(0), user_id(1), item_name(2), item_level(3), block(4), evasion(5), 
            ward(6), armor_passive(7), is_equipped(8), temper_remaining(9), 
            imbue_remaining(10), pdr(11), fdr(12)
    """
    if not data: 
        return None

    return Armor(
        item_id=data[0],
        user=data[1],
        name=data[2],
        level=data[3],
        block=data[4],
        evasion=data[5],
        ward=data[6],
        passive=data[7],
        is_equipped=bool(data[8]),
        temper_remaining=data[9],
        imbue_remaining=data[10],
        pdr=data[11],
        fdr=data[12],
        description=""
    )

def create_glove(data: tuple) -> Glove:
    """
    Maps a database tuple from table `gloves` to a Glove object.
    Schema: item_id(0), user_id(1), item_name(2), item_level(3), attack(4), defence(5), 
            ward(6), pdr(7), fdr(8), passive(9), is_equipped(10), 
            potential_remaining(11), passive_lvl(12)
    """
    if not data: 
        return None

    return Glove(
        item_id=data[0],
        user=data[1],
        name=data[2],
        level=data[3],
        attack=data[4],
        defence=data[5],
        ward=data[6],
        pdr=data[7],
        fdr=data[8],
        passive=data[9],
        is_equipped=bool(data[10]),
        potential_remaining=data[11],
        passive_lvl=data[12],
        description=""
    )

def create_boot(data: tuple) -> Boot:
    """
    Maps a database tuple from table `boots` to a Boot object.
    Schema: item_id(0), user_id(1), item_name(2), item_level(3), attack(4), defence(5), 
            ward(6), pdr(7), fdr(8), passive(9), is_equipped(10), 
            potential_remaining(11), passive_lvl(12)
    """
    if not data: 
        return None

    return Boot(
        item_id=data[0],
        user=data[1],
        name=data[2],
        level=data[3],
        attack=data[4],
        defence=data[5],
        ward=data[6],
        pdr=data[7],
        fdr=data[8],
        passive=data[9],
        is_equipped=bool(data[10]),
        potential_remaining=data[11],
        passive_lvl=data[12],
        description=""
    )

def create_helmet(data: tuple) -> Helmet:
    """
    Schema: item_id(0), user_id(1), item_name(2), item_level(3), defence(4), 
            ward(5), passive(6), passive_lvl(7), is_equipped(8), potential_remaining(9)
    """
    if not data: return None
    return Helmet(
        item_id=data[0], user=data[1], name=data[2], level=data[3],
        defence=data[4], ward=data[5], 
        pdr=data[6], fdr=data[7],
        passive=data[8], passive_lvl=data[9],
        is_equipped=bool(data[10]), potential_remaining=data[11], description=""
    )


def create_companion(data: tuple) -> Companion:
    """
    Maps a database tuple from table `companions` to a Companion object.
    Schema: id(0), user_id(1), name(2), species(3), image_url(4), 
            level(5), exp(6), passive_type(7), passive_tier(8), is_active(9), created_at(10)
    """
    if not data: return None
    return Companion(
        id=data[0],
        user_id=data[1],
        name=data[2],
        species=data[3],
        image_url=data[4],
        level=data[5],
        exp=data[6],
        passive_type=data[7],
        passive_tier=data[8],
        is_active=bool(data[9])
    )

async def load_player(user_id: str, user_data: tuple, database) -> Player:
    """
    Creates a Player object from the user tuple and asynchronously fetches 
    and attaches all equipped gear using the database connection.
    
    Args:
        user_id (str): The Discord User ID
        user_data (tuple): The raw tuple from the 'users' table
        database (DatabaseManager): The active database manager instance
    """
    # 1. Initialize Player with base stats from 'users' table
    # Schema: 3:name, 4:level, 5:exp, 9:atk, 10:def, 11:cur_hp, 12:max_hp, 15:asc, 16:pots
    player = Player(
        id=user_id,
        name=user_data[3],
        level=user_data[4],
        ascension=user_data[15],
        exp=user_data[5],
        current_hp=user_data[11],
        max_hp=user_data[12],
        base_attack=user_data[9],
        base_defence=user_data[10],
        potions=user_data[16],
        # Defaults
        base_rarity=0,
        base_crit_chance_target=95,
        combat_ward=0
    )

    server_id = user_data[2] # Assuming index 2 is server_id in users table
    
    # Settlement buffs
    b_tier, b_workers = await database.settlement.get_building_details(user_id, server_id, "barracks")
    a_tier, a_workers = await database.settlement.get_building_details(user_id, server_id, "apothecary")
    
    player.apothecary_workers = a_workers

    if b_workers > 0:
        atk_bonus = int(player.base_attack * (b_workers * 0.0001))
        def_bonus = int(player.base_defence * (b_workers * 0.0001))
        
        player.base_attack += atk_bonus
        player.base_defence += def_bonus

    
    # 2. Fetch and Attach Gear
    # We await the database calls here so the resulting Player object is fully populated
    
    wep_data = await database.equipment.get_equipped(user_id, "weapon")
    if wep_data:
        player.equipped_weapon = create_weapon(wep_data)

    acc_data = await database.equipment.get_equipped(user_id, "accessory")
    if acc_data:
        player.equipped_accessory = create_accessory(acc_data)

    armor_data = await database.equipment.get_equipped(user_id, "armor")
    if armor_data:
        player.equipped_armor = create_armor(armor_data)

    glove_data = await database.equipment.get_equipped(user_id, "glove")
    if glove_data:
        player.equipped_glove = create_glove(glove_data)

    boot_data = await database.equipment.get_equipped(user_id, "boot")
    if boot_data:
        player.equipped_boot = create_boot(boot_data)

    helmet_data = await database.equipment.get_equipped(user_id, "helmet")
    if helmet_data:
        player.equipped_helmet = create_helmet(helmet_data)

    comp_rows = await database.companions.get_active(user_id)
    if comp_rows:
        player.active_companions = [create_companion(row) for row in comp_rows]

    # 3. Calculate Combat Initialization Stats (Optional but helpful)
    # This pre-calculates the ward pool based on equipped gear percentages
    player.combat_ward = player.get_combat_ward_value()

    # 4. Handle Passive Stat Modifiers that affect Base Stats immediately (e.g. Hearty Boots)
    if player.equipped_boot:
        if player.equipped_boot.passive == "hearty" and player.equipped_boot.passive_lvl > 0:
            hp_bonus_percentage = player.equipped_boot.passive_lvl * 0.05 # 5% per level
            bonus_hp = int(player.max_hp * hp_bonus_percentage)
            player.max_hp += bonus_hp
            player.current_hp += bonus_hp
        
        if player.equipped_boot.passive == "speedster" and player.equipped_boot.passive_lvl > 0:
            player.combat_cooldown_reduction_seconds = player.equipped_boot.passive_lvl * 60
    return player