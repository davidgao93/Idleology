import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.codex.mechanics import (
    apply_signature_modifier,
    reset_for_new_codex_run,
    select_run_chapters,
)
from core.codex.views.run_view import (
    CodexRunView,
    _generate_codex_wave_monster,
    build_wave_baseline,
)
from core.codex.views.tomes_view import CodexTomsView
from core.combat import ui as combat_ui
from core.combat.turns import engine
from core.images import SERAPHINE_PORTRAIT, SERAPHINE_THUMBNAIL
from core.npc_voices import get_quip
from core.models import Player


class CodexMenuRow(discord.ui.ActionRow["CodexMenuView"]):
    @discord.ui.button(label="Begin Run", style=ButtonStyle.danger, emoji="📖")
    async def begin_run_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_begin_run(interaction)

    @discord.ui.button(label="Tomes", style=ButtonStyle.primary, emoji="📚")
    async def tomes_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_view_tomes(interaction)

    @discord.ui.button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
    async def close_btn(self, interaction: Interaction, button: ui.Button):
        await self.view._on_close(interaction)


class CodexMenuView(BaseLayoutView):
    def __init__(
        self,
        bot,
        user_id: str,
        player: Player,
        fragments: int,
        pages: int,
        rerolls: int,
        chapter_history: dict,
        antique_tomes: int = 0,
        server_id: str = "",
        saved_run: dict | None = None,
        player_avatar_url: str | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.fragments = fragments
        self.pages = pages
        self.rerolls = rerolls
        self.chapter_history = chapter_history
        self.antique_tomes = antique_tomes
        self.saved_run = saved_run
        self.player_avatar_url = player_avatar_url
        self._processing = False

        self.row = CodexMenuRow()
        if saved_run is not None:
            self.row.begin_run_btn.label = "Resume Run"
            self.row.begin_run_btn.emoji = "▶️"

        self.add_item(combat_ui.embed_to_container(self.build_embed()))
        self.add_item(self.row)

    def build_embed(self) -> discord.Embed:
        tomes = self.player.codex_tomes
        embed = discord.Embed(
            title="📖 The Codex",
            description=(
                f"*{get_quip('codex')}*\n\n"
                "An onslaught of curated chapters, each more brutal than the last.\n"
                "Five chapters are drawn at random per run. Manage your Tomes of power."
            ),
            color=discord.Color.dark_purple(),
        )
        embed.set_author(name="Seraphine", icon_url=SERAPHINE_PORTRAIT)
        embed.set_thumbnail(url=SERAPHINE_THUMBNAIL)
        embed.add_field(
            name="Resources",
            value=(
                f"📖 {self.antique_tomes} Antique Tome(s)  |  "
                f"🔷 {self.fragments} Fragments  |  📄 {self.pages} Pages"
            ),
            inline=False,
        )
        if self.saved_run is not None:
            embed.add_field(
                name="▶️ Run in Progress",
                value=(
                    f"Saved at **Chapter {self.saved_run.get('chapter_idx', 0) + 1}/5** "
                    f"({self.saved_run.get('chapters_cleared', 0)} cleared, "
                    f"{self.saved_run.get('deaths', 0)} death(s)). "
                    "Resume costs no Tome."
                ),
                inline=False,
            )
        total_clears = sum(v["clears"] for v in self.chapter_history.values())
        total_perfects = sum(v["perfect_clears"] for v in self.chapter_history.values())
        embed.add_field(name="Chapter Clears", value=str(total_clears), inline=True)
        embed.add_field(name="Perfect Clears", value=str(total_perfects), inline=True)
        embed.add_field(
            name="Tome Slots Unlocked", value=f"{len(tomes)}/5", inline=True
        )
        embed.set_footer(
            text=(
                "Level 80+ required to begin a run.\n"
                "Save & Exit only checkpoints at the start of each chapter — "
                "mid-chapter progress is lost if you save."
            )
        )
        return embed

    async def _on_begin_run(self, interaction: Interaction):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True

        # Resume a persisted run (chapter-boundary checkpoint) — no Tome cost.
        saved = await self.bot.database.codex.get_run(self.user_id, self.server_id)
        if saved is not None:
            await interaction.response.defer()
            self.bot.state_manager.set_active(self.user_id, "codex")
            view = await CodexRunView.resume_from_snapshot(
                self.bot,
                self.user_id,
                self.player,
                saved,
                server_id=self.server_id,
                player_avatar_url=self.player_avatar_url,
            )
            self.stop()
            msg = await interaction.edit_original_response(view=view)
            view.message = msg
            return

        current_tomes = await self.bot.database.users.get_currency(
            self.user_id, "antique_tome"
        )
        if current_tomes < 1:
            self._processing = False
            return await interaction.response.send_message(
                "You need an **Antique Tome** to begin a Codex run.", ephemeral=True
            )

        await interaction.response.defer()

        self.bot.state_manager.set_active(self.user_id, "codex")

        reset_for_new_codex_run(self.player)

        # Clear active task species — prevents slayer task completion and species-gated
        # emblem bonuses (slayer_dmg / slayer_def), which are tied to assigned tasks.
        self.player.active_task_species = None

        chapters = select_run_chapters(5)
        chapter = chapters[0]

        self.player.combat_ward = self.player.get_combat_ward_value()
        apply_signature_modifier(self.player, chapter)

        wave_baseline = build_wave_baseline(self.player)

        monster = await _generate_codex_wave_monster(self.player, chapter, 1)
        engine.apply_stat_effects(self.player, monster)
        start_logs = engine.apply_combat_start_passives(self.player, monster)

        view = CodexRunView(
            self.bot,
            self.user_id,
            self.player,
            chapters,
            monster,
            start_logs,
            chapter_wave_baseline=wave_baseline,
            server_id=self.server_id,
            player_avatar_url=self.player_avatar_url,
        )

        # Atomic entry: the Tome is only spent together with the initial
        # checkpoint, so a crash can never eat the entry cost without
        # leaving a resumable run behind.
        async with self.bot.database.transaction():
            await self.bot.database.users.modify_currency(
                self.user_id, "antique_tome", -1
            )
            await self.bot.database.codex.upsert_run(
                self.user_id, self.server_id, view.to_snapshot()
            )

        self.stop()
        msg = await interaction.edit_original_response(view=view)
        view.message = msg

    async def _on_view_tomes(self, interaction: Interaction):
        tomes_view = CodexTomsView(
            self.bot,
            self.user_id,
            self.player,
            self.fragments,
            self.pages,
            self.rerolls,
            self.chapter_history,
            server_id=self.server_id,
            player_avatar_url=self.player_avatar_url,
        )
        self.stop()
        await interaction.response.edit_message(view=tomes_view)

    async def _on_close(self, interaction: Interaction):
        # No clear_active here: the /codex cog never calls set_active for the browsing
        # menu (only begin_run does, and it clears on every exit path of CodexRunView).
        # Clearing here could wipe an unrelated feature's active state if the user
        # started something else while this menu sat open.
        # session-terminating Close for menu (no active guard for browse state)
        await interaction.response.defer()
        self.stop()
        await interaction.delete_original_response()
