import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.combat import ui as combat_ui
from core.combat.mobgen.gen_mob import generate_uber_neet
from core.combat.turns import engine
from core.combat.views.views import CombatView
from core.combat.views.views_uber_hub import UberHubView, UberReturnView
from core.images import BOSS_NEET
from core.models import Monster, Player


class UberNEETLobbyView(BaseView):
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
        self.shards = uber_data["void_shards"]
        self.message = None
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        btn_start = ui.Button(
            label="Challenge NEET",
            style=ButtonStyle.danger if self.shards >= 3 else ButtonStyle.secondary,
            disabled=(self.shards < 3),
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
        embed = discord.Embed(
            title="⬛ The Void Sovereign", color=discord.Color.dark_theme()
        )

        desc = (
            "A Chibi voidling NEET appears:\n"
            '*"You have wandered too far into the void. Give me some shards and I may guide you back."*\n\n'
            f"**Entry Cost:** 3 Void Sigils\n"
            f"**Owned:** {self.shards}\n\n"
            f"**Assessment:** {self.readiness_text}\n\n"
            "⬛ **Void Protection** — globally reduces all incoming damage by 60%.\n"
            "⬛ **Void Drain** siphons 0.5% of your ATK and DEF each round."
        )
        embed.description = desc

        bp_status = (
            "✅ Unlocked" if self.uber_data["void_blueprint_unlocked"] else "🔒 Locked"
        )
        embed.add_field(
            name="Void Engrams",
            value=str(self.uber_data["void_engrams"]),
            inline=True,
        )
        embed.add_field(name="Void Sanctum Blueprint", value=bp_status, inline=True)
        embed.set_thumbnail(url=BOSS_NEET)
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
        current_data = await self.bot.database.uber.get_uber_progress(
            self.user_id, self.server_id
        )
        if current_data["void_shards"] < 3:
            return await interaction.response.send_message(
                "You do not have enough Void Sigils.", ephemeral=True
            )

        await interaction.response.defer()

        await self.bot.database.uber.increment_void_shards(
            self.user_id, self.server_id, -3
        )
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
        monster = generate_uber_neet(self.player, monster)

        self.player.combat_ward = self.player.get_combat_ward_value()
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        monster.is_uber = True

        embed = combat_ui.create_combat_embed(
            self.player, monster, start_logs, title_override="⬛ UBER ENCOUNTER"
        )
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
        )

        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()
