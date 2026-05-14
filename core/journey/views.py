import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.base_view import BaseView
from core.journey.rewards import MILESTONES

# Level → milestone dict for O(1) lookup
_MILESTONE_MAP: dict[int, dict] = {m["level"]: m for m in MILESTONES}

# Embed colours
_COLOR_CLAIMED = 0x57F287  # green
_COLOR_READY = 0xF4C542  # gold
_COLOR_LOCKED = 0x4F545C  # dark grey


def _milestone_status(milestone_level: int, player_level: int, claimed: set) -> str:
    if milestone_level in claimed:
        return "claimed"
    if player_level >= milestone_level:
        return "ready"
    return "locked"


def _build_milestone_embed(
    milestone: dict, player_level: int, claimed: set
) -> discord.Embed:
    lvl = milestone["level"]
    status = _milestone_status(lvl, player_level, claimed)

    if status == "claimed":
        icon = "✅"
        color = _COLOR_CLAIMED
        status_text = "Reward claimed."
    elif status == "ready":
        icon = "🎁"
        color = _COLOR_READY
        status_text = "**Reward ready to claim!** Press *Claim Rewards* below."
    else:
        icon = "🔒"
        color = _COLOR_LOCKED
        status_text = f"Reach **Level {lvl}** to unlock this reward."

    embed = discord.Embed(
        title=f"{icon} Level {lvl} — {milestone['title']}",
        description=status_text,
        color=color,
    )

    embed.add_field(name="Reward", value=milestone["reward_desc"], inline=False)

    if milestone["systems"]:
        embed.add_field(
            name="Systems Unlocked",
            value="\n".join(f"• {s}" for s in milestone["systems"]),
            inline=True,
        )

    if milestone["commands"]:
        embed.add_field(
            name="Commands",
            value="  ".join(f"`{c}`" for c in milestone["commands"]),
            inline=True,
        )

    embed.set_image(url=milestone["image"])
    embed.set_footer(text=f"Your Level: {player_level}")
    return embed


def _default_milestone_level(player_level: int) -> int:
    """Returns the highest milestone level that the player has reached."""
    reached = [m["level"] for m in MILESTONES if m["level"] <= player_level]
    return reached[-1] if reached else MILESTONES[0]["level"]


class JourneyView(BaseView):
    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        player_level: int,
        claimed: set,
    ):
        super().__init__(bot, user_id, server_id=server_id)
        self.player_level = player_level
        self.claimed = claimed
        self.selected_lvl = _default_milestone_level(player_level)
        self._rebuild_items()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pending_milestones(self) -> list:
        return [
            m
            for m in MILESTONES
            if self.player_level >= m["level"] and m["level"] not in self.claimed
        ]

    def _build_select_options(self) -> list[SelectOption]:
        options = []
        for m in MILESTONES:
            status = _milestone_status(m["level"], self.player_level, self.claimed)
            if status == "claimed":
                desc = "✅ Claimed"
            elif status == "ready":
                desc = "🎁 Ready to claim!"
            else:
                desc = f"🔒 Reach Level {m['level']}"
            options.append(
                SelectOption(
                    label=f"Level {m['level']} — {m['title']}",
                    value=str(m["level"]),
                    description=desc,
                    default=(m["level"] == self.selected_lvl),
                )
            )
        return options

    def _rebuild_items(self) -> None:
        self.clear_items()

        # Row 0 — milestone browser
        select = ui.Select(
            placeholder="Browse milestones...",
            options=self._build_select_options(),
            row=0,
        )
        select.callback = self._on_select
        self.add_item(select)

        # Row 1 — claim + close
        pending = self._pending_milestones()
        claim_btn = ui.Button(
            label=f"Claim Rewards ({len(pending)})" if pending else "Nothing to Claim",
            style=ButtonStyle.success if pending else ButtonStyle.secondary,
            disabled=not pending,
            row=1,
        )
        claim_btn.callback = self._on_claim
        self.add_item(claim_btn)

        close_btn = ui.Button(
            label="Close",
            style=ButtonStyle.secondary,
            row=1,
        )
        close_btn.callback = self._on_close
        self.add_item(close_btn)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    async def _on_select(self, interaction: Interaction) -> None:
        self.selected_lvl = int(interaction.data["values"][0])
        self._rebuild_items()
        embed = _build_milestone_embed(
            _MILESTONE_MAP[self.selected_lvl], self.player_level, self.claimed
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_claim(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        pending = self._pending_milestones()
        if not pending:
            await interaction.followup.send("No rewards to claim.", ephemeral=True)
            return

        all_lines: list[str] = []
        for m in pending:
            lines = await m["grant"](self.bot, self.user_id, self.server_id)
            all_lines.extend(lines)
            await self.bot.database.journey.claim(self.user_id, m["level"])
            self.claimed.add(m["level"])

        # After claiming, default the view to the latest newly-claimed milestone
        self.selected_lvl = pending[-1]["level"]
        self._rebuild_items()
        embed = _build_milestone_embed(
            _MILESTONE_MAP[self.selected_lvl], self.player_level, self.claimed
        )

        reward_embed = discord.Embed(
            title="🎉 Rewards Claimed!",
            description="\n".join(all_lines),
            color=_COLOR_CLAIMED,
        )
        await interaction.edit_original_response(embed=embed, view=self)
        await interaction.followup.send(embed=reward_embed, ephemeral=True)

    async def _on_close(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


def build_journey_embed(player_level: int, claimed: set) -> discord.Embed:
    """Builds the initial embed shown when /journey is first opened."""
    default_lvl = _default_milestone_level(player_level)
    return _build_milestone_embed(_MILESTONE_MAP[default_lvl], player_level, claimed)
