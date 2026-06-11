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
        # Runes
        "Rune of Refinement": ("users", "refinement_runes"),
        "Rune of Potential": ("users", "potential_runes"),
        "Rune of Imbuing": ("users", "imbue_runes"),
        "Rune of Shattering": ("users", "shatter_runes"),
        # Mining
        "Iron Ore": ("mining", "iron"),
        "Coal": ("mining", "coal"),
        "Gold Ore": ("mining", "gold"),
        "Platinum Ore": ("mining", "platinum"),
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
