class TradeManager:
    """Handles logic for mapping items/resources and executing transfers."""

    # Mappings for "Special Items" / Resources
    RESOURCE_MAP = {
        # Keys & Misc
        "Draconic Key": ("users", "dragon_key"),
        "Angelic Key": ("users", "angel_key"),
        "Void Key": ("users", "void_keys"),
        "Soul Core": ("users", "soul_cores"),
        "Void Fragment": ("users", "void_frags"),
        "Fragment of Balance": ("users", "balance_fragment"),
        "Curio": ("users", "curios"),
        "Curio Puzzle Box": ("users", "curio_puzzle_boxes"),
        "Pinnacle Key": ("users", "pinnacle_key"),
        "Spirit Stone": ("users", "spirit_stones"),
        "Antique Tome": ("users", "antique_tome"),
        "Codex Fragment": ("users", "codex_fragments"),
        "Codex Page": ("users", "codex_pages"),
        "Codex Reroll": ("users", "codex_rerolls"),
        # Runes
        "Rune of Refinement": ("users", "refinement_runes"),
        "Rune of Potential": ("users", "potential_runes"),
        "Rune of Imbuing": ("users", "imbue_runes"),
        "Rune of Shattering": ("users", "shatter_runes"),
        "Rune of Partnership": ("users", "partnership_runes"),
        "Rune of Regret": ("users", "rune_of_regret"),
        "Rune of Nature": ("users", "runes_of_nature"),
        "Rune of Mirage (Imperfect)": ("users", "mirage_runes_imperfect"),
        "Rune of Mirage (Perfected)": ("users", "mirage_runes_perfected"),
        # Mining
        "Iron Ore": ("mining", "iron_ore"),
        "Coal": ("mining", "coal_ore"),
        "Gold Ore": ("mining", "gold_ore"),
        "Platinum Ore": ("mining", "platinum_ore"),
        # Woodcutting
        "Oak Logs": ("woodcutting", "oak_logs"),
        "Willow Logs": ("woodcutting", "willow_logs"),
        "Mahogany Logs": ("woodcutting", "mahogany_logs"),
        "Magic Logs": ("woodcutting", "magic_logs"),
        # Fishing
        "Desiccated Bones": ("fishing", "desiccated_bones"),
        "Regular Bones": ("fishing", "regular_bones"),
        "Sturdy Bones": ("fishing", "sturdy_bones"),
        "Reinforced Bones": ("fishing", "reinforced_bones"),
        # Meta Shards (apex table, server-scoped)
        "Sharpened Fang": ("apex", "sharpened_fang"),
        "Engorged Heart": ("apex", "engorged_heart"),
        "Condensed Blood": ("apex", "condensed_blood"),
        "Primal Essence": ("apex", "primal_essence"),
        "Soul Vessel": ("apex", "soul_vessel"),
        # Essences (player_essences table)
        "Power Essence": ("essences", "power"),
        "Protection Essence": ("essences", "protection"),
        "Insight Essence": ("essences", "insight"),
        "Evasion Essence": ("essences", "evasion"),
        "Blocking Essence": ("essences", "blocking"),
        "Deftness Essence": ("essences", "deftness"),
        "Precision Essence": ("essences", "precision"),
        "Gluttony Essence": ("essences", "gluttony"),
        "Cleansing Essence": ("essences", "cleansing"),
        "Chaos Essence": ("essences", "chaos"),
        "Annulment Essence": ("essences", "annulment"),
        "Aphrodite Essence": ("essences", "aphrodite"),
        "Lucifer Essence": ("essences", "lucifer"),
        "Gemini Essence": ("essences", "gemini"),
        "NEET Essence": ("essences", "neet"),
        # Settlement Materials (settlement_materials table)
        "Magma Core": ("settlement_materials", "magma_core"),
        "Life Root": ("settlement_materials", "life_root"),
        "Spirit Shard": ("settlement_materials", "spirit_shard"),
        "Celestial Stone": ("settlement_materials", "celestial_stone"),
        "Void Crystal": ("settlement_materials", "void_crystal"),
        "Infernal Cinder": ("settlement_materials", "infernal_cinder"),
        "Bound Crystal": ("settlement_materials", "bound_crystal"),
        "Diviner's Rod": ("settlement_materials", "diviners_rod"),
        "Unidentified Blueprint": ("settlement_materials", "unidentified_blueprint"),
    }

    @staticmethod
    async def get_resource_balance(
        bot, user_id: str, server_id: str, resource_name: str
    ) -> int:
        table, col = TradeManager.RESOURCE_MAP[resource_name]

        if table == "users":
            return await bot.database.users.get_currency(user_id, col)
        elif table == "apex":
            shards = await bot.database.apex.get_or_create_meta_shards(
                user_id, server_id
            )
            return shards.get(col, 0)
        elif table == "essences":
            return await bot.database.essences.get_quantity(user_id, col)
        elif table == "settlement_materials":
            all_mats = await bot.database.settlement_materials.get_all(user_id)
            return all_mats.get(col, 0)
        else:
            return await bot.database.skills.get_single_resource(
                user_id, server_id, table, col
            )

    @staticmethod
    async def transfer_gold(bot, sender_id: str, receiver_id: str, amount: int) -> bool:
        if not await bot.database.users.deduct_gold_atomic(sender_id, amount):
            return False
        await bot.database.users.modify_gold(receiver_id, amount)
        return True

    @staticmethod
    async def transfer_resource(
        bot,
        sender_id: str,
        receiver_id: str,
        server_id: str,
        resource_name: str,
        amount: int,
    ) -> bool:
        table, col = TradeManager.RESOURCE_MAP[resource_name]

        if table == "users":
            if not await bot.database.users.deduct_currency_atomic(
                sender_id, col, amount
            ):
                return False
            await bot.database.users.modify_currency(receiver_id, col, amount)
        elif table == "apex":
            if not await bot.database.apex.deduct_meta_shard_atomic(
                sender_id, server_id, col, amount
            ):
                return False
            await bot.database.apex.modify_meta_shard(
                receiver_id, server_id, col, amount
            )
        elif table == "essences":
            if not await bot.database.essences.consume(sender_id, col, amount):
                return False
            await bot.database.essences.add(receiver_id, col, amount)
        elif table == "settlement_materials":
            all_mats = await bot.database.settlement_materials.get_all(sender_id)
            if all_mats.get(col, 0) < amount:
                return False
            await bot.database.settlement_materials.modify(sender_id, col, -amount)
            await bot.database.settlement_materials.modify(receiver_id, col, amount)
        else:
            # Skill tables require server_id
            await bot.database.skills.update_single_resource(
                sender_id, server_id, table, col, -amount
            )
            await bot.database.skills.update_single_resource(
                receiver_id, server_id, table, col, amount
            )
        return True

    @staticmethod
    async def transfer_equipment(
        bot, sender_id: str, receiver_id: str, item_type: str, item_id: int
    ):
        # Using the generic transfer method in equipment repo
        await bot.database.equipment.transfer(item_id, receiver_id, item_type)
