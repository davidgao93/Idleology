import discord
from discord import ButtonStyle, Interaction, ui

from core.base_view import BaseView
from core.journey.rewards import MILESTONES


def _build_embed(player_level: int, claimed: set) -> discord.Embed:
    embed = discord.Embed(
        title="📜 Adventurer's Journey",
        description=(
            "Your path through Idleology — claim milestone rewards as you grow stronger.\n"
            "New systems unlock at each tier, expanding the world available to you.\n​"
        ),
        color=0xF4C542,
    )

    for m in MILESTONES:
        lvl = m["level"]
        reached = player_level >= lvl
        is_claimed = lvl in claimed

        if is_claimed:
            icon = "✅"
            status = "Claimed"
        elif reached:
            icon = "🎁"
            status = "**Ready to Claim!**"
        else:
            icon = "🔒"
            status = f"Reach Level {lvl}"

        systems_text = ""
        if m["systems"]:
            systems_text = "\n*Unlocks: " + ", ".join(m["systems"]) + "*"

        embed.add_field(
            name=f"{icon} Level {lvl}",
            value=f"{status}\n{m['reward_desc']}{systems_text}",
            inline=True,
        )

    embed.set_footer(text=f"Your Level: {player_level}")
    return embed


class JourneyView(BaseView):
    def __init__(self, bot, user_id: str, server_id: str, player_level: int, claimed: set):
        super().__init__(bot, user_id, server_id=server_id)
        self.player_level = player_level
        self.claimed = claimed
        self._update_button()

    def _pending_milestones(self) -> list:
        return [
            m for m in MILESTONES
            if self.player_level >= m["level"] and m["level"] not in self.claimed
        ]

    def _update_button(self):
        self.clear_items()
        pending = self._pending_milestones()
        btn = ui.Button(
            label=f"Claim Rewards ({len(pending)})" if pending else "Nothing to Claim",
            style=ButtonStyle.success if pending else ButtonStyle.secondary,
            disabled=not pending,
            custom_id="journey_claim",
        )
        btn.callback = self._on_claim
        self.add_item(btn)

    async def _on_claim(self, interaction: Interaction):
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

        self._update_button()
        embed = _build_embed(self.player_level, self.claimed)

        reward_embed = discord.Embed(
            title="🎉 Rewards Claimed!",
            description="\n".join(all_lines),
            color=0x57F287,
        )
        await interaction.edit_original_response(embed=embed, view=self)
        await interaction.followup.send(embed=reward_embed, ephemeral=True)


def build_journey_embed(player_level: int, claimed: set) -> discord.Embed:
    return _build_embed(player_level, claimed)
