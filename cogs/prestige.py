import asyncio
import io
import urllib.request

import discord
from discord import ButtonStyle, app_commands, ui
from discord.ext import commands

# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

AVATAR_COST = 100_000_000

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

DEFAULT_COLOR = 0xBEBEFE


def _title_label(key: str) -> str:
    return TITLES.get(key, {}).get("label", "")


def _flair_label(key: str) -> str:
    return FLAIRS.get(key, {}).get("label", "")


# ---------------------------------------------------------------------------
# Avatar validation
# ---------------------------------------------------------------------------


async def _validate_avatar_url(url: str) -> tuple[bool, str]:
    """Returns (is_valid, error_message). Blocks in a thread to avoid blocking the event loop."""

    def _check() -> tuple[bool, str]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Idleology/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                ct = resp.headers.get("Content-Type", "")
                if not ct.startswith("image/"):
                    return (
                        False,
                        "URL must point to a direct image file (jpg, png, gif, webp).",
                    )
                data = resp.read(4 * 1024 * 1024)  # 4 MB cap
        except Exception as exc:
            return False, f"Could not fetch the URL: {exc}"

        try:
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            w, h = img.size
            if w != h:
                return False, f"Image must be square (1:1 ratio). Got {w}×{h}."
            if w > 600:
                return False, f"Image must be 600×600 or smaller. Got {w}×{h}."
            return True, ""
        except Exception as exc:
            return False, f"Could not read image dimensions: {exc}"

    return await asyncio.to_thread(_check)


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------


class AvatarModal(discord.ui.Modal, title="Set Custom Avatar"):
    url_input = discord.ui.TextInput(
        label="Image URL",
        placeholder="Direct link to a square image (≤ 600×600)…",
        min_length=10,
        max_length=500,
    )

    def __init__(self, bot, user_id: str, hub_view: "PrestigeHubView"):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.hub_view = hub_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        url = self.url_input.value.strip()

        valid, error = await _validate_avatar_url(url)
        if not valid:
            return await interaction.followup.send(error, ephemeral=True)

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < AVATAR_COST:
            return await interaction.followup.send(
                f"You need **{AVATAR_COST:,}g** to set a custom avatar. You have **{gold:,}g**.",
                ephemeral=True,
            )

        await self.bot.database.users.modify_gold(self.user_id, -AVATAR_COST)
        await self.bot.database.users.update_appearance(self.user_id, url)

        embed = await self.hub_view.refresh_and_sync()
        await interaction.followup.send(
            f"Avatar updated! (-{AVATAR_COST:,}g)", ephemeral=True
        )


class RenameModal(discord.ui.Modal, title="Rename Character"):
    new_name = discord.ui.TextInput(
        label="New Name",
        placeholder="Enter your new in-game name…",
        min_length=2,
        max_length=32,
    )

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        current_gold: int,
        hub_view: "PrestigeHubView",
    ):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.current_gold = current_gold
        self.hub_view = hub_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.new_name.value.strip()
        if self.current_gold < RENAME_COST:
            return await interaction.response.send_message(
                f"You need **{RENAME_COST:,}g** to rename. You have **{self.current_gold:,}g**.",
                ephemeral=True,
            )
        await self.bot.database.users.modify_gold(self.user_id, -RENAME_COST)
        await self.bot.database.prestige.set_field(
            self.user_id, "prestige_display_name", name
        )

        await interaction.response.send_message(
            f"Your name has been changed to **{name}**. (-{RENAME_COST:,}g)",
            ephemeral=True,
        )
        await self.hub_view.refresh_and_sync()


class DeathMessageModal(discord.ui.Modal, title="Set Death Message"):
    message = discord.ui.TextInput(
        label="Death Message",
        placeholder="Shown when you fall in combat…",
        min_length=2,
        max_length=120,
    )

    def __init__(
        self,
        bot,
        user_id: str,
        current_gold: int,
        already_unlocked: bool,
        hub_view: "PrestigeHubView",
    ):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.current_gold = current_gold
        self.already_unlocked = already_unlocked
        self.hub_view = hub_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cost = 0 if self.already_unlocked else DEATH_MSG_COST
        if cost > 0 and self.current_gold < cost:
            return await interaction.response.send_message(
                f"You need **{cost:,}g** to unlock a death message. You have **{self.current_gold:,}g**.",
                ephemeral=True,
            )
        if not self.already_unlocked:
            await self.bot.database.users.modify_gold(self.user_id, -cost)
            await self.bot.database.prestige.add_owned(
                self.user_id, "death_message", "unlocked"
            )
        await self.bot.database.prestige.set_field(
            self.user_id, "prestige_death_message", self.message.value.strip()
        )

        suffix = f" (-{cost:,}g)" if cost else ""
        await interaction.response.send_message(
            f"Death message set.{suffix}", ephemeral=True
        )
        await self.hub_view.refresh_and_sync()


