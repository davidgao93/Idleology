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


def _gcol(row, col, default=None):
    """Get a named column from a sqlite3.Row, returning default if not present."""
    try:
        return row[col]
    except IndexError:
        return default


def create_weapon(data) -> Weapon:
    """Map a DB row from the `items` table to a Weapon model."""
    if not data:
        return None

    return Weapon(
        item_id=data["item_id"],
        user=data["user_id"],
        name=data["item_name"],
        level=data["item_level"],
        attack=data["attack"],
        defence=data["defence"],
        rarity=data["rarity"],
        passive=data["passive"],
        is_equipped=bool(data["is_equipped"]),
        forges_remaining=data["forges_remaining"],
        refines_remaining=data["refines_remaining"],
        refinement_lvl=data["refinement_lvl"],
        p_passive=_gcol(data, "pinnacle_passive", "none"),
        u_passive=_gcol(data, "utmost_passive", "none"),
        infernal_passive=_gcol(data, "infernal_passive", "none"),
        forge_tier=_gcol(data, "forge_tier", 0),
        hit_chance=_gcol(data, "hit_chance", 0.60),
        crit_chance=_gcol(data, "crit_chance", 0.00),
        crit_multi=_gcol(data, "crit_multi", 2.00),
        base_rarity=_gcol(data, "base_rarity", 3),
        description="",  # Description is typically generated dynamically in views
    )


def create_accessory(data) -> Accessory:
    """Map a DB row from the `accessories` table to an Accessory model."""
    if not data:
        return None

    return Accessory(
        item_id=data["item_id"],
        user=data["user_id"],
        name=data["item_name"],
        level=data["item_level"],
        attack=data["attack"],
        defence=data["defence"],
        rarity=data["rarity"],
        ward=data["ward"],
        crit=data["crit"],
        passive=data["passive"],
        is_equipped=bool(data["is_equipped"]),
        potential_remaining=data["potential_remaining"],
        passive_lvl=data["passive_lvl"],
        void_passive=_gcol(data, "void_passive", "none"),
        description="",
    )


def create_armor(data) -> Armor:
    """Map a DB row from the `armor` table to an Armor model."""
    if not data:
        return None

    return Armor(
        item_id=data["item_id"],
        user=data["user_id"],
        name=data["item_name"],
        level=data["item_level"],
        block=data["block"],
        evasion=data["evasion"],
        ward=data["ward"],
        passive=data["armor_passive"],
        is_equipped=bool(data["is_equipped"]),
        temper_remaining=data["temper_remaining"],
        imbue_remaining=data["imbue_remaining"],
        pdr=data["pdr"],
        fdr=data["fdr"],
        celestial_passive=_gcol(data, "celestial_armor_passive", "none"),
        main_stat_type=_gcol(data, "main_stat_type", "def"),
        main_stat=_gcol(data, "main_stat", 0),
        reinforces_remaining=_gcol(data, "reinforces_remaining", 0),
        reinforcement_lvl=_gcol(data, "reinforcement_lvl", 0),
        description="",
    )


def create_glove(data) -> Glove:
    """Map a DB row from the `gloves` table to a Glove model."""
    if not data:
        return None

    return Glove(
        item_id=data["item_id"],
        user=data["user_id"],
        name=data["item_name"],
        level=data["item_level"],
        attack=data["attack"],
        defence=data["defence"],
        ward=data["ward"],
        pdr=data["pdr"],
        fdr=data["fdr"],
        passive=data["passive"],
        is_equipped=bool(data["is_equipped"]),
        potential_remaining=data["potential_remaining"],
        passive_lvl=data["passive_lvl"],
        essence_1=_gcol(data, "essence_1") or "none",
        essence_1_val=_gcol(data, "essence_1_val") or 0.0,
        essence_2=_gcol(data, "essence_2") or "none",
        essence_2_val=_gcol(data, "essence_2_val") or 0.0,
        essence_3=_gcol(data, "essence_3") or "none",
        essence_3_val=_gcol(data, "essence_3_val") or 0.0,
        corrupted_essence=_gcol(data, "corrupted_essence") or "none",
        reinforces_remaining=_gcol(data, "reinforces_remaining", 0),
        reinforcement_lvl=_gcol(data, "reinforcement_lvl", 0),
        description="",
    )


