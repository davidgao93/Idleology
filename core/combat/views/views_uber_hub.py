import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.images import UBER_HUB
from core.models import Player


class UberReturnView(BaseView):
    """Minimal post-combat view that lets the player return to the Uber Hub."""

    def __init__(self, bot, user_id: str, server_id: str, player):
        super().__init__(bot, user_id, server_id)
        self.player = player

    @ui.button(label="↩ Return to Lobby", style=ButtonStyle.blurple)
    async def return_to_lobby(self, interaction: Interaction, button: ui.Button):
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


class UberHubView(BaseView):
    def __init__(
        self, bot, user_id: str, server_id: str, player: Player, uber_data: dict
    ):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.uber_data = uber_data
        self.message = None
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        btn_aphro = ui.Button(
            label="Aphrodite",
            style=ButtonStyle.blurple,
            emoji="🌌",
            row=0,
        )
        btn_aphro.callback = self.open_aphrodite
        self.add_item(btn_aphro)

        btn_lucifer = ui.Button(
            label="Lucifer",
            style=ButtonStyle.danger,
            emoji="🔥",
            row=0,
        )
        btn_lucifer.callback = self.open_lucifer
        self.add_item(btn_lucifer)

        btn_neet = ui.Button(
            label="NEET",
            style=ButtonStyle.secondary,
            emoji="⬛",
            row=0,
        )
        btn_neet.callback = self.open_neet
        self.add_item(btn_neet)

        btn_gemini = ui.Button(
            label="Gemini",
            style=ButtonStyle.blurple,
            emoji="♊",
            row=0,
        )
        btn_gemini.callback = self.open_gemini
        self.add_item(btn_gemini)

        btn_evelynn = ui.Button(
            label="Evelynn",
            style=ButtonStyle.danger,
            emoji="☠️",
            row=1,
        )
        btn_evelynn.callback = self.open_evelynn
        self.add_item(btn_evelynn)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=2)
        btn_close.callback = self.close_view

        self.add_item(btn_close)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⚔️ Uber Encounters",
            description=(
                "These are the most powerful beings in existence. "
                "Only the truly prepared dare to challenge them.\n\n"
                "Select a boss to view your readiness and available keys."
            ),
            color=discord.Color.dark_gold(),
        )
        embed.set_thumbnail(url=UBER_HUB)
        embed.add_field(
            name="🌌 Aphrodite, Celestial Sovereign",
            value=(
                f"Aphrodite's fury has been unleashed.\n"
                f"**Keys:** {self.uber_data['celestial_sigils']} Celestial Sigils *(costs 3)*"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔥 Lucifer, Infernal Sovereign",
            value=(
                f"Lucifer's fury knows no bounds.\n"
                f"**Keys:** {self.uber_data['infernal_sigils']} Infernal Sigils *(costs 3)*"
            ),
            inline=False,
        )
        embed.add_field(
            name="⬛ NEET, Void Sovereign",
            value=(
                f"NEET's pain has no known depths.\n"
                f"**Keys:** {self.uber_data['void_shards']} Void Sigils *(costs 3)*"
            ),
            inline=False,
        )
        embed.add_field(
            name="♊ Castor & Pollux, Bound Sovereigns",
            value=(
                f"The Gemini's balance is absolute.\n"
                f"**Keys:** {self.uber_data['gemini_sigils']} Gemini Sigils *(costs 3)*"
            ),
            inline=False,
        )
        embed.add_field(
            name="☠️ Evelynn, the Primordial Corruptor",
            value=(
                f"The source of all corruption stirs.\n"
                f"**Keys:** {self.uber_data['corruption_sigils']} Sigils of Corruption *(costs 3)*"
            ),
            inline=False,
        )
        return embed

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    async def open_aphrodite(self, interaction: Interaction):
        from core.combat.dojo.dummy_engine import DummyEngine
        from core.combat.views.views_uber_aphrodite import UberAphroditeLobbyView

        await interaction.response.defer()
        readiness_text = DummyEngine.assess_readiness(
            self.player, target="aphrodite_uber"
        )
        lobby = UberAphroditeLobbyView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.uber_data,
            readiness_text,
        )
        embed = lobby.build_embed()
        await interaction.edit_original_response(embed=embed, view=lobby)
        lobby.message = await interaction.original_response()
        self.stop()

    async def open_lucifer(self, interaction: Interaction):
        from core.combat.dojo.dummy_engine import DummyEngine
        from core.combat.views.views_uber_lucifer import UberLuciferLobbyView

        await interaction.response.defer()
        readiness_text = DummyEngine.assess_readiness(
            self.player, target="lucifer_uber"
        )
        lobby = UberLuciferLobbyView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.uber_data,
            readiness_text,
        )
        embed = lobby.build_embed()
        await interaction.edit_original_response(embed=embed, view=lobby)
        lobby.message = await interaction.original_response()
        self.stop()

    async def open_neet(self, interaction: Interaction):
        from core.combat.dojo.dummy_engine import DummyEngine
        from core.combat.views.views_uber_neet import UberNEETLobbyView

        await interaction.response.defer()
        readiness_text = DummyEngine.assess_readiness(self.player, target="neet_uber")
        lobby = UberNEETLobbyView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.uber_data,
            readiness_text,
        )
        embed = lobby.build_embed()
        await interaction.edit_original_response(embed=embed, view=lobby)
        lobby.message = await interaction.original_response()
        self.stop()

    async def open_gemini(self, interaction: Interaction):
        from core.combat.dojo.dummy_engine import DummyEngine
        from core.combat.views.views_uber_gemini import UberGeminiLobbyView

        await interaction.response.defer()
        readiness_text = DummyEngine.assess_readiness(self.player, target="gemini_uber")
        lobby = UberGeminiLobbyView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.uber_data,
            readiness_text,
        )
        embed = lobby.build_embed()
        await interaction.edit_original_response(embed=embed, view=lobby)
        lobby.message = await interaction.original_response()
        self.stop()

    async def open_evelynn(self, interaction: Interaction):
        from core.combat.dojo.dummy_engine import DummyEngine
        from core.combat.views.views_uber_evelynn import UberEvelynnLobbyView

        await interaction.response.defer()
        readiness_text = DummyEngine.assess_readiness(
            self.player, target="evelynn_uber"
        )
        lobby = UberEvelynnLobbyView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            self.uber_data,
            readiness_text,
        )
        embed = lobby.build_embed()
        await interaction.edit_original_response(embed=embed, view=lobby)
        lobby.message = await interaction.original_response()
        self.stop()
