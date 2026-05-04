import discord
from discord import ButtonStyle, Interaction, ui

from core.curios.logic import CurioManager
from core.curios.puzzle_box_views import PuzzleBoxView
from core.images import CURIO_BULK, CURIO_UNOPENED

_UNOPENED_IMAGE = CURIO_UNOPENED
_BULK_IMAGE = CURIO_BULK


class CustomAmountModal(ui.Modal, title="Open Custom Amount"):
    def __init__(self, max_amount: int):
        super().__init__()
        self.max_amount = max_amount
        self.chosen_amount: int | None = None
        self.amount_input = ui.TextInput(
            label=f"Amount (1–{max_amount})",
            placeholder=f"Enter a number from 1 to {max_amount}",
            min_length=1,
            max_length=7,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: Interaction):
        try:
            value = int(self.amount_input.value)
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.", ephemeral=True
            )
            return
        if not (1 <= value <= self.max_amount):
            await interaction.response.send_message(
                f"Must be between 1 and {self.max_amount}.", ephemeral=True
            )
            return
        self.chosen_amount = value
        await interaction.response.defer()


class CurioView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        curio_count: int,
        puzzle_box_count: int = 0,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.curio_count = curio_count
        self.puzzle_box_count = puzzle_box_count
        self.message = None
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        btn_1 = ui.Button(
            label="Open 1",
            style=ButtonStyle.primary,
            emoji="🎁",
            row=0,
            disabled=self.curio_count < 1,
        )
        btn_1.callback = lambda i: self._process_open(i, 1)
        self.add_item(btn_1)

        btn_5 = ui.Button(
            label="Open 5",
            style=ButtonStyle.primary,
            emoji="🎁",
            row=0,
            disabled=self.curio_count < 5,
        )
        btn_5.callback = lambda i: self._process_open(i, 5)
        self.add_item(btn_5)

        btn_10 = ui.Button(
            label="Open 10",
            style=ButtonStyle.primary,
            emoji="🎁",
            row=0,
            disabled=self.curio_count < 10,
        )
        btn_10.callback = lambda i: self._process_open(i, 10)
        self.add_item(btn_10)

        btn_custom = ui.Button(
            label="Custom",
            style=ButtonStyle.secondary,
            emoji="✏️",
            row=0,
            disabled=self.curio_count < 1,
        )
        btn_custom.callback = self._open_custom_modal
        self.add_item(btn_custom)

        btn_box = ui.Button(
            label=f"Puzzle Box ({self.puzzle_box_count})",
            style=ButtonStyle.success,
            emoji="📦",
            row=1,
            disabled=self.puzzle_box_count < 1,
        )
        btn_box.callback = self._open_puzzle_box
        self.add_item(btn_box)

        btn_close = ui.Button(label="Close", style=ButtonStyle.danger, row=1)
        btn_close.callback = self._close
        self.add_item(btn_close)

    def build_hub_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎁 Curios",
            description=(
                f"You have **{self.curio_count}** Curio{'s' if self.curio_count != 1 else ''}.\n"
                f"Select an amount to open."
            ),
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=_UNOPENED_IMAGE)
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)
        except Exception:
            pass

    async def _process_open(self, interaction: Interaction, amount: int):
        await interaction.response.defer()
        result = await CurioManager.process_open(
            self.bot, self.user_id, self.server_id, amount
        )
        self.curio_count -= amount

        embed = discord.Embed(
            title=f"Opened {amount} Curio{'s' if amount != 1 else ''}",
            color=discord.Color.green(),
        )
        embed.description = "\n".join(
            f"**{k}** x{v}" for k, v in result["summary"].items()
        )

        if result["loot_logs"]:
            preview = "\n".join(result["loot_logs"][:5])
            if len(result["loot_logs"]) > 5:
                preview += f"\n…and {len(result['loot_logs']) - 5} more."
            embed.add_field(name="Gear Details", value=preview, inline=False)

        if amount == 1:
            item_name = list(result["summary"].keys())[0]
            url = CurioManager.get_image_url(item_name)
            if url:
                embed.set_image(url=url)
        else:
            embed.set_image(url=_BULK_IMAGE)

        embed.set_footer(text=f"Remaining Curios: {self.curio_count}")

        self._build_buttons()
        if self.curio_count == 0:
            embed.add_field(
                name="Empty!", value="You have no curios left.", inline=False
            )
            await interaction.edit_original_response(embed=embed, view=None)
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
        else:
            await interaction.edit_original_response(embed=embed, view=self)

    async def _open_custom_modal(self, interaction: Interaction):
        modal = CustomAmountModal(max_amount=self.curio_count)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.chosen_amount is None:
            return
        # Re-fetch fresh interaction context via follow-up edit
        await self._process_open_after_modal(interaction, modal.chosen_amount)

    async def _process_open_after_modal(self, interaction: Interaction, amount: int):
        result = await CurioManager.process_open(
            self.bot, self.user_id, self.server_id, amount
        )
        self.curio_count -= amount

        embed = discord.Embed(
            title=f"Opened {amount} Curio{'s' if amount != 1 else ''}",
            color=discord.Color.green(),
        )
        embed.description = "\n".join(
            f"**{k}** x{v}" for k, v in result["summary"].items()
        )

        if result["loot_logs"]:
            preview = "\n".join(result["loot_logs"][:5])
            if len(result["loot_logs"]) > 5:
                preview += f"\n…and {len(result['loot_logs']) - 5} more."
            embed.add_field(name="Gear Details", value=preview, inline=False)

        if amount == 1:
            item_name = list(result["summary"].keys())[0]
            url = CurioManager.get_image_url(item_name)
            if url:
                embed.set_image(url=url)
        else:
            embed.set_image(url=_BULK_IMAGE)

        embed.set_footer(text=f"Remaining Curios: {self.curio_count}")

        self._build_buttons()
        if self.curio_count == 0:
            embed.add_field(
                name="Empty!", value="You have no curios left.", inline=False
            )
            await interaction.edit_original_response(embed=embed, view=None)
            self.bot.state_manager.clear_active(self.user_id)
            self.stop()
        else:
            await interaction.edit_original_response(embed=embed, view=self)

    async def _open_puzzle_box(self, interaction: Interaction):
        if self.puzzle_box_count < 1:
            return await interaction.response.send_message(
                "You don't have any Curio Puzzle Boxes.", ephemeral=True
            )

        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

        self.bot.state_manager.set_active(self.user_id, "puzzle_box")
        view = PuzzleBoxView(self.bot, self.user_id, self.server_id)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    async def _close(self, interaction: Interaction):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.edit_message(view=None)
