import asyncio
import random
from datetime import datetime

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.combat.loot import (
    generate_accessory,
    generate_armor,
    generate_boot,
    generate_glove,
    generate_helmet,
    generate_weapon,
)
from core.companions.mechanics import CompanionMechanics
from core.images import SETTLEMENT_BUILDINGS, SETTLEMENT_HUB
from core.items.factory import load_player
from core.models import Building, Settlement
from core.settlement.mechanics import SettlementMechanics


class BulkTradeModal(ui.Modal):
    TRADES = {
        "equip": {
            "label": "Equipment Caches (2.5M Gold each)",
            "key": "equip",
        },
        "rune": {
            "label": "Rune Caches (1 each: Refine/Potential/Shatter)",
            "key": "rune",
        },
        "key": {"label": "Boss Key Caches (1 Void Key each)", "key": "key"},
    }

    quantity = ui.TextInput(
        label="How many trades?",
        placeholder="Enter a number e.g. 5",
        min_length=1,
        max_length=4,
    )

    def __init__(self, market_view: "BlackMarketView", trade_key: str):
        short_titles = {
            "equip": "Bulk Trade: Equipment Caches",
            "rune": "Bulk Trade: Rune Caches",
            "key": "Bulk Trade: Boss Key Caches",
        }

        super().__init__(title=short_titles[trade_key])
        self.market_view = market_view
        self.trade_key = trade_key

    async def on_submit(self, interaction: Interaction):
        try:
            requested = int(self.quantity.value)
            if requested <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a positive integer.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        mv = self.market_view
        uid, sid = mv.user_id, mv.parent.server_id

        if self.trade_key == "equip":
            await mv._bulk_equip_cache(interaction, requested)
        elif self.trade_key == "rune":
            await mv._bulk_rune_cache(interaction, requested)
        elif self.trade_key == "key":
            await mv._bulk_key_cache(interaction, requested)


