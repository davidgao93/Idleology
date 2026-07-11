"""
core/nether_market/views/hub_view.py — Nether Market Buy/Sell hub (the "Market" tab).
Browse and Mastery are separate sibling views navigated to via buttons (same
child-view-swap discipline as core/alchemy/views.py:AlchemyHubView).

Buy/Sell flow: clicking Buy/Sell swaps this same view's buttons for a select
dropdown of the active offers (the embed — gold, holdings, tiers, etc. — never
changes, so nothing needs to be reproduced). Selecting an item opens a quantity
Modal, which hands off to a separate ConfirmTransactionView ("Vex" confirms the
trade) -> back to a freshly rebuilt Hub.
"""

import time

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.emojis import NETHER_MARKET_PLUNDER
from core.hall_of_firsts import triggers as hof_triggers
from core.images import VEX_PORTRAIT, VEX_THUMBNAIL
from core.nether_market.data import WEALTH_TIERS
from core.nether_market.mechanics import MAX_CHARGES
from core.nether_market.mechanics import NetherMarketMechanics as M
from core.npc_voices import get_quip

_TIER_LABELS = (("cheap", "Cheap"), ("med", "Medium"), ("expensive", "Expensive"))
_VARIANT_LABELS = (("lo", "Bargain", "\U0001f516"), ("hi", "Premium", "\U0001f48e"))


def _iter_offers(rotation: dict, holdings: dict) -> list[dict]:
    """Flattens the rotation into one entry per active offer (6 total), each
    carrying its tier/variant labels, item data, price, and the player's held qty."""
    offers = []
    for tier_key, tier_label in _TIER_LABELS:
        for variant_key, variant_label, emoji in _VARIANT_LABELS:
            item_key = rotation[f"{tier_key}_{variant_key}_item"]
            price = rotation[f"{tier_key}_{variant_key}_price"]
            item = M.get_item(item_key)
            offers.append(
                {
                    "tier_key": tier_key,
                    "tier_label": tier_label,
                    "variant_key": variant_key,
                    "variant_label": variant_label,
                    "emoji": emoji,
                    "item_key": item_key,
                    "price": price,
                    "item": item,
                    "held": holdings.get(item_key, 0),
                }
            )
    return offers


async def build_hub_view(bot, user_id: str, server_id: str) -> "NetherMarketHubView":
    """Fetches all Nether Market state from the DB and returns a fresh hub view.
    Rolls an initial rotation on first-ever use for a server, and also re-rolls
    if an existing rotation predates the lo/hi expansion (NULL new columns)."""
    rotation = await bot.database.nether_market.get_rotation(server_id)
    if rotation is None or rotation.get("cheap_lo_item") is None:
        rolled = M.roll_rotation()
        await bot.database.nether_market.save_rotation(server_id, **rolled)
        rotation = await bot.database.nether_market.get_rotation(server_id)

    holdings = await bot.database.nether_market.get_holdings(user_id, server_id)
    profile = await bot.database.nether_market.get_or_create_profile(user_id, server_id)
    gold = await bot.database.users.get_gold(user_id)
    plunder_notice = await bot.database.nether_market.pop_plunder_notice(
        user_id, server_id
    )

    regen_seconds = M.get_charge_regen_seconds(profile["mastery_nodes"])
    charges, new_ts = M.calculate_charges(
        profile["plunder_charges"], profile["last_charge_time"], regen_seconds
    )
    if (charges, new_ts) != (profile["plunder_charges"], profile["last_charge_time"]):
        await bot.database.nether_market.restore_charges(
            user_id, server_id, charges, new_ts
        )
        profile["plunder_charges"] = charges
        profile["last_charge_time"] = new_ts

    return NetherMarketHubView(
        bot, user_id, server_id, rotation, holdings, profile, gold, plunder_notice
    )


