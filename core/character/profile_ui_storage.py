"""
core/character/profile_ui_storage.py
Embed builders for the inventory, crafting, resources, uber, and essences
tabs of the Profile Hub.
"""

import discord


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

        dragon_keys = await bot.database.users.get_currency(user_id, "dragon_key")
        angel_keys = await bot.database.users.get_currency(user_id, "angel_key")
        void_frags = await bot.database.users.get_currency(user_id, "void_frags")
        soul_cores = await bot.database.users.get_currency(user_id, "soul_cores")
        k_balance = await bot.database.users.get_currency(user_id, "balance_fragment")
        curios = await bot.database.users.get_currency(user_id, "curios")
        antique_tomes = await bot.database.users.get_currency(user_id, "antique_tome")
        pinnacle_keys = await bot.database.users.get_currency(user_id, "pinnacle_key")
        puzzle_boxes = await bot.database.users.get_currency(user_id, "curio_puzzle_boxes")
        items = await bot.database.partners.get_items(user_id)
        guild_tickets = items.get("guild_tickets", 0)

        embed = discord.Embed(
            title="Inventory Summary",
            description=f"💰 **Gold:** {user['gold']:,}\n🧪 **Potions:** {user['potions']:,}",
            color=0x00FF00,
        )
        embed.set_thumbnail(url=user["appearance"])

        embed.add_field(
            name="⚔️ **Gear**",
            value=(
                f"⚔️ Weapons: {w_count}/60\n🛡️ Armor: {ar_count}/60\n📿 Accessories: {a_count}/60\n"
                f"🧤 Gloves: {g_count}/60\n👢 Boots: {b_count}/60\n🪖 Helmets: {h_count}/60\n🐾 Companions: {pet_count}/20"
            ),
            inline=True,
        )

        embed.add_field(
            name="🔑 **Boss Items**",
            value=(
                f"🐉 Draconic Keys: {dragon_keys}\n🪽 Angelic Keys: {angel_keys}\n🟣 Void Frags: {void_frags}\n"
                f"⚖️ Balance Frags: {k_balance}\n❤️‍🔥 Soul Cores: {soul_cores}"
            ),
            inline=True,
        )

        embed.add_field(
            name="📦 **Misc Items**",
            value=(
                f"🎁 Curios: {curios}\n"
                f"🎁 Puzzle Boxes: {puzzle_boxes}\n"
                f"🎫 Guild Tickets: {guild_tickets}\n"
                f"📖 Antique Tomes: {antique_tomes}\n🗝️ Pinnacle Keys: {pinnacle_keys}"
            ),
            inline=True,
        )

        return embed

    @staticmethod
    async def build_crafting(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)

        ref_runes = await bot.database.users.get_currency(user_id, "refinement_runes")
        pot_runes = await bot.database.users.get_currency(user_id, "potential_runes")
        imbue_runes = await bot.database.users.get_currency(user_id, "imbue_runes")
        shat_runes = await bot.database.users.get_currency(user_id, "shatter_runes")
        r_partner = await bot.database.users.get_currency(user_id, "partnership_runes")
        mirage_imp = await bot.database.users.get_currency(user_id, "mirage_runes_imperfect")
        mirage_perf = await bot.database.users.get_currency(user_id, "mirage_runes_perfected")
        void_keys = await bot.database.users.get_currency(user_id, "void_keys")

        essence_data = await bot.database.essences.get_all(user_id)

        embed = discord.Embed(title="⚗️ Crafting Materials", color=0x9B59B6)
        embed.set_thumbnail(url=user["appearance"])

        embed.add_field(
            name="💎 **Runes**",
            value=(
                f"🔨 Refinement: {ref_runes}\n✨ Potential: {pot_runes}\n🔮 Imbuing: {imbue_runes}\n"
                f"💥 Shatter: {shat_runes}\n🤝 Partnership: {r_partner}\n"
                f"🪞 Mirage (Imperfect): {mirage_imp}\n🪞 Mirage (Perfected): {mirage_perf}"
            ),
            inline=True,
        )

        embed.add_field(
            name="🗝️ **Void Keys**",
            value=f"🗝️ Void Keys: {void_keys}",
            inline=True,
        )

        if essence_data:
            items = {}
            if hasattr(essence_data, "keys"):
                items = {
                    k: v
                    for k, v in dict(essence_data).items()
                    if k not in ("user_id", "server_id", "id")
                }
            if items:
                lines = []
                for e_type, count in items.items():
                    safe_count = count if count is not None else 0
                    name = str(e_type).replace("_", " ").title()
                    lines.append(f"✦ **{name}**: {safe_count:,}")
                chunk_size = 12
                for i in range(0, len(lines), chunk_size):
                    chunk = lines[i : i + chunk_size]
                    embed.add_field(
                        name="🧪 Stored Essences" if i == 0 else "​",
                        value="\n".join(chunk),
                        inline=True,
                    )

        return embed

    @staticmethod
    async def build_resources(bot, user_id: str, server_id: str) -> discord.Embed:
        settlement = await bot.database.settlement.get_settlement(user_id, server_id)
        mat_all = await bot.database.settlement_materials.get_all(user_id)
        blueprint_count = mat_all.get("unidentified_blueprint", 0)

        ores = await bot.database.skills.get_multi_resource(
            user_id, server_id, "mining", ["iron_ore", "coal_ore", "gold_ore", "platinum_ore", "idea_ore"]
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

        mastery_row = await bot.database.skills.get_mastery(user_id, server_id)
        geode_cores = mastery_row.get("geode_cores", 0) or 0
        tide_relics = mastery_row.get("tide_relics", 0) or 0
        heartwood_shards = mastery_row.get("heartwood_shards", 0) or 0
        blessed_bismuth = mastery_row.get("blessed_bismuth", 0) or 0
        sparkling_sprig = mastery_row.get("sparkling_sprig", 0) or 0
        capricious_carp = mastery_row.get("capricious_carp", 0) or 0

        embed = discord.Embed(
            title="Storage Warehouse", color=discord.Color.dark_orange()
        )

        gathering_value = (
            f"**Ores:** Iron {ores[0]:,} · Coal {ores[1]:,} · Gold {ores[2]:,} · Plat {ores[3]:,} · Idea {ores[4]:,}\n"
            f"**Logs:** Oak {logs[0]:,} · Willow {logs[1]:,} · Mahog {logs[2]:,} · Magic {logs[3]:,} · Idea {logs[4]:,}\n"
            f"**Bones:** Desic {bones[0]:,} · Reg {bones[1]:,} · Sturdy {bones[2]:,} · Reinf {bones[3]:,} · Titan {bones[4]:,}\n"
            f"**Elemental Keys:** 💎 Bismuth: {blessed_bismuth} · 🌿 Sprig: {sparkling_sprig} · 🐟 Carp: {capricious_carp}"
        )
        embed.add_field(name="⛏️ Gathering", value=gathering_value, inline=False)

        settlement_value = (
            f"🪵 Timber: {settlement.timber:,} · 🪨 Stone: {settlement.stone:,}\n"
            f"**Ingots:** Iron {ingots[0]:,} · Steel {ingots[1]:,} · Gold {ingots[2]:,} · Plat {ingots[3]:,} · Idea {ingots[4]:,}\n"
            f"**Planks:** Oak {planks[0]:,} · Willow {planks[1]:,} · Mahog {planks[2]:,} · Magic {planks[3]:,} · Idea {planks[4]:,}\n"
            f"**Essence:** Desic {essence[0]:,} · Reg {essence[1]:,} · Sturdy {essence[2]:,} · Reinf {essence[3]:,} · Titan {essence[4]:,}\n"
            f"**Rare Materials:** 🔥 Magma Core: {rares[0]} · 🌿 Life Root: {rares[1]} · 👻 Spirit Shard: {rares[2]}\n"
            f"📋 Unidentified Blueprints: {blueprint_count}"
        )
        embed.add_field(name="🏭 Settlement", value=settlement_value, inline=False)

        mastery_value = (
            f"⛏️ **Geode Cores:** {geode_cores:,}\n"
            f"🐟 **Tide Relics:** {tide_relics:,}\n"
            f"🪵 **Heartwood Shards:** {heartwood_shards:,}"
        )
        embed.add_field(
            name="🌿 Artisan Mastery (Remnants)", value=mastery_value, inline=False
        )

        return embed

    @staticmethod
    async def build_uber(bot, user_id: str, server_id: str) -> discord.Embed:
        uber_data = await bot.database.uber.get_uber_progress(user_id, server_id)
        specials = await bot.database.settlement_materials.get_uber_materials(user_id)

        embed = discord.Embed(title="Uber Encounters", color=discord.Color.dark_gold())

        bp_status = (
            "✅ Unlocked" if uber_data["celestial_blueprint_unlocked"] else "🔒 Locked"
        )
        embed.add_field(
            name="**Aphrodite**",
            value=(
                f"🔮 Celestial Sigils: {uber_data['celestial_sigils']}\n"
                f"💠 Celestial Engrams: {uber_data['celestial_engrams']}\n"
                f"🪨 Celestial Stone: {specials[0]}\n"
                f"📜 Celestial Statue Blueprint: {bp_status}"
            ),
            inline=True,
        )

        infernal_bp_status = (
            "✅ Unlocked" if uber_data["infernal_blueprint_unlocked"] else "🔒 Locked"
        )
        embed.add_field(
            name="**Lucifer**",
            value=(
                f"🔥 Infernal Sigils: {uber_data['infernal_sigils']}\n"
                f"🔴 Infernal Engrams: {uber_data['infernal_engrams']}\n"
                f"🔥 Infernal Cinder: {specials[1]}\n"
                f"📜 Infernal Statue Blueprint: {infernal_bp_status}"
            ),
            inline=True,
        )

        void_bp_status = (
            "✅ Unlocked"
            if uber_data.get("void_blueprint_unlocked", 0)
            else "🔒 Locked"
        )
        embed.add_field(
            name="**NEET**",
            value=(
                f"⬛ Void Sigils: {uber_data.get('void_shards', 0)}\n"
                f"🔮 Void Engrams: {uber_data.get('void_engrams', 0)}\n"
                f"💎 Void Crystal: {specials[2]}\n"
                f"📜 Void Statue Blueprint: {void_bp_status}"
            ),
            inline=True,
        )

        gemini_bp_status = (
            "✅ Unlocked"
            if uber_data.get("gemini_blueprint_unlocked", 0)
            else "🔒 Locked"
        )
        embed.add_field(
            name="**Castor & Pollux**",
            value=(
                f"♊ Gemini Sigils: {uber_data.get('gemini_sigils', 0)}\n"
                f"💠 Gemini Engrams: {uber_data.get('gemini_engrams', 0)}\n"
                f"🔷 Bound Crystal: {specials[3]}\n"
                f"📜 Twin Statue Blueprint: {gemini_bp_status}"
            ),
            inline=True,
        )
        corrupted_bp_status = (
            "✅ Unlocked"
            if uber_data.get("corruption_blueprint_unlocked", 0)
            else "🔒 Locked"
        )
        embed.add_field(
            name="**Evelynn**",
            value=(
                f"☠️ Corruption Sigils: {uber_data.get('corruption_sigils', 0)}\n"
                f"📜 Corrupted Statue Blueprint: {corrupted_bp_status}"
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
