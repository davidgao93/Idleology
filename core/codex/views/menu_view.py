import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.codex.mechanics import apply_signature_modifier, select_run_chapters
from core.codex.views.run_view import CodexRunView, _generate_codex_wave_monster
from core.codex.views.tomes_view import CodexTomsView
from core.combat import jewel_engine as _je
from core.combat.turns import engine
from core.images import SERAPHINE_PORTRAIT, SERAPHINE_THUMBNAIL
from core.npc_voices import get_quip
from core.models import Player


class CodexMenuView(BaseView):
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
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.fragments = fragments
        self.pages = pages
        self.rerolls = rerolls
        self.chapter_history = chapter_history
        self.antique_tomes = antique_tomes

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
        total_clears = sum(v["clears"] for v in self.chapter_history.values())
        total_perfects = sum(v["perfect_clears"] for v in self.chapter_history.values())
        embed.add_field(name="Chapter Clears", value=str(total_clears), inline=True)
        embed.add_field(name="Perfect Clears", value=str(total_perfects), inline=True)
        embed.add_field(
            name="Tome Slots Unlocked", value=f"{len(tomes)}/5", inline=True
        )
        embed.set_footer(text="Level 80+ required to begin a run.")
        return embed

    @ui.button(label="Begin Run", style=ButtonStyle.danger, emoji="📖", row=0)
    async def begin_run(self, interaction: Interaction, button: ui.Button):
        current_tomes = await self.bot.database.users.get_currency(
            self.user_id, "antique_tome"
        )
        if current_tomes < 1:
            return await interaction.response.send_message(
                "You need an **Antique Tome** to begin a Codex run.", ephemeral=True
            )

        await interaction.response.defer()

        await self.bot.database.users.modify_currency(self.user_id, "antique_tome", -1)
        self.bot.state_manager.set_active(self.user_id, "codex")

        _je.reset_jewel_charges(self.player)

        # Clear active task species — prevents slayer task completion and species-gated
        # emblem bonuses (slayer_dmg / slayer_def), which are tied to assigned tasks.
        self.player.active_task_species = None

        chapters = select_run_chapters(5)
        chapter = chapters[0]

        self.player.combat_ward = self.player.get_combat_ward_value()
        apply_signature_modifier(self.player, chapter)

        wave_baseline = {
            "bonus_crit": self.player.bonus_crit,
            "bonus_max_hp": self.player.bonus_max_hp,
            "combat_ward": self.player.combat_ward,
            "atk_multiplier": self.player.atk_multiplier,
            "def_multiplier": self.player.def_multiplier,
            "crit_multiplier": self.player.crit_multiplier,
            "chapter_hit_penalty": self.player.chapter_hit_penalty,
            "chapter_pdr_reduction": self.player.chapter_pdr_reduction,
            "chapter_ward_gen_mult": self.player.chapter_ward_gen_mult,
            "chapter_crit_dmg_reduction": self.player.chapter_crit_dmg_reduction,
            "chapter_hp_entry_pct": self.player.chapter_hp_entry_pct,
        }

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
        )

        embed = view._combat_embed()
        self.stop()
        msg = await interaction.edit_original_response(embed=embed, view=view)
        view._message_ref = msg

    @ui.button(label="Tomes", style=ButtonStyle.primary, emoji="📚", row=0)
    async def view_tomes(self, interaction: Interaction, button: ui.Button):
        tomes_view = CodexTomsView(
            self.bot,
            self.user_id,
            self.player,
            self.fragments,
            self.pages,
            self.rerolls,
            self.chapter_history,
        )
        self.stop()
        await interaction.response.edit_message(
            embed=tomes_view._build_embed(), view=tomes_view
        )

    @ui.button(label="Close", style=ButtonStyle.secondary, row=0)
    async def exit_btn(self, interaction: Interaction, button: ui.Button):
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()