class MonumentModal(discord.ui.Modal, title="Set Monument Quote"):
    quote = discord.ui.TextInput(
        label="Quote",
        placeholder="Your words, etched in stone…",
        min_length=2,
        max_length=150,
    )

    def __init__(
        self,
        bot,
        user_id: str,
        current_gold: int,
        already_owned: bool,
        hub_view: "PrestigeHubView",
    ):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.current_gold = current_gold
        self.already_owned = already_owned
        self.hub_view = hub_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cost = 0 if self.already_owned else MONUMENT_COST
        if cost > 0 and self.current_gold < cost:
            return await interaction.response.send_message(
                f"You need **{cost:,}g** for a monument slot. You have **{self.current_gold:,}g**.",
                ephemeral=True,
            )
        if not self.already_owned:
            await self.bot.database.users.modify_gold(self.user_id, -cost)
            await self.bot.database.prestige.add_owned(
                self.user_id, "monument", "unlocked"
            )
        await self.bot.database.prestige.set_field(
            self.user_id, "prestige_monument", self.quote.value.strip()
        )

        suffix = f" (-{cost:,}g)" if cost else ""
        await interaction.response.send_message(
            f"Monument quote updated.{suffix}", ephemeral=True
        )
        await self.hub_view.refresh_and_sync()


# ---------------------------------------------------------------------------
# Embed builders
# ---------------------------------------------------------------------------


