from core.models import (
    Accessory,
    Armor,
    Boot,
    Companion,
    Glove,
    Helmet,
    MonsterPart,
    Player,
    Weapon,
)


def create_weapon(data: tuple) -> Weapon:
    """Map a DB row tuple from the `items` table to a Weapon model.
    See database/schema.sql (column order) and core/items/models.py (dataclass).
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
        infernal_passive=data[14] if len(data) > 14 else "none",
        forge_tier=data[15] if len(data) > 15 else 0,
        hit_chance=data[16] if len(data) > 16 else 0.60,
        crit_chance=data[17] if len(data) > 17 else 0.00,
        crit_multi=data[18] if len(data) > 18 else 2.00,
        base_rarity=data[19] if len(data) > 19 else 3,
        description="",  # Description is typically generated dynamically in views
    )


def create_accessory(data: tuple) -> Accessory:
    """Map a DB row tuple from the `accessories` table to an Accessory model.
    See database/schema.sql (column order) and core/items/models.py (dataclass).
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
        void_passive=data[13] if len(data) > 13 else "none",
        description="",
    )


def create_armor(data: tuple) -> Armor:
    """Map a DB row tuple from the `armor` table to an Armor model.
    See database/schema.sql (column order) and core/items/models.py (dataclass).
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
        celestial_passive=data[13] if len(data) > 13 else "none",
        main_stat_type=data[14] if len(data) > 14 else "def",
        main_stat=data[15] if len(data) > 15 else 0,
        reinforces_remaining=data[16] if len(data) > 16 else 0,
        reinforcement_lvl=data[17] if len(data) > 17 else 0,
        description="",
    )


def create_glove(data: tuple) -> Glove:
    """Map a DB row tuple from the `gloves` table to a Glove model.
    See database/schema.sql (column order) and core/items/models.py (dataclass).
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
        essence_1=data[13] if len(data) > 13 and data[13] is not None else "none",
        essence_1_val=data[14] if len(data) > 14 and data[14] is not None else 0.0,
        essence_2=data[15] if len(data) > 15 and data[15] is not None else "none",
        essence_2_val=data[16] if len(data) > 16 and data[16] is not None else 0.0,
        essence_3=data[17] if len(data) > 17 and data[17] is not None else "none",
        essence_3_val=data[18] if len(data) > 18 and data[18] is not None else 0.0,
        corrupted_essence=(
            data[19] if len(data) > 19 and data[19] is not None else "none"
        ),
        reinforces_remaining=data[20] if len(data) > 20 else 0,
        reinforcement_lvl=data[21] if len(data) > 21 else 0,
        description="",
    )