def create_boot(data) -> Boot:
    """Map a DB row from the `boots` table to a Boot model."""
    if not data:
        return None

    return Boot(
        item_id=data["item_id"],
        user=data["user_id"],
        name=data["item_name"],
        level=data["item_level"],
        attack=data["attack"],
        defence=data["defence"],
        ward=data["ward"],
        pdr=data["pdr"],
        fdr=data["fdr"],
        passive=data["passive"],
        is_equipped=bool(data["is_equipped"]),
        potential_remaining=data["potential_remaining"],
        passive_lvl=data["passive_lvl"],
        essence_1=_gcol(data, "essence_1") or "none",
        essence_1_val=_gcol(data, "essence_1_val") or 0.0,
        essence_2=_gcol(data, "essence_2") or "none",
        essence_2_val=_gcol(data, "essence_2_val") or 0.0,
        essence_3=_gcol(data, "essence_3") or "none",
        essence_3_val=_gcol(data, "essence_3_val") or 0.0,
        corrupted_essence=_gcol(data, "corrupted_essence") or "none",
        reinforces_remaining=_gcol(data, "reinforces_remaining", 0),
        reinforcement_lvl=_gcol(data, "reinforcement_lvl", 0),
        description="",
    )


def create_helmet(data) -> Helmet:
    """Map a DB row from the `helmets` table to a Helmet model."""
    if not data:
        return None
    return Helmet(
        item_id=data["item_id"],
        user=data["user_id"],
        name=data["item_name"],
        level=data["item_level"],
        defence=data["defence"],
        ward=data["ward"],
        pdr=data["pdr"],
        fdr=data["fdr"],
        passive=data["passive"],
        passive_lvl=data["passive_lvl"],
        is_equipped=bool(data["is_equipped"]),
        potential_remaining=data["potential_remaining"],
        essence_1=_gcol(data, "essence_1") or "none",
        essence_1_val=_gcol(data, "essence_1_val") or 0.0,
        essence_2=_gcol(data, "essence_2") or "none",
        essence_2_val=_gcol(data, "essence_2_val") or 0.0,
        essence_3=_gcol(data, "essence_3") or "none",
        essence_3_val=_gcol(data, "essence_3_val") or 0.0,
        corrupted_essence=_gcol(data, "corrupted_essence") or "none",
        reinforces_remaining=_gcol(data, "reinforces_remaining", 0),
        reinforcement_lvl=_gcol(data, "reinforcement_lvl", 0),
        description="",
    )


def create_companion(data) -> Companion:
    """Maps a database row from table `companions` to a Companion object."""
    if not data:
        return None
    return Companion(
        id=data["id"],
        user_id=data["user_id"],
        name=data["name"],
        species=data["species"],
        image_url=data["image_url"],
        level=data["level"],
        exp=data["exp"],
        passive_type=data["passive_type"],
        passive_tier=data["passive_tier"],
        is_active=bool(data["is_active"]),
        balanced_passive=_gcol(data, "balanced_passive") or "none",
        balanced_passive_tier=_gcol(data, "balanced_passive_tier") or 0,
    )


