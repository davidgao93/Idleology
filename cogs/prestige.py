import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

BORDERS: dict[str, dict] = {
    "golden": {"label": "Golden", "color": 0xFFD700, "price": 150_000_000},
    "crimson": {"label": "Crimson", "color": 0xDC143C, "price": 600_000_000},
    "emerald": {"label": "Emerald", "color": 0x50C878, "price": 600_000_000},
    "infernal": {"label": "Infernal", "color": 0xFF4500, "price": 800_000_000},
    "celestial": {"label": "Celestial", "color": 0x87CEEB, "price": 800_000_000},
    "void": {"label": "Void", "color": 0x4B0082, "price": 1_000_000_000},
}

TITLES: dict[str, dict] = {
    "the_gilded": {"label": "The Gilded", "price": 1_000_000_000},
    "iron_warden": {"label": "Iron Warden", "price": 1_000_000_000},
    "the_blessed": {"label": "The Blessed", "price": 1_000_000_000},
    "void_touched": {"label": "Void-Touched", "price": 1_000_000_000},
    "shadowborn": {"label": "Shadowborn", "price": 1_000_000_000},
    "ascendant": {"label": "Ascendant", "price": 1_000_000_000},
}

FLAIRS: dict[str, dict] = {
    "casual": {"label": "Casual", "price": 1_000_000_000},
    "heroic": {"label": "Heroic", "price": 1_000_000_000},
    "ominous": {"label": "Ominous", "price": 1_000_000_000},
}

RENAME_COST = 750_000_000
DEATH_MSG_COST = 300_000_000
MONUMENT_COST = 2_000_000_000
MONUMENT_UPDATE_FREE = True  # updating monument text after first purchase is free

DEFAULT_COLOR = 0xBEBEFE


def _border_color(border_key: str) -> int:
    return BORDERS.get(border_key, {}).get("color", DEFAULT_COLOR)


def _title_label(title_key: str) -> str:
    return TITLES.get(title_key, {}).get("label", "")


def _flair_label(flair_key: str) -> str:
    return FLAIRS.get(flair_key, {}).get("label", "")


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------