def create_boot(data: tuple) -> Boot:
    """Map a DB row tuple from the `boots` table to a Boot model.
    See database/schema.sql (column order) and core/items/models.py (dataclass).
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
        essence_1=data[13] if len(data) > 13 and data[13] is not None else "none",
        essence_1_val=data[14] if len(data) > 14 and data[14] is not None else 0.0,
        essence_2=data[15] if len(data) > 15 and data[15] is not None else "none",
        essence_2_val=data[16] if len(data) > 16 and data[16] is not None else 0.0,
        essence_3=data[17] if len(data) > 17 and data[17] is not None else "none",
        essence_3_val=data[18] if len(data) > 18 and data[18] is not None else 0.0,
        corrupted_essence=(
            data[19] if len(data) > 19 and data[19] is not None else "none"
        ),
        reinforces_remaining=data[20] if len(data) > 20 else 0,
        reinforcement_lvl=data[21] if len(data) > 21 else 0,
        description="",
    )


def create_helmet(data: tuple) -> Helmet:
    """Map a DB row tuple from the `helmets` table to a Helmet model.
    See database/schema.sql (column order) and core/items/models.py (dataclass).
    """
    if not data:
        return None
    return Helmet(
        item_id=data[0],
        user=data[1],
        name=data[2],
        level=data[3],
        defence=data[4],
        ward=data[5],
        pdr=data[6],
        fdr=data[7],
        passive=data[8],
        passive_lvl=data[9],
        is_equipped=bool(data[10]),
        potential_remaining=data[11],
        essence_1=data[12] if len(data) > 12 and data[12] is not None else "none",
        essence_1_val=data[13] if len(data) > 13 and data[13] is not None else 0.0,
        essence_2=data[14] if len(data) > 14 and data[14] is not None else "none",
        essence_2_val=data[15] if len(data) > 15 and data[15] is not None else 0.0,
        essence_3=data[16] if len(data) > 16 and data[16] is not None else "none",
        essence_3_val=data[17] if len(data) > 17 and data[17] is not None else 0.0,
        corrupted_essence=(
            data[18] if len(data) > 18 and data[18] is not None else "none"
        ),
        reinforces_remaining=data[19] if len(data) > 19 else 0,
        reinforcement_lvl=data[20] if len(data) > 20 else 0,
        description="",
    )


def create_companion(data: tuple) -> Companion:
    """
    Maps a database tuple from table `companions` to a Companion object.
    Schema: id(0), user_id(1), name(2), species(3), image_url(4),
            level(5), exp(6), passive_type(7), passive_tier(8), is_active(9), created_at(10)
    """
    if not data:
        return None
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
        is_active=bool(data[9]),
        balanced_passive=(
            data[11] if len(data) > 11 and data[11] is not None else "none"
        ),
        balanced_passive_tier=(
            data[12] if len(data) > 12 and data[12] is not None else 0
        ),
    )


def create_monster_part(row) -> MonsterPart:
    """Maps a monster_parts DB row to a MonsterPart object."""
    return MonsterPart(
        id=row[0],
        user_id=row[1],
        slot_type=row[2],
        monster_name=row[3],
        ilvl=row[4],
        hp_value=row[5],
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
    )

    server_id = user_data[2]  # Assuming index 2 is server_id in users table

    # Settlement buffs
    b_tier, b_workers = await database.settlement.get_building_details(
        user_id, server_id, "barracks"
    )
    a_tier, a_workers = await database.settlement.get_building_details(
        user_id, server_id, "apothecary"
    )

    player.apothecary_workers = a_workers
    player.barracks_workers = b_workers

    # Settlement adjacency bonuses (Apothecary Annex + Shrine Garden / Sacred Ground)
    try:
        combat_bonuses = await database.settlement.get_combat_bonuses(user_id, server_id)
        player.apothecary_boost_pct = combat_bonuses["apothecary_boost_pct"]
        player.shrine_effectiveness = combat_bonuses["shrine_effectiveness"]
    except Exception:
        pass  # defaults to 0.0 / {} from Player dataclass

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

    # --- Fetch Slayer Data ---
    try:
        # Load Emblem
        player.slayer_emblem = await database.slayer.get_emblem(user_id, server_id)
        # Load Active Task to check for Slayer-specific buffs
        profile = await database.slayer.get_profile(user_id, server_id)
        player.active_task_species = profile.get("active_task_species")
    except Exception:
        # Failsafe if player hasn't opened /slayer yet
        player.slayer_emblem = {}
        player.active_task_species = None

    # --- Fetch Codex Tomes ---
    try:
        player.codex_tomes = await database.codex.get_tomes(user_id)
    except Exception:
        player.codex_tomes = []

    # --- Fetch Ascension Pinnacle Unlocks ---
    try:
        player.ascension_unlocks = await database.ascension.get_unlocked_floors(user_id)
    except Exception:
        player.ascension_unlocks = set()

    # --- Fetch Alchemy Potion Passives ---
    try:
        player.potion_passives = await database.alchemy.get_potion_passives(user_id)
    except Exception:
        player.potion_passives = []

    # --- Fetch Equipped Monster Body Parts ---
    try:
        player.equipped_parts = await database.monster_parts.get_equipped_parts(user_id)
    except Exception:
        player.equipped_parts = {}

    # --- Fetch Paradise Jewel Data ---
    try:
        player.jewel_of_paradise = await database.paradise.get(user_id)
    except Exception:
        pass  # keeps default empty structure

    # --- Fetch Active Combat Partner ---
    try:
        partner_row = await database.partners.get_active_combat(user_id)
        if partner_row:
            from core.models import Partner
            from core.partners.data import PARTNER_DATA

            static = PARTNER_DATA.get(partner_row[2])
            if static:
                player.active_partner = Partner.from_row(partner_row, static)
    except Exception:
        player.active_partner = None

    # --- Fetch Hematurgy Passives ---
    try:
        raw = await database.hematurgy.get_all_passives(user_id)
        player.hematurgy_passives = {v["passive_id"]: v["tier"] for v in raw.values()}
    except Exception:
        player.hematurgy_passives = {}

    # --- Fetch Soul Stone ---
    try:
        ss_row = await database.apex.get_or_create_soul_stone(user_id, server_id)
        from core.apex.models import soul_stone_from_db
        player.soul_stone = soul_stone_from_db(ss_row)
    except Exception:
        player.soul_stone = None

    # --- Fetch Stat Investments (passive_point allocations) ---
    try:
        stat_inv = await database.users.get_stat_investments(user_id)
        player.stat_invest_atk = stat_inv["atk"]
        player.stat_invest_def = stat_inv["def"]
        player.stat_invest_hp = stat_inv["hp"]
        player.stat_invest_gold = stat_inv["gold"]
    except Exception:
        pass  # defaults to 0 from Player dataclass

    # 3. Pre-compute flat stat cache (base + gear + essences + barracks).
    # Must be done after all gear is attached and before any combat begins.
    player.compute_flat_stats()

    # 4. Calculate Combat Initialization Stats (Optional but helpful)
    # This pre-calculates the ward pool based on equipped gear percentages
    player.combat_ward = player.get_combat_ward_value()

    # 4. Boot passives that affect session-start state
    if player.equipped_boot:
        # Speedster: pre-compute combat cooldown reduction for the cog to read
        if (
            player.equipped_boot.passive == "speedster"
            and player.equipped_boot.passive_lvl > 0
        ):
            player.combat_cooldown_reduction_seconds = (
                player.equipped_boot.passive_lvl * 60
            )

    # Hearty boot passive is now a percentage in total_max_hp (additive with Vitality).
    # If the player was at or above their base max HP (e.g. full HP from a previous session),
    # restore current_hp to the new full total_max_hp so the Hearty bonus takes effect immediately.
    if player.current_hp >= player.max_hp:
        player.current_hp = player.total_max_hp

    if player.get_celestial_armor_passive() == "celestial_wind_dancer":
        player.equipped_helmet = None  # Completely nullify the helmet stats/passives

    return player