class BlackMarketView(ui.View):
    def __init__(self, bot, user_id, parent_view, building: Building):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.parent = parent_view
        self.building = building
        self.setup_ui()

    def _get_multiplier(self) -> float:
        t = self.building.tier
        if t == 1:
            return 1.0
        if t == 2:
            return 1.2
        if t == 3:
            return 1.3
        if t == 4:
            return 1.4
        if t == 5:
            return 1.5
        return 1.0

    def _get_upgrade_cost(self, target_tier):
        base_wood = 50000
        base_stone = 50000
        base_gold = 50000

        cost = {
            "timber": int(base_wood * (target_tier**1.5)),
            "stone": int(base_stone * (target_tier**1.5)),
            "gold": int(base_gold * (target_tier**1.5)),
        }

        # Special Material: Spirit Shard
        if target_tier >= 3:
            cost["special_key"] = "magma_core"
            cost["special_name"] = "Magma Core"
            cost["special_qty"] = target_tier - 1  # T3=2, T4=3, T5=4

        return cost

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.stop()

    def setup_ui(self):
        self.clear_items()

        mult = int((self._get_multiplier() - 1) * 100)
        bonus_str = f" (+{mult}%)" if mult > 0 else ""

        # 1. Caches
        btn_equip = ui.Button(
            label=f"Equipment{bonus_str}", style=ButtonStyle.primary, emoji="🎒"
        )
        btn_equip.callback = self.buy_equip_cache
        self.add_item(btn_equip)

        btn_rune = ui.Button(
            label=f"Runes{bonus_str}", style=ButtonStyle.primary, emoji="💎"
        )
        btn_rune.callback = self.buy_rune_cache
        self.add_item(btn_rune)

        btn_key = ui.Button(
            label=f"Keys{bonus_str}", style=ButtonStyle.primary, emoji="🗝️"
        )
        btn_key.callback = self.buy_key_cache
        self.add_item(btn_key)

        # 2. Bulk trade-in
        btn_bulk = ui.Button(
            label="Bulk Trade-In", style=ButtonStyle.secondary, emoji="📦", row=1
        )
        btn_bulk.callback = self.open_bulk_trade
        self.add_item(btn_bulk)

        # 3. Upgrade Button
        if self.building.tier < 5:
            btn_up = ui.Button(
                label="Upgrade Facility", style=ButtonStyle.success, emoji="⬆️", row=1
            )
            btn_up.callback = self.upgrade_facility
            self.add_item(btn_up)
        else:
            btn_max = ui.Button(
                label="Max Level", style=ButtonStyle.success, disabled=True, row=1
            )
            self.add_item(btn_max)

        # Back
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    def build_embed(self):
        tier = self.building.tier
        mult = self._get_multiplier()

        embed = discord.Embed(
            title=f"🕵️ The Black Market (Tier {tier})", color=discord.Color.dark_gray()
        )
        embed.description = f"**Loot Bonus:** {int((mult-1)*100)}%\nGoods acquired through... unconventional means.\n"

        embed.add_field(
            name="🎒 Equipment Cache",
            value="**Cost:** 2,500,000 Gold\n**Contents:** 1 Random Equipment (ilvl capped at 100)",
            inline=False,
        )
        embed.add_field(
            name="💎 Rune Cache",
            value="**Cost:** 1 Refinement Rune, 1 Potential Rune, 1 Shatter Rune\n**Contents:** 1-5 Random Runes",
            inline=False,
        )
        embed.add_field(
            name="🗝️ Boss Key Cache",
            value="**Cost:** 1 Void Key\n**Contents:** 1-5 Random Boss Keys",
            inline=False,
        )

        if tier < 5:
            costs = self._get_upgrade_cost(tier + 1)
            cost_str = (
                f"🪵 {costs['timber']:,} | 🪨 {costs['stone']:,} | 💰 {costs['gold']:,}"
            )
            if "special_key" in costs:
                cost_str += f" | ✨ {costs['special_name']} x{costs['special_qty']}"
            embed.add_field(name="Next Upgrade Cost", value=cost_str, inline=False)

        embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["black_market"])
        return embed

    async def upgrade_facility(self, interaction: Interaction):
        target_tier = self.building.tier + 1
        costs = self._get_upgrade_cost(target_tier)

        # 1. Check Settlement Resources
        if (
            self.parent.settlement.timber < costs["timber"]
            or self.parent.settlement.stone < costs["stone"]
        ):
            return await interaction.response.send_message(
                "Insufficient Timber or Stone!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < costs["gold"]:
            return await interaction.response.send_message(
                "Insufficient Gold!", ephemeral=True
            )

        if "special_key" in costs:
            col = costs["special_key"]
            req = costs["special_qty"]
            async with self.bot.database.connection.execute(
                f"SELECT {col} FROM users WHERE user_id = ?", (self.user_id,)
            ) as c:
                owned = (await c.fetchone())[0]
            if owned < req:
                return await interaction.response.send_message(
                    f"Need {req}x {costs['special_name']}!", ephemeral=True
                )

            await self.bot.database.users.modify_currency(self.user_id, col, -req)

        await interaction.response.defer()

        # 2. Consume Resources
        changes = {
            "timber": -costs["timber"],
            "stone": -costs["stone"],
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -costs["gold"])

        # 3. Update DB
        await self.bot.database.connection.execute(
            "UPDATE buildings SET tier = tier + 1 WHERE id = ?", (self.building.id,)
        )
        await self.bot.database.connection.commit()

        # 4. Update Local State
        self.building.tier += 1
        self.parent.settlement.timber -= costs["timber"]
        self.parent.settlement.stone -= costs["stone"]

        # 5. Refresh
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def buy_equip_cache(self, interaction: Interaction):
        uid, sid = self.user_id, self.parent.server_id
        cost = 2_500_000
        data = await self.bot.database.users.get(uid, sid)
        if not await self.bot.check_user_registered(interaction, data):
            return

        gold = await self.bot.database.users.get_gold(uid)
        if gold < cost:
            return await interaction.response.send_message(
                f"Not enough Gold! Need {cost:,}g.", ephemeral=True
            )

        player = await load_player(uid, data, self.bot.database)
        await interaction.response.defer()

        await self.bot.database.users.modify_gold(uid, -cost)

        ilvl = min(player.level, 100)
        slot = random.choices(
            population=["weapon", "armor", "accessory", "glove", "boot", "helmet"],
            weights=[35, 10, 25, 10, 10, 10],
            k=1,
        )[0]

        item = None
        if slot == "weapon":
            item = await generate_weapon(uid, ilvl, False)
            await self.bot.database.equipment.create_weapon(item)
        elif slot == "armor":
            item = await generate_armor(uid, ilvl, False)
            await self.bot.database.equipment.create_armor(item)
        elif slot == "accessory":
            item = await generate_accessory(uid, ilvl, False)
            await self.bot.database.equipment.create_accessory(item)
        elif slot == "glove":
            item = await generate_glove(uid, ilvl)
            await self.bot.database.equipment.create_glove(item)
        elif slot == "boot":
            item = await generate_boot(uid, ilvl)
            await self.bot.database.equipment.create_boot(item)
        elif slot == "helmet":
            item = await generate_helmet(uid, ilvl)
            await self.bot.database.equipment.create_helmet(item)

        name = item.name if item else "Nothing"
        await interaction.followup.send(f"📦 **Cache Opened:**\n{name}", ephemeral=True)

    async def buy_rune_cache(self, interaction: Interaction):
        uid = self.user_id
        owned_ref = await self.bot.database.users.get_currency(uid, "refinement_runes")
        owned_pot = await self.bot.database.users.get_currency(uid, "potential_runes")
        owned_sha = await self.bot.database.users.get_currency(uid, "shatter_runes")

        if owned_ref < 1 or owned_pot < 1 or owned_sha < 1:
            return await interaction.response.send_message(
                "Need 1 Refinement Rune, 1 Potential Rune, and 1 Shatter Rune!",
                ephemeral=True,
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_currency(uid, "refinement_runes", -1)
        await self.bot.database.users.modify_currency(uid, "potential_runes", -1)
        await self.bot.database.users.modify_currency(uid, "shatter_runes", -1)

        base_qty = random.randint(1, 5)
        final_qty = int(base_qty * self._get_multiplier())
        rewards = []
        rune_pool = ["refinement_runes", "potential_runes", "shatter_runes"]
        for _ in range(final_qty):
            rtype = random.choice(rune_pool)
            await self.bot.database.users.modify_currency(uid, rtype, 1)
            label = rtype.replace("_runes", "").replace("_", " ").title() + " Rune"
            rewards.append(label)

        await interaction.followup.send(
            f"💎 **Rune Cache Opened:**\n{', '.join(rewards)}", ephemeral=True
        )

    async def buy_key_cache(self, interaction: Interaction):
        cost = 1
        owned = await self.bot.database.users.get_currency(self.user_id, "void_keys")

        if owned < cost:
            return await interaction.response.send_message(
                "Not enough Void Keys!", ephemeral=True
            )

        await interaction.response.defer()
        await self.bot.database.users.modify_currency(self.user_id, "void_keys", -cost)

        base_qty = random.randint(1, 5)
        final_qty = int(base_qty * self._get_multiplier())
        rewards = []
        for _ in range(final_qty):
            ktype = random.choice(
                ["dragon_key", "angel_key", "soul_cores", "balance_fragment"]
            )
            await self.bot.database.users.modify_currency(self.user_id, ktype, 1)
            rewards.append(ktype.replace("_", " ").title())

        await interaction.followup.send(
            f"🗝️ **Boss Cache Opened:**\n{', '.join(rewards)}", ephemeral=True
        )

    async def open_bulk_trade(self, interaction: Interaction):
        class TradeSelect(ui.Select):
            def __init__(self_inner):
                options = [
                    SelectOption(
                        label="Equipment Cache",
                        description="2.5M Gold each",
                        emoji="🎒",
                        value="equip",
                    ),
                    SelectOption(
                        label="Rune Cache",
                        description="1 each: Refine/Potential/Shatter Rune",
                        emoji="💎",
                        value="rune",
                    ),
                    SelectOption(
                        label="Boss Key Cache",
                        description="1 Void Key each",
                        emoji="🗝️",
                        value="key",
                    ),
                ]
                super().__init__(
                    placeholder="Select trade type...",
                    options=options,
                    min_values=1,
                    max_values=1,
                )

            async def callback(self_inner, inner_interaction: Interaction):
                modal = BulkTradeModal(self, self_inner.values[0])
                await inner_interaction.response.send_modal(modal)

        select_view = ui.View(timeout=600)
        select_view.add_item(TradeSelect())
        await interaction.response.send_message(
            "Select which trade to bulk execute:", view=select_view, ephemeral=True
        )

    async def _bulk_equip_cache(self, interaction: Interaction, requested: int):
        uid, sid = self.user_id, self.parent.server_id
        cost_per = 2_500_000

        gold = await self.bot.database.users.get_gold(uid)
        possible = min(requested, gold // cost_per)
        if possible <= 0:
            return await interaction.followup.send(
                f"Not enough Gold for even one Equipment Cache (need {cost_per:,}g each).",
                ephemeral=True,
            )

        total_cost = possible * cost_per
        await self.bot.database.users.modify_gold(uid, -total_cost)

        data = await self.bot.database.users.get(uid, sid)
        player = await load_player(uid, data, self.bot.database)
        ilvl = min(player.level, 100)

        log = []
        for _ in range(possible):
            slot = random.choices(
                ["weapon", "armor", "accessory", "glove", "boot", "helmet"],
                weights=[35, 10, 25, 10, 10, 10],
                k=1,
            )[0]
            item = None
            if slot == "weapon":
                item = await generate_weapon(uid, ilvl, False)
                await self.bot.database.equipment.create_weapon(item)
            elif slot == "armor":
                item = await generate_armor(uid, ilvl, False)
                await self.bot.database.equipment.create_armor(item)
            elif slot == "accessory":
                item = await generate_accessory(uid, ilvl, False)
                await self.bot.database.equipment.create_accessory(item)
            elif slot == "glove":
                item = await generate_glove(uid, ilvl)
                await self.bot.database.equipment.create_glove(item)
            elif slot == "boot":
                item = await generate_boot(uid, ilvl)
                await self.bot.database.equipment.create_boot(item)
            elif slot == "helmet":
                item = await generate_helmet(uid, ilvl)
                await self.bot.database.equipment.create_helmet(item)
            if item:
                log.append(item.name)

        unused = requested - possible
        msg = (
            f"📦 **Bulk Equipment Cache** ({possible}x opened)\n"
            f"**Consumed:** {total_cost:,} Gold\n"
            f"**Received:** {', '.join(log) or 'Nothing'}"
        )
        if unused > 0:
            msg += f"\n*({unused} trades skipped — insufficient gold)*"
        await interaction.followup.send(msg, ephemeral=True)

    async def _bulk_rune_cache(self, interaction: Interaction, requested: int):
        uid = self.user_id
        owned_ref = await self.bot.database.users.get_currency(uid, "refinement_runes")
        owned_pot = await self.bot.database.users.get_currency(uid, "potential_runes")
        owned_sha = await self.bot.database.users.get_currency(uid, "shatter_runes")
        possible = min(requested, owned_ref, owned_pot, owned_sha)

        if possible <= 0:
            return await interaction.followup.send(
                "Need 1 of each rune (Refinement, Potential, Shatter) per cache.",
                ephemeral=True,
            )

        await self.bot.database.users.modify_currency(
            uid, "refinement_runes", -possible
        )
        await self.bot.database.users.modify_currency(uid, "potential_runes", -possible)
        await self.bot.database.users.modify_currency(uid, "shatter_runes", -possible)

        rune_pool = ["refinement_runes", "potential_runes", "shatter_runes"]
        rewards = []
        for _ in range(possible):
            base_qty = random.randint(1, 5)
            final_qty = int(base_qty * self._get_multiplier())
            for _ in range(final_qty):
                rtype = random.choice(rune_pool)
                await self.bot.database.users.modify_currency(uid, rtype, 1)
                label = rtype.replace("_runes", "").replace("_", " ").title() + " Rune"
                rewards.append(label)

        from collections import Counter

        tally = Counter(rewards)
        tally_str = ", ".join(f"{v}x {k}" for k, v in tally.items())

        unused = requested - possible
        msg = (
            f"💎 **Bulk Rune Cache** ({possible}x opened)\n"
            f"**Consumed:** {possible}x each Refinement/Potential/Shatter Rune\n"
            f"**Received:** {tally_str or 'Nothing'}"
        )
        if unused > 0:
            msg += f"\n*({unused} trades skipped — insufficient runes)*"
        await interaction.followup.send(msg, ephemeral=True)

    async def _bulk_key_cache(self, interaction: Interaction, requested: int):
        uid = self.user_id
        owned = await self.bot.database.users.get_currency(uid, "void_keys")
        possible = min(requested, owned)

        if possible <= 0:
            return await interaction.followup.send(
                "No Void Keys available.", ephemeral=True
            )

        await self.bot.database.users.modify_currency(uid, "void_keys", -possible)

        rewards = []
        for _ in range(possible):
            base_qty = random.randint(1, 5)
            final_qty = int(base_qty * self._get_multiplier())
            for _ in range(final_qty):
                ktype = random.choice(
                    ["dragon_key", "angel_key", "soul_cores", "balance_fragment"]
                )
                await self.bot.database.users.modify_currency(uid, ktype, 1)
                rewards.append(ktype.replace("_", " ").title())

        from collections import Counter

        tally = Counter(rewards)
        tally_str = ", ".join(f"{v}x {k}" for k, v in tally.items())

        unused = requested - possible
        msg = (
            f"🗝️ **Bulk Boss Key Cache** ({possible}x opened)\n"
            f"**Consumed:** {possible} Void Key(s)\n"
            f"**Received:** {tally_str or 'Nothing'}"
        )
        if unused > 0:
            msg += f"\n*({unused} trades skipped — only had {owned} Void Keys)*"
        await interaction.followup.send(msg, ephemeral=True)

    async def go_back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


class TownHallView(ui.View):
    def __init__(self, bot, user_id, settlement, parent_view):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.settlement = settlement
        self.parent = parent_view
        self.setup_ui()

    async def on_timeout(self):
        try:
            expired_embed = discord.Embed(
                title="Town Hall Session Expired",
                description="This Town Hall management session has timed out.\n\n"
                "Reopen your settlement dashboard to manage it again.",
                color=discord.Color.dark_grey(),
            )
            await self.parent.message.edit(embed=expired_embed, view=None)
        except:
            pass
        finally:
            self.stop()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    def build_embed(self):
        tier = self.settlement.town_hall_tier
        slots = self.settlement.building_slots

        # Calculate next tier benefits
        next_slots = slots + 1

        desc = (
            f"**Level:** {tier}/5\n"
            f"**Building Slots:** {slots}\n"
            f"**Follower Cap Buff:** +{tier * 10}%\n"
        )

        embed = discord.Embed(
            title="🏛️ Town Hall", description=desc, color=discord.Color.dark_blue()
        )

        if tier < 5:
            costs = self._get_upgrade_cost(tier + 1)
            cost_str = (
                f"🪵 {costs['timber']:,} | 🪨 {costs['stone']:,} | 💰 {costs['gold']:,}"
            )

            # Format multiple special materials
            if "specials" in costs:
                reqs = [f"{s['name']} x{s['qty']}" for s in costs["specials"]]
                cost_str += f"\n✨ **Requires:** {', '.join(reqs)}"

            embed.add_field(
                name="Upgrade Benefits",
                value=f"Slots: {slots} ➡️ **{next_slots}**",
                inline=False,
            )
            embed.add_field(name="Upgrade Cost", value=cost_str, inline=False)
        else:
            embed.add_field(
                name="Status", value="🌟 Maximum Authority Reached", inline=False
            )
        embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["town_hall"])
        return embed

    def setup_ui(self):
        self.clear_items()

        btn_up = ui.Button(
            label="Upgrade Hall",
            style=ButtonStyle.success,
            emoji="⬆️",
            disabled=(self.settlement.town_hall_tier >= 5),
        )
        btn_up.callback = self.upgrade
        self.add_item(btn_up)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def upgrade(self, interaction: Interaction):
        target_tier = self.settlement.town_hall_tier + 1
        costs = self._get_upgrade_cost(target_tier)

        # 1. Check Resources
        if (
            self.settlement.timber < costs["timber"]
            or self.settlement.stone < costs["stone"]
        ):
            return await interaction.response.send_message(
                "Insufficient Timber or Stone!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < costs["gold"]:
            return await interaction.response.send_message(
                "Insufficient Gold!", ephemeral=True
            )

        # 2. Check multiple special materials safely
        if "specials" in costs:
            # Validate ALL balances before deducting any to prevent partial consumption on failure
            for sp in costs["specials"]:
                async with self.bot.database.connection.execute(
                    f"SELECT {sp['key']} FROM users WHERE user_id = ?", (self.user_id,)
                ) as c:
                    owned = (await c.fetchone())[0]

                if owned < sp["qty"]:
                    return await interaction.response.send_message(
                        f"Need {sp['qty']}x {sp['name']}! (You have {owned})",
                        ephemeral=True,
                    )

            # If all checks pass, deduct them
            for sp in costs["specials"]:
                await self.bot.database.users.modify_currency(
                    self.user_id, sp["key"], -sp["qty"]
                )

        await interaction.response.defer()

        # 3. Consume Resources
        changes = {
            "timber": -costs["timber"],
            "stone": -costs["stone"],
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -costs["gold"])

        # 4. Update DB (Settlements Table)
        await self.bot.database.connection.execute(
            """UPDATE settlements 
               SET town_hall_tier = town_hall_tier + 1, 
                   building_slots = building_slots + 1 
               WHERE user_id = ? AND server_id = ?""",
            (self.user_id, self.parent.server_id),
        )
        await self.bot.database.connection.commit()

        # 5. Update Local State & Refresh
        self.settlement.town_hall_tier += 1
        self.settlement.building_slots += 1
        self.settlement.timber -= costs["timber"]
        self.settlement.stone -= costs["stone"]
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        # We need to refresh the parent grid because slots might have increased
        self.parent.update_grid()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


class SettlementDashboardView(ui.View):
    def __init__(
        self, bot, user_id, server_id, settlement: Settlement, follower_count: int
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.settlement = settlement
        self.follower_count = follower_count
        self.update_grid()

    RESOURCE_DISPLAY_NAMES = {
        "timber": "Timber",
        "stone": "Stone",
        "gold": "Gold",
        "iron": "Iron Ore",
        "coal": "Coal",
        "platinum": "Platinum Ore",
        "idea": "Idea Ore",
        "iron_bar": "Iron Bars",
        "steel_bar": "Steel Bars",
        "gold_bar": "Gold Bars",
        "platinum_bar": "Platinum Bars",
        "idea_bar": "Idea Bars",
        "oak_logs": "Oak Logs",
        "willow_logs": "Willow Logs",
        "mahogany_logs": "Mahogany Logs",
        "magic_logs": "Magic Logs",
        "idea_logs": "Idea Logs",
        "oak_plank": "Oak Planks",
        "willow_plank": "Willow Planks",
        "mahogany_plank": "Mahogany Planks",
        "magic_plank": "Magic Planks",
        "idea_plank": "Idea Planks",
        "desiccated_bones": "Desiccated Bones",
        "regular_bones": "Regular Bones",
        "sturdy_bones": "Sturdy Bones",
        "reinforced_bones": "Reinforced Bones",
        "titanium_bones": "Titanium Bones",
        "desiccated_essence": "Desiccated Essence",
        "regular_essence": "Regular Essence",
        "sturdy_essence": "Sturdy Essence",
        "reinforced_essence": "Reinforced Essence",
        "titanium_essence": "Titanium Essence",
    }

    def _format_changes(self, changes: dict) -> str:
        positive_items = []
        for key, value in changes.items():
            if value <= 0:
                continue
            name = self.RESOURCE_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            emoji = ""
            if key == "timber":
                emoji = "🪵 "
            elif key == "stone":
                emoji = "🪨 "
            elif key == "gold":
                emoji = "💰 "
            positive_items.append(f"{emoji}{name}: +{value:,}")

        if not positive_items:
            return "No resources produced (no workers, generators, or raw materials)."

        return "\n".join(positive_items)

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            expired_embed = discord.Embed(
                title="Settlement Session Expired",
                description="This settlement management session has timed out.\n\n"
                "Run the command again to reopen the dashboard.",
                color=discord.Color.dark_grey(),
            )
            await self.message.edit(embed=expired_embed, view=None)
        except:
            pass

    def build_embed(self) -> discord.Embed:
        workers_used = sum(b.workers_assigned for b in self.settlement.buildings)

        embed = discord.Embed(title="Town Hall", color=discord.Color.dark_green())
        embed.description = (
            f"**Tier {self.settlement.town_hall_tier}** Settlement\n"
            f"👥 **Workforce:** {workers_used}/{self.follower_count}\n"
            f"🪵 **Timber:** {self.settlement.timber:,}\n"
            f"🪨 **Stone:** {self.settlement.stone:,}"
        )
        embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["town_hall"])

        if self.settlement.buildings:
            lines = []
            for b in self.settlement.buildings:
                status = "🟢" if b.workers_assigned > 0 else "🔴"
                if b.name == "Black Market":
                    status = "⚫"
                lines.append(f"• **{b.name}** (T{b.tier}) {status}")
            embed.add_field(name="Buildings", value="\n".join(lines), inline=False)
        else:
            embed.add_field(
                name="Buildings", value="No buildings constructed yet.", inline=False
            )

        return embed

    def update_grid(self):
        self.clear_items()

        built_map = {b.slot_index: b for b in self.settlement.buildings}

        # Row 0 — Select dropdown (all slots: built + empty)
        options = []
        for i in range(self.settlement.building_slots):
            if i in built_map:
                b = built_map[i]
                status = "🟢" if b.workers_assigned > 0 else "🔴"
                if b.name == "Black Market":
                    status = "⚫"
                options.append(
                    SelectOption(
                        label=f"{b.name} (T{b.tier})",
                        value=f"built_{i}",
                        description=f"Workers: {b.workers_assigned} | Status: {status}",
                        emoji=status,
                    )
                )
            else:
                options.append(
                    SelectOption(
                        label=f"Slot {i+1} — Empty",
                        value=f"empty_{i}",
                        description="Click to construct a new building",
                        emoji="🔨",
                    )
                )

        if options:
            select = ui.Select(
                placeholder="Select a building to manage...",
                options=options,
                row=0,
            )

            async def _on_select(interaction: Interaction, s=select):
                value = s.values[0]
                if value.startswith("built_"):
                    slot = int(value.split("_")[1])
                    await self.open_building(interaction, built_map[slot])
                else:
                    slot = int(value.split("_")[1])
                    await self.open_build_menu(interaction, slot)

            select.callback = _on_select
            self.add_item(select)

        # Row 1 — Controls
        th_btn = ui.Button(
            label=f"Town Hall (T{self.settlement.town_hall_tier})",
            style=ButtonStyle.primary,
            row=1,
            emoji="🏛️",
        )
        th_btn.callback = self.open_town_hall
        self.add_item(th_btn)

        collect_btn = ui.Button(
            label="Collect", style=ButtonStyle.success, row=1, emoji="🚜"
        )
        collect_btn.callback = self.collect_resources
        self.add_item(collect_btn)

        guide_btn = ui.Button(
            label="Guide", style=ButtonStyle.secondary, row=1, emoji="📖"
        )
        guide_btn.callback = self.show_guide
        self.add_item(guide_btn)

        close_btn = ui.Button(label="Close", style=ButtonStyle.danger, row=1)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    async def show_guide(self, interaction: Interaction):
        embed = discord.Embed(title="📖 Building Guide", color=discord.Color.blue())
        for btype, info in BuildConstructionView.BUILDING_INFO.items():
            embed.add_field(
                name=btype.replace("_", " ").title(),
                value=info,
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def open_town_hall(self, interaction: Interaction):
        view = TownHallView(self.bot, self.user_id, self.settlement, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_build_menu(self, interaction: Interaction, slot_index: int):
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, self.server_id
        )
        view = BuildConstructionView(
            self.bot, self.user_id, slot_index, self, uber_prog
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_building(self, interaction: Interaction, building: Building):
        if building.building_type == "black_market":
            view = BlackMarketView(self.bot, self.user_id, self, building)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)
        else:
            view = BuildingDetailView(self.bot, self.user_id, building, self)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def collect_resources(self, interaction: Interaction):
        await interaction.response.defer()

        uid, sid = self.user_id, self.server_id

        # 1. Fetch inventory for limiting logic
        mining = await self.bot.database.skills.get_data(uid, sid, "mining")
        wood = await self.bot.database.skills.get_data(uid, sid, "woodcutting")
        fish = await self.bot.database.skills.get_data(uid, sid, "fishing")

        raw_inv = {
            "iron": mining[3],
            "coal": mining[4],
            "gold": mining[5],
            "platinum": mining[6],
            "idea": mining[7],
            "oak_logs": wood[3],
            "willow_logs": wood[4],
            "mahogany_logs": wood[5],
            "magic_logs": wood[6],
            "idea_logs": wood[7],
            "desiccated_bones": fish[3],
            "regular_bones": fish[4],
            "sturdy_bones": fish[5],
            "reinforced_bones": fish[6],
            "titanium_bones": fish[7],
        }

        # 2. Calculate time elapsed
        now = datetime.now()
        last = datetime.fromisoformat(self.settlement.last_collection_time)
        hours = (now - last).total_seconds() / 3600

        if hours < 0.1:  # Minimum 6 minutes
            return await interaction.followup.send(
                "Your workers haven't generated anything yet.", ephemeral=True
            )

        # 3. Calculate changes
        total_changes: dict[str, int] = {}
        for b in self.settlement.buildings:
            changes = SettlementMechanics.calculate_production(
                b.building_type, b.tier, b.workers_assigned, hours, raw_inv
            )
            for k, v in changes.items():
                total_changes[k] = total_changes.get(k, 0) + v
                if k in raw_inv:
                    raw_inv[k] += v

        print("DEBUG total_changes AFTER MERGE:", total_changes)

        # Make a copy specifically for display (so you can filter it safely)
        display_changes = dict(total_changes)

        cookie_xp = 0
        if "companion_cookie" in total_changes:
            cookies = total_changes.pop("companion_cookie")
            cookie_xp = cookies

            if "companion_cookie" in display_changes:
                display_changes["Companion XP"] = display_changes.pop(
                    "companion_cookie"
                )

        # Pop market gold before committing to skill tables (it belongs in users.gold)
        market_gold = 0
        if "market_gold" in total_changes:
            market_gold = total_changes.pop("market_gold")
            display_changes["Market Gold"] = display_changes.pop(
                "market_gold", market_gold
            )

        # 4. Commit to DB with the full changes
        await self.bot.database.settlement.commit_production(uid, sid, total_changes)
        if market_gold > 0:
            await self.bot.database.users.modify_gold(uid, market_gold)
        await self.bot.database.settlement.update_collection_timer(uid, sid)

        # Commit companion XP
        xp_msg = ""
        if cookie_xp > 0:
            active_rows = await self.bot.database.companions.get_active(self.user_id)
            if active_rows:
                xp_per_pet = cookie_xp // len(active_rows)
                for row in active_rows:
                    comp_id, cur_lvl, cur_exp = row[0], row[5], row[6]

                    # Add XP
                    cur_exp += xp_per_pet
                    # Level logic
                    while cur_lvl < 100:
                        req = CompanionMechanics.calculate_next_level_xp(cur_lvl)
                        if cur_exp >= req:
                            cur_exp -= req
                            cur_lvl += 1
                        else:
                            break
                    await self.bot.database.companions.update_stats(
                        comp_id, cur_lvl, cur_exp
                    )

                xp_msg = f"\n🐾 **Companion Ranch:** Distributed {cookie_xp:,} XP among active pets."

        # 5. Update local settlement state
        self.settlement.timber += display_changes.get("timber", 0)
        self.settlement.stone += display_changes.get("stone", 0)
        self.settlement.last_collection_time = now.isoformat()

        # 6. Build updated embed
        embed = self.build_embed()

        # 7. Use display_changes for the Last Collection field
        formatted_changes = self._format_changes(display_changes) + xp_msg
        embed.add_field(
            name="Last Collection",
            value=(
                f"⏱️ Time since last collection: {hours:.2f} hours\n\n"
                f"📦 Yield:\n{formatted_changes}"
            ),
            inline=False,
        )

        # 8. Content message depending on whether anything positive was produced
        has_positive = any(v > 0 for v in display_changes.values())
        if has_positive:
            content = "✅ **Collection Complete**"
        else:
            content = "ℹ️ Collection complete, but no resources were produced."

        await interaction.edit_original_response(embed=embed, view=self)
        await asyncio.sleep(1.0)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


class BuildConstructionView(ui.View):
    # Class-level definitions for easy access in embed generation
    BUILDING_INFO = {
        "logging_camp": "Generates Timber over time.",
        "quarry": "Generates Stone over time.",
        "foundry": "Converts Ore into Ingots (for high-tier crafting).",
        "sawmill": "Converts Logs into Planks (for settlement upgrades).",
        "reliquary": "Converts Bones into Essence (for enchantments).",
        "market": "Generates Passive Gold based on workforce size.",
        "barracks": "Passive: +0.01% Base Atk/Def per assigned Worker.",
        "temple": "Passive: +0.05% Propagate follower gain per assigned Worker.",
        "apothecary": "Passive: Increases Potion Healing (+0.2 HP per assigned Worker).",
        "black_market": "Special: Trade resources for Caches.",
        "companion_ranch": "Generator: Produces XP Cookies for pets.",
        "celestial_shrine": "Passive: Increases chance to find Celestial Sigils from Aphrodite.",
        "infernal_forge": "Passive: Increases chance to find Infernal Sigils from Lucifer.",
        "void_sanctum": "Passive: Increases chance to find Void Sigils from NEET.",
        "twin_shrine": "Passive: Increases chance to find Gemini Sigils from the Gemini Twins.",
    }

    def __init__(self, bot, user_id, slot_index, parent_view, uber_prog):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.slot_index = slot_index
        self.parent = parent_view
        self.uber_prog = uber_prog

        self.COSTS = {
            "logging_camp": {"gold": 100, "stone": 0},
            "quarry": {"gold": 100, "timber": 0},
            "foundry": {"gold": 5000, "timber": 200, "stone": 200},
            "sawmill": {"gold": 5000, "timber": 200, "stone": 200},
            "reliquary": {"gold": 5000, "timber": 200, "stone": 200},
            "market": {"gold": 10000, "timber": 500, "stone": 500},
            "barracks": {"gold": 15000, "timber": 1000, "stone": 1000},
            "temple": {"gold": 20000, "timber": 1500, "stone": 1500},
            "apothecary": {"gold": 25000, "timber": 2000, "stone": 2000},
            "black_market": {"gold": 50000, "timber": 5000, "stone": 5000},
            "companion_ranch": {"gold": 30000, "timber": 3000, "stone": 3000},
            "celestial_shrine": {"gold": 100000, "timber": 100000, "stone": 100000},
            "infernal_forge": {"gold": 100000, "timber": 100000, "stone": 100000},
            "void_sanctum": {"gold": 100000, "timber": 100000, "stone": 100000},
            "twin_shrine": {"gold": 100000, "timber": 100000, "stone": 100000},
        }

        self.setup_select()

    def build_embed(self):
        embed = discord.Embed(
            title="🏗️ Construction Site",
            description="Select a blueprint to begin construction.\n\n__**Available Blueprints**__",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=SETTLEMENT_HUB)
        existing_types = {b.building_type for b in self.parent.settlement.buildings}

        UBER_LOCKS = {
            "celestial_shrine": self.uber_prog["celestial_blueprint_unlocked"] == 0,
            "infernal_forge": self.uber_prog.get("infernal_blueprint_unlocked", 0) == 0,
            "void_sanctum": self.uber_prog.get("void_blueprint_unlocked", 0) == 0,
            "twin_shrine": self.uber_prog.get("gemini_blueprint_unlocked", 0) == 0,
        }

        for b_type, info in self.BUILDING_INFO.items():
            # Skip uber buildings whose blueprint hasn't been unlocked yet
            if UBER_LOCKS.get(b_type, False):
                continue

            # Formatting
            name = b_type.replace("_", " ").title()
            cost = self.COSTS[b_type]

            cost_str = f"💰 {cost.get('gold', 0):,}"
            if cost.get("timber"):
                cost_str += f" | 🪵 {cost['timber']}"
            if cost.get("stone"):
                cost_str += f" | 🪨 {cost['stone']}"

            status_icon = "✅"
            if b_type in existing_types:
                status_icon = "🔒 (Already Built)"

            # Add field
            embed.add_field(
                name=f"{status_icon} {name}",
                value=f"{info}\n*Cost: {cost_str}*",
                inline=False,
            )

        return embed

    async def on_timeout(self):
        try:
            expired_embed = discord.Embed(
                title="Construction Menu Expired",
                description="This construction selection session has timed out.\n\n"
                "Open the empty slot again from the settlement dashboard to build.",
                color=discord.Color.dark_grey(),
            )
            await self.parent.message.edit(embed=expired_embed, view=None)
        except:
            pass
        finally:
            self.stop()

    def setup_select(self):
        self.clear_items()

        existing_types = {b.building_type for b in self.parent.settlement.buildings}
        options = []

        for key, cost in self.COSTS.items():
            if key in existing_types:
                continue

            if (
                key == "celestial_shrine"
                and self.uber_prog["celestial_blueprint_unlocked"] == 0
            ):
                continue

            if (
                key == "infernal_forge"
                and self.uber_prog.get("infernal_blueprint_unlocked", 0) == 0
            ):
                continue

            if (
                key == "void_sanctum"
                and self.uber_prog.get("void_blueprint_unlocked", 0) == 0
            ):
                continue

            if (
                key == "twin_shrine"
                and self.uber_prog.get("gemini_blueprint_unlocked", 0) == 0
            ):
                continue

            lbl = key.replace("_", " ").title()
            # Brief description for dropdown
            desc = f"Cost: {cost.get('gold',0)}g"
            if cost.get("timber"):
                desc += f", {cost['timber']} Wood"
            if cost.get("stone"):
                desc += f", {cost['stone']} Stone"

            options.append(SelectOption(label=lbl, value=key, description=desc))

        if not options:
            self.add_item(
                ui.Button(
                    label="No New Blueprints Available",
                    style=ButtonStyle.gray,
                    disabled=True,
                )
            )
        else:
            select = ui.Select(placeholder="Select Blueprint...", options=options)
            select.callback = self.on_select
            self.add_item(select)

        cancel = ui.Button(label="Cancel", style=ButtonStyle.danger)
        cancel.callback = self.cancel
        self.add_item(cancel)

    async def on_select(self, interaction: Interaction):
        b_type = interaction.data["values"][0]
        cost = self.COSTS[b_type]

        used_slots = len(self.parent.settlement.buildings)
        max_slots = self.parent.settlement.building_slots

        if used_slots >= max_slots:
            return await interaction.response.send_message(
                "No building slots remaining! Upgrade your Town Hall to build more.",
                ephemeral=True,
            )

        # Check Funds
        u_gold = await self.bot.database.users.get_gold(self.user_id)
        u_timber = self.parent.settlement.timber
        u_stone = self.parent.settlement.stone

        if (
            u_gold < cost.get("gold", 0)
            or u_timber < cost.get("timber", 0)
            or u_stone < cost.get("stone", 0)
        ):
            return await interaction.response.send_message(
                "Insufficient resources!", ephemeral=True
            )

        await interaction.response.defer()

        # Deduct
        changes = {
            "timber": -cost.get("timber", 0),
            "stone": -cost.get("stone", 0),
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -cost.get("gold", 0))

        # Build
        await self.bot.database.settlement.build_structure(
            self.user_id, self.parent.server_id, b_type, self.slot_index
        )

        # Update Parent
        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )
        self.parent.update_grid()

        await interaction.edit_original_response(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()

    async def cancel(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


class BuildingDetailView(ui.View):
    def __init__(self, bot, user_id, building: Building, parent_view):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.building = building
        self.parent = parent_view

        self.setup_ui()

    async def on_timeout(self):
        try:
            expired_embed = discord.Embed(
                title="Building Session Expired",
                description=f"Management for **{self.building.name}** has timed out.\n\n"
                "Open the building again from the settlement dashboard to continue.",
                color=discord.Color.dark_grey(),
            )
            await self.parent.message.edit(embed=expired_embed, view=None)
        except:
            pass
        finally:
            self.stop()

    SPECIAL_MAP = {
        "foundry": "magma_core",
        "quarry": "magma_core",
        "sawmill": "life_root",
        "barracks": "magma_core",
        "logging_camp": "life_root",
        "reliquary": "spirit_shard",
        "temple": "spirit_shard",
        "market": "spirit_shard",
        "town_hall": "spirit_shard",
        "apothecary": "life_root",
        "companion_ranch": "life_root",
        "celestial_shrine": "celestial_stone",
        "infernal_forge": "infernal_cinder",
        "void_sanctum": "void_crystal",
        "twin_shrine": "bound_crystal",
    }

    ITEM_NAMES = {
        "magma_core": "Magma Core",
        "life_root": "Life Root",
        "spirit_shard": "Spirit Shard",
        "celestial_stone": "Celestial Stone",
        "infernal_cinder": "Infernal Cinder",
        "void_crystal": "Void Crystal",
        "bound_crystal": "Bound Crystal",
    }

    THUMBNAILS = SETTLEMENT_BUILDINGS

    BUILDING_INFO = {
        "logging_camp": "Generates Timber. Required for upgrades.",
        "quarry": "Generates Stone. Required for upgrades.",
        "foundry": "Converts Ore -> Ingots (Crafting/Upgrades).",
        "sawmill": "Converts Logs -> Planks (Crafting/Upgrades).",
        "reliquary": "Converts Bones -> Essence (Crafting/Upgrades).",
        "market": "Generates Passive Gold based on workforce.",
        "barracks": "Passive: +0.01% Base Atk/Def per assigned Worker.",
        "temple": "Passive: +0.05% Propagate follower gain per assigned Worker.",
        "apothecary": "Passive: Increases Potion Healing (+0.2 HP per assigned Worker).",
        "black_market": "Special: Trade resources for Caches.",
        "companion_ranch": "Generator: Produces XP Cookies for pets.",
        "celestial_shrine": "Passive: Increases chance to find Celestial Sigils from Aphrodite.",
        "infernal_forge": "Passive: Increases chance to find Infernal Sigils from Lucifer.",
        "void_sanctum": "Passive: Increases chance to find Void Sigils from NEET.",
        "twin_shrine": "Passive: Increases chance to find Gemini Sigils from the Gemini Twins.",
    }

    def build_embed(self):
        b_data = SettlementMechanics.BUILDINGS.get(self.building.building_type)
        max_w = SettlementMechanics.get_max_workers(self.building.tier)

        # Calculate Rate Safely
        base_rate = b_data.get("base_rate", 0)
        rate = base_rate * self.building.tier * self.building.workers_assigned

        # Adjust description based on building type
        if b_data.get("type") in ["generator", "converter"]:
            output_name = (
                b_data.get("output", "Refined Goods").replace("_", " ").title()
            )
            desc = (
                f"**Level:** {self.building.tier}/5\n"
                f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
                f"**Output:** ~{rate}/hr ({output_name})"
            )
        else:
            desc = (
                f"**Level:** {self.building.tier}/5\n"
                f"**Workers:** {self.building.workers_assigned}/{max_w}\n"
                f"**Type:** {b_data.get('type', 'Passive').title()}"
            )

        embed = discord.Embed(
            title=f"{self.building.name}", description=desc, color=discord.Color.gold()
        )

        thumb = self.THUMBNAILS.get(self.building.building_type)
        if thumb:
            embed.set_thumbnail(url=thumb)

        info = self.BUILDING_INFO.get(self.building.building_type)
        if info:
            embed.add_field(name="Function", value=info, inline=False)

        # Upgrade Cost Preview
        next_cost = self._get_upgrade_cost(self.building.tier + 1)
        if self.building.tier < 5:
            cost_str = f"🪵 {next_cost.get('timber'):,} | 🪨 {next_cost.get('stone'):,} | 💰 {next_cost.get('gold'):,}"
            if "special_name" in next_cost:
                cost_str += (
                    f" | ✨ {next_cost['special_name']} x{next_cost['special_qty']}"
                )
            embed.add_field(name="Next Upgrade Cost", value=cost_str, inline=False)
        else:
            embed.add_field(name="Status", value="🌟 Max Level Reached", inline=False)
        return embed

    UBER_BUILDINGS = {
        "celestial_shrine",
        "infernal_forge",
        "void_sanctum",
        "twin_shrine",
    }

    def _get_upgrade_cost(self, target_tier):
        # Uber buildings use a flat linear formula: target_tier * 100k each
        if self.building.building_type in self.UBER_BUILDINGS:
            cost = {
                "timber": target_tier * 100_000,
                "stone": target_tier * 100_000,
                "gold": target_tier * 100_000,
            }
            # Special material required from T2+ (qty = target_tier - 1)
            special_col = self.SPECIAL_MAP.get(self.building.building_type)
            if special_col:
                cost["special_key"] = special_col
                cost["special_name"] = self.ITEM_NAMES.get(
                    special_col, "Special Material"
                )
                cost["special_qty"] = target_tier - 1
            return cost

        # Standard buildings: Base * Tier^1.5
        base_wood = 200
        base_stone = 200
        base_gold = 5000

        cost = {
            "timber": int(base_wood * (target_tier**1.5)),
            "stone": int(base_stone * (target_tier**1.5)),
            "gold": int(base_gold * (target_tier**1.5)),
        }

        # Special Materials (T3+)
        if target_tier >= 3:
            # Map building type -> db_column -> Display Name
            special_col = self.SPECIAL_MAP.get(
                self.building.building_type, "magma_core"
            )
            display_name = self.ITEM_NAMES.get(special_col, "Special Material")

            cost["special_key"] = special_col  # For DB logic
            cost["special_name"] = display_name  # For Display logic

            # Quantity Logic
            if target_tier == 3:
                cost["special_qty"] = 1
            elif target_tier == 4:
                cost["special_qty"] = 2
            elif target_tier == 5:
                cost["special_qty"] = 3

        return cost

    def setup_ui(self):
        self.clear_items()

        # Workers
        btn_workers = ui.Button(
            label="Assign Workers", style=ButtonStyle.primary, emoji="👥"
        )
        btn_workers.callback = self.manage_workers
        self.add_item(btn_workers)

        btn_max = ui.Button(label="Max Workers", style=ButtonStyle.primary, row=0)
        btn_max.callback = self.max_workers
        self.add_item(btn_max)

        # Upgrade
        btn_upgrade = ui.Button(
            label="Upgrade",
            style=ButtonStyle.success,
            emoji="⬆️",
            disabled=(self.building.tier >= 5),
        )
        btn_upgrade.callback = self.upgrade_building
        self.add_item(btn_upgrade)

        if self.building.building_type != "town_hall":
            btn_demo = ui.Button(label="Demolish", style=ButtonStyle.danger, row=1)
            btn_demo.callback = self.demolish_prompt
            self.add_item(btn_demo)

        # Back
        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def demolish_prompt(self, interaction: Interaction):
        """Swaps UI to ask for confirmation to prevent accidental deletion."""
        self.clear_items()

        confirm_btn = ui.Button(
            label="CONFIRM DEMOLISH", style=ButtonStyle.danger, emoji="⚠️"
        )
        confirm_btn.callback = self.execute_demolish
        self.add_item(confirm_btn)

        cancel_btn = ui.Button(label="Cancel", style=ButtonStyle.secondary)
        cancel_btn.callback = self.cancel_demolish
        self.add_item(cancel_btn)

        # Overwrite embed to show warning
        embed = self.build_embed()
        embed.color = discord.Color.red()
        embed.add_field(
            name="⚠️ DEMOLITION WARNING",
            value="Are you sure you want to demolish this building?\nWorkers will be returned, but **all materials spent on construction and upgrades will be permanently lost.**",
            inline=False,
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def cancel_demolish(self, interaction: Interaction):
        """Reverts back to the standard building UI."""
        self.setup_ui()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def execute_demolish(self, interaction: Interaction):
        """The actual database execution after confirmation."""
        await interaction.response.defer()

        # 1. Remove from DB
        await self.bot.database.connection.execute(
            "DELETE FROM buildings WHERE id = ?", (self.building.id,)
        )
        await self.bot.database.connection.commit()

        # 2. Update Local State
        self.parent.settlement.buildings = [
            b for b in self.parent.settlement.buildings if b.id != self.building.id
        ]

        # 3. Refresh Parent Grid
        self.parent.update_grid()

        await interaction.edit_original_response(
            content=f"💥 **{self.building.name}** has been demolished. Workers returned to pool.",
            embed=self.parent.build_embed(),
            view=self.parent,
        )
        self.stop()

    async def manage_workers(self, interaction: Interaction):
        modal = WorkerModal(self)
        await interaction.response.send_modal(modal)

    async def max_workers(self, interaction: Interaction):
        # Calculate Max Possible
        cap_per_building = SettlementMechanics.get_max_workers(self.building.tier)

        total_assigned_global = sum(
            b.workers_assigned for b in self.parent.settlement.buildings
        )
        currently_in_this = self.building.workers_assigned

        # Total free people in town
        free_followers = self.parent.follower_count - (
            total_assigned_global - currently_in_this
        )

        # We can fill up to the cap, or as many as we have free
        target_amount = min(cap_per_building, free_followers)

        if target_amount == self.building.workers_assigned:
            return await interaction.response.send_message(
                "Building already at optimal capacity.", ephemeral=True
            )

        await interaction.response.defer()

        await self.bot.database.settlement.assign_workers(
            self.building.id, target_amount
        )

        # Refresh settlement from DB to sync worker counts for all buildings
        self.parent.settlement = await self.bot.database.settlement.get_settlement(
            self.user_id, self.parent.server_id
        )

        # Refresh this building reference from the updated settlement
        for b in self.parent.settlement.buildings:
            if b.id == self.building.id:
                self.building = b
                break

        # Rebuild parent grid (so button labels & 🟢/🔴 match)
        self.parent.update_grid()

        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def upgrade_building(self, interaction: Interaction):
        target_tier = self.building.tier + 1
        costs = self._get_upgrade_cost(target_tier)

        # Check Settlement Resources
        if (
            self.parent.settlement.timber < costs["timber"]
            or self.parent.settlement.stone < costs["stone"]
        ):
            return await interaction.response.send_message(
                "Insufficient Timber or Stone!", ephemeral=True
            )

        # Check Gold
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < costs["gold"]:
            return await interaction.response.send_message(
                "Insufficient Gold!", ephemeral=True
            )

        # 3. Check Special Items (T3+)
        if "special_key" in costs:
            col = costs["special_key"]
            req = costs["special_qty"]

            # Explicitly check user's special inventory
            async with self.bot.database.connection.execute(
                f"SELECT {col} FROM users WHERE user_id = ?", (self.user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                owned = row[0] if row else 0

            if owned < req:
                return await interaction.response.send_message(
                    f"Missing Material: You need **{req}x {costs['special_name']}** (Owned: {owned})",
                    ephemeral=True,
                )

            # Prepare deduction
            await self.bot.database.users.modify_currency(self.user_id, col, -req)

        await interaction.response.defer()

        # Deduct
        changes = {
            "timber": -costs["timber"],
            "stone": -costs["stone"],
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -costs["gold"])

        # Upgrade DB
        await self.bot.database.connection.execute(
            "UPDATE buildings SET tier = tier + 1 WHERE id = ?", (self.building.id,)
        )

        # --- NEW: TOWN HALL SPECIAL EFFECT ---
        if self.building.building_type == "town_hall":
            # Town Hall upgrades increase max slots by 1 per tier
            await self.bot.database.connection.execute(
                "UPDATE settlements SET building_slots = building_slots + 1 WHERE user_id = ? AND server_id = ?",
                (self.user_id, self.parent.server_id),
            )
            # Update local state so UI reflects it immediately
            self.parent.settlement.building_slots += 1

        await self.bot.database.connection.commit()

        # Update Local
        self.building.tier += 1
        self.parent.settlement.timber -= costs["timber"]
        self.parent.settlement.stone -= costs["stone"]
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()


class WorkerModal(ui.Modal, title="Manage Workforce"):
    count = ui.TextInput(label="Number of Workers", min_length=1, max_length=4)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            val = int(self.count.value)
            if val < 0:
                raise ValueError

            # Validation: Cap check
            max_w = SettlementMechanics.get_max_workers(self.parent_view.building.tier)
            if val > max_w:
                return await interaction.response.send_message(
                    f"This building can only hold {max_w} workers.", ephemeral=True
                )

            # Validation: Total Available
            total_assigned_global = sum(
                b.workers_assigned for b in self.parent_view.parent.settlement.buildings
            )
            currently_in_this = self.parent_view.building.workers_assigned
            free_followers = self.parent_view.parent.follower_count - (
                total_assigned_global - currently_in_this
            )

            if val > free_followers:
                return await interaction.response.send_message(
                    f"You only have {free_followers} available followers.",
                    ephemeral=True,
                )

            # Update DB
            await self.parent_view.bot.database.settlement.assign_workers(
                self.parent_view.building.id, val
            )

            # Refresh settlement from DB so the grid state is accurate
            self.parent_view.parent.settlement = (
                await self.parent_view.bot.database.settlement.get_settlement(
                    self.parent_view.user_id, self.parent_view.parent.server_id
                )
            )

            # Update local building reference (same object, but we re-sync)
            # Find the updated building in the refreshed settlement
            for b in self.parent_view.parent.settlement.buildings:
                if b.id == self.parent_view.building.id:
                    self.parent_view.building = b
                    break

            # Rebuild parent grid so green/red icons match worker assignments
            self.parent_view.parent.update_grid()

            await interaction.response.edit_message(
                embed=self.parent_view.build_embed(), view=self.parent_view
            )

        except ValueError:
            await interaction.response.send_message("Invalid number.", ephemeral=True)
