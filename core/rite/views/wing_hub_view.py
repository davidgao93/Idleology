"""Milestone 2 scaffolding: a minimal wing-selection hub for The Rite of
Convergence's 5 standalone wing fights.

No key consumption, no attempts/retry, no writs, no loot payout — those land
in Milestones 3-5. This view exists so the 5 wing encounters and their new
combat mechanics (Unbreakable, Judgment, True Reckoning, Void Drain) can be
fought and verified end-to-end before the run/attempt state machine is built.
"""

import discord
from discord import ButtonStyle, Interaction, ui

from core.base_layout_view import BaseLayoutView
from core.combat import ui as combat_ui
from core.combat.turns import engine
from core.combat.turns import jewel_engine as _je
from core.combat.views.views import CombatView
from core.images import (
    MONSTER_APHRODITE,
    MONSTER_EVELYNN,
    MONSTER_GEMINI,
    MONSTER_LUCIFER,
    MONSTER_NEET,
)
from core.models import Monster, Player
from core.rite import mobgen

# (key, display name, subtitle, generator fn, thumbnail)
_WINGS = [
    (
        "aphrodite",
        "Aphrodite Reborn",
        "Defensive Test — Unbreakable",
        mobgen.generate_wing_aphrodite,
        MONSTER_APHRODITE,
    ),
    (
        "lucifer",
        "Lucifer Reborn",
        "Offensive Test — Judgment",
        mobgen.generate_wing_lucifer,
        MONSTER_LUCIFER,
    ),
    (
        "gemini",
        "Castor & Pollux Reborn",
        "Sustain Test — True Reckoning",
        mobgen.generate_wing_gemini,
        MONSTER_GEMINI,
    ),
    (
        "neet",
        "NEET Reborn",
        "Void Drain",
        mobgen.generate_wing_neet,
        MONSTER_NEET,
    ),
    (
        "evelynn",
        "Evelynn Reborn",
        "All Modifiers — Nightmarish",
        mobgen.generate_wing_evelynn,
        MONSTER_EVELYNN,
    ),
]
_WING_BY_KEY = {w[0]: w for w in _WINGS}


class WingReturnRow(discord.ui.ActionRow["WingReturnView"]):
    @discord.ui.button(label="↩ Return to Wing Select", style=ButtonStyle.secondary)
    async def return_to_hub(self, interaction: Interaction, button: ui.Button):
        await self.view._on_return(interaction)


class WingReturnView(BaseLayoutView):
    """Minimal post-fight view. Milestone 3 replaces this with the real
    attempts/respite flow."""

    def __init__(self, bot, user_id: str, server_id: str, player, wings_cleared: set):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.wings_cleared = wings_cleared
        self.row = WingReturnRow()

    def set_content(self, embed: discord.Embed) -> None:
        self.clear_items()
        self.add_item(combat_ui.embed_to_container(embed))
        self.add_item(self.row)

    async def _on_return(self, interaction: Interaction):
        await interaction.response.defer()
        hub = WingHubView(
            self.bot, self.user_id, self.server_id, self.player, self.wings_cleared
        )
        await interaction.edit_original_response(view=hub)
        hub.message = await interaction.original_response()
        self.stop()


