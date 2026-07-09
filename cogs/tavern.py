from datetime import datetime, timedelta

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from core.emojis import GOLD_COIN, POTION
from core.first_use import TutorialGateView
from core.images import (
    BAR_MAID,
    BAR_MAID_AUTHOR,
    CHECKIN,
    POTION_SHOP,
    POTION_SHOP_AUTHOR,
    QUEST_SHOP_AUTHOR,
    TAVERN_GAMES,
)
from core.items.factory import load_player
from core.npc_voices import get_quip
from core.quests.data import CHECKIN_DAY_LABELS
from core.tavern.mechanics import TavernMechanics
from core.tavern.views import (
    CasinoMenuView,
    RestView,
    ShopView,
    build_casino_lobby_embed,
)


def _build_checkin_embed(
    current_day: int,
    can_checkin: bool,
    remaining: timedelta | None,
) -> discord.Embed:
    """Build the 14-day check-in track embed."""
    embed = discord.Embed(title="📅 Daily Check-in Track", color=0x7289DA)
    embed.set_author(name="Lira", icon_url=QUEST_SHOP_AUTHOR)
    embed.set_thumbnail(url=CHECKIN)

    # Build two rows of 7 days — spaces between cells for readability
    cells: list[str] = []
    for day in range(1, 15):
        if day <= current_day:
            cells.append("✅")
        elif day == current_day + 1:
            cells.append("🔶")
        else:
            cells.append("⬜")

    row1 = " ".join(cells[:7])
    row2 = " ".join(cells[7:])

    milestone_lines = "\n".join(
        f"  **Day {d}** — {CHECKIN_DAY_LABELS.get(d, '')}" for d in (1, 7, 14)
    )

    track_display = (
        f"**Days 1–7:**\n{row1}\n"
        f"**Days 8–14:**\n{row2}\n\n"
        f"**Milestones:**\n{milestone_lines}"
    )
    embed.description = f"*{get_quip('checkin')}*\n\n{track_display}"

    if current_day > 0:
        embed.add_field(
            name="Current Day",
            value=f"Day **{current_day}** / 14",
            inline=True,
        )

    if can_checkin:
        next_day = (current_day % 14) + 1 if current_day > 0 else 1
        label = CHECKIN_DAY_LABELS.get(next_day, "")
        embed.add_field(
            name="Next Reward",
            value=f"Day {next_day} — {label}",
            inline=True,
        )
        embed.add_field(
            name="Lira",
            value="You're right on time! I've got something set aside for you — come pick it up.",
            inline=False,
        )
    else:
        if remaining:
            total_secs = int(remaining.total_seconds())
            h = total_secs // 3600
            m = (total_secs % 3600) // 60
            embed.add_field(
                name="Available In",
                value=f"**{h}h {m}m**",
                inline=True,
            )

    return embed


