import discord
from discord import ButtonStyle, Interaction, ui

from core.combat import engine
from core.combat import ui as combat_ui
from core.combat.gen_mob import (
    generate_uber_aphrodite,
    generate_uber_gemini,
    generate_uber_lucifer,
    generate_uber_neet,
)
from core.combat.views import CombatView  # Reuse the battle engine
from core.images import BOSS_APHRODITE, BOSS_GEMINI, BOSS_LUCIFER, BOSS_NEET
from core.models import Monster, Player


class UberHubView(ui.View):
    def __init__(
        self, bot, user_id: str, server_id: str, player: Player, uber_data: dict
    ):
        super().__init__(timeout=120)
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
            label="Challenge Aphrodite",
            style=ButtonStyle.blurple,
            emoji="🌌",
            row=0,
        )
        btn_aphro.callback = self.open_aphrodite
        self.add_item(btn_aphro)

        btn_lucifer = ui.Button(
            label="Challenge Lucifer",
            style=ButtonStyle.danger,
            emoji="🔥",
            row=0,
        )
        btn_lucifer.callback = self.open_lucifer
        self.add_item(btn_lucifer)

        btn_neet = ui.Button(
            label="Challenge NEET",
            style=ButtonStyle.secondary,
            emoji="⬛",
            row=1,
        )
        btn_neet.callback = self.open_neet
        self.add_item(btn_neet)

        btn_gemini = ui.Button(
            label="Challenge Gemini",
            style=ButtonStyle.blurple,
            emoji="♊",
            row=2,
        )
        btn_gemini.callback = self.open_gemini
        self.add_item(btn_gemini)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=3)
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
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    async def open_aphrodite(self, interaction: Interaction):
        from core.combat.dummy_engine import DummyEngine

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
        from core.combat.dummy_engine import DummyEngine

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
        from core.combat.dummy_engine import DummyEngine

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
        from core.combat.dummy_engine import DummyEngine

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


class UberAphroditeLobbyView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        uber_data: dict,
        readiness_text: str,
    ):
        super().__init__(timeout=120)
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

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🌌 The Celestial Apex", color=discord.Color.gold())
        embed.set_thumbnail(url=BOSS_APHRODITE)

        desc = (
            "A chibi angel appears and says: ME HUNGRY, FEED ME SIGILS!\n\n"
            f"**Entry Cost:** 3 Celestial Sigils\n"
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

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

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
        if current_data["celestial_sigils"] < 3:
            return await interaction.response.send_message(
                "You do not have enough Celestial Sigils.", ephemeral=True
            )

        await interaction.response.defer()

        await self.bot.database.uber.increment_sigils(self.user_id, self.server_id, -3)
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
        print(monster)
        self.player.combat_ward = self.player.get_combat_ward_value()
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        monster.is_uber = True

        embed = combat_ui.create_combat_embed(
            self.player, monster, start_logs, title_override="🌌 UBER ENCOUNTER"
        )
        view = CombatView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            monster,
            start_logs,
            combat_phases=None,
        )

        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()


class UberLuciferLobbyView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        uber_data: dict,
        readiness_text: str,
    ):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.uber_data = uber_data
        self.readiness_text = readiness_text
        self.sigils = uber_data["infernal_sigils"]
        self.message = None
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()

        btn_start = ui.Button(
            label="Challenge Lucifer",
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

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
        btn_close.callback = self.close_view
        self.add_item(btn_close)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔥 The Infernal Sovereign", color=discord.Color.dark_red()
        )

        desc = (
            "A chibi Lucifer appears and squeaks:\n"
            '*"You dare enter my domain? I will grind your bones to ash."*\n'
            '*"Hand me your sigils and I may let you live..."*\n\n'
            f"**Entry Cost:** 3 Infernal Sigils\n"
            f"**Owned:** {self.sigils}\n\n"
            f"**Assessment:** {self.readiness_text}\n\n"
            "🔥 **Infernal Protection** — globally reduces all incoming damage by 60%.\n"
            "🔥 **Infernal Strength** — ATK is doubled. "
        )
        embed.description = desc

        bp_status = (
            "✅ Unlocked"
            if self.uber_data["infernal_blueprint_unlocked"]
            else "🔒 Locked"
        )
        embed.add_field(
            name="Infernal Engrams",
            value=str(self.uber_data["infernal_engrams"]),
            inline=True,
        )
        embed.add_field(name="Infernal Forge Blueprint", value=bp_status, inline=True)
        embed.set_thumbnail(url=BOSS_LUCIFER)
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

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
        if current_data["infernal_sigils"] < 3:
            return await interaction.response.send_message(
                "You do not have enough Infernal Sigils.", ephemeral=True
            )

        await interaction.response.defer()

        await self.bot.database.uber.increment_infernal_sigils(
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
        monster = await generate_uber_lucifer(self.player, monster)
        print(monster)
        self.player.combat_ward = self.player.get_combat_ward_value()
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        monster.is_uber = True

        embed = combat_ui.create_combat_embed(
            self.player, monster, start_logs, title_override="🔥 UBER ENCOUNTER"
        )
        view = CombatView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            monster,
            start_logs,
            combat_phases=None,
        )

        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()


class UberNEETLobbyView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        uber_data: dict,
        readiness_text: str,
    ):
        super().__init__(timeout=120)
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

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

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
        print(monster)
        self.player.combat_ward = self.player.get_combat_ward_value()
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        monster.is_uber = True

        embed = combat_ui.create_combat_embed(
            self.player, monster, start_logs, title_override="⬛ UBER ENCOUNTER"
        )
        view = CombatView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            monster,
            start_logs,
            combat_phases=None,
        )

        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()


class UberGeminiLobbyView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        uber_data: dict,
        readiness_text: str,
    ):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.player = player
        self.uber_data = uber_data
        self.readiness_text = readiness_text
        self.sigils = uber_data["gemini_sigils"]
        self.message = None
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

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, row=1)
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

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

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
        if current_data["gemini_sigils"] < 3:
            return await interaction.response.send_message(
                "You do not have enough Gemini Sigils.", ephemeral=True
            )

        await interaction.response.defer()

        await self.bot.database.uber.increment_gemini_sigils(
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
        monster = generate_uber_gemini(self.player, monster)
        print(monster)
        self.player.combat_ward = self.player.get_combat_ward_value()
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        monster.is_uber = True

        embed = combat_ui.create_combat_embed(
            self.player, monster, start_logs, title_override="♊ UBER ENCOUNTER"
        )
        view = CombatView(
            self.bot,
            self.user_id,
            self.server_id,
            self.player,
            monster,
            start_logs,
            combat_phases=None,
        )

        await interaction.edit_original_response(embed=embed, view=view)
        self.stop()
