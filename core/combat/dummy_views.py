import discord
from discord import ui, ButtonStyle, Interaction, SelectOption
from core.combat.dummy_engine import DummyEngine
from core.models import Monster
from core.combat.gen_mob import get_modifier_description, calculate_monster_stats
from core.combat.modifier_data import (
    COMMON_MOD_NAMES, RARE_TIERED_MOD_NAMES, RARE_FLAT_MOD_NAMES,
    BOSS_MOD_NAMES, make_modifier,
)

# ---------------------------------------------------------------------------
# Modifier catalogue
# ---------------------------------------------------------------------------

# Normal / rare modifiers available in the dummy configurator
_NORMAL_MODS = sorted(COMMON_MOD_NAMES + RARE_TIERED_MOD_NAMES + RARE_FLAT_MOD_NAMES)

# Boss / uber modifiers
_SPECIAL_MODS = list(BOSS_MOD_NAMES) + [
    "Radiant Protection", "Infernal Protection", "Balanced Protection", "Void Protection",
    "Hell's Fury", "Void Aura", "Balanced Strikes",
]


# ---------------------------------------------------------------------------
# Level modal
# ---------------------------------------------------------------------------

class SetLevelModal(discord.ui.Modal, title="Set Dummy Level"):
    level_input = discord.ui.TextInput(
        label="Dummy Level",
        placeholder="Enter any positive number, e.g. 150",
        min_length=1,
        max_length=5,
    )

    def __init__(self, parent_view: "DummyConfigView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            lvl = int(self.level_input.value)
            if lvl < 1:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "Please enter a valid positive number.", ephemeral=True
            )
        self.parent_view.dummy_level = lvl
        self.parent_view.update_components()
        await interaction.response.edit_message(
            embed=self.parent_view.build_embed(), view=self.parent_view
        )


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------