class WingHubView(BaseLayoutView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player: Player,
        wings_cleared: set | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.player = player
        self.wings_cleared = wings_cleared if wings_cleared is not None else set()
        self._processing = False
        self._sync_items()

    def _build_container(self) -> discord.ui.Container:
        def _wing_section(key, name, subtitle, thumb_url) -> discord.ui.Section:
            status = "✅ Cleared" if key in self.wings_cleared else "⚔️ Not yet cleared"
            text = f"### {name}\n{subtitle}\n**Status:** {status}"
            return discord.ui.Section(
                text, accessory=discord.ui.Thumbnail(thumb_url, description=name)
            )

        sep = lambda: discord.ui.Separator(spacing=discord.SeparatorSpacing.small)

        children: list = [
            discord.ui.TextDisplay(
                "## 🕯️ The Rite of Convergence — Wing Select\n"
                "*(Milestone 2 scaffolding: no keys, no attempts, no loot yet.)*\n\n"
                f"**Wings cleared:** {len(self.wings_cleared)}/5"
            ),
            sep(),
        ]
        for key, name, subtitle, _fn, thumb in _WINGS:
            children.append(_wing_section(key, name, subtitle, thumb))
        return discord.ui.Container(*children, accent_color=discord.Color.dark_purple())

    def _build_rows(self) -> list[discord.ui.ActionRow]:
        row0 = discord.ui.ActionRow()
        row1 = discord.ui.ActionRow()
        row2 = discord.ui.ActionRow()

        for i, (key, name, _subtitle, _fn, _thumb) in enumerate(_WINGS):
            btn = ui.Button(
                label=name.split(" Reborn")[0].split(" &")[0],
                style=ButtonStyle.success if key in self.wings_cleared else ButtonStyle.danger,
                custom_id=f"rite_wing_{key}",
            )
            btn.callback = self._make_start_callback(key)
            (row0 if i < 3 else row1).add_item(btn)

        btn_close = ui.Button(label="Close", style=ButtonStyle.secondary, emoji="✖️")
        btn_close.callback = self.close_view
        row2.add_item(btn_close)

        return [row0, row1, row2]

    def _sync_items(self):
        self.clear_items()
        self.add_item(self._build_container())
        for row in self._build_rows():
            self.add_item(row)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

    def _make_start_callback(self, wing_key: str):
        async def _start(interaction: Interaction):
            if self._processing:
                await interaction.response.defer()
                return
            self._processing = True
            await interaction.response.defer()

            _key, name, _subtitle, generate_fn, _thumb = _WING_BY_KEY[wing_key]

            # Wing hub reuses the same Player object across fights (same reason
            # Uber lobbies do — see start_uber() precedent), so leftover combat
            # stacks/buffs from a previous wing must be cleared first.
            self.player.reset_combat_state()

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
            monster = generate_fn(self.player, monster)
            self.player.combat_ward = self.player.get_combat_ward_value()
            engine.apply_stat_effects(self.player, monster)
            start_logs = engine.apply_combat_start_passives(self.player, monster)

            user_row = await self.bot.database.users.get(self.user_id, self.server_id)
            view = CombatView(
                self.bot,
                self.user_id,
                self.server_id,
                self.player,
                monster,
                start_logs,
                combat_phases=None,
                rite_callback=self._make_end_state_callback(wing_key),
                title_override=f"🕯️ RITE OF CONVERGENCE — {name.upper()}",
                player_avatar_url=user_row["appearance"] if user_row else None,
            )

            self.bot.state_manager.set_active(self.user_id, "rite")
            await interaction.edit_original_response(embed=None, view=view)
            view.message = await interaction.original_response()
            self.stop()

        return _start

    def _make_end_state_callback(self, wing_key: str):
        async def _end_state(view: CombatView, message, interaction: Interaction):
            won = view.monster.hp <= 0 and view.player.current_hp > 0

            view.bot.state_manager.clear_active(view.user_id)
            await view.bot.database.users.update_from_player_object(view.player)
            await _je.save_jewel_state(view.bot, view.user_id, view.player)

            if won:
                self.wings_cleared.add(wing_key)
                embed = discord.Embed(
                    title=f"✅ {view.monster.name} defeated!",
                    description=(
                        "Wing cleared.\n\n"
                        "*(Milestone 2 scaffolding — no rewards yet; attempts, HP "
                        "carry-through, and respite land in Milestone 3.)*"
                    ),
                    color=discord.Color.green(),
                )
            else:
                embed = discord.Embed(
                    title=f"💀 Defeated by {view.monster.name}",
                    description=(
                        "*(Milestone 2 scaffolding — attempts/retry-on-death land "
                        "in Milestone 3; this run simply ends here for now.)*"
                    ),
                    color=discord.Color.red(),
                )

            return_view = WingReturnView(
                view.bot, view.user_id, view.server_id, view.player, self.wings_cleared
            )
            return_view.set_content(embed)
            await message.edit(view=return_view)
            return_view.message = message
            view.stop()

        return _end_state
