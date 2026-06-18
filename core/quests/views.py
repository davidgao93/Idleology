"""
core/quests/views.py — Quest Board UI: pre-contract board, active contracts, horizon path.
"""

from __future__ import annotations

from datetime import timedelta

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.images import AMARA_AUTHOR, QUEST_BOARD
from core.quests.data import DAILY_QUESTS, HORIZON_PATHS, TOKEN_SHOP_ITEMS
from core.quests.mechanics import (
    BOARD_COOLDOWN_HOURS,
    compute_goal_for_quest,
    format_goal_description,
    get_board_cooldown_remaining,
    grant_contract_reward,
    grant_horizon_reward,
    reroll_slot,
    roll_board,
)

_BOARD_COLOR = 0x5865F2


def _fmt_td(td: timedelta) -> str:
    total = int(td.total_seconds())
    if total <= 0:
        return "0m"
    h = total // 3600
    m = (total % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


class QuestBoardView(BaseView):
    def __init__(self, bot, user_id: str, server_id: str):
        super().__init__(bot, user_id, server_id)
        self._processing = False

        # Loaded state
        self.board: list = []
        self.contracts: list = []
        self.horizon = None
        self.meta: dict = {}

        # Board level (loaded in load())
        self._player_level: int = 1

    async def load(self) -> None:
        """Load all quest state from DB."""
        self.meta = await self.bot.database.quests.get_meta(self.user_id)
        self.board = await self.bot.database.quests.get_board(
            self.user_id, self.server_id
        )
        self.contracts = await self.bot.database.quests.get_contracts(
            self.user_id, self.server_id
        )
        self.horizon = await self.bot.database.quests.get_horizon(
            self.user_id, self.server_id
        )

        user_row = await self.bot.database.users.get(self.user_id, self.server_id)
        self._player_level = user_row["level"] if user_row else 1

        # If no board and no contracts, roll a fresh board
        active_contracts = [c for c in self.contracts if not c["turned_in"]]
        if not active_contracts and not self.board and not self._is_on_cooldown():
            await self._roll_fresh_board()

    def _is_on_cooldown(self) -> bool:
        """Check if the board is on cooldown based on latest contract locked_at."""
        if not self.contracts:
            return False
        latest = max(self.contracts, key=lambda c: c.get("locked_at", ""), default=None)
        if not latest:
            return False
        remaining = get_board_cooldown_remaining(latest["locked_at"])
        return remaining.total_seconds() > 0

    def _cooldown_remaining(self) -> timedelta:
        if not self.contracts:
            return timedelta(0)
        latest = max(self.contracts, key=lambda c: c.get("locked_at", ""), default=None)
        if not latest:
            return timedelta(0)
        return get_board_cooldown_remaining(latest["locked_at"])

    async def _roll_fresh_board(self) -> None:
        await self.bot.database.quests.clear_board(self.user_id, self.server_id)
        rolls = roll_board(self._player_level)
        for i, (quest_id, tier) in enumerate(rolls, start=1):
            await self.bot.database.quests.set_board_slot(
                self.user_id, self.server_id, i, quest_id, tier
            )
        self.board = await self.bot.database.quests.get_board(
            self.user_id, self.server_id
        )

    def _get_state(self) -> str:
        """Determine view state: 'board', 'contracts', or 'empty'."""
        active_contracts = [c for c in self.contracts if not c["turned_in"]]
        if active_contracts:
            return "contracts"
        if self.board:
            return "board"
        if self._is_on_cooldown():
            return "empty"
        return "board"

    def build_embed(self) -> discord.Embed:
        state = self._get_state()
        tokens = self.meta.get("tokens", 0)

        if state == "board":
            return self._build_board_embed(tokens)
        elif state == "contracts":
            return self._build_contracts_embed(tokens)
        else:
            return self._build_empty_embed(tokens)

    def _build_board_embed(self, tokens: int) -> discord.Embed:
        embed = discord.Embed(
            title="The Quest Board",
            description="There you are. The board's fresh — a few contracts worth risking your neck over. Choose wisely, adventurer.",
            color=_BOARD_COLOR,
        )
        embed.set_author(name="Guildmaster Amara", icon_url=AMARA_AUTHOR)
        embed.set_thumbnail(url=QUEST_BOARD)

        for slot_row in self.board:
            slot = slot_row["slot"]
            quest_id = slot_row["quest_id"]
            tier = slot_row["tier"]
            quest_def = next((q for q in DAILY_QUESTS if q["id"] == quest_id), None)
            if quest_def is None:
                continue

            goal = compute_goal_for_quest(quest_id, tier, self._player_level)
            star = "⭐" if tier == 1 else "⭐⭐⭐"
            gold = 25_000 if tier == 1 else 75_000
            token_word = "Token" if tier == 1 else "Tokens"
            obj_desc = format_goal_description(quest_id, tier, goal)

            embed.add_field(
                name=f"{star} Slot {slot} — {quest_def['label']}",
                value=(
                    f"{quest_def['flavor']}\n"
                    f"**Objective:** {obj_desc}\n"
                    f"**Reward:** {tier} Quest {token_word} + {gold:,} Gold"
                ),
                inline=False,
            )

        # Horizon section
        if self.horizon and not self.horizon["turned_in"]:
            path_def = HORIZON_PATHS.get(self.horizon["path_id"])
            if path_def:
                progress = self.horizon["progress"]
                goal = self.horizon["goal"]
                embed.add_field(
                    name=f"🌀 Horizon Path — {path_def['name']}",
                    value=(
                        f"{path_def['description']}\n"
                        f"**Progress:** {progress}/{goal}\n"
                        f"**Reward:** {path_def['token_reward']} Quest Tokens + {path_def.get('loot_preview', 'special loot')}"
                    ),
                    inline=False,
                )
        else:
            embed.add_field(
                name="🌀 Horizon Path — None selected",
                value="Select a Horizon Path below to begin a long-form quest.",
                inline=False,
            )

        embed.set_footer(text=f"Quest Tokens: {tokens}  |  Ready to take contracts")
        return embed

    def _build_contracts_embed(self, tokens: int) -> discord.Embed:
        embed = discord.Embed(
            title="Active Contracts",
            description="Still breathing? Good. Here's what you've got on the fire right now. Don't let me down.",
            color=_BOARD_COLOR,
        )
        embed.set_author(name="Guildmaster Amara", icon_url=AMARA_AUTHOR)
        embed.set_thumbnail(url=QUEST_BOARD)

        active = [c for c in self.contracts if not c["turned_in"]]
        for contract in active:
            quest_def = next(
                (q for q in DAILY_QUESTS if q["id"] == contract["quest_id"]), None
            )
            label = quest_def["label"] if quest_def else contract["quest_id"]
            progress = min(contract["progress"], contract["goal"])
            if contract["completed"]:
                status = "✅ Complete — Claim your reward!"
                status_emoji = "✅"
            else:
                status = "In Progress"
                status_emoji = "🔄"

            flavor = quest_def["flavor"] if quest_def else ""
            embed.add_field(
                name=f"{status_emoji} {label} — Slot {contract['slot']}",
                value=(
                    f"{flavor}\n"
                    f"**Progress:** {progress}/{contract['goal']}\n"
                    f"**Status:** {status}"
                ),
                inline=False,
            )

        # Horizon section
        if self.horizon and not self.horizon["turned_in"]:
            path_def = HORIZON_PATHS.get(self.horizon["path_id"])
            if path_def:
                progress = self.horizon["progress"]
                goal = self.horizon["goal"]
                h_status = (
                    "✅ Complete — Claim your reward!"
                    if self.horizon["completed"]
                    else "In Progress"
                )
                embed.add_field(
                    name=f"🌀 Horizon Path — {path_def['name']}",
                    value=(
                        f"{path_def['description']}\n"
                        f"**Progress:** {progress}/{goal}\n"
                        f"**Status:** {h_status}"
                    ),
                    inline=False,
                )

        rem = self._cooldown_remaining()
        if rem.total_seconds() > 0:
            footer = f"Quest Tokens: {tokens}  |  Next board in: {_fmt_td(rem)}"
        else:
            footer = f"Quest Tokens: {tokens}  |  Board ready after contracts are done"
        embed.set_footer(text=footer)
        return embed

    def _build_empty_embed(self, tokens: int) -> discord.Embed:
        rem = self._cooldown_remaining()
        embed = discord.Embed(
            title="Board's Clear",
            description=f"Cleaned the board out, did you? Come back in **{_fmt_td(rem)}** — I'll have fresh work for you then.",
            color=_BOARD_COLOR,
        )
        embed.set_author(name="Guildmaster Amara", icon_url=AMARA_AUTHOR)
        embed.set_thumbnail(url=QUEST_BOARD)
        embed.set_footer(text=f"Quest Tokens: {tokens}")
        return embed

    def _build_view_components(self) -> None:
        """Rebuild all buttons/selects for the current state."""
        self.clear_items()
        state = self._get_state()
        tokens = self.meta.get("tokens", 0)

        if state == "board":
            self._add_board_components(tokens)
        elif state == "contracts":
            self._add_contract_components(tokens)
        else:
            self._add_empty_components()

    def _add_board_components(self, tokens: int) -> None:
        # Reroll buttons for each slot
        for slot_row in self.board:
            slot = slot_row["slot"]
            free_used = bool(slot_row["free_reroll_used"])
            if not free_used:
                label = f"Reroll Slot {slot} (Free)"
                style = ButtonStyle.success
                disabled = False
            else:
                label = f"Reroll Slot {slot} (1🎫)"
                style = ButtonStyle.secondary
                disabled = tokens < 1

            btn = _RerollButton(
                slot=slot, label=label, style=style, disabled=disabled, row=0
            )
            self.add_item(btn)

        # Horizon path select
        self.add_item(_HorizonSelect(self._player_level, self.horizon, row=1))

        # Take Contracts
        take_btn = discord.ui.Button(
            label="Take Contracts",
            style=ButtonStyle.primary,
            row=2,
        )
        take_btn.callback = self._on_take_contracts
        self.add_item(take_btn)

        # Quest Shop
        shop_btn = discord.ui.Button(
            label="Quest Shop", style=ButtonStyle.secondary, row=2
        )
        shop_btn.callback = self._on_open_shop
        self.add_item(shop_btn)

        # Close
        close_btn = discord.ui.Button(label="Close", style=ButtonStyle.secondary, row=2)
        close_btn.callback = self._on_close
        self.add_item(close_btn)

    def _add_contract_components(self, tokens: int) -> None:
        active = [c for c in self.contracts if not c["turned_in"]]

        # Claim buttons (row 0)
        for i, contract in enumerate(active[:3]):
            slot = contract["slot"]
            can_claim = bool(contract["completed"]) and not bool(contract["turned_in"])
            label = f"✅ Claim Slot {slot}" if can_claim else f"-- Slot {slot}"
            btn = _ClaimButton(slot=slot, label=label, disabled=not can_claim, row=0)
            self.add_item(btn)

        # Abandon select (row 1) — only show incomplete slots
        incomplete = [c for c in active if not c["completed"]]
        if incomplete:
            self.add_item(_AbandonSelect(incomplete, row=1))

        # Horizon path select (row 2) — always available so paths can be swapped at any time
        self.add_item(_HorizonSelect(self._player_level, self.horizon, row=2))

        # Claim Horizon (row 3)
        horizon_complete = (
            self.horizon and self.horizon["completed"] and not self.horizon["turned_in"]
        )
        h_btn = discord.ui.Button(
            label="Claim Horizon",
            style=ButtonStyle.success,
            disabled=not horizon_complete,
            row=3,
        )
        h_btn.callback = self._on_claim_horizon
        self.add_item(h_btn)

        # Quest Shop
        shop_btn = discord.ui.Button(
            label="Quest Shop", style=ButtonStyle.secondary, row=3
        )
        shop_btn.callback = self._on_open_shop
        self.add_item(shop_btn)

        # Close
        close_btn = discord.ui.Button(label="Close", style=ButtonStyle.secondary, row=3)
        close_btn.callback = self._on_close
        self.add_item(close_btn)

    def _add_empty_components(self) -> None:
        # Allow horizon path selection even while waiting for the board to reset
        self.add_item(_HorizonSelect(self._player_level, self.horizon, row=0))

        shop_btn = discord.ui.Button(
            label="Quest Shop", style=ButtonStyle.secondary, row=1
        )
        shop_btn.callback = self._on_open_shop
        self.add_item(shop_btn)

        close_btn = discord.ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
        close_btn.callback = self._on_close
        self.add_item(close_btn)

    async def refresh(self, interaction: Interaction) -> None:
        """Reload state and edit the message."""
        await self.load()
        self._build_view_components()
        embed = self.build_embed()
        await interaction.edit_original_response(embed=embed, view=self)

    # ------------------------------------------------------------------
    # Reroll handler (called by _RerollButton)
    # ------------------------------------------------------------------

    async def handle_reroll(self, interaction: Interaction, slot: int) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            slot_row = next((r for r in self.board if r["slot"] == slot), None)
            if not slot_row:
                return

            tokens = self.meta.get("tokens", 0)
            free_used = bool(slot_row["free_reroll_used"])

            if not free_used:
                # Use free reroll
                await self.bot.database.quests.mark_free_reroll_used(
                    self.user_id, self.server_id, slot
                )
            else:
                # Spend 1 token
                if tokens < 1:
                    await interaction.followup.send(
                        "Not enough Quest Tokens (need 1).", ephemeral=True
                    )
                    return
                ok = await self.bot.database.quests.spend_tokens(self.user_id, 1)
                if not ok:
                    await interaction.followup.send(
                        "Not enough Quest Tokens.", ephemeral=True
                    )
                    return

            # Roll new quest — always tier 3, excluding already-shown quests
            existing_ids = [r["quest_id"] for r in self.board]
            new_quest_id, new_tier = reroll_slot(
                self._player_level,
                exclude_quest_ids=existing_ids,
            )
            await self.bot.database.quests.update_board_slot_quest(
                self.user_id, self.server_id, slot, new_quest_id, new_tier
            )
            await self.refresh(interaction)
        finally:
            self._processing = False

    # ------------------------------------------------------------------
    # Take Contracts callback
    # ------------------------------------------------------------------

    async def _on_take_contracts(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            if not self.board:
                await interaction.followup.send("No board to take.", ephemeral=True)
                return

            # Copy board to contracts with computed goals
            for slot_row in self.board:
                goal = compute_goal_for_quest(
                    slot_row["quest_id"], slot_row["tier"], self._player_level
                )
                await self.bot.database.quests.set_contract_slot(
                    self.user_id,
                    self.server_id,
                    slot_row["slot"],
                    slot_row["quest_id"],
                    slot_row["tier"],
                    goal,
                )

            # Clear the board
            await self.bot.database.quests.clear_board(self.user_id, self.server_id)
            await self.refresh(interaction)
        finally:
            self._processing = False

    # ------------------------------------------------------------------
    # Claim Contract (called by _ClaimButton)
    # ------------------------------------------------------------------

    async def handle_claim(self, interaction: Interaction, slot: int) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            msgs = await grant_contract_reward(
                self.bot, self.user_id, self.server_id, slot
            )
            if not msgs:
                await interaction.followup.send(
                    "That contract isn't ready to claim.", ephemeral=True
                )
                return

            await self.load()
            self._build_view_components()
            embed = self.build_embed()
            embed.add_field(
                name=f"✅ Contract Slot {slot} Claimed!",
                value="\n".join(msgs),
                inline=False,
            )
            await interaction.edit_original_response(embed=embed, view=self)

            # Check if all contracts are done — if so and cooldown expired, roll fresh
            await self._check_for_fresh_board_ready(interaction)
        finally:
            self._processing = False

    # ------------------------------------------------------------------
    # Abandon (called by _AbandonConfirmView after user confirms)
    # ------------------------------------------------------------------

    async def execute_abandon(self, slot: int) -> None:
        """Performs the abandon and refreshes the main message. Called from the confirm view."""
        await self.bot.database.quests.abandon_contract(
            self.user_id, self.server_id, slot
        )
        await self.load()
        active = [c for c in self.contracts if not c["turned_in"]]
        if not active and not self._is_on_cooldown():
            await self._roll_fresh_board()
        self._build_view_components()
        await self.message.edit(embed=self.build_embed(), view=self)

    async def _check_for_fresh_board_ready(self, interaction: Interaction) -> None:
        """If all contracts are done/abandoned and cooldown expired, reload board."""
        await self.load()
        active = [c for c in self.contracts if not c["turned_in"]]
        if not active and not self._is_on_cooldown():
            await self._roll_fresh_board()
            self._build_view_components()
            await interaction.edit_original_response(
                embed=self.build_embed(), view=self
            )

    # ------------------------------------------------------------------
    # Claim Horizon
    # ------------------------------------------------------------------

    async def _on_claim_horizon(self, interaction: Interaction) -> None:
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()

        try:
            user_row = await self.bot.database.users.get(self.user_id, self.server_id)
            # Build a minimal player-like object if needed by grant_horizon_reward
            from core.items.factory import load_player

            player = await load_player(self.user_id, user_row, self.bot.database)

            msgs = await grant_horizon_reward(
                self.bot, self.user_id, self.server_id, player
            )
            if not msgs:
                await interaction.followup.send(
                    "Horizon quest isn't ready to claim.", ephemeral=True
                )
                return

            await self.load()
            self._build_view_components()
            embed = self.build_embed()
            embed.add_field(
                name="🌀 Horizon Reward Claimed!", value="\n".join(msgs), inline=False
            )
            await interaction.edit_original_response(embed=embed, view=self)
        finally:
            self._processing = False

    # ------------------------------------------------------------------
    # Horizon path selected (called by _HorizonSelect)
    # ------------------------------------------------------------------

    async def handle_horizon_select(
        self, interaction: Interaction, path_id: str
    ) -> None:
        """Entry point from _HorizonSelect. Shows a confirmation if switching an active path."""
        path_def = HORIZON_PATHS.get(path_id)
        if not path_def:
            await interaction.response.defer()
            return
        if self._player_level < path_def["level_required"]:
            await interaction.response.send_message(
                f"You need to be level {path_def['level_required']} for this path.",
                ephemeral=True,
            )
            return

        current = self.horizon
        switching_active = (
            current is not None
            and not current.get("turned_in")
            and not current.get("completed")
            and current.get("path_id") != path_id
            and current.get("progress", 0) > 0
        )
        if switching_active:
            confirm = _HorizonSwitchConfirmView(
                self.bot, self, path_id, path_def["name"]
            )
            await interaction.response.send_message(
                f"Switch to **{path_def['name']}**? Your progress on the current path will be lost.",
                view=confirm,
                ephemeral=True,
            )
        else:
            await interaction.response.defer()
            await self.execute_horizon_select(path_id, path_def)

    async def execute_horizon_select(self, path_id: str, path_def: dict) -> None:
        """Writes the horizon selection and refreshes the main message."""
        await self.bot.database.quests.set_horizon(
            self.user_id, self.server_id, path_id, path_def["goal"]
        )
        await self.load()
        self._build_view_components()
        await self.message.edit(embed=self.build_embed(), view=self)

    # ------------------------------------------------------------------
    # Shop / Close
    # ------------------------------------------------------------------

    async def _on_open_shop(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        from core.quests.shop_views import TokenShopView

        tokens = self.meta.get("tokens", 0)
        shop = TokenShopView(
            self.bot, parent=self, tokens=tokens, player_level=self._player_level
        )
        embed = shop.build_embed()
        await interaction.edit_original_response(embed=embed, view=shop)

    async def _on_close(self, interaction: Interaction) -> None:
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.message.delete()


# ---------------------------------------------------------------------------
# Sub-components
# ---------------------------------------------------------------------------


class _RerollButton(discord.ui.Button):
    def __init__(
        self, slot: int, label: str, style: ButtonStyle, disabled: bool, row: int
    ):
        super().__init__(label=label, style=style, disabled=disabled, row=row)
        self.slot = slot

    async def callback(self, interaction: Interaction) -> None:
        await self.view.handle_reroll(interaction, self.slot)


class _ClaimButton(discord.ui.Button):
    def __init__(self, slot: int, label: str, disabled: bool, row: int):
        super().__init__(
            label=label,
            style=ButtonStyle.success if not disabled else ButtonStyle.secondary,
            disabled=disabled,
            row=row,
        )
        self.slot = slot

    async def callback(self, interaction: Interaction) -> None:
        await self.view.handle_claim(interaction, self.slot)


class _AbandonSelect(discord.ui.Select):
    def __init__(self, incomplete_contracts: list, row: int):
        self._contracts = incomplete_contracts
        options = []
        for c in incomplete_contracts:
            quest_def = next(
                (q for q in DAILY_QUESTS if q["id"] == c["quest_id"]), None
            )
            label = quest_def["label"] if quest_def else c["quest_id"]
            options.append(
                discord.SelectOption(
                    label=f"Slot {c['slot']}: {label}",
                    value=str(c["slot"]),
                )
            )
        super().__init__(
            placeholder="Abandon a contract...",
            options=options,
            row=row,
        )

    async def callback(self, interaction: Interaction) -> None:
        slot = int(self.values[0])
        contract = next((c for c in self._contracts if c["slot"] == slot), None)
        quest_def = (
            next((q for q in DAILY_QUESTS if q["id"] == contract["quest_id"]), None)
            if contract
            else None
        )
        quest_label = quest_def["label"] if quest_def else f"Slot {slot}"
        confirm = _AbandonConfirmView(self.view.bot, self.view, slot, quest_label)
        await interaction.response.send_message(
            f"Walk away from **{quest_label}** (Slot {slot})? Your progress will be lost.",
            view=confirm,
            ephemeral=True,
        )


class _AbandonConfirmView(BaseView):
    """Ephemeral confirmation before abandoning a contract."""

    def __init__(self, bot, parent: QuestBoardView, slot: int, quest_label: str):
        super().__init__(bot, parent=parent)
        self.main_view = parent
        self.slot = slot
        self.quest_label = quest_label
        self._done = False

    @ui.button(label="Abandon", style=ButtonStyle.danger)
    async def confirm_btn(self, interaction: Interaction, button: ui.Button):
        if self._done:
            await interaction.response.defer()
            return
        self._done = True
        await interaction.response.edit_message(
            content=f"Contract **{self.quest_label}** abandoned.", view=None
        )
        await self.main_view.execute_abandon(self.slot)
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()


class _HorizonSwitchConfirmView(BaseView):
    """Ephemeral confirmation before switching an in-progress Horizon path."""

    def __init__(self, bot, parent: QuestBoardView, path_id: str, path_name: str):
        super().__init__(bot, parent=parent)
        self.main_view = parent
        self.path_id = path_id
        self.path_name = path_name
        self._done = False

    @ui.button(label="Switch Path", style=ButtonStyle.danger)
    async def confirm_btn(self, interaction: Interaction, button: ui.Button):
        if self._done:
            await interaction.response.defer()
            return
        self._done = True
        await interaction.response.edit_message(
            content=f"Switched to **{self.path_name}**.", view=None
        )
        path_def = HORIZON_PATHS.get(self.path_id)
        await self.main_view.execute_horizon_select(self.path_id, path_def)
        self.stop()

    @ui.button(label="Cancel", style=ButtonStyle.secondary)
    async def cancel_btn(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="Cancelled.", view=None)
        self.stop()


class _HorizonSelect(discord.ui.Select):
    def __init__(self, player_level: int, current_horizon, row: int):
        options = []
        sorted_paths = sorted(
            HORIZON_PATHS.items(), key=lambda x: x[1]["level_required"]
        )
        for path_id, path_def in sorted_paths:
            label = path_def["name"][:50]
            desc = f"Lv.{path_def['level_required']} req  |  {path_def['token_reward']} tokens"
            options.append(
                discord.SelectOption(
                    label=label,
                    value=path_id,
                    description=desc,
                    default=(
                        current_horizon is not None
                        and current_horizon.get("path_id") == path_id
                    ),
                )
            )
        super().__init__(
            placeholder="Select Horizon Path...",
            options=options[:25],
            row=row,
        )

    async def callback(self, interaction: Interaction) -> None:
        await self.view.handle_horizon_select(interaction, self.values[0])
