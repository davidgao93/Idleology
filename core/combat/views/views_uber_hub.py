import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.images import ARBITER_PORTRAIT, ARBITER_THUMBNAIL
from core.npc_voices import get_quip
from core.models import Player


class UberReturnRow(discord.ui.ActionRow["UberReturnView"]):
    @discord.ui.button(label="↩ Return to Lobby", style=ButtonStyle.secondary)
    async def return_to_lobby(self, interaction: Interaction, button: ui.Button):
        await self.view._on_return_to_lobby(interaction)


class UberReturnView(BaseLayoutView):
    """Minimal post-combat view that lets the player return to the Uber Hub."""

    def __init__(self, bot, user_id: str, server_id: str, player):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.row = UberReturnRow()

    def set_content(self, embed: discord.Embed) -> None:
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(self.row)

    async def _on_return_to_lobby(self, interaction: Interaction):
        await interaction.response.defer()
        uber_data = await self.bot.database.uber.get_uber_progress(
            self.user_id, self.server_id
        )
        hub = UberHubView(
            self.bot, self.user_id, self.server_id, self.player, uber_data
        )
        await interaction.edit_original_response(view=hub)
        hub.message = await interaction.original_response()
        self.stop()


class UberHubView(BaseLayoutView):
    def __init__(
        self, bot, user_id: str, server_id: str, player: Player, uber_data: dict
    ):
        super().__init__(bot, user_id, server_id)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.uber_data = uber_data
        self._processing = False
        self._sync_items()

    # Minimum level required per boss
    _BOSS_LEVELS = {
        "aphrodite": 20,
        "lucifer": 30,
        "gemini": 40,
        "neet": 50,
        "evelynn": 100,
    }

    def _build_rows(self) -> list[discord.ui.ActionRow]:
        lvl = self.player.level
        row0 = discord.ui.ActionRow()
        row1 = discord.ui.ActionRow()
        row2 = discord.ui.ActionRow()

        btn_aphro = ui.Button(
            label="Aphrodite",
            style=ButtonStyle.blurple,
            emoji="🌌",
            disabled=lvl < self._BOSS_LEVELS["aphrodite"],
        )
        btn_aphro.callback = self.open_aphrodite
        row0.add_item(btn_aphro)

        btn_lucifer = ui.Button(
            label="Lucifer",
            style=ButtonStyle.danger,
            emoji="🔥",
            disabled=lvl < self._BOSS_LEVELS["lucifer"],
        )
        btn_lucifer.callback = self.open_lucifer
        row0.add_item(btn_lucifer)

        btn_gemini = ui.Button(
            label="Gemini",
            style=ButtonStyle.blurple,
            emoji="♊",
            disabled=lvl < self._BOSS_LEVELS["gemini"],
        )
        btn_gemini.callback = self.open_gemini
        row0.add_item(btn_gemini)

        btn_neet = ui.Button(
            label="NEET",
            style=ButtonStyle.secondary,
            emoji="⬛",
            disabled=lvl < self._BOSS_LEVELS["neet"],
        )
        btn_neet.callback = self.open_neet
        row0.add_item(btn_neet)

        btn_evelynn = ui.Button(
            label="Evelynn",
            style=ButtonStyle.danger,
            emoji="☠️",
            disabled=lvl < self._BOSS_LEVELS["evelynn"],
        )
        btn_evelynn.callback = self.open_evelynn
        row1.add_item(btn_evelynn)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        btn_close.callback = self.close_view
        row2.add_item(btn_close)

        return [row0, row1, row2]

    def _sync_items(self):
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(self.build_embed()))
        for row in self._build_rows():
            self.add_item(row)

    def build_embed(self) -> discord.Embed:
        lvl = self.player.level
        embed = discord.Embed(
            title="⚔️ Uber Encounters",
            description=(
                f"*{get_quip('uber')}*\n\n"
                "These are the most powerful beings in existence. "
                "Only the truly prepared dare to challenge them.\n\n"
                "Select a boss to view your readiness and available keys."
            ),
            color=discord.Color.dark_gold(),
        )
        embed.set_author(name="The Arbiter", icon_url=ARBITER_PORTRAIT)
        embed.set_thumbnail(url=ARBITER_THUMBNAIL)

        def _boss_field(name: str, flavor: str, key_text: str, req_lvl: int) -> str:
            if lvl >= req_lvl:
                return f"{flavor}\n**Keys:** {key_text}"
            return f"🔒 Unlocks at Level {req_lvl}"

        embed.add_field(
            name="🌌 Aphrodite, Celestial Sovereign",
            value=_boss_field(
                "aphrodite",
                "Aphrodite's fury has been unleashed.",
                f"{self.uber_data['celestial_sigils']} Celestial Sigils *(costs 3)*",
                self._BOSS_LEVELS["aphrodite"],
            ),
            inline=False,
        )
        embed.add_field(
            name="🔥 Lucifer, Infernal Sovereign",
            value=_boss_field(
                "lucifer",
                "Lucifer's fury knows no bounds.",
                f"{self.uber_data['infernal_sigils']} Infernal Sigils *(costs 3)*",
                self._BOSS_LEVELS["lucifer"],
            ),
            inline=False,
        )
        embed.add_field(
            name="♊ Castor & Pollux, Bound Sovereigns",
            value=_boss_field(
                "gemini",
                "The Gemini's balance is absolute.",
                f"{self.uber_data['gemini_sigils']} Gemini Sigils *(costs 3)*",
                self._BOSS_LEVELS["gemini"],
            ),
            inline=False,
        )
        embed.add_field(
            name="⬛ NEET, Void Sovereign",
            value=_boss_field(
                "neet",
                "NEET's pain has no known depths.",
                f"{self.uber_data['void_shards']} Void Sigils *(costs 3)*",
                self._BOSS_LEVELS["neet"],
            ),
            inline=False,
        )
        embed.add_field(
            name="☠️ Evelynn, the Primordial Corruptor",
            value=_boss_field(
                "evelynn",
                "The source of all corruption stirs.",
                f"{self.uber_data['corruption_sigils']} Sigils of Corruption *(costs 3)*",
                self._BOSS_LEVELS["evelynn"],
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
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
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
        # UberAphroditeLobbyView stays classic — this is a genuine scene
        # change (boss-specific lobby, not part of the combat thread), so it
        # gets a fresh message rather than reusing this one.
        await combat_ui.freeze_and_handoff(interaction.message, embed, lobby)
        self.stop()

    async def open_lucifer(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
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
        await combat_ui.freeze_and_handoff(interaction.message, embed, lobby)
        self.stop()

    async def open_neet(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
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
        await combat_ui.freeze_and_handoff(interaction.message, embed, lobby)
        self.stop()

    async def open_gemini(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
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
        await combat_ui.freeze_and_handoff(interaction.message, embed, lobby)
        self.stop()

    async def open_evelynn(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
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
        await combat_ui.freeze_and_handoff(interaction.message, embed, lobby)
        self.stop()