class RenameModal(discord.ui.Modal, title="Rename Character"):
    new_name = discord.ui.TextInput(
        label="New Name",
        placeholder="Enter your new in-game name…",
        min_length=2,
        max_length=32,
    )

    def __init__(
        self, cog: "Prestige", user_id: str, server_id: str, current_gold: int
    ):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.server_id = server_id
        self.current_gold = current_gold

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.new_name.value.strip()
        if self.current_gold < RENAME_COST:
            return await interaction.response.send_message(
                f"You need **{RENAME_COST:,}g** to rename. You have **{self.current_gold:,}g**.",
                ephemeral=True,
            )
        await self.cog.bot.database.users.modify_gold(self.user_id, -RENAME_COST)
        await self.cog.bot.database.prestige.set_field(
            self.user_id, "prestige_display_name", name
        )
        embed = discord.Embed(
            description=f"Your name has been changed to **{name}**. (-{RENAME_COST:,}g)",
            color=DEFAULT_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DeathMessageModal(discord.ui.Modal, title="Set Death Message"):
    message = discord.ui.TextInput(
        label="Death Message",
        placeholder="Shown when you fall in combat…",
        min_length=2,
        max_length=120,
    )

    def __init__(
        self, cog: "Prestige", user_id: str, current_gold: int, already_unlocked: bool
    ):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.current_gold = current_gold
        self.already_unlocked = already_unlocked

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cost = 0 if self.already_unlocked else DEATH_MSG_COST
        if cost > 0 and self.current_gold < cost:
            return await interaction.response.send_message(
                f"You need **{cost:,}g** to unlock a death message. You have **{self.current_gold:,}g**.",
                ephemeral=True,
            )
        if not self.already_unlocked:
            await self.cog.bot.database.users.modify_gold(self.user_id, -cost)
            await self.cog.bot.database.prestige.add_owned(
                self.user_id, "death_message", "unlocked"
            )
        await self.cog.bot.database.prestige.set_field(
            self.user_id, "prestige_death_message", self.message.value.strip()
        )
        suffix = f" (-{cost:,}g)" if cost else ""
        embed = discord.Embed(
            description=f"Death message set.{suffix}",
            color=DEFAULT_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MonumentModal(discord.ui.Modal, title="Set Monument Quote"):
    quote = discord.ui.TextInput(
        label="Quote",
        placeholder="Your words, etched in stone…",
        min_length=2,
        max_length=150,
    )

    def __init__(
        self, cog: "Prestige", user_id: str, current_gold: int, already_owned: bool
    ):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.current_gold = current_gold
        self.already_owned = already_owned

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cost = 0 if self.already_owned else MONUMENT_COST
        if cost > 0 and self.current_gold < cost:
            return await interaction.response.send_message(
                f"You need **{cost:,}g** for a monument slot. You have **{self.current_gold:,}g**.",
                ephemeral=True,
            )
        if not self.already_owned:
            await self.cog.bot.database.users.modify_gold(self.user_id, -cost)
            await self.cog.bot.database.prestige.add_owned(
                self.user_id, "monument", "unlocked"
            )
        await self.cog.bot.database.prestige.set_field(
            self.user_id, "prestige_monument", self.quote.value.strip()
        )
        suffix = f" (-{cost:,}g)" if cost else ""
        embed = discord.Embed(
            description=f"Your monument quote has been updated.{suffix}",
            color=DEFAULT_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------


class Prestige(commands.Cog, name="prestige"):
    def __init__(self, bot) -> None:
        self.bot = bot

    prestige_group = app_commands.Group(
        name="prestige", description="Spend gold on cosmetic vanity upgrades."
    )

    # --- Shop overview ---

    @prestige_group.command(
        name="shop", description="Browse all prestige cosmetics and prices."
    )
    async def prestige_shop(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(title="Prestige Shop", color=DEFAULT_COLOR)

        borders_text = "\n".join(
            f"`{k}` — {v['label']} · **{v['price']:,}g**" for k, v in BORDERS.items()
        )
        titles_text = "\n".join(
            f"`{k}` — {v['label']} · **{v['price']:,}g**" for k, v in TITLES.items()
        )
        flairs_text = "\n".join(
            f"`{k}` — {v['label']} · **{v['price']:,}g**" for k, v in FLAIRS.items()
        )

        embed.add_field(name="Profile Borders", value=borders_text, inline=False)
        embed.add_field(name="Titles", value=titles_text, inline=False)
        embed.add_field(name="Combat Flairs", value=flairs_text, inline=False)
        embed.add_field(
            name="Other",
            value=(
                f"`/prestige rename` — Change your in-game name · **{RENAME_COST:,}g** per rename\n"
                f"`/prestige death_message` — Custom death message · **{DEATH_MSG_COST:,}g** to unlock\n"
                f"`/prestige monument` — Hall of fame quote · **{MONUMENT_COST:,}g** to unlock"
            ),
            inline=False,
        )
        embed.set_footer(
            text="Borders and titles are purchased once and can be freely swapped."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Profile overview ---

    @prestige_group.command(
        name="profile", description="View your active prestige cosmetics."
    )
    async def prestige_profile(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        active = await self.bot.database.prestige.get_active(user_id)
        gold = await self.bot.database.users.get_gold(user_id)

        owned_borders = await self.bot.database.prestige.get_owned(user_id, "border")
        owned_titles = await self.bot.database.prestige.get_owned(user_id, "title")
        owned_flairs = await self.bot.database.prestige.get_owned(user_id, "flair")

        color = _border_color(active.get("border", "none"))
        embed = discord.Embed(title="Your Prestige", color=color)

        display_name = active.get("display_name") or user[3]
        title_label = _title_label(active.get("title", "none"))
        name_str = (
            f"{title_label} **{display_name}**"
            if title_label
            else f"**{display_name}**"
        )
        embed.description = name_str

        embed.add_field(
            name="Active Cosmetics",
            value=(
                f"**Border:** {BORDERS[active['border']]['label'] if active.get('border') in BORDERS else 'None'}\n"
                f"**Title:** {title_label or 'None'}\n"
                f"**Flair:** {_flair_label(active.get('flair', 'none')) or 'None'}\n"
                f"**Death Msg:** {active.get('death_message') or 'None'}\n"
                f"**Monument:** {active.get('monument') or 'None'}"
            ),
            inline=False,
        )

        def _fmt_owned(keys: list[str], catalogue: dict) -> str:
            if not keys:
                return "None"
            return ", ".join(catalogue[k]["label"] for k in keys if k in catalogue)

        embed.add_field(
            name="Owned",
            value=(
                f"**Borders:** {_fmt_owned(owned_borders, BORDERS)}\n"
                f"**Titles:** {_fmt_owned(owned_titles, TITLES)}\n"
                f"**Flairs:** {_fmt_owned(owned_flairs, FLAIRS)}"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Gold: {gold:,}g")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Border ---

    @prestige_group.command(
        name="border", description="Buy or equip a profile border color."
    )
    @app_commands.describe(style="The border style to buy or equip.")
    @app_commands.choices(
        style=[
            app_commands.Choice(name="Golden", value="golden"),
            app_commands.Choice(name="Crimson", value="crimson"),
            app_commands.Choice(name="Emerald", value="emerald"),
            app_commands.Choice(name="Infernal", value="infernal"),
            app_commands.Choice(name="Celestial", value="celestial"),
            app_commands.Choice(name="Void", value="void"),
        ]
    )
    async def prestige_border(
        self, interaction: discord.Interaction, style: app_commands.Choice[str]
    ) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        info = BORDERS[style.value]
        already_owned = await self.bot.database.prestige.owns(
            user_id, "border", style.value
        )

        if not already_owned:
            gold = await self.bot.database.users.get_gold(user_id)
            if gold < info["price"]:
                return await interaction.response.send_message(
                    f"You need **{info['price']:,}g** for the {info['label']} border. You have **{gold:,}g**.",
                    ephemeral=True,
                )
            await self.bot.database.users.modify_gold(user_id, -info["price"])
            await self.bot.database.prestige.add_owned(user_id, "border", style.value)

        await self.bot.database.prestige.set_field(
            user_id, "prestige_border", style.value
        )
        suffix = f" (-{info['price']:,}g)" if not already_owned else " (free swap)"
        embed = discord.Embed(
            description=f"**{info['label']}** border equipped.{suffix}",
            color=info["color"],
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Title ---

    @prestige_group.command(name="title", description="Buy or equip a title.")
    @app_commands.describe(title="The title to buy or equip.")
    @app_commands.choices(
        title=[
            app_commands.Choice(name="The Gilded", value="the_gilded"),
            app_commands.Choice(name="Iron Warden", value="iron_warden"),
            app_commands.Choice(name="The Blessed", value="the_blessed"),
            app_commands.Choice(name="Void-Touched", value="void_touched"),
            app_commands.Choice(name="Shadowborn", value="shadowborn"),
            app_commands.Choice(name="Ascendant", value="ascendant"),
        ]
    )
    async def prestige_title(
        self, interaction: discord.Interaction, title: app_commands.Choice[str]
    ) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        info = TITLES[title.value]
        already_owned = await self.bot.database.prestige.owns(
            user_id, "title", title.value
        )

        if not already_owned:
            gold = await self.bot.database.users.get_gold(user_id)
            if gold < info["price"]:
                return await interaction.response.send_message(
                    f"You need **{info['price']:,}g** for the title '{info['label']}'. You have **{gold:,}g**.",
                    ephemeral=True,
                )
            await self.bot.database.users.modify_gold(user_id, -info["price"])
            await self.bot.database.prestige.add_owned(user_id, "title", title.value)

        await self.bot.database.prestige.set_field(
            user_id, "prestige_title", title.value
        )
        suffix = f" (-{info['price']:,}g)" if not already_owned else " (free swap)"
        embed = discord.Embed(
            description=f"Title **{info['label']}** equipped.{suffix}",
            color=DEFAULT_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Flair ---

    @prestige_group.command(
        name="flair", description="Buy or equip a combat log flair style."
    )
    @app_commands.describe(style="The flair variant to buy or equip.")
    @app_commands.choices(
        style=[
            app_commands.Choice(name="Casual", value="casual"),
            app_commands.Choice(name="Heroic", value="heroic"),
            app_commands.Choice(name="Ominous", value="ominous"),
        ]
    )
    async def prestige_flair(
        self, interaction: discord.Interaction, style: app_commands.Choice[str]
    ) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        info = FLAIRS[style.value]
        already_owned = await self.bot.database.prestige.owns(
            user_id, "flair", style.value
        )

        if not already_owned:
            gold = await self.bot.database.users.get_gold(user_id)
            if gold < info["price"]:
                return await interaction.response.send_message(
                    f"You need **{info['price']:,}g** for the {info['label']} flair. You have **{gold:,}g**.",
                    ephemeral=True,
                )
            await self.bot.database.users.modify_gold(user_id, -info["price"])
            await self.bot.database.prestige.add_owned(user_id, "flair", style.value)

        await self.bot.database.prestige.set_field(
            user_id, "prestige_flair", style.value
        )
        suffix = f" (-{info['price']:,}g)" if not already_owned else " (free swap)"
        embed = discord.Embed(
            description=f"**{info['label']}** flair equipped.{suffix}",
            color=DEFAULT_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Rename ---

    @prestige_group.command(
        name="rename",
        description=f"Change your in-game display name ({RENAME_COST:,}g each time).",
    )
    async def prestige_rename(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        gold = await self.bot.database.users.get_gold(user_id)
        await interaction.response.send_modal(
            RenameModal(self, user_id, server_id, gold)
        )

    # --- Death Message ---

    @prestige_group.command(
        name="death_message",
        description=f"Set a custom death message ({DEATH_MSG_COST:,}g to unlock, free to update).",
    )
    async def prestige_death_message(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        already_unlocked = await self.bot.database.prestige.owns(
            user_id, "death_message", "unlocked"
        )
        gold = await self.bot.database.users.get_gold(user_id)
        await interaction.response.send_modal(
            DeathMessageModal(self, user_id, gold, already_unlocked)
        )

    # --- Monument ---

    @prestige_group.command(
        name="monument",
        description=f"Etch your name into the server Hall of Fame ({MONUMENT_COST:,}g, free to update).",
    )
    async def prestige_monument(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        already_owned = await self.bot.database.prestige.owns(
            user_id, "monument", "unlocked"
        )
        gold = await self.bot.database.users.get_gold(user_id)
        await interaction.response.send_modal(
            MonumentModal(self, user_id, gold, already_owned)
        )

    # --- Hall of Fame ---

    @prestige_group.command(name="hall", description="View the server Hall of Fame.")
    async def prestige_hall(self, interaction: discord.Interaction) -> None:
        server_id = str(interaction.guild.id)
        rows = await self.bot.database.prestige.get_monument_hall(server_id)

        embed = discord.Embed(title="Hall of Fame", color=DEFAULT_COLOR)
        if not rows:
            embed.description = "No monuments have been erected yet."
        else:
            lines = []
            for name, quote, title_key, level in rows:
                title_str = (
                    f"{_title_label(title_key)} "
                    if title_key and title_key in TITLES
                    else ""
                )
                lines.append(f'**{title_str}{name}** (Lv.{level})\n*"{quote}"*')
            embed.description = "\n\n".join(lines)

        await interaction.response.send_message(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(Prestige(bot))