class PrestigeBuilder:

    @staticmethod
    async def build_overview(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        active = await bot.database.prestige.get_active(user_id)
        gold = await bot.database.users.get_gold(user_id)
        owned_titles = await bot.database.prestige.get_owned(user_id, "title")
        owned_flairs = await bot.database.prestige.get_owned(user_id, "flair")

        embed = discord.Embed(title="Prestige", color=DEFAULT_COLOR)

        display_name = active.get("display_name") or user[3]
        title_label = _title_label(active.get("title", ""))
        name_str = (
            f"{title_label} **{display_name}**"
            if title_label
            else f"**{display_name}**"
        )
        embed.description = name_str
        embed.set_thumbnail(url=user[7])

        active_flair = _flair_label(active.get("flair", ""))
        embed.add_field(
            name="Active Cosmetics",
            value=(
                f"**Title:** {title_label or 'None'}\n"
                f"**Flair:** {active_flair or 'None'}\n"
                f"**Death Msg:** {active.get('death_message') or 'None'}\n"
                f"**Monument:** {active.get('monument') or 'None'}\n"
                f"**Avatar:** {'Custom' if user[7] else 'Default'}"
            ),
            inline=False,
        )

        def _fmt_owned(keys: list[str], catalogue: dict) -> str:
            labels = [catalogue[k]["label"] for k in keys if k in catalogue]
            return ", ".join(labels) if labels else "None"

        embed.add_field(
            name="Owned",
            value=(
                f"**Titles:** {_fmt_owned(owned_titles, TITLES)}\n"
                f"**Flairs:** {_fmt_owned(owned_flairs, FLAIRS)}"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Gold: {gold:,}g")
        return embed

    @staticmethod
    def build_shop() -> discord.Embed:
        embed = discord.Embed(title="Prestige Shop", color=DEFAULT_COLOR)

        titles_text = "\n".join(
            f"`{k}` — {v['label']} · **{v['price']:,}g**" for k, v in TITLES.items()
        )
        flairs_text = "\n".join(
            f"`{k}` — {v['label']} · **{v['price']:,}g**" for k, v in FLAIRS.items()
        )

        embed.add_field(name="Titles", value=titles_text, inline=False)
        embed.add_field(name="Combat Flairs", value=flairs_text, inline=False)
        embed.add_field(
            name="Other",
            value=(
                f"🖼️ **Custom Avatar** — **{AVATAR_COST:,}g** (per upload)\n"
                f"✏️ **Rename** — **{RENAME_COST:,}g** per rename\n"
                f"💀 **Death Message** — **{DEATH_MSG_COST:,}g** to unlock, free to update\n"
                f"🗿 **Monument** — **{MONUMENT_COST:,}g** to unlock, free to update"
            ),
            inline=False,
        )
        embed.set_footer(
            text="Titles and flairs are purchased once and freely swappable."
        )
        return embed

    @staticmethod
    async def build_hall(bot, server_id: str) -> discord.Embed:
        rows = await bot.database.prestige.get_monument_hall(server_id)
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
        return embed


# ---------------------------------------------------------------------------
# Hub view
# ---------------------------------------------------------------------------


class PrestigeHubView(ui.View):
    def __init__(self, bot, user_id: str, server_id: str):
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.active_tab = "overview"
        self.message: discord.Message | None = None

        # Cached state, populated by refresh()
        self.gold = 0
        self.active: dict = {}
        self.owned_titles: list[str] = []
        self.owned_flairs: list[str] = []

    async def refresh(self) -> None:
        """Re-fetch live state from DB and rebuild buttons."""
        self.gold = await self.bot.database.users.get_gold(self.user_id)
        self.active = await self.bot.database.prestige.get_active(self.user_id)
        self.owned_titles = await self.bot.database.prestige.get_owned(
            self.user_id, "title"
        )
        self.owned_flairs = await self.bot.database.prestige.get_owned(
            self.user_id, "flair"
        )
        self._rebuild()

    async def refresh_and_sync(self) -> discord.Embed:
        """Refresh state, rebuild, and push overview to the hub message. Returns the new embed."""
        await self.refresh()
        embed = await PrestigeBuilder.build_overview(
            self.bot, self.user_id, self.server_id
        )
        self.active_tab = "overview"
        self._rebuild()
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except Exception:
                pass
        return embed

    def _rebuild(self) -> None:
        self.clear_items()

        # Row 0: navigation tabs + close
        for tab_id, label in [
            ("overview", "Overview"),
            ("shop", "Shop"),
            ("hall", "Hall of Fame"),
        ]:
            style = (
                ButtonStyle.primary
                if self.active_tab == tab_id
                else ButtonStyle.secondary
            )
            btn = ui.Button(label=label, style=style, custom_id=f"tab_{tab_id}", row=0)
            btn.callback = self._handle_tab
            self.add_item(btn)

        close_btn = ui.Button(label="Close", style=ButtonStyle.danger, row=0)
        close_btn.callback = self._handle_close
        self.add_item(close_btn)

        # Row 1: action buttons
        for label, emoji, cb in [
            ("Set Avatar", "🖼️", self._handle_avatar),
            ("Rename", "✏️", self._handle_rename),
            ("Death Msg", "💀", self._handle_death_msg),
            ("Monument", "🗿", self._handle_monument),
        ]:
            btn = ui.Button(
                label=label, emoji=emoji, style=ButtonStyle.secondary, row=1
            )
            btn.callback = cb
            self.add_item(btn)

        # Row 2: title select
        active_title = self.active.get("title") or ""
        title_options = [
            discord.SelectOption(
                label=v["label"],
                value=k,
                description=(
                    "Owned — free to equip"
                    if k in self.owned_titles
                    else f"{v['price']:,}g"
                ),
                default=(k == active_title),
            )
            for k, v in TITLES.items()
        ]
        title_sel = ui.Select(
            placeholder="Equip a Title…", options=title_options, row=2
        )
        title_sel.callback = self._handle_title_select
        self.add_item(title_sel)

        # Row 3: flair select
        active_flair = self.active.get("flair") or ""
        flair_options = [
            discord.SelectOption(
                label=v["label"],
                value=k,
                description=(
                    "Owned — free to equip"
                    if k in self.owned_flairs
                    else f"{v['price']:,}g"
                ),
                default=(k == active_flair),
            )
            for k, v in FLAIRS.items()
        ]
        flair_sel = ui.Select(
            placeholder="Equip a Flair…", options=flair_options, row=3
        )
        flair_sel.callback = self._handle_flair_select
        self.add_item(flair_sel)

    # --- Lifecycle ---

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.user_id

    async def on_timeout(self) -> None:
        try:
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass

    # --- Tab navigation ---

    async def _handle_tab(self, interaction: discord.Interaction) -> None:
        tab_id = interaction.data["custom_id"].removeprefix("tab_")
        self.active_tab = tab_id
        self._rebuild()
        await interaction.response.defer()

        if tab_id == "overview":
            embed = await PrestigeBuilder.build_overview(
                self.bot, self.user_id, self.server_id
            )
        elif tab_id == "shop":
            embed = PrestigeBuilder.build_shop()
        else:
            embed = await PrestigeBuilder.build_hall(self.bot, self.server_id)

        await interaction.edit_original_response(embed=embed, view=self)

    # --- Action buttons ---

    async def _handle_close(self, interaction: discord.Interaction) -> None:
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()

    async def _handle_avatar(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AvatarModal(self.bot, self.user_id, self))

    async def _handle_rename(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            RenameModal(self.bot, self.user_id, self.server_id, self.gold, self)
        )

    async def _handle_death_msg(self, interaction: discord.Interaction) -> None:
        already_unlocked = await self.bot.database.prestige.owns(
            self.user_id, "death_message", "unlocked"
        )
        await interaction.response.send_modal(
            DeathMessageModal(self.bot, self.user_id, self.gold, already_unlocked, self)
        )

    async def _handle_monument(self, interaction: discord.Interaction) -> None:
        already_owned = await self.bot.database.prestige.owns(
            self.user_id, "monument", "unlocked"
        )
        await interaction.response.send_modal(
            MonumentModal(self.bot, self.user_id, self.gold, already_owned, self)
        )

    # --- Select interactions ---

    async def _handle_title_select(self, interaction: discord.Interaction) -> None:
        key = interaction.data["values"][0]
        info = TITLES[key]
        already_owned = key in self.owned_titles

        if already_owned and key == (self.active.get("title") or ""):
            return await interaction.response.defer()

        if not already_owned:
            if self.gold < info["price"]:
                return await interaction.response.send_message(
                    f"You need **{info['price']:,}g** for the title **{info['label']}**. You have **{self.gold:,}g**.",
                    ephemeral=True,
                )
            await self.bot.database.users.modify_gold(self.user_id, -info["price"])
            await self.bot.database.prestige.add_owned(self.user_id, "title", key)

        await self.bot.database.prestige.set_field(self.user_id, "prestige_title", key)
        suffix = f" (-{info['price']:,}g)" if not already_owned else " (free)"
        await interaction.response.defer()
        embed = await self.refresh_and_sync()
        await interaction.edit_original_response(
            embed=embed,
            view=self,
            content=f"Title **{info['label']}** equipped.{suffix}",
        )
        # Clear the content after a beat so it doesn't persist
        await asyncio.sleep(3)
        try:
            await interaction.edit_original_response(content=None)
        except Exception:
            pass

    async def _handle_flair_select(self, interaction: discord.Interaction) -> None:
        key = interaction.data["values"][0]
        info = FLAIRS[key]
        already_owned = key in self.owned_flairs

        if already_owned and key == (self.active.get("flair") or ""):
            return await interaction.response.defer()

        if not already_owned:
            if self.gold < info["price"]:
                return await interaction.response.send_message(
                    f"You need **{info['price']:,}g** for the flair **{info['label']}**. You have **{self.gold:,}g**.",
                    ephemeral=True,
                )
            await self.bot.database.users.modify_gold(self.user_id, -info["price"])
            await self.bot.database.prestige.add_owned(self.user_id, "flair", key)

        await self.bot.database.prestige.set_field(self.user_id, "prestige_flair", key)
        suffix = f" (-{info['price']:,}g)" if not already_owned else " (free)"
        await interaction.response.defer()
        embed = await self.refresh_and_sync()
        await interaction.edit_original_response(
            embed=embed,
            view=self,
            content=f"Flair **{info['label']}** equipped.{suffix}",
        )
        await asyncio.sleep(3)
        try:
            await interaction.edit_original_response(content=None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------


class Prestige(commands.Cog, name="prestige"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="prestige",
        description="Open the Prestige hub to browse cosmetics and manage your appearance.",
    )
    async def prestige(self, interaction: discord.Interaction) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)
        user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, user):
            return

        view = PrestigeHubView(self.bot, user_id, server_id)
        await view.refresh()
        embed = await PrestigeBuilder.build_overview(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Prestige(bot))
