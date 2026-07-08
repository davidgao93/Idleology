"""
core/character/profile_ui_storage.py
Embed builders for the inventory, crafting, resources, uber, and essences
tabs of the Profile Hub.
"""

import discord

from core.emojis import (
    ACCESSORY_SLOT,
    ANGEL_KEY,
    ARMOR_SLOT,
    BARS_REFINED,
    BLESSED_BISMUTH,
    BOOT_SLOT,
    BOUND_CRYSTAL,
    BOUND_ENGRAM,
    BOUND_SIGIL,
    CAPRICIOUS_CARP,
    CELESTIAL_ENGRAM,
    CELESTIAL_SIGIL,
    CELESTIAL_STONE,
    COAL_ORE,
    CONSUME_ICON,
    CORRUPTION_CORE,
    CORRUPTION_ENGRAM,
    CORRUPTION_SIGIL,
    COSMIC_DUST,
    CURIO,
    DESICCATED_BONES,
    DEVELOPMENT_CONTRACT,
    DIVINER_ROD,
    DRAGON_KEY,
    ESSENCE_COMMON,
    ESSENCE_CORRUPT,
    ESSENCE_RARE,
    GEAR_BACKPACK,
    GEODE_CORE,
    GLOVE_SLOT,
    GOLD_COIN,
    GOLD_ORE,
    HEARTWOOD_SHARD,
    HELMET_SLOT,
    IDEA_LOGS,
    IDEA_ORE,
    INFERNAL_CINDER,
    INFERNAL_ENGRAM,
    INFERNAL_SIGIL,
    IRON_ORE,
    LIFE_ROOT,
    MAGIC_LOGS,
    MAGMA_CORE,
    MAHOGANY_LOGS,
    OAK_LOGS,
    PARADISE_JEWEL_UNCUT,
    PINNACLE_KEY,
    PLATINUM_ORE,
    POTION,
    PUZZLE_BOX,
    REGULAR_BONES,
    REINFORCED_BONES,
    RUNE_GENERIC,
    RUNE_IMBUE,
    RUNE_MIRAGE_IMPERFECT,
    RUNE_MIRAGE_PERFECT,
    RUNE_NATURE,
    RUNE_PARTNERSHIP,
    RUNE_POTENTIAL,
    RUNE_REFINEMENT,
    RUNE_REGRET,
    RUNE_SHATTER,
    SOUL_CORE,
    SPARKLING_SPRIG,
    SPIRIT_SHARD,
    SPIRIT_STONE,
    STURDY_BONES,
    TIDE_RELIC,
    TITANIUM_BONES,
    VOID_CRYSTAL,
    VOID_ENGRAM,
    VOID_FRAG,
    VOID_KEY,
    VOID_SIGIL,
    WEAPON_SLOT,
    WILLOW_LOGS,
    WOODEN_PLANKS,
)


