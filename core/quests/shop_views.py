"""
core/quests/shop_views.py — Token Shop UI for Quest Board.
"""

from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.images import QUEST_SHOP, QUEST_SHOP_AUTHOR
from core.quests.data import TOKEN_SHOP_ITEMS

_SHOP_COLOR = 0xF0A500


class TokenShopView(BaseView):
    def __init__(self, bot, parent: "BaseView", tokens: int = 0, player_level: int = 1):
        super().__init__(bot, parent=parent)
        self._processing = False
        self._selected_item_id: str | None = None
        self._tokens = tokens
        self._player_level = player_level
        self._build_components()

    def _visible_items(self) -> list:
        """Return shop items visible at this player's level."""
        out = []
        for item in TOKEN_SHOP_ITEMS:
            if item["id"] == "key_cache" and self._player_level < 50:
                continue
            out.append(item)
        return out

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Quest Token Shop",
            description=(
                "Oh good, you're here. Those tokens burning a hole in your pocket? "
                "I've got just the thing to lighten the load — upgrades, caches, the usual. "
                "Spend wisely.\n\n"
                f"🎫 **Your Tokens: {self._tokens}**"
            ),
            color=_SHOP_COLOR,
        )
        embed.set_author(name="Lira", icon_url=QUEST_SHOP_AUTHOR)
        embed.set_thumbnail(url=QUEST_SHOP)
        for item in self._visible_items():
            one_time = " *(One-time)*" if item.get("one_time") else ""
            selected = item["id"] == self._selected_item_id
            name_prefix = "➤ " if selected else ""
            embed.add_field(
                name=f"{name_prefix}{item['label']} — {item['cost']}🎫{one_time}",
                value=item["description"],
                inline=False,
            )
        return embed

    def _build_components(self) -> None:
        self.clear_items()

        # Item select
        options = []
        for item in self._visible_items():
            options.append(
                discord.SelectOption(
                    label=f"{item['label']} ({item['cost']}🎫)",
                    value=item["id"],
                    description=item["description"][:50],
                )
            )
        sel = _ShopItemSelect(options, row=0)
        self.add_item(sel)

        # Confirm button (disabled until item selected)
        confirm = discord.ui.Button(
            label="Confirm Purchase",
            style=ButtonStyle.primary,
            disabled=True,
            row=1,
        )
        confirm.callback = self._on_confirm
        self.confirm_btn = confirm
        self.add_item(confirm)

        # Back button
        back = discord.ui.Button(label="Back", style=ButtonStyle.secondary, row=1)
        back.callback = self._on_back
        self.add_item(back)

    def set_selected(self, item_id: str) -> None:
        self._selected_item_id = item_id
        self.confirm_btn.disabled = False

    async def _on_confirm(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            if not self._selected_item_id:
                return

            item_def = next(
                (i for i in TOKEN_SHOP_ITEMS if i["id"] == self._selected_item_id), None
            )
            if not item_def:
                return

            meta = await self.bot.database.quests.get_meta(self.user_id)

            # Check one-time unlock
            if item_def.get("one_time"):
                field = item_def.get("unlock_field", "")
                if meta.get(field):
                    await interaction.followup.send(
                        "You have already unlocked this upgrade.", ephemeral=True
                    )
                    return

            # Spend tokens
            ok = await self.bot.database.quests.spend_tokens(
                self.user_id, item_def["cost"]
            )
            if not ok:
                await interaction.followup.send(
                    f"Not enough Quest Tokens (need {item_def['cost']}).",
                    ephemeral=True,
                )
                return

            # Update local token count and clear selection
            self._tokens -= item_def["cost"]
            self._selected_item_id = None
            self.confirm_btn.disabled = True

            # Apply effect
            result_msg = await self._apply_item(item_def, meta)

            embed = self.build_embed()
            embed.add_field(name="✅ Purchase Complete", value=result_msg, inline=False)
            await interaction.edit_original_response(embed=embed, view=self)

        finally:
            self._processing = False

    async def _apply_item(self, item_def: dict, meta: dict) -> str:
        import random as _random

        item_id = item_def["id"]

        # ── Consumables ──────────────────────────────────────────────────────
        if item_id == "curio":
            await self.bot.database.users.modify_currency(self.user_id, "curios", 1)
            return "+1 Curio purchased!"

        elif item_id == "equip_cache":
            from core.combat.economy.loot import (
                generate_accessory,
                generate_armor,
                generate_boot,
                generate_glove,
                generate_helmet,
                generate_weapon,
            )

            user_row = await self.bot.database.users.get(self.user_id, self.server_id)
            level = user_row["level"] if user_row else 1
            ilvl = min(level, 100)
            slot = _random.choices(
                ["weapon", "armor", "accessory", "glove", "boot", "helmet"],
                weights=[35, 10, 25, 10, 10, 10],
                k=1,
            )[0]
            if slot == "weapon":
                item = await generate_weapon(self.user_id, ilvl, False)
                await self.bot.database.equipment.create_weapon(item)
            elif slot == "armor":
                item = await generate_armor(self.user_id, ilvl, False)
                await self.bot.database.equipment.create_armor(item)
            elif slot == "accessory":
                item = await generate_accessory(self.user_id, ilvl, False)
                await self.bot.database.equipment.create_accessory(item)
            elif slot == "glove":
                item = await generate_glove(self.user_id, ilvl)
                await self.bot.database.equipment.create_glove(item)
            elif slot == "boot":
                item = await generate_boot(self.user_id, ilvl)
                await self.bot.database.equipment.create_boot(item)
            else:
                item = await generate_helmet(self.user_id, ilvl)
                await self.bot.database.equipment.create_helmet(item)
            return f"📦 Equipment Cache opened: **{item.name}**"

        elif item_id == "rune_cache":
            rune_pool = ["refinement_runes", "potential_runes", "shatter_runes"]
            qty = _random.randint(1, 5)
            received = []
            for _ in range(qty):
                rtype = _random.choice(rune_pool)
                await self.bot.database.users.modify_currency(self.user_id, rtype, 1)
                received.append(
                    rtype.replace("_runes", "").replace("_", " ").title() + " Rune"
                )
            from collections import Counter

            tally = Counter(received)
            return "💎 Rune Cache: " + ", ".join(f"{v}× {k}" for k, v in tally.items())

        elif item_id == "key_cache":
            key_pool = ["dragon_key", "angel_key", "soul_cores", "balance_fragment"]
            qty = _random.randint(1, 5)
            received = []
            for _ in range(qty):
                ktype = _random.choice(key_pool)
                await self.bot.database.users.modify_currency(self.user_id, ktype, 1)
                received.append(ktype.replace("_", " ").title())
            from collections import Counter

            tally = Counter(received)
            return "🗝️ Key Cache: " + ", ".join(f"{v}× {k}" for k, v in tally.items())

        # ── Utility ──────────────────────────────────────────────────────────
        elif item_id == "board_reset":
            await self.bot.database.quests.reset_board_cooldown(
                self.user_id, self.server_id
            )
            return "Board cooldown cleared!"

        elif item_id == "horizon_boost":
            current_uses = meta.get("horizon_boost_uses", 0)
            await self.bot.database.quests.set_meta_field(
                self.user_id, "horizon_boost_uses", current_uses + 10
            )
            return "+10 Horizon Boost uses added!"

        # ── Permanent Upgrades ───────────────────────────────────────────────
        elif item_id == "enrichment":
            await self.bot.database.quests.set_meta_field(
                self.user_id, "enrichment_unlocked", 1
            )
            return (
                "Enrichment unlocked! Quest gold rewards permanently increased by 50%."
            )

        elif item_id == "prospector_license":
            await self.bot.database.quests.set_meta_field(
                self.user_id, "prospector_unlocked", 1
            )
            return "Prospector's License unlocked! Gathering cache granted on every quest turn-in."

        elif item_id == "quest_veteran":
            await self.bot.database.quests.set_meta_field(
                self.user_id, "veteran_unlocked", 1
            )
            return "Quest Veteran unlocked! +1 bonus token on every completion."

        elif item_id == "extra_slot":
            await self.bot.database.quests.set_meta_field(
                self.user_id, "extra_slot_unlocked", 1
            )
            return "Contract Extension unlocked! 4th slot available."

        return "Purchase applied."

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        from core.quests.views import QuestBoardView

        board_view = QuestBoardView(self.bot, self.user_id, self.server_id)
        await board_view.load()
        board_view._build_view_components()
        embed = board_view.build_embed()
        await interaction.edit_original_response(embed=embed, view=board_view)


class _ShopItemSelect(discord.ui.Select):
    def __init__(self, options: list, row: int):
        super().__init__(
            placeholder="Choose an item...",
            options=options,
            row=row,
        )

    async def callback(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.view.set_selected(self.values[0])
        # Rebuild embed to show selection indicator and enable confirm button
        embed = self.view.build_embed()
        await interaction.edit_original_response(embed=embed, view=self.view)
