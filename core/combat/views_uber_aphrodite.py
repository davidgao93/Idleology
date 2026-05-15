import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.combat import engine
from core.combat import ui as combat_ui
from core.combat.gen.gen_mob import generate_uber_aphrodite
from core.combat.views import CombatView
from core.combat.views_uber_hub import UberHubView, UberReturnView
from core.images import BOSS_APHRODITE
from core.models import Monster, Player


class UberAphroditeLobbyView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        uber_data: dict,
        readiness_text: str,
    ):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.uber_data = uber_data
        self.readiness_text = readiness_text
        self.sigils = uber_data["celestial_sigils"]
        self.message = None
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        btn_start = ui.Button(
            label="Challenge Aphrodite",
            style=ButtonStyle.danger if self.sigils >= 5 else ButtonStyle.secondary,
            disabled=(self.sigils < 5),
            emoji="⚔️",
            row=0,
        )
        btn_start.callback = self.start_uber
        self.add_item(btn_start)

        btn_back = ui.Button(label="← Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🌌 The Celestial Apex", color=discord.Color.gold())
        embed.set_thumbnail(url=BOSS_APHRODITE)

        desc = (
            "A chibi angel appears and says: ME HUNGRY, FEED ME SIGILS!\n\n"
            f"**Entry Cost:** 5 Celestial Sigils\n"
            f"**Owned:** {self.sigils}\n\n"
            f"**Assessment:** {self.readiness_text}\n\n"
            "🛡️ **Radiant Protection** — globally reduces all incoming damage by 60%.\n"
            "🛡️ **Alabaster Skin** — HP is doubled. "
        )
        embed.description = desc

        bp_status = (
            "✅ Unlocked"
            if self.uber_data["celestial_blueprint_unlocked"]
            else "🔒 Locked"
        )
        embed.add_field(
            name="Celestial Engrams",
            value=str(self.uber_data["celestial_engrams"]),
            inline=True,
        )
        embed.add_field(name="Settlement Blueprint", value=bp_status, inline=True)

        return embed

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    async def go_back(self, interaction: Interaction):
        await interaction.response.defer()
        uber_data = await self.bot.database.uber.get_uber_progress(
            self.user_id, self.server_id
        )
        hub = UberHubView(
            self.bot, self.user_id, self.server_id, self.player, uber_data
        )
        embed = hub.build_embed()
        await interaction.edit_original_response(embed=embed, view=hub)
        hub.message = await interaction.original_response()
        self.stop()

    async def start_uber(self, interaction: Interaction):
        if not await self.bot.check_is_active(interaction, self.user_id):
            return

        current_data = await self.bot.database.uber.get_uber_progress(
            self.user_id, self.server_id
        )
        if current_data["celestial_sigils"] < 5:
            return await interaction.response.send_message(
                "You do not have enough Celestial Sigils.", ephemeral=True
            )

        await interaction.response.defer()

        await self.bot.database.uber.increment_sigils(self.user_id, self.server_id, -5)
        self.bot.state_manager.set_active(self.user_id, "uber_boss")

        monster = Monster(
            name="",
            level=0,
            hp=0,
            max_hp=0,
            xp=0,
            attack=0,
            defence=0,
            modifiers=[],
            image="",
            flavor="",
        )
        monster = await generate_uber_aphrodite(self.player, monster)

        self.player.combat_ward = self.player.get_combat_ward_value()
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        monster.is_uber = True

        embed = combat_ui.create_combat_embed(
            self.player, monster, start_logs, title_override="UBER ENCOUNTER"
        )
        return_view = UberReturnView(self.bot, self.user_id, self.server_id, self.player)
        view = CombatView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            monster,
            start_logs,
            combat_phases=None,
            post_combat_view=return_view,
        )

        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()
