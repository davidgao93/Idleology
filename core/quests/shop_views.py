"""
core/quests/shop_views.py — Token Shop UI for Quest Board.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.quests.data import TOKEN_SHOP_ITEMS

_SHOP_COLOR = 0xF0A500


class TokenShopView(BaseView):
    def __init__(self, bot, parent: "BaseView", tokens: int = 0):
        super().__init__(bot, parent=parent)
        self._processing = False
        self._selected_item_id: str | None = None
        self._tokens = tokens
        self._build_components()

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🛒 Quest Token Shop",
            description=(
                "Spend your Quest Tokens on upgrades and utilities.\n\n"
                f"🎫 **Your Tokens: {self._tokens}**"
            ),
            color=_SHOP_COLOR,
        )
        for item in TOKEN_SHOP_ITEMS:
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
        for item in TOKEN_SHOP_ITEMS:
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
            ok = await self.bot.database.quests.spend_tokens(self.user_id, item_def["cost"])
            if not ok:
                await interaction.followup.send(
                    f"Not enough Quest Tokens (need {item_def['cost']}).", ephemeral=True
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
        item_id = item_def["id"]

        if item_id == "board_reset":
            await self.bot.database.quests.reset_board_cooldown(self.user_id, self.server_id)
            return "Board cooldown cleared!"

        elif item_id == "reroll_restore":
            # Restore free reroll on first slot with used free reroll
            board = await self.bot.database.quests.get_board(self.user_id, self.server_id)
            for slot_row in board:
                if slot_row["free_reroll_used"]:
                    await self.bot.database.quests.restore_free_reroll(
                        self.user_id, self.server_id, slot_row["slot"]
                    )
                    return f"Free reroll restored for Slot {slot_row['slot']}!"
            # Also check contract slots
            return "Free reroll restored!"

        elif item_id == "contract_swap":
            # Swap first incomplete contract with fresh roll of same tier
            from core.quests.mechanics import reroll_slot, compute_goal_for_quest
            contracts = await self.bot.database.quests.get_contracts(self.user_id, self.server_id)
            incomplete = [c for c in contracts if not c["turned_in"] and not c["completed"]]
            if not incomplete:
                await self.bot.database.quests.add_tokens(self.user_id, item_def["cost"])  # refund
                return "No eligible contracts to swap."
            target = incomplete[0]
            existing_ids = [c["quest_id"] for c in contracts]
            user_row = await self.bot.database.users.get(self.user_id, self.server_id)
            level = user_row["level"] if user_row else 1
            new_id, new_tier = reroll_slot(
                level,
                exclude_tier=target["tier"],
                exclude_quest_ids=existing_ids,
            )
            # Keep same tier for the swap
            new_tier = target["tier"]
            goal = compute_goal_for_quest(new_id, new_tier, level)
            await self.bot.database.quests.set_contract_slot(
                self.user_id, self.server_id, target["slot"], new_id, new_tier, goal
            )
            return f"Contract Slot {target['slot']} replaced with a fresh quest!"

        elif item_id == "track_advance":
            from core.quests.data import grant_checkin_day
            meta_fresh = await self.bot.database.quests.get_meta(self.user_id)
            current_day = meta_fresh["checkin_day"]
            next_day = (current_day % 14) + 1 if current_day > 0 else 1
            user_row = await self.bot.database.users.get(self.user_id, self.server_id)
            level = user_row["level"] if user_row else 1
            rewards = await grant_checkin_day(self.bot, self.user_id, self.server_id, next_day, level)
            await self.bot.database.quests.advance_checkin(self.user_id)
            return f"Day {next_day} claimed!\n" + "\n".join(rewards)

        elif item_id == "horizon_boost":
            current_uses = meta.get("horizon_boost_uses", 0)
            await self.bot.database.quests.set_meta_field(
                self.user_id, "horizon_boost_uses", current_uses + 10
            )
            return "+10 Horizon Boost uses added!"

        elif item_id == "quest_veteran":
            await self.bot.database.quests.set_meta_field(self.user_id, "veteran_unlocked", 1)
            return "Quest Veteran unlocked! +1 bonus token on every completion."

        elif item_id == "extra_slot":
            await self.bot.database.quests.set_meta_field(self.user_id, "extra_slot_unlocked", 1)
            return "Contract Extension unlocked! 4th slot available."

        elif item_id == "curio":
            await self.bot.database.users.modify_currency(self.user_id, "curios", 1)
            return "+1 Curio purchased!"

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