class Tavern(commands.Cog, name="tavern"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="shop", description="Visit the tavern shop to buy items."
    )
    async def shop(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        self.bot.state_manager.set_active(user_id, "shop")

        async def _build():
            gold = user_data["gold"]
            potions = user_data["potions"]
            level = user_data["level"]
            potion_cost = TavernMechanics.calculate_potion_cost(level)
            topup_qty = max(0, 20 - potions)
            embed = discord.Embed(
                title="Tavern Shop",
                description=get_quip("shop"),
                color=0xFFCC00,
            )
            embed.set_author(name="Elara", icon_url=POTION_SHOP_AUTHOR)
            embed.set_thumbnail(url=POTION_SHOP)
            embed.add_field(
                name=f"Your Gold {GOLD_COIN}", value=f"{gold:,}", inline=False
            )
            embed.add_field(
                name=f"Potion {POTION}",
                value=(
                    f"x1: **{potion_cost:,}** gold\n"
                    f"x5: **{potion_cost * 5:,}** gold\n"
                    f"Top Up ({topup_qty}): **{potion_cost * topup_qty:,}** gold"
                ),
                inline=False,
            )
            embed.add_field(name="Elara", value="What'll it be?", inline=False)
            if not await self.bot.database.users.get_auto_potion_reload(user_id):
                embed.set_footer(
                    text="💡 Tip: enable Auto-Reload Potions in /player_settings "
                    "to top off automatically after combat."
                )
            view = ShopView(self.bot, user_id, user_data)
            return embed, view

        if not await self.bot.database.tutorials.has_seen(user_id, "shop"):
            await self.bot.database.tutorials.mark_seen(user_id, "shop")
            gate = TutorialGateView(
                self.bot, user_id, server_id, "shop", build_main=_build
            )
            await interaction.response.send_message(embed=gate.build_embed(), view=gate)
            gate.message = await interaction.original_response()
            return

        embed, view = await _build()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="rest", description="Rest your weary body and mind.")
    async def rest(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        player = await load_player(user_id, user, self.bot.database)
        current_hp = user["current_hp"]
        max_hp = player.total_max_hp

        if current_hp >= max_hp:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="The Tavern 🛏️",
                    description="You are already fully rested.",
                    color=0xFFCC00,
                ),
                ephemeral=True,
            )

        # Cooldown Check
        last_rest = user["last_rest_time"]
        cooldown = timedelta(hours=2)
        on_cooldown = False
        remaining_str = ""

        if last_rest:
            try:
                diff = datetime.now() - datetime.fromisoformat(last_rest)
                if diff < cooldown:
                    on_cooldown = True
                    rem = cooldown - diff
                    remaining_str = (
                        f"**{rem.seconds // 3600}h {(rem.seconds // 60) % 60}m**"
                    )
            except Exception:
                pass

        if not on_cooldown:
            # Free Rest
            await self.bot.database.users.update_hp(user_id, max_hp)
            await self.bot.database.users.update_timer(user_id, "last_rest_time")

            embed = discord.Embed(
                title="The Tavern 🛏️",
                description=f"You have rested and regained your health! Current HP: **{max_hp}**.",
                color=0xFFCC00,
            )
            embed.set_thumbnail(url=TAVERN_GAMES)
            await interaction.response.send_message(embed=embed)
        else:
            # Paid Rest (cooldown active)
            cost = TavernMechanics.calculate_rest_cost(user["level"])
            gold = user["gold"]
            auto_pay = await self.bot.database.users.get_auto_rest_pay(user_id)

            embed = discord.Embed(
                title="The Tavern 🛏️",
                description=f"*{get_quip('rest')}*\n\nYou need to wait {remaining_str} before resting for free again.",
                color=0xFFCC00,
            )
            embed.set_thumbnail(url=BAR_MAID)

            if gold >= cost:
                if auto_pay:
                    # Auto-pay path: perform the rest immediately without confirmation
                    await self.bot.database.users.modify_gold(user_id, -cost)
                    await self.bot.database.users.update_hp(user_id, max_hp)

                    success_embed = discord.Embed(
                        title="The Tavern 🛏️",
                        description=(
                            f"**Auto-paid {cost} gold** for a room.\n"
                            f"You have rested and regained your health! Current HP: **{max_hp}**."
                        ),
                        color=0x00CC77,
                    )
                    success_embed.set_thumbnail(url=TAVERN_GAMES)
                    await interaction.response.send_message(embed=success_embed)
                else:
                    # Normal paid rest prompt
                    self.bot.state_manager.set_active(user_id, "rest")
                    embed.set_author(name="Gilda", icon_url=BAR_MAID_AUTHOR)
                    embed.add_field(
                        name="Gilda",
                        value=f"I have an extra room available for **{cost} gold**. Clean sheets and no questions asked.",
                    )
                    embed.set_footer(
                        text="💡 Tip: enable Auto-Pay Rest in /player_settings to skip this prompt."
                    )
                    view = RestView(self.bot, user_id, cost, max_hp)
                    await interaction.response.send_message(embed=embed, view=view)
                    view.message = await interaction.original_response()
            else:
                embed.set_author(name="Gilda", icon_url=BAR_MAID_AUTHOR)
                embed.add_field(
                    name="Gilda",
                    value=f"I have a room for **{cost} gold**, but you can't afford it. Come back when you're not so broke.",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="gamble", description="Gamble your gold in the tavern!")
    @app_commands.describe(amount="The amount of gold to bet.")
    async def gamble(self, interaction: Interaction, amount: int) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user_data = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user_data):
            return
        if not await self.bot.check_is_active(interaction, user_id):
            return

        if amount <= 0:
            return await interaction.response.send_message(
                "Bet must be positive.", ephemeral=True
            )
        if amount > user_data["gold"]:
            return await interaction.response.send_message(
                f"Insufficient funds. You have **{user_data['gold']:,}**.",
                ephemeral=True,
            )

        self.bot.state_manager.set_active(user_id, "gamble")

        embed = build_casino_lobby_embed(amount)
        view = CasinoMenuView(self.bot, user_id, amount)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(
        name="checkin", description="Daily check-in — claim your track reward."
    )
    async def checkin(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        # Level gate
        if user["level"] < 10:
            return await interaction.response.send_message(
                "The check-in track unlocks at **Level 10**.", ephemeral=True
            )

        await self.bot.database.quests.ensure_meta(user_id)
        meta = await self.bot.database.quests.get_meta(user_id)

        last_time = meta["checkin_last_time"]
        cooldown = timedelta(hours=18)
        can_checkin = True
        rem = None
        if last_time:
            try:
                diff = datetime.now() - datetime.fromisoformat(last_time)
                if diff < cooldown:
                    rem = cooldown - diff
                    can_checkin = False
            except Exception:
                pass

        current_day = meta["checkin_day"]
        next_day = (current_day % 14) + 1 if current_day > 0 else 1

        embed = _build_checkin_embed(current_day, can_checkin, rem)

        if can_checkin:
            level = user["level"]
            from core.quests.data import grant_checkin_day

            rewards = await grant_checkin_day(
                self.bot, user_id, server_id, next_day, level
            )
            await self.bot.database.quests.advance_checkin(user_id)
            embed = _build_checkin_embed(next_day, False, timedelta(hours=18))
            embed.add_field(
                name=f"Day {next_day} Reward",
                value="\n".join(rewards) if rewards else "No rewards this day.",
                inline=False,
            )
            embed.add_field(
                name="Lira",
                value="There you go — all packed up just for you. See you again tomorrow!",
                inline=False,
            )
            embed.color = 0x00CC77
            embed.set_thumbnail(url=CHECKIN)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(Tavern(bot))
