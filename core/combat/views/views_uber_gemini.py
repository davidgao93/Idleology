import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.combat.mobgen.gen_mob import generate_uber_gemini
from core.combat.turns import engine
from core.combat.views.views import CombatView
from core.combat.views.views_uber_hub import UberHubView, UberReturnView
from core.images import BOSS_GEMINI
from core.models import Monster, Player


class UberGeminiLobbyView(BaseView):
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
        self.sigils = uber_data["gemini_sigils"]
        self.message = None
        self._processing = False
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        btn_start = ui.Button(
            label="Challenge the Twins",
            style=ButtonStyle.danger if self.sigils >= 3 else ButtonStyle.secondary,
            disabled=(self.sigils < 3),
            emoji="⚔️",
            row=0,
        )
        btn_start.callback = self.start_uber
        self.add_item(btn_start)

        btn_back = ui.Button(label="← Back", style=ButtonStyle.secondary, row=1)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, emoji="✖️", row=1)
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="♊ The Bound Sovereigns", color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=BOSS_GEMINI)

        desc = (
            "You approach two chubby kids. A voice — no, two voices, perfectly in time:\n"
            '*"We are balance made flesh. For every blow you land, we answer in kind."*\n'
            '*"You think to yourself, I need to layoff the drugs..."*\n\n'
            f"**Entry Cost:** 3 Gemini Sigils\n"
            f"**Owned:** {self.sigils}\n\n"
            f"**Assessment:** {self.readiness_text}\n\n"
            "⚡ **Balanced Protection** — globally reduces all incoming damage by 60%.\n"
            "⚡ **Twin Strike** — every other turn, deal a ward-piercing blow."
        )
        embed.description = desc

        bp_status = (
            "✅ Unlocked"
            if self.uber_data.get("gemini_blueprint_unlocked", 0)
            else "🔒 Locked"
        )
        embed.add_field(
            name="Gemini Engrams",
            value=str(self.uber_data.get("gemini_engrams", 0)),
            inline=True,
        )
        embed.add_field(name="Twin Shrine Blueprint", value=bp_status, inline=True)

        return embed

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        self.bot.state_manager.clear_active(self.user_id)
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
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        current_data = await self.bot.database.uber.get_uber_progress(
            self.user_id, self.server_id
        )
        if current_data["gemini_sigils"] < 3:
            self._processing = False
            return await interaction.response.send_message(
                "You do not have enough Gemini Sigils.", ephemeral=True
            )

        await interaction.response.defer()

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
        monster = generate_uber_gemini(self.player, monster)
        self.player.combat_ward = self.player.get_combat_ward_value()
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)
        monster.is_uber = True
        return_view = UberReturnView(
            self.bot, self.user_id, self.server_id, self.player
        )
        view = CombatView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            monster,
            start_logs,
            combat_phases=None,
            post_combat_view=return_view,
            title_override="♊ UBER ENCOUNTER",
        )

        await self.bot.database.uber.increment_gemini_sigils(
            self.user_id, self.server_id, -3
        )
        self.bot.state_manager.set_active(self.user_id, "uber_boss")
        try:
            await interaction.edit_original_response(embed=None, view=view)
            view.message = await interaction.original_response()
        except Exception:
            await self.bot.database.uber.increment_gemini_sigils(
                self.user_id, self.server_id, 3
            )
            self.bot.state_manager.clear_active(self.user_id)
            await interaction.followup.send(
                "Something went wrong starting the encounter. Your sigils have been refunded.",
                ephemeral=True,
            )
            return
        self.stop()
