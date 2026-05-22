import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.combat.mobgen.modifier_data import (
    COMMON_MOD_NAMES,
    RARE_FLAT_MOD_NAMES,
    RARE_TIERED_MOD_NAMES,
)
from core.combat.turns import engine
from core.images import COMBAT_LOW_HEALTH, CORRUPTION_GATE


class LowHealthWarningView(BaseView):
    def __init__(
        self, bot, user_id, server_id, existing_user, player, continue_callback
    ):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.existing_user = existing_user
        self.player = player
        self.continue_callback = (
            continue_callback  # The function to call to actually start combat
        )

        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        # Potion Button
        btn_heal = ui.Button(
            label=f"Drink Potion ({self.player.potions})",
            style=ButtonStyle.success,
            emoji="🧪",
            disabled=(self.player.potions <= 0),
        )
        btn_heal.callback = self.heal
        self.add_item(btn_heal)

        # Fight Button (Changes color if safe)
        is_safe = self.player.current_hp >= (self.player.total_max_hp * 0.25)
        btn_fight = ui.Button(
            label="Fight" if is_safe else "Fight Anyway",
            style=ButtonStyle.primary if is_safe else ButtonStyle.danger,
            emoji="⚔️",
        )
        btn_fight.callback = self.fight
        self.add_item(btn_fight)

        # Flee Button
        btn_flee = ui.Button(label="Flee", style=ButtonStyle.secondary)
        btn_flee.callback = self.flee
        self.add_item(btn_flee)

    def build_embed(self) -> discord.Embed:
        is_safe = self.player.current_hp >= (self.player.total_max_hp * 0.25)
        color = discord.Color.orange() if is_safe else discord.Color.red()

        embed = discord.Embed(title="⚠️ Warning: Low Health", color=color)
        embed.description = f"You are about to enter combat with **{self.player.current_hp}/{self.player.total_max_hp} HP**.\nDeath results in a 10% XP penalty."
        embed.set_thumbnail(url=COMBAT_LOW_HEALTH)
        return embed

    async def heal(self, interaction: Interaction):
        msg = engine.process_heal(self.player)
        await self.bot.database.users.update_from_player_object(self.player)

        self.update_buttons()
        await interaction.response.edit_message(
            content=f"*{msg}*", embed=self.build_embed(), view=self
        )

    async def fight(self, interaction: Interaction):
        # We MUST defer here because generating the monster/boss can take a second
        await interaction.response.defer()

        # We pass control back to the Cog to run the rest of the combat logic
        await self.continue_callback(
            interaction, self.user_id, self.server_id, self.existing_user, self.player
        )
        self.stop()

    async def flee(self, interaction: Interaction):
        await interaction.response.edit_message(
            content="You back away from the danger. Live to fight another day.",
            embed=None,
            view=None,
        )
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()


class CorruptedEncounterGateView(BaseView):
    """Pre-encounter gate shown when a Corrupted monster spawns.

    The player may choose to face it or flee (which falls back to a
    regular encounter).  No currency cost — the gate is purely informational.
    """

    _MOD_COUNT = (
        len(COMMON_MOD_NAMES) + len(RARE_TIERED_MOD_NAMES) + len(RARE_FLAT_MOD_NAMES)
    )

    def __init__(self, bot, user_id: str):
        super().__init__(bot, user_id)
        self.bot = bot
        self.user_id = user_id
        self.accepted: bool = False

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="☠️ A Corrupted Entity Approaches",
            description=(
                "An ancient evil has seeped into this realm, twisting a creature beyond recognition.\n\n"
                "This is no ordinary encounter. The entity before you carries **every modifier** "
                "at maximum potency — a trial meant to break the strong.\n\n"
                "*Only those who've proven themselves may stand a chance.*"
            ),
            color=0x6A0DAD,
        )
        embed.set_image(url=CORRUPTION_GATE)
        embed.set_footer(text="Flee to face a regular encounter instead.")
        return embed

    @ui.button(label="Face the Corrupted", style=ButtonStyle.danger, emoji="☠️")
    async def face(self, interaction: Interaction, button: ui.Button):
        self.accepted = True
        await interaction.response.defer()
        self.stop()

    @ui.button(label="Flee", style=ButtonStyle.secondary)
    async def flee(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        self.stop()