def create_monster_part(row) -> MonsterPart:
    """Maps a monster_parts DB row to a MonsterPart object."""
    return MonsterPart(
        id=row["id"],
        user_id=row["user_id"],
        slot_type=row["slot_type"],
        monster_name=row["monster_name"],
        ilvl=row["ilvl"],
        hp_value=row["hp_value"],
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
    # 1. Initialize Player with base stats from 'users' table.
    # The connection uses sqlite3.Row as its row_factory (set in bot.py on_ready),
    # so user_data supports both named access and integer indexing. Named access
    # is used here so column insertions/reorderings in schema.sql never silently
    # corrupt stats.
    display_name = _gcol(user_data, "prestige_display_name") or user_data["name"]
    player = Player(
        id=user_id,
        name=display_name,
        level=user_data["level"],
        ascension=user_data["ascension"],
        exp=user_data["experience"],
        current_hp=user_data["current_hp"],
        max_hp=user_data["max_hp"],
        base_attack=user_data["attack"],
        base_defence=user_data["defence"],
        potions=user_data["potions"],
    )

    prestige_title = _gcol(user_data, "prestige_title")
    if prestige_title and prestige_title != "none":
        player.prestige_title = prestige_title
    emblem_key = _gcol(user_data, "prestige_emblem")
    if emblem_key:
        from core.emojis import EMBLEM_CATALOG

        entry = EMBLEM_CATALOG.get(emblem_key)
        if entry:
            player.prestige_emblem = entry[1]

    server_id = user_data["server_id"]

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
        combat_bonuses = await database.settlement.get_combat_bonuses(
            user_id, server_id
        )
        player.apothecary_boost_pct = combat_bonuses["apothecary_boost_pct"]
        player.shrine_effectiveness = combat_bonuses["shrine_effectiveness"]
    except Exception as e:
        print(f"[load_player] settlement combat bonuses failed for {user_id}: {e}")
        # defaults to 0.0 / {} from Player dataclass

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

    # --- Fetch Companion Mastery ---
    # Each block below uses bare except so that a missing row (first-time unlock)
    # or a mid-migration schema gap silently falls back to safe defaults rather
    # than crashing the entire player load.  The print lets us catch unexpected
    # DB errors without spamming logs for every new player who hasn't visited
    # the feature yet.
    try:
        mastery = await database.companions.get_mastery(user_id, server_id)
        nodes = mastery.get("nodes_owned", {})
        from core.companions.mastery import get_passive_mult, has_elite_bond

        player.companion_passive_mult = get_passive_mult(
            nodes, len(player.active_companions)
        )
        player.companion_elite_bond = has_elite_bond(nodes)
    except Exception as e:
        print(f"[load_player] companion mastery failed for {user_id}: {e}")
        # defaults (1.0 / False) from Player dataclass

    # --- Fetch Slayer Data ---
    try:
        # Load Emblem
        player.slayer_emblem = await database.slayer.get_emblem(user_id, server_id)
        # Load Active Task to check for Slayer-specific buffs
        profile = await database.slayer.get_profile(user_id, server_id)
        player.active_task_species = profile.get("active_task_species")
    except Exception as e:
        # Expected for players who haven't opened /slayer yet (no profile row).
        # Any other exception here is unexpected and worth investigating.
        print(f"[load_player] slayer data failed for {user_id}: {e}")
        player.slayer_emblem = {}
        player.active_task_species = None

    # --- Fetch Codex Tomes ---
    try:
        player.codex_tomes = await database.codex.get_tomes(user_id)
    except Exception as e:
        print(f"[load_player] codex tomes failed for {user_id}: {e}")
        player.codex_tomes = []

    # --- Fetch Ascension Pinnacle Unlocks ---
    try:
        player.ascension_unlocks = await database.ascension.get_unlocked_floors(user_id)
    except Exception as e:
        print(f"[load_player] ascension unlocks failed for {user_id}: {e}")
        player.ascension_unlocks = set()

    # --- Fetch Alchemy Potion Passives ---
    try:
        player.potion_passives = await database.alchemy.get_potion_passives(user_id)
    except Exception as e:
        print(f"[load_player] alchemy passives failed for {user_id}: {e}")
        player.potion_passives = []

    # --- Fetch Equipped Monster Body Parts ---
    try:
        player.equipped_parts = await database.monster_parts.get_equipped_parts(user_id)
    except Exception as e:
        print(f"[load_player] monster parts failed for {user_id}: {e}")
        player.equipped_parts = {}

    # --- Fetch Paradise Jewel Data ---
    try:
        player.jewel_of_paradise = await database.paradise.get(user_id)
    except Exception as e:
        print(f"[load_player] paradise jewel failed for {user_id}: {e}")
        # keeps default empty structure

    # --- Fetch Active Combat Partner ---
    try:
        partner_row = await database.partners.get_active_combat(user_id)
        if partner_row:
            from core.models import Partner
            from core.partners.data import PARTNER_DATA

            static = PARTNER_DATA.get(partner_row["partner_id"])
            if static:
                player.active_partner = Partner.from_row(partner_row, static)
    except Exception as e:
        print(f"[load_player] active partner failed for {user_id}: {e}")
        player.active_partner = None

    # --- Fetch Hematurgy Passives ---
    try:
        raw = await database.hematurgy.get_all_passives(user_id)
        player.hematurgy_passives = {v["passive_id"]: v["tier"] for v in raw.values()}
    except Exception as e:
        print(f"[load_player] hematurgy passives failed for {user_id}: {e}")
        player.hematurgy_passives = {}

    # --- Fetch Soul Stone ---
    try:
        ss_row = await database.apex.get_or_create_soul_stone(user_id, server_id)
        from core.apex.models import soul_stone_from_db

        player.soul_stone = soul_stone_from_db(ss_row)
    except Exception as e:
        print(f"[load_player] soul stone failed for {user_id}: {e}")
        player.soul_stone = None

    # --- Fetch Stat Investments (passive_point allocations) ---
    try:
        stat_inv = await database.users.get_stat_investments(user_id)
        player.stat_invest_atk = stat_inv["atk"]
        player.stat_invest_def = stat_inv["def"]
        player.stat_invest_hp = stat_inv["hp"]
        player.stat_invest_gold = stat_inv["gold"]
    except Exception as e:
        print(f"[load_player] stat investments failed for {user_id}: {e}")
        # defaults to 0 from Player dataclass

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

    # HP ceiling enforcement — single enforcement point at load time.
    #
    # total_max_hp is always >= max_hp (it only adds bonuses), so any stored
    # current_hp that is at or above the base max_hp must be clamped to the
    # current total_max_hp.  This handles the common "swap out Hearty/gluttony
    # gear while at full HP" case: the DB row retains the old inflated value,
    # and this line corrects it on next load without needing a migration or a
    # per-equip clamp in the inventory system.
    #
    # If current_hp is below max_hp (player was wounded), total_max_hp >= max_hp
    # so the value is already safe — no clamp needed.
    if player.current_hp >= player.max_hp:
        player.current_hp = player.total_max_hp

    if player.get_celestial_armor_passive() == "celestial_wind_dancer":
        player.equipped_helmet = None  # Completely nullify the helmet stats/passives

    return player