class StorageProfileBuilder:
    """Embed builders for inventory, crafting, resources, uber, and essences tabs."""

    @staticmethod
    async def build_inventory(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)

        w_count = await bot.database.equipment.get_count(user_id, "weapon")
        a_count = await bot.database.equipment.get_count(user_id, "accessory")
        ar_count = await bot.database.equipment.get_count(user_id, "armor")
        g_count = await bot.database.equipment.get_count(user_id, "glove")
        b_count = await bot.database.equipment.get_count(user_id, "boot")
        h_count = await bot.database.equipment.get_count(user_id, "helmet")
        pet_count = await bot.database.companions.get_count(user_id)

        cur = await bot.database.users.get_all_currencies(user_id)
        dragon_keys = cur["dragon_key"]
        angel_keys = cur["angel_key"]
        void_frags = cur["void_frags"]
        soul_cores = cur["soul_cores"]
        k_balance = cur["balance_fragment"]
        curios = cur["curios"]
        antique_tomes = cur["antique_tome"]
        pinnacle_keys = cur["pinnacle_key"]
        puzzle_boxes = cur["curio_puzzle_boxes"]
        spirit_stones = cur["spirit_stones"]
        items = await bot.database.partners.get_items(user_id)
        guild_tickets = items.get("guild_tickets", 0)

        cosmic_dust = await bot.database.alchemy.get_cosmic_dust(user_id)
        uber_data = await bot.database.uber.get_uber_progress(user_id, server_id)
        paradise_jewels = uber_data.get("paradise_jewels", 0)

        parts_count = await bot.database.monster_parts.get_count(user_id)
        egg_count = await bot.database.eggs.get_egg_count(user_id)
        blood = await bot.database.hematurgy.get_blood(user_id)

        await bot.database.apex.get_or_create_shards(user_id, server_id)
        await bot.database.apex.get_or_create_meta_shards(user_id, server_id)

        embed = discord.Embed(
            title="Inventory Summary",
            description=f"{GOLD_COIN} **Gold:** {user['gold']:,}\n{POTION} **Potions:** {user['potions']:,}",
            color=0x00FF00,
        )
        embed.set_thumbnail(url=user["appearance"])

        embed.add_field(
            name=f"{GEAR_BACKPACK} **Gear**",
            value=(
                f"{WEAPON_SLOT} Weapons: {w_count}/60\n{ARMOR_SLOT} Armor: {ar_count}/60\n{ACCESSORY_SLOT} Accs: {a_count}/60\n"
                f"{GLOVE_SLOT} Gloves: {g_count}/60\n{BOOT_SLOT} Boots: {b_count}/60\n{HELMET_SLOT} Helms: {h_count}/60\n🐾 Pets: {pet_count}/20"
            ),
            inline=True,
        )

        embed.add_field(
            name="🔑 **Boss Items**",
            value=(
                f"{DRAGON_KEY} Draconic Keys: {dragon_keys}\n{ANGEL_KEY} Angelic Keys: {angel_keys}\n{VOID_FRAG} Void Frags: {void_frags}\n"
                f"⚖️ Balance Frags: {k_balance}\n{SOUL_CORE} Soul Cores: {soul_cores}"
            ),
            inline=True,
        )

        embed.add_field(
            name="📦 **Misc Items**",
            value=(
                f"{CURIO} Curios: {curios}\n"
                f"{PUZZLE_BOX} Puzzle Boxes: {puzzle_boxes}\n"
                f"🎫 Guild Tickets: {guild_tickets}\n"
                f"📖 Antique Tomes: {antique_tomes}\n{PINNACLE_KEY} Pinnacle Keys: {pinnacle_keys}"
            ),
            inline=True,
        )

        embed.add_field(
            name="⚗️ **Alchemy**",
            value=(
                f"{COSMIC_DUST} Cosmic Dust: {cosmic_dust:,}\n"
                f"{SPIRIT_STONE} Spirit Stones: {spirit_stones}\n"
                f"{PARADISE_JEWEL_UNCUT} Uncut Jewels: {paradise_jewels}"
            ),
            inline=True,
        )

        embed.add_field(
            name=f"{CONSUME_ICON} **Consume**",
            value=(
                f"🦴 Parts: {parts_count}/20\n"
                f"🥚 Eggs: {egg_count}/20\n"
                f"🩸 Primordial: {blood['primordial']:,}\n"
                f"🧬 Evolutionary: {blood['evolutionary']:,}\n"
                f"☣️ Mutative: {blood['mutative']:,}"
            ),
            inline=True,
        )

        return embed

    @staticmethod
    async def build_crafting(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)

        cur = await bot.database.users.get_all_currencies(user_id)
        ref_runes = cur["refinement_runes"]
        pot_runes = cur["potential_runes"]
        imbue_runes = cur["imbue_runes"]
        shat_runes = cur["shatter_runes"]
        r_partner = cur["partnership_runes"]
        r_regret = cur["rune_of_regret"]
        mirage_imp = cur["mirage_runes_imperfect"]
        mirage_perf = cur["mirage_runes_perfected"]
        void_keys = cur["void_keys"]

        essence_data = await bot.database.essences.get_all(user_id)

        embed = discord.Embed(title="⚗️ Crafting Materials", color=0x9B59B6)
        embed.set_thumbnail(url=user["appearance"])

        embed.add_field(
            name=f"{RUNE_GENERIC} **Runes**",
            value=(
                f"{RUNE_REFINEMENT} Refinement: {ref_runes}\n{RUNE_POTENTIAL} Potential: {pot_runes}\n{RUNE_IMBUE} Imbuing: {imbue_runes}\n"
                f"{RUNE_SHATTER} Shatter: {shat_runes}\n{RUNE_PARTNERSHIP} Partnership: {r_partner}\n{RUNE_REGRET} Regret: {r_regret}\n"
                f"{RUNE_MIRAGE_IMPERFECT} Mirage (Imperfect): {mirage_imp}\n{RUNE_MIRAGE_PERFECT} Mirage (Perfected): {mirage_perf}"
            ),
            inline=True,
        )

        embed.add_field(
            name="⭐ **Special**",
            value=f"{VOID_KEY} Void Keys: {void_keys}",
            inline=True,
        )

        _COMMON_ESSENCES = ["power", "protection"]
        _RARE_ESSENCES = [
            "insight",
            "evasion",
            "blocking",
            "deftness",
            "precision",
            "gluttony",
            "cleansing",
            "chaos",
            "annulment",
        ]
        _CORRUPTED_ESSENCES = ["aphrodite", "lucifer", "gemini", "neet"]

        def _essence_lines(types):
            return "\n".join(
                f"✦ **{e.replace('_', ' ').title()}**: {essence_data.get(e, 0):,}"
                for e in types
            )

        embed.add_field(
            name=f"{ESSENCE_COMMON} **Common Essences**",
            value=_essence_lines(_COMMON_ESSENCES),
            inline=False,
        )
        embed.add_field(
            name=f"{ESSENCE_RARE} **Rare Essences**",
            value=_essence_lines(_RARE_ESSENCES),
            inline=True,
        )
        embed.add_field(
            name=f"{ESSENCE_CORRUPT} **Corrupted Essences**",
            value=_essence_lines(_CORRUPTED_ESSENCES),
            inline=True,
        )

        return embed

    @staticmethod
    async def build_resources(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        settlement = await bot.database.settlement.get_settlement(user_id, server_id)
        mat_all = await bot.database.settlement_materials.get_all(user_id)
        blueprint_count = mat_all.get("unidentified_blueprint", 0)

        ores = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "mining",
            ["iron_ore", "coal_ore", "gold_ore", "platinum_ore", "idea_ore"],
        )
        logs = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "woodcutting",
            ["oak_logs", "willow_logs", "mahogany_logs", "magic_logs", "idea_logs"],
        )
        bones = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "fishing",
            [
                "desiccated_bones",
                "regular_bones",
                "sturdy_bones",
                "reinforced_bones",
                "titanium_bones",
            ],
        )
        ingots = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "mining",
            ["iron_bar", "steel_bar", "gold_bar", "platinum_bar", "idea_bar"],
        )
        planks = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "woodcutting",
            [
                "oak_plank",
                "willow_plank",
                "mahogany_plank",
                "magic_plank",
                "idea_plank",
            ],
        )
        essence = await bot.database.skills.get_multi_resource(
            user_id,
            server_id,
            "fishing",
            [
                "desiccated_essence",
                "regular_essence",
                "sturdy_essence",
                "reinforced_essence",
                "titanium_essence",
            ],
        )
        rares = await bot.database.settlement_materials.get_rare_materials(user_id)
        dev_contracts = await bot.database.settlement.get_development_contracts(
            user_id, server_id
        )

        mastery_row = await bot.database.skills.get_mastery(user_id, server_id)
        geode_cores = mastery_row.get("geode_cores", 0) or 0
        tide_relics = mastery_row.get("tide_relics", 0) or 0
        heartwood_shards = mastery_row.get("heartwood_shards", 0) or 0
        blessed_bismuth = mastery_row.get("blessed_bismuth", 0) or 0
        sparkling_sprig = mastery_row.get("sparkling_sprig", 0) or 0
        capricious_carp = mastery_row.get("capricious_carp", 0) or 0
        runes_of_nature = await bot.database.users.get_currency(
            user_id, "runes_of_nature"
        )

        embed = discord.Embed(
            title="Storage Warehouse", color=discord.Color.dark_orange()
        )
        embed.set_thumbnail(url=user["appearance"])

        # ── Gathering ── Row 1: Ore | Logs | Bones — Row 2: Elemental Keys | Artisan Remnants
        embed.add_field(name="⛏️ **Gathering**", value="​", inline=False)

        embed.add_field(
            name="⛏️ Ore",
            value=(
                f"{IRON_ORE} Iron: {ores[0]:,}\n{COAL_ORE} Coal: {ores[1]:,}\n{GOLD_ORE} Gold: {ores[2]:,}\n"
                f"{PLATINUM_ORE} Plat: {ores[3]:,}\n{IDEA_ORE} Idea: {ores[4]:,}"
            ),
            inline=True,
        )
        embed.add_field(
            name="🪓 Logs",
            value=(
                f"{OAK_LOGS} Oak: {logs[0]:,}\n{WILLOW_LOGS} Willow: {logs[1]:,}\n{MAHOGANY_LOGS} Mahog: {logs[2]:,}\n"
                f"{MAGIC_LOGS} Magic: {logs[3]:,}\n{IDEA_LOGS} Idea: {logs[4]:,}"
            ),
            inline=True,
        )
        embed.add_field(
            name="🎣 Bones",
            value=(
                f"{DESICCATED_BONES} Desic: {bones[0]:,}\n{REGULAR_BONES} Reg: {bones[1]:,}\n{STURDY_BONES} Sturdy: {bones[2]:,}\n"
                f"{REINFORCED_BONES} Reinf: {bones[3]:,}\n{TITANIUM_BONES} Titan: {bones[4]:,}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🗝️ Elemental Keys",
            value=(
                f"{BLESSED_BISMUTH} Bismuth: {blessed_bismuth}\n"
                f"{SPARKLING_SPRIG} Sprig: {sparkling_sprig}\n"
                f"{CAPRICIOUS_CARP} Carp: {capricious_carp}"
            ),
            inline=True,
        )
        embed.add_field(
            name="🌿 Artisan Remnants",
            value=(
                f"{GEODE_CORE} Geode Cores: {geode_cores:,}\n"
                f"{TIDE_RELIC} Tide Relics: {tide_relics:,}\n"
                f"{HEARTWOOD_SHARD} Heartwood Shards: {heartwood_shards:,}\n"
                f"{RUNE_NATURE} Runes of Nature: {runes_of_nature:,}"
            ),
            inline=True,
        )

        # ── Settlement ── Row 1: Building | Rare — Row 2: Ingots | Planks | Essence
        embed.add_field(name="🏭 **Settlement**", value="​", inline=False)

        embed.add_field(
            name="🏗️ Building",
            value=(
                f"🪵 Timber: {settlement.timber:,}\n"
                f"🪨 Stone: {settlement.stone:,}\n"
                f"📋 Blueprints: {blueprint_count}\n"
                f"{DIVINER_ROD} Diviner's Rods: {mat_all.get('diviners_rod', 0)}\n"
                f"{DEVELOPMENT_CONTRACT} Dev Contracts: {dev_contracts:,}"
            ),
            inline=True,
        )
        embed.add_field(
            name="💎 Rare",
            value=(
                f"{MAGMA_CORE} Magma Core: {rares[0]}\n"
                f"{LIFE_ROOT} Life Root: {rares[1]}\n"
                f"{SPIRIT_SHARD} Spirit Shard: {rares[2]}"
            ),
            inline=True,
        )

        embed.add_field(name="​", value="​", inline=False)

        embed.add_field(
            name=f"{BARS_REFINED} Ingots",
            value=(
                f"Iron: {ingots[0]:,}\nSteel: {ingots[1]:,}\nGold: {ingots[2]:,}\n"
                f"Plat: {ingots[3]:,}\nIdea: {ingots[4]:,}"
            ),
            inline=True,
        )
        embed.add_field(
            name=f"{WOODEN_PLANKS} Planks",
            value=(
                f"Oak: {planks[0]:,}\nWillow: {planks[1]:,}\nMahog: {planks[2]:,}\n"
                f"Magic: {planks[3]:,}\nIdea: {planks[4]:,}"
            ),
            inline=True,
        )
        embed.add_field(
            name="🧪 Essence",
            value=(
                f"Desic: {essence[0]:,}\nReg: {essence[1]:,}\nSturdy: {essence[2]:,}\n"
                f"Reinf: {essence[3]:,}\nTitan: {essence[4]:,}"
            ),
            inline=True,
        )

        return embed

    @staticmethod
    async def build_uber(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        uber_data = await bot.database.uber.get_uber_progress(user_id, server_id)
        specials = await bot.database.settlement_materials.get_uber_materials(user_id)

        embed = discord.Embed(title="Uber Encounters", color=discord.Color.dark_gold())
        embed.set_thumbnail(url=user["appearance"])

        def _bp_emoji(unlocked) -> str:
            return "✅" if unlocked else "🔒"

        # Row 1: Aphrodite | Lucifer | NEET — Row 2: Gemini | Evelynn
        embed.add_field(
            name="**Aphrodite (Celestial)**",
            value=(
                f"{CELESTIAL_SIGIL} Sigil: {uber_data['celestial_sigils']}\n"
                f"{CELESTIAL_ENGRAM} Engram: {uber_data['celestial_engrams']}\n"
                f"{CELESTIAL_STONE} Stone: {specials[0]}\n"
                f"📜 Blueprint: {_bp_emoji(uber_data['celestial_blueprint_unlocked'])}"
            ),
            inline=True,
        )

        embed.add_field(
            name="**Lucifer (Infernal)**",
            value=(
                f"{INFERNAL_SIGIL} Sigil: {uber_data['infernal_sigils']}\n"
                f"{INFERNAL_ENGRAM} Engram: {uber_data['infernal_engrams']}\n"
                f"{INFERNAL_CINDER} Cinder: {specials[1]}\n"
                f"📜 Blueprint: {_bp_emoji(uber_data['infernal_blueprint_unlocked'])}"
            ),
            inline=True,
        )

        embed.add_field(
            name="**NEET (Void)**",
            value=(
                f"{VOID_SIGIL} Sigil: {uber_data.get('void_shards', 0)}\n"
                f"{VOID_ENGRAM} Engram: {uber_data.get('void_engrams', 0)}\n"
                f"{VOID_CRYSTAL} Crystal: {specials[2]}\n"
                f"📜 Blueprint: {_bp_emoji(uber_data.get('void_blueprint_unlocked', 0))}"
            ),
            inline=True,
        )

        embed.add_field(
            name="**Gemini (Bound)**",
            value=(
                f"{BOUND_SIGIL} Sigil: {uber_data.get('gemini_sigils', 0)}\n"
                f"{BOUND_ENGRAM} Engram: {uber_data.get('gemini_engrams', 0)}\n"
                f"{BOUND_CRYSTAL} Crystal: {specials[3]}\n"
                f"📜 Blueprint: {_bp_emoji(uber_data.get('gemini_blueprint_unlocked', 0))}"
            ),
            inline=True,
        )

        embed.add_field(
            name="**Evelynn (Corruption)**",
            value=(
                f"{CORRUPTION_SIGIL} Sigil: {uber_data.get('corruption_sigils', 0)}\n"
                f"{CORRUPTION_ENGRAM} Engram: {uber_data.get('corruption_engrams', 0)}\n"
                f"{CORRUPTION_CORE} Core: {specials[4]}\n"
                f"📜 Blueprint: {_bp_emoji(uber_data.get('corruption_blueprint_unlocked', 0))}"
            ),
            inline=True,
        )

        return embed

    @staticmethod
    async def build_essences(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        essence_data = await bot.database.essences.get_all(user_id)

        embed = discord.Embed(
            title="Essence Vault",
            description="Essences used to enchant and upgrade equipment.",
            color=0x9B59B6,
        )
        embed.set_thumbnail(url=user["appearance"])

        if not essence_data:
            embed.add_field(
                name="Empty", value="No essence data found for your account."
            )
            return embed

        items = {}
        if hasattr(essence_data, "keys"):
            items = {
                k: v
                for k, v in dict(essence_data).items()
                if k not in ("user_id", "server_id", "id")
            }

        if not items:
            embed.add_field(name="Empty", value="No essence data available.")
            return embed

        lines = []
        for e_type, count in items.items():
            safe_count = count if count is not None else 0
            name = str(e_type).replace("_", " ").title()
            lines.append(f"✦ **{name}**: {safe_count:,}")

        chunk_size = 12
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i : i + chunk_size]
            embed.add_field(
                name="Stored Essences" if i == 0 else "​",
                value="\n".join(chunk),
                inline=True,
            )

        return embed
