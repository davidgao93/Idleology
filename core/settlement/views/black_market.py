# core/settlement/views/black_market.py
import random

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
from core.images import SETTLEMENT_BUILDINGS
from core.items.factory import load_player
from core.settlement.mechanics import SettlementMechanics

from .base import SettlementBaseView


class BulkTradeModal(ui.Modal):
    quantity = ui.TextInput(
        label="How many trades? (1-99)",
        placeholder="Enter a number e.g. 5",
        min_length=1,
        max_length=2,
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
        if self.trade_key == "equip":
            await mv._bulk_equip_cache(interaction, requested)
        elif self.trade_key == "rune":
            await mv._bulk_rune_cache(interaction, requested)
        elif self.trade_key == "key":
            await mv._bulk_key_cache(interaction, requested)


class BlackMarketView(SettlementBaseView):
    def __init__(self, bot, user_id, parent_view, building):
        super().__init__(bot, user_id)
        self.parent = parent_view
        self.building = building
        self.setup_ui()

    def _get_multiplier(self) -> float:
        return SettlementMechanics.get_multiplier(self.building.tier)

    def _get_upgrade_cost(self, target_tier):
        return SettlementMechanics.get_upgrade_cost("black_market", self.building.tier)

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

        embed.set_thumbnail(
            url=SETTLEMENT_BUILDINGS["black_market"]
        )  # still imported from main views for now
        return embed

    # ─────────────────────────────────────────────────────────────
    # All the original methods (buy_*, _bulk_*, upgrade_facility, etc.)
    # are copied exactly as they were — no changes needed.
    # ─────────────────────────────────────────────────────────────

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

        base_qty = random.randint(1, 3)
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
            base_qty = random.randint(1, 4)
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