class NetherMarketHubView(BaseView):
    def __init__(
        self,
        bot,
        user_id,
        server_id,
        rotation,
        holdings,
        profile,
        gold,
        plunder_notice=None,
    ):
        super().__init__(bot, user_id, server_id)
        self.rotation = rotation
        self.holdings = holdings
        self.profile = profile
        self.gold = gold
        self.plunder_notice = plunder_notice
        self._processing = False
        self.mode = (
            "normal"  # "normal" | "buy" | "sell" — controls which buttons are shown
        )
        self._build_buttons()

    @property
    def cap(self) -> int:
        return M.get_holdings_cap(self.profile["mastery_nodes"])

    @property
    def held_count(self) -> int:
        return sum(self.holdings.values())

    def build_embed(self) -> discord.Embed:
        value = M.compute_holdings_value(self.holdings, self.rotation)
        tier_name = WEALTH_TIERS[M.get_wealth_tier(value)]["name"]
        show_true_value = bool(self.profile["mastery_nodes"].get("trunk_market_sense"))

        embed = discord.Embed(
            title="\U0001f573️ Nether Market", color=discord.Color.dark_purple()
        )
        embed.set_author(name="Vex, the Fence", icon_url=VEX_PORTRAIT)
        if VEX_THUMBNAIL:
            embed.set_thumbnail(url=VEX_THUMBNAIL)
        embed.set_footer(
            text=f"{get_quip('nether_market')}\n\U0001f4e6×N = quantity you currently hold"
        )

        offers = _iter_offers(self.rotation, self.holdings)
        for tier_key, tier_label in _TIER_LABELS:
            lines = []
            for offer in offers:
                if offer["tier_key"] != tier_key:
                    continue
                item = offer["item"]
                dev = M.deviation_pct(offer["price"], item["true_value"])
                sign = "+" if dev >= 0 else ""
                held_tag = f" \U0001f4e6×{offer['held']}" if offer["held"] > 0 else ""
                line = (
                    f"{offer['emoji']} **{item['name']}**{held_tag} — \U0001f4b0 {offer['price']:,} "
                    f"({sign}{dev:.0f}%)"
                )
                if show_true_value:
                    line += f" *(true: {item['true_value']:,})*"
                lines.append(line)
            embed.add_field(name=tier_label, value="\n".join(lines), inline=False)

        embed.add_field(name="Gold", value=f"\U0001f4b0 {self.gold:,}", inline=True)
        embed.add_field(
            name="Holdings",
            value=f"{self.held_count} / {self.cap} slots (worth ~{value:,})",
            inline=True,
        )
        embed.add_field(name="Wealth Tier", value=f"**{tier_name}**", inline=True)

        expires_at = self.profile.get("shield_expires_at")
        shielded = bool(expires_at) and expires_at > time.time()
        embed.add_field(
            name="Marks",
            value=f"\U0001f536 {self.profile['nether_marks']}",
            inline=True,
        )
        embed.add_field(
            name="Charges",
            value=f"{self.profile['plunder_charges']} / {MAX_CHARGES}",
            inline=True,
        )
        embed.add_field(
            name="Protected", value="Yes" if shielded else "No", inline=True
        )
        if shielded:
            embed.add_field(
                name="Protection Timer", value=f"<t:{int(expires_at)}:R>", inline=True
            )

        if self.plunder_notice:
            notice = self.plunder_notice
            item_lines = []
            for item_key, qty in notice.get("items", {}).items():
                item = M.get_item(item_key)
                name = item["name"] if item else item_key
                item_lines.append(f"{qty}x {name}")
            haul_parts = []
            if item_lines:
                haul_parts.append(", ".join(item_lines))
            if notice.get("overflow_gold"):
                haul_parts.append(
                    f"\U0001f4b0 {notice['overflow_gold']:,} gold (overflow)"
                )
            haul = "; ".join(haul_parts) if haul_parts else "nothing of value"
            embed.insert_field_at(
                0,
                name="⚠️ You Were Plundered!",
                value=(
                    f"**{notice.get('attacker_name', 'Someone')}** cracked your vault "
                    f"<t:{int(notice['timestamp'])}:R> and made off with {haul}."
                ),
                inline=False,
            )
            self.plunder_notice = (
                None  # only ever shown on the first render of this view
            )
        return embed

    def _build_buttons(self):
        self.clear_items()
        if self.mode == "normal":
            self._build_normal_buttons()
        else:
            self._build_select_menu()

    def _build_normal_buttons(self):
        buy_btn = ui.Button(
            label="Buy", style=ButtonStyle.green, emoji="\U0001f6d2", row=0
        )
        buy_btn.callback = self._make_enter_select_callback("buy")
        self.add_item(buy_btn)

        sell_btn = ui.Button(
            label="Sell", style=ButtonStyle.red, emoji="\U0001f4b8", row=0
        )
        sell_btn.callback = self._make_enter_select_callback("sell")
        self.add_item(sell_btn)

        holdings_btn = ui.Button(
            label="Holdings", style=ButtonStyle.blurple, emoji="\U0001f4e6", row=1
        )
        holdings_btn.callback = self.open_holdings
        self.add_item(holdings_btn)

        browse_btn = ui.Button(
            label="Browse Targets",
            style=ButtonStyle.blurple,
            emoji=NETHER_MARKET_PLUNDER,
            row=1,
        )
        browse_btn.callback = self.open_browse
        self.add_item(browse_btn)

        mastery_btn = ui.Button(
            label="Tricks of the Trade",
            style=ButtonStyle.blurple,
            emoji="\U0001f3ad",
            row=1,
        )
        mastery_btn.callback = self.open_mastery
        self.add_item(mastery_btn)

        close_btn = ui.Button(
            label="Close", style=ButtonStyle.secondary, emoji="✖️", row=1
        )
        close_btn.callback = self.handle_close
        self.add_item(close_btn)

    def _build_select_menu(self):
        """Replaces the normal buttons with a dropdown of the active offers —
        buy lists all 6, sell lists only what the player currently holds. The
        embed itself is untouched, so nothing about the hub needs reproducing.

        Note: selecting an item opens a Modal, and we deliberately do NOT set
        `_processing` for that step — Discord gives no signal if the user
        dismisses a modal without submitting, so guarding it would permanently
        lock out the Cancel button below with no way to recover."""
        offers = _iter_offers(self.rotation, self.holdings)
        if self.mode == "sell":
            offers = [o for o in offers if o["held"] > 0]

        options = []
        for i, offer in enumerate(offers):
            item = offer["item"]
            label = f"{offer['tier_label']} · {offer['variant_label']}: {item['name']}"[
                :100
            ]
            description = f"\U0001f4b0 {offer['price']:,} each · Held: {offer['held']}"[
                :100
            ]
            options.append(
                discord.SelectOption(
                    label=label,
                    description=description,
                    value=str(i),
                    emoji=offer["emoji"],
                )
            )
        select = ui.Select(
            placeholder=f"Select an item to {self.mode}...", options=options, row=0
        )
        select.callback = self._make_select_callback(select, offers)
        self.add_item(select)

        cancel_btn = ui.Button(label="Cancel", style=ButtonStyle.secondary, row=1)
        cancel_btn.callback = self._cancel_select
        self.add_item(cancel_btn)

    def _make_enter_select_callback(self, mode: str):
        async def _callback(interaction: Interaction):
            if self._processing:
                return await interaction.response.defer()
            if mode == "sell":
                offers = _iter_offers(self.rotation, self.holdings)
                if not any(o["held"] > 0 for o in offers):
                    return await interaction.response.send_message(
                        "You don't hold any of the currently active offers.",
                        ephemeral=True,
                    )

            self._processing = True
            self.mode = mode
            self._build_buttons()
            await interaction.response.edit_message(view=self)
            self._processing = False

        return _callback

    async def _cancel_select(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        self.mode = "normal"
        self._build_buttons()
        await interaction.response.edit_message(view=self)
        self._processing = False

    def _make_select_callback(self, select: ui.Select, offers: list[dict]):
        async def _callback(interaction: Interaction):
            offer = offers[int(select.values[0])]
            modal_cls = BuyModal if self.mode == "buy" else SellModal
            await interaction.response.send_modal(
                modal_cls(
                    offer["item_key"],
                    offer["price"],
                    self.bot,
                    self.user_id,
                    self.server_id,
                )
            )

        return _callback

    async def open_holdings(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.holdings_view import build_holdings_view

        view = await build_holdings_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(
            embed=view.build_embed(), view=view
        )
        view.message = msg
        self.stop()

    async def open_browse(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.browse_view import build_browse_view

        view = await build_browse_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(
            embed=await view.build_embed(), view=view
        )
        view.message = msg
        self.stop()

    async def open_mastery(self, interaction: Interaction):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        from core.nether_market.views.mastery_view import build_mastery_view

        view = await build_mastery_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(
            embed=view.build_embed(), view=view
        )
        view.message = msg
        self.stop()

    async def handle_close(self, interaction: Interaction):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()


class BuyModal(ui.Modal, title="Buy Curiosity"):
    quantity_input = ui.TextInput(
        label="Quantity",
        placeholder="e.g. 5",
        min_length=1,
        max_length=4,
        required=True,
    )

    def __init__(self, item_key: str, price: int, bot, user_id: str, server_id: str):
        super().__init__()
        item = M.get_item(item_key)
        self.quantity_input.placeholder = f"{item['name'][:60]} @ {price:,} each"
        self.item_key = item_key
        self.price = price
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id

    async def on_submit(self, interaction: Interaction):
        try:
            qty = int(self.quantity_input.value.strip())
            if qty <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Enter a positive whole number.", ephemeral=True
            )

        current_gold = await self.bot.database.users.get_gold(self.user_id)
        view = ConfirmTransactionView(
            self.bot,
            self.user_id,
            self.server_id,
            "buy",
            self.item_key,
            self.price,
            qty,
            current_gold,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()


class SellModal(ui.Modal, title="Sell Curiosity"):
    quantity_input = ui.TextInput(
        label="Quantity",
        placeholder="e.g. 5",
        min_length=1,
        max_length=4,
        required=True,
    )

    def __init__(self, item_key: str, price: int, bot, user_id: str, server_id: str):
        super().__init__()
        item = M.get_item(item_key)
        self.quantity_input.placeholder = f"{item['name'][:60]} @ {price:,} each"
        self.item_key = item_key
        self.price = price
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id

    async def on_submit(self, interaction: Interaction):
        try:
            qty = int(self.quantity_input.value.strip())
            if qty <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Enter a positive whole number.", ephemeral=True
            )

        current_gold = await self.bot.database.users.get_gold(self.user_id)
        view = ConfirmTransactionView(
            self.bot,
            self.user_id,
            self.server_id,
            "sell",
            self.item_key,
            self.price,
            qty,
            current_gold,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()


class ConfirmTransactionView(BaseView):
    """Vex confirms the trade before it's executed — Confirm performs the DB
    writes, Cancel discards it. Either way we return to a freshly rebuilt hub."""

    def __init__(
        self,
        bot,
        user_id,
        server_id,
        mode: str,
        item_key: str,
        price: int,
        qty: int,
        current_gold: int,
    ):
        super().__init__(bot, user_id, server_id)
        self.mode = mode
        self.item_key = item_key
        self.price = price
        self.qty = qty
        self.current_gold = current_gold
        self._processing = False

    def build_embed(self) -> discord.Embed:
        item = M.get_item(self.item_key)
        total = self.price * self.qty
        verb = "BUY" if self.mode == "buy" else "SELL"
        preposition = "at" if self.mode == "buy" else "for"
        expected_gold = (
            self.current_gold - total
            if self.mode == "buy"
            else self.current_gold + total
        )

        embed = discord.Embed(title="Confirm Transaction", color=discord.Color.gold())
        embed.set_author(name="Vex, the Fence", icon_url=VEX_PORTRAIT)
        embed.description = (
            f'*"You are about to **{verb}** {self.qty}x **{item["name"]}** '
            f'{preposition} \U0001f4b0 {total:,} gold, are you sure?"*'
        )
        embed.add_field(
            name="Current Gold", value=f"\U0001f4b0 {self.current_gold:,}", inline=True
        )
        embed.add_field(
            name="Gold After Transaction",
            value=f"\U0001f4b0 {expected_gold:,}",
            inline=True,
        )
        return embed

    @ui.button(label="Confirm", style=ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()

        if self.mode == "buy":
            await self._execute_buy(interaction)
        else:
            await self._execute_sell(interaction)

    async def _execute_buy(self, interaction: Interaction):
        profile = await self.bot.database.nether_market.get_or_create_profile(
            self.user_id, self.server_id
        )
        cap = M.get_holdings_cap(profile["mastery_nodes"])
        held_count = await self.bot.database.nether_market.get_holdings_count(
            self.user_id, self.server_id
        )
        if held_count + self.qty > cap:
            return await self._fail(
                interaction,
                f"That would exceed your holdings cap ({held_count}/{cap}).",
            )

        cost = self.price * self.qty
        if not await self.bot.database.users.deduct_gold_atomic(self.user_id, cost):
            return await self._fail(interaction, "You don't have enough gold.")

        await self.bot.database.nether_market.modify_holdings(
            self.user_id, self.server_id, self.item_key, self.qty
        )
        await self._succeed(interaction)

    async def _execute_sell(self, interaction: Interaction):
        holdings = await self.bot.database.nether_market.get_holdings(
            self.user_id, self.server_id
        )
        held = holdings.get(self.item_key, 0)
        if self.qty > held:
            return await self._fail(interaction, f"You only hold {held} of that.")

        await self.bot.database.nether_market.modify_holdings(
            self.user_id, self.server_id, self.item_key, -self.qty
        )
        gold_gained = self.price * self.qty
        await self.bot.database.users.modify_gold(self.user_id, gold_gained)
        await hof_triggers.check_the_trickster(self.bot, self.user_id, gold_gained)
        await self._succeed(interaction)

    async def _fail(self, interaction: Interaction, message: str):
        await interaction.followup.send(message, ephemeral=True)
        view = await build_hub_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(
            embed=view.build_embed(), view=view
        )
        view.message = msg
        self.stop()

    async def _succeed(self, interaction: Interaction):
        view = await build_hub_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(
            embed=view.build_embed(), view=view
        )
        view.message = msg
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        if self._processing:
            return await interaction.response.defer()
        self._processing = True
        await interaction.response.defer()
        view = await build_hub_view(self.bot, self.user_id, self.server_id)
        msg = await interaction.edit_original_response(
            embed=view.build_embed(), view=view
        )
        view.message = msg
        self.stop()