class DummyConfigView(ui.View):
    def __init__(self, bot, user_id: str, player):
        super().__init__(timeout=300)
        self.bot      = bot
        self.user_id  = user_id
        self.player   = player

        # Configuration state
        self.dummy_level = player.level
        self.active_mods: list[str] = []
        self.is_boss_mode   = False   # Applies boss_dmg emblem instead of combat_dmg
        self.slayer_active  = False   # Simulates slayer task matching this dummy

        self.update_components()

    # ---------------------------------------------------------------------- #
    # discord.py checks                                                        #
    # ---------------------------------------------------------------------- #

    async def interaction_check(self, interaction: Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            await self.message.edit(view=None)
        except Exception:
            pass

    # ---------------------------------------------------------------------- #
    # Embed                                                                    #
    # ---------------------------------------------------------------------- #

    def build_embed(self, results=None) -> discord.Embed:
        mode_tag = "⚔️ Boss" if self.is_boss_mode else "🗡️ Normal"
        slay_tag = " | ⚔️ Slayer" if self.slayer_active else ""
        embed = discord.Embed(
            title="🥋 Combat Dojo",
            color=discord.Color.green() if results else discord.Color.light_grey(),
        )
        embed.set_thumbnail(url="https://i.imgur.com/v1BrB1M.png")

        # Settings summary
        mods_text = ", ".join(self.active_mods) if self.active_mods else "None"
        embed.description = (
            f"**Level:** {self.dummy_level} | **Mode:** {mode_tag}{slay_tag}\n"
            f"**Mods ({len(self.active_mods)}):** {mods_text}"
        )

        if results:
            total_turns = results.turns
            hit_pct  = int(results.hits  / total_turns * 100)
            crit_pct = int(results.crits / total_turns * 100)

            # Damage taken assessment
            lethal_icon = "☠️ **LETHAL**" if results.is_max_lethal else "✅ Survivable"

            outgoing = (
                f"**Avg / Turn:** {results.average_damage:,.1f}\n"
                f"**Total:** {results.total_damage:,}\n"
                f"**Range:** {results.min_hit:,} – {results.max_hit:,}\n"
                f"**Accuracy:** {hit_pct}% hits | {crit_pct}% crits"
            )
            incoming = (
                f"**Avg / Turn:** {results.avg_damage_taken:,.1f}\n"
                f"**Max Single Hit:** {results.max_damage_taken:,} ({lethal_icon})\n"
                f"**Your HP:** {self.player.total_max_hp:,}"
            )
            embed.add_field(name=f"⚔️ Outgoing DPS ({total_turns} turns)", value=outgoing, inline=True)
            embed.add_field(name="💔 Incoming Damage", value=incoming, inline=True)
        else:
            embed.add_field(
                name="Instructions",
                value=(
                    "Configure the dummy with the menus and buttons below, "
                    "then press **▶ Run Simulation**.\n\n"
                    "• **Set Level** — enter any exact level via modal\n"
                    "• **All Normal / All Special** — adds every mod in that group at once\n"
                    "• **Boss Mode** — applies boss damage emblems\n"
                    "• **Slayer Task** — simulates a matching slayer assignment"
                ),
                inline=False,
            )

        return embed

    # ---------------------------------------------------------------------- #
    # Component builder                                                        #
    # ---------------------------------------------------------------------- #

    def update_components(self):
        self.clear_items()

        # --- Row 0: Normal mods select ---
        normal_options = [
            SelectOption(
                label=("✅ " if m.strip() in self.active_mods else "") + m.strip()[:98],
                value=m.strip(),
                description=(get_modifier_description(m.strip()) or "")[:100],
            )
            for m in _NORMAL_MODS
        ][:25]

        sel_normal = ui.Select(
            placeholder="Add Normal Modifier…",
            options=normal_options,
            row=0,
        )
        sel_normal.callback = self.mod_callback
        self.add_item(sel_normal)

        # --- Row 1: Special / Boss / Uber mods select ---
        special_options = [
            SelectOption(
                label=("✅ " if m in self.active_mods else "") + m[:98],
                value=m,
                description=(get_modifier_description(m) or "")[:100],
            )
            for m in _SPECIAL_MODS
        ][:25]

        sel_special = ui.Select(
            placeholder="Add Boss / Special Modifier…",
            options=special_options,
            row=1,
        )
        sel_special.callback = self.mod_callback
        self.add_item(sel_special)

        # --- Row 2: Level + bulk mod controls ---
        btn_level = ui.Button(label="📝 Set Level", style=ButtonStyle.primary, row=2)
        btn_level.callback = self.open_level_modal
        self.add_item(btn_level)

        btn_all_normal = ui.Button(label="➕ All Normal", style=ButtonStyle.secondary, row=2)
        btn_all_normal.callback = self.add_all_normal
        self.add_item(btn_all_normal)

        btn_all_special = ui.Button(label="➕ All Special", style=ButtonStyle.secondary, row=2)
        btn_all_special.callback = self.add_all_special
        self.add_item(btn_all_special)

        btn_clear = ui.Button(label="🗑️ Clear Mods", style=ButtonStyle.danger, row=2)
        btn_clear.callback = self.clear_mods
        self.add_item(btn_clear)

        # --- Row 3: Mode toggles + run + exit ---
        boss_style  = ButtonStyle.success if self.is_boss_mode  else ButtonStyle.secondary
        slay_style  = ButtonStyle.success if self.slayer_active else ButtonStyle.secondary
        boss_label  = "🗡️ Boss Mode: ON"  if self.is_boss_mode  else "🗡️ Boss Mode: OFF"
        slay_label  = "🎯 Slayer: ON"     if self.slayer_active else "🎯 Slayer: OFF"

        btn_boss = ui.Button(label=boss_label, style=boss_style, row=3)
        btn_boss.callback = self.toggle_boss
        self.add_item(btn_boss)

        btn_slay = ui.Button(label=slay_label, style=slay_style, row=3)
        btn_slay.callback = self.toggle_slayer
        self.add_item(btn_slay)

        btn_run = ui.Button(label="▶ Run Simulation", style=ButtonStyle.success, emoji="⚔️", row=3)
        btn_run.callback = self.run_sim
        self.add_item(btn_run)

        btn_exit = ui.Button(label="Exit", style=ButtonStyle.danger, row=3)
        btn_exit.callback = self.close_view
        self.add_item(btn_exit)

    # ---------------------------------------------------------------------- #
    # Callbacks                                                                #
    # ---------------------------------------------------------------------- #

    async def open_level_modal(self, interaction: Interaction):
        await interaction.response.send_modal(SetLevelModal(self))

    async def mod_callback(self, interaction: Interaction):
        mod = interaction.data["values"][0]
        if mod in self.active_mods:
            self.active_mods.remove(mod)   # Toggle off if already active
        else:
            self.active_mods.append(mod)
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def add_all_normal(self, interaction: Interaction):
        for m in _NORMAL_MODS:
            m = m.strip()
            if m not in self.active_mods:
                self.active_mods.append(m)
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def add_all_special(self, interaction: Interaction):
        for m in _SPECIAL_MODS:
            if m not in self.active_mods:
                self.active_mods.append(m)
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def clear_mods(self, interaction: Interaction):
        self.active_mods = []
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_boss(self, interaction: Interaction):
        self.is_boss_mode = not self.is_boss_mode
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def toggle_slayer(self, interaction: Interaction):
        self.slayer_active = not self.slayer_active
        # Temporarily inject / remove a matching species on the player
        # We store it as a sentinel species on the dummy in run_sim
        self.update_components()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def run_sim(self, interaction: Interaction):
        await interaction.response.defer()

        lvl = self.dummy_level

        monster = Monster(
            name="Combat Dummy",
            level=lvl,
            hp=9_999_999, max_hp=9_999_999, xp=0,
            attack=0, defence=0,
            image="", flavor="",
            species="_dojo_dummy_",        # Unique species — Slayer won't match by default
        )
        calculate_monster_stats(monster)
        monster.modifiers = [make_modifier(name, lvl) for name in self.active_mods]

        # Apply spawn-time stat mutations (Empowered/Fortified/Titanic/Ascended/Veiled)
        from core.combat.gen_mob import _apply_spawn_modifiers
        _apply_spawn_modifiers(monster)
        monster.max_hp = 9_999_999  # restore after any Titanic mutation

        monster.is_boss = self.is_boss_mode

        # Temporarily override player species to match for Slayer emblem simulation
        saved_species = self.player.active_task_species
        if self.slayer_active:
            self.player.active_task_species = "_dojo_dummy_"

        try:
            results = DummyEngine.run_simulation(self.player, monster, turns=100)
        finally:
            self.player.active_task_species = saved_species

        await interaction.edit_original_response(
            embed=self.build_embed(results=results), view=self
        )

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
