import asyncio
import io
import re
import urllib.request

import discord
from discord import ButtonStyle, app_commands, ui
from discord.ext import commands
from core.base_view import BaseView
from core.character.prestige_display import format_prestige_name
from core.emojis import EMBLEM_CATALOG
from core.images import (
    ELIZA_PORTRAIT,
    ELIZA_THUMBNAIL,
    PRESTIGE_HALL,
    PRESTIGE_AVATARS_MALE,
    PRESTIGE_AVATARS_FEMALE,
    PRESTIGE_AVATARS_FEMALE_SS,
)
from core.npc_voices import get_quip

# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

AVATAR_COST = 100_000_000
EMBLEM_COST = 200_000_000
TITLE_COST = 300_000_000
RENAME_COST = 750_000_000
MONUMENT_COST = 2_000_000_000

AVATAR_TIER_PRICES: dict[str, int] = {
    "male": 250_000_000,
    "female": 500_000_000,
    "female_ss": 1_000_000_000,
}
# Tabs are labelled with their gender emoji rather than a text tier name —
# ⭐ marks the "Prestige" variant of a gender's gallery.
AVATAR_TIER_LABELS: dict[str, str] = {
    "male": "♂️",
    "female": "♀️",
    "female_ss": "♀️⭐",
}

# Purchasable animated avatar gallery. Tier -> codename -> {label, url}.
# Codenames match the keys in core.images.PRESTIGE_AVATARS_*; labels are
# the presentation names shown to players.
PRESTIGE_AVATAR_CATALOG: dict[str, dict[str, dict]] = {
    "male": {
        "berserker": {"label": "Berserker", "url": PRESTIGE_AVATARS_MALE["berserker"]},
        "gilded": {"label": "Gilded Champion", "url": PRESTIGE_AVATARS_MALE["gilded"]},
        "ronin": {"label": "Ronin", "url": PRESTIGE_AVATARS_MALE["ronin"]},
        "wiz": {"label": "Archmage", "url": PRESTIGE_AVATARS_MALE["wiz"]},
    },
    "female": {
        "bloodmage": {"label": "Blood Mage", "url": PRESTIGE_AVATARS_FEMALE["bloodmage"]},
        "gem": {"label": "Crystal Warden", "url": PRESTIGE_AVATARS_FEMALE["gem"]},
        "hunt": {"label": "Huntress", "url": PRESTIGE_AVATARS_FEMALE["hunt"]},
        "ninja": {"label": "Kunoichi", "url": PRESTIGE_AVATARS_FEMALE["ninja"]},
        "sorc": {"label": "Sorceress", "url": PRESTIGE_AVATARS_FEMALE["sorc"]},
        "void": {"label": "Void Walker", "url": PRESTIGE_AVATARS_FEMALE["void"]},
        "warriorangel": {"label": "Seraph Warrior", "url": PRESTIGE_AVATARS_FEMALE["warriorangel"]},
    },
    "female_ss": {
        "bride": {"label": "Eternal Bride", "url": PRESTIGE_AVATARS_FEMALE_SS["bride"]},
        "deepocean": {"label": "Abyssal Sovereign", "url": PRESTIGE_AVATARS_FEMALE_SS["deepocean"]},
        "fox": {"label": "Ninetails Fox", "url": PRESTIGE_AVATARS_FEMALE_SS["fox"]},
        "ice": {"label": "Glacial Sovereign", "url": PRESTIGE_AVATARS_FEMALE_SS["ice"]},
        "oni": {"label": "Oni Sovereign", "url": PRESTIGE_AVATARS_FEMALE_SS["oni"]},
        "petals": {"label": "Blossom Sovereign", "url": PRESTIGE_AVATARS_FEMALE_SS["petals"]},
        "snow": {"label": "Winter Sovereign", "url": PRESTIGE_AVATARS_FEMALE_SS["snow"]},
        "storm": {"label": "Storm Sovereign", "url": PRESTIGE_AVATARS_FEMALE_SS["storm"]},
        "tech": {"label": "Neon Sovereign", "url": PRESTIGE_AVATARS_FEMALE_SS["tech"]},
    },
}

_TITLE_RE = re.compile(r"^[A-Za-z0-9]{1,10}$")

DEFAULT_COLOR = 0xBEBEFE


def _avatar_label_for_url(url: str) -> str | None:
    """Reverse-lookup a preset avatar's display label from its equipped URL."""
    for tier_catalog in PRESTIGE_AVATAR_CATALOG.values():
        for info in tier_catalog.values():
            if info["url"] == url:
                return info["label"]
    return None


def _active_title(active: dict) -> str:
    title = active.get("title") or ""
    return "" if title == "none" else title


def _active_emblem_emoji(active: dict) -> str:
    key = active.get("emblem") or ""
    entry = EMBLEM_CATALOG.get(key)
    return entry[1] if entry else ""


def _active_emblem_label(active: dict) -> str:
    key = active.get("emblem") or ""
    entry = EMBLEM_CATALOG.get(key)
    return entry[0] if entry else "None"


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

        await self.hub_view.refresh_and_sync()
        await interaction.followup.send(
            f"Avatar updated! (-{AVATAR_COST:,}g)", ephemeral=True
        )


_AVATAR_TIER_ORDER = ("male", "female", "female_ss")


class AvatarGalleryView(BaseView):
    """Preset prestige avatar gallery: browse one animated avatar at a time
    (GIF rendered full-size via embed.set_image) with tier tabs + prev/next,
    a Buy & Equip button, and a Custom URL fallback."""

    def __init__(self, bot, parent: "PrestigeHubView"):
        super().__init__(bot, parent=parent)
        self.hub_view = parent
        self.owned_avatars: list[str] = []
        self.tier = "male"
        self.index = 0

    async def refresh(self) -> None:
        self.owned_avatars = await self.bot.database.prestige.get_owned(
            self.user_id, "avatar"
        )
        self._rebuild()

    def _tier_ids(self) -> list[str]:
        return list(PRESTIGE_AVATAR_CATALOG[self.tier].keys())

    def _current(self) -> tuple[str, dict]:
        avatar_id = self._tier_ids()[self.index]
        return avatar_id, PRESTIGE_AVATAR_CATALOG[self.tier][avatar_id]

    def build_embed(self) -> discord.Embed:
        avatar_id, info = self._current()
        price = AVATAR_TIER_PRICES[self.tier]
        owned = f"{self.tier}:{avatar_id}" in self.owned_avatars
        ids = self._tier_ids()

        embed = discord.Embed(
            title=info["label"],
            description=(
                f"**Tier {AVATAR_TIER_LABELS[self.tier]}**\n"
                + ("Owned — free to equip" if owned else f"**{price:,}g**")
            ),
            color=DEFAULT_COLOR,
        )
        embed.set_author(name="Eliza", icon_url=ELIZA_PORTRAIT)
        embed.set_image(url=info["url"])
        embed.set_footer(text=f"{self.index + 1} of {len(ids)} — {AVATAR_TIER_LABELS[self.tier]}")
        return embed

    def _rebuild(self) -> None:
        self.clear_items()

        for tier in _AVATAR_TIER_ORDER:
            style = ButtonStyle.primary if tier == self.tier else ButtonStyle.secondary
            btn = ui.Button(
                label=AVATAR_TIER_LABELS[tier],
                style=style,
                custom_id=f"avtier_{tier}",
                row=0,
            )
            btn.callback = self._handle_tier
            self.add_item(btn)

        # Prestige Male tier — art not ready yet, shown as a disabled placeholder.
        placeholder_btn = ui.Button(
            label="♂️⭐", style=ButtonStyle.secondary, disabled=True, row=0
        )
        self.add_item(placeholder_btn)

        ids = self._tier_ids()
        prev_btn = ui.Button(
            label="◀", style=ButtonStyle.secondary, disabled=(self.index == 0), row=1
        )
        prev_btn.callback = self._handle_prev
        self.add_item(prev_btn)

        avatar_id, info = self._current()
        price = AVATAR_TIER_PRICES[self.tier]
        owned = f"{self.tier}:{avatar_id}" in self.owned_avatars
        buy_btn = ui.Button(
            label="Equip" if owned else f"Buy & Equip — {price:,}g",
            style=ButtonStyle.success if owned else ButtonStyle.primary,
            row=1,
        )
        buy_btn.callback = self._handle_buy
        self.add_item(buy_btn)

        next_btn = ui.Button(
            label="▶",
            style=ButtonStyle.secondary,
            disabled=(self.index == len(ids) - 1),
            row=1,
        )
        next_btn.callback = self._handle_next
        self.add_item(next_btn)

        custom_btn = ui.Button(
            label="Custom URL", emoji="🖼️", style=ButtonStyle.secondary, row=2
        )
        custom_btn.callback = self._handle_custom
        self.add_item(custom_btn)

        # Back gets its own row, mirroring the Close convention on the hub.
        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=3)
        back_btn.callback = self._handle_back
        self.add_item(back_btn)

    async def _handle_tier(self, interaction: discord.Interaction) -> None:
        self.tier = interaction.data["custom_id"].removeprefix("avtier_")
        self.index = 0
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _handle_prev(self, interaction: discord.Interaction) -> None:
        self.index -= 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _handle_next(self, interaction: discord.Interaction) -> None:
        self.index += 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _handle_back(self, interaction: discord.Interaction) -> None:
        await self.hub_view.refresh()
        embed = await PrestigeBuilder.build_overview(self.bot, self.user_id, self.server_id)
        self.hub_view.active_tab = "overview"
        self.hub_view._rebuild()
        await interaction.response.defer()
        await interaction.edit_original_response(embed=embed, view=self.hub_view)
        self.hub_view.message = await interaction.original_response()

    async def _handle_custom(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(AvatarModal(self.bot, self.user_id, self.hub_view))

    async def _handle_buy(self, interaction: discord.Interaction) -> None:
        avatar_id, info = self._current()
        item_key = f"{self.tier}:{avatar_id}"
        price = AVATAR_TIER_PRICES[self.tier]
        owned = item_key in self.owned_avatars

        if not owned:
            gold = await self.bot.database.users.get_gold(self.user_id)
            if gold < price:
                return await interaction.response.send_message(
                    f"You need **{price:,}g** for **{info['label']}**. You have **{gold:,}g**.",
                    ephemeral=True,
                )
            await self.bot.database.users.modify_gold(self.user_id, -price)
            await self.bot.database.prestige.add_owned(self.user_id, "avatar", item_key)
            self.owned_avatars.append(item_key)

        await self.bot.database.users.update_appearance(self.user_id, info["url"])
        self._rebuild()

        suffix = f" (-{price:,}g)" if not owned else " (free)"
        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=self.build_embed(),
            view=self,
            content=f"Avatar **{info['label']}** equipped.{suffix}",
        )
        await asyncio.sleep(3)
        try:
            await interaction.edit_original_response(content=None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Emblem gallery
# ---------------------------------------------------------------------------

_EMBLEM_PAGE_SIZE = 25


class EmblemGalleryView(BaseView):
    """Browse the bot's uploaded emoji collection page by page and pick one
    to display beside your name. Flat cost per new emblem unlocked; already
    owned emblems are free to re-equip."""

    def __init__(self, bot, parent: "PrestigeHubView"):
        super().__init__(bot, parent=parent)
        self.hub_view = parent
        self.owned_emblems: list[str] = []
        self.active_emblem = ""
        self.keys = list(EMBLEM_CATALOG.keys())
        self.page = 0

    async def refresh(self) -> None:
        self.owned_emblems = await self.bot.database.prestige.get_owned(
            self.user_id, "emblem"
        )
        active = await self.bot.database.prestige.get_active(self.user_id)
        self.active_emblem = active.get("emblem") or ""
        self._rebuild()

    def _total_pages(self) -> int:
        return max(1, -(-len(self.keys) // _EMBLEM_PAGE_SIZE))

    def _page_keys(self) -> list[str]:
        start = self.page * _EMBLEM_PAGE_SIZE
        return self.keys[start : start + _EMBLEM_PAGE_SIZE]

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Prestige Emblem", color=DEFAULT_COLOR)
        embed.set_author(name="Eliza", icon_url=ELIZA_PORTRAIT)
        active_entry = EMBLEM_CATALOG.get(self.active_emblem)
        active_str = f"{active_entry[1]} {active_entry[0]}" if active_entry else "None"
        embed.description = (
            f"Pick an emblem to display beside your name. **{EMBLEM_COST:,}g** to unlock "
            "a new one — emblems you already own are free to re-equip.\n\n"
            f"**Currently equipped:** {active_str}"
        )
        embed.set_footer(text=f"Page {self.page + 1} of {self._total_pages()}")
        return embed

    def _rebuild(self) -> None:
        self.clear_items()

        page_keys = self._page_keys()
        options = []
        for key in page_keys:
            label, emoji = EMBLEM_CATALOG[key]
            owned = key in self.owned_emblems
            options.append(
                discord.SelectOption(
                    label=label,
                    value=key,
                    emoji=emoji,
                    description="Owned — free to equip" if owned else f"{EMBLEM_COST:,}g",
                    default=(key == self.active_emblem),
                )
            )
        select = ui.Select(placeholder="Choose an emblem…", options=options, row=0)
        select.callback = self._handle_select
        self.add_item(select)

        total_pages = self._total_pages()
        prev_btn = ui.Button(
            label="◀ Prev", style=ButtonStyle.secondary, disabled=(self.page == 0), row=1
        )
        prev_btn.callback = self._handle_prev
        self.add_item(prev_btn)

        next_btn = ui.Button(
            label="▶ Next",
            style=ButtonStyle.secondary,
            disabled=(self.page >= total_pages - 1),
            row=1,
        )
        next_btn.callback = self._handle_next
        self.add_item(next_btn)

        clear_btn = ui.Button(
            label="Remove Emblem",
            style=ButtonStyle.secondary,
            disabled=(not self.active_emblem),
            row=1,
        )
        clear_btn.callback = self._handle_clear
        self.add_item(clear_btn)

        back_btn = ui.Button(label="Back", style=ButtonStyle.secondary, row=2)
        back_btn.callback = self._handle_back
        self.add_item(back_btn)

    async def _handle_prev(self, interaction: discord.Interaction) -> None:
        self.page -= 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _handle_next(self, interaction: discord.Interaction) -> None:
        self.page += 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _handle_back(self, interaction: discord.Interaction) -> None:
        await self.hub_view.refresh()
        embed = await PrestigeBuilder.build_overview(self.bot, self.user_id, self.server_id)
        self.hub_view.active_tab = "overview"
        self.hub_view._rebuild()
        await interaction.response.defer()
        await interaction.edit_original_response(embed=embed, view=self.hub_view)
        self.hub_view.message = await interaction.original_response()

    async def _handle_clear(self, interaction: discord.Interaction) -> None:
        await self.bot.database.prestige.set_field(self.user_id, "prestige_emblem", "")
        self.active_emblem = ""
        self._rebuild()
        await interaction.response.edit_message(
            embed=self.build_embed(), view=self, content="Emblem removed."
        )
        await asyncio.sleep(3)
        try:
            await interaction.edit_original_response(content=None)
        except Exception:
            pass

    async def _handle_select(self, interaction: discord.Interaction) -> None:
        key = interaction.data["values"][0]
        label, emoji = EMBLEM_CATALOG[key]
        owned = key in self.owned_emblems

        if not owned:
            gold = await self.bot.database.users.get_gold(self.user_id)
            if gold < EMBLEM_COST:
                return await interaction.response.send_message(
                    f"You need **{EMBLEM_COST:,}g** to unlock **{emoji} {label}**. You have **{gold:,}g**.",
                    ephemeral=True,
                )
            await self.bot.database.users.modify_gold(self.user_id, -EMBLEM_COST)
            await self.bot.database.prestige.add_owned(self.user_id, "emblem", key)
            self.owned_emblems.append(key)

        await self.bot.database.prestige.set_field(self.user_id, "prestige_emblem", key)
        self.active_emblem = key
        self._rebuild()

        suffix = f" (-{EMBLEM_COST:,}g)" if not owned else " (free)"
        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=self.build_embed(),
            view=self,
            content=f"Emblem **{emoji} {label}** equipped.{suffix}",
        )
        await asyncio.sleep(3)
        try:
            await interaction.edit_original_response(content=None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------


class TitleModal(discord.ui.Modal, title="Set Prestige Title"):
    title_input = discord.ui.TextInput(
        label="Title",
        placeholder="Letters and numbers only, up to 10 characters…",
        min_length=1,
        max_length=10,
    )

    def __init__(self, bot, user_id: str, server_id: str, hub_view: "PrestigeHubView"):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.server_id = server_id
        self.hub_view = hub_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        text = self.title_input.value.strip()

        if not _TITLE_RE.match(text):
            return await interaction.followup.send(
                "Titles may only contain letters (A-Z) and numbers (0-9), up to 10 characters.",
                ephemeral=True,
            )

        user = await self.bot.database.users.get(self.user_id, self.server_id)
        active = await self.bot.database.prestige.get_active(self.user_id)
        gold = await self.bot.database.users.get_gold(self.user_id)

        display_name = active.get("display_name") or user["name"]
        preview = format_prestige_name(display_name, text, _active_emblem_emoji(active))

        embed = discord.Embed(
            title="Confirm Prestige Title",
            description=(
                f"**Preview:** {preview}\n\n"
                f"Cost: **{TITLE_COST:,}g**\nYour gold: **{gold:,}g**"
            ),
            color=DEFAULT_COLOR,
        )
        embed.set_author(name="Eliza", icon_url=ELIZA_PORTRAIT)
        view = TitlePreviewView(self.bot, self.user_id, self.server_id, text, self.hub_view)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class TitlePreviewView(BaseView):
    """Ephemeral confirm/cancel view shown after a title is typed, previewing
    the final display name before any gold is spent."""

    def __init__(
        self, bot, user_id: str, server_id: str, title_text: str, hub_view: "PrestigeHubView"
    ):
        super().__init__(bot, user_id, server_id)
        self.title_text = title_text
        self.hub_view = hub_view

    @ui.button(label="Confirm", style=ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button) -> None:
        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < TITLE_COST:
            return await interaction.response.edit_message(
                content=f"You need **{TITLE_COST:,}g** for a title. You have **{gold:,}g**.",
                embed=None,
                view=None,
            )
        await self.bot.database.users.modify_gold(self.user_id, -TITLE_COST)
        await self.bot.database.prestige.set_field(
            self.user_id, "prestige_title", self.title_text
        )
        await interaction.response.edit_message(
            content=f"Title set to **{self.title_text}**! (-{TITLE_COST:,}g)",
            embed=None,
            view=None,
        )
        await self.hub_view.refresh_and_sync()

    @ui.button(label="Cancel", style=ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await interaction.response.edit_message(
            content="Title purchase cancelled.", embed=None, view=None
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
        owned_emblems = await bot.database.prestige.get_owned(user_id, "emblem")
        owned_avatars = await bot.database.prestige.get_owned(user_id, "avatar")

        embed = discord.Embed(title="Prestige Shop", color=DEFAULT_COLOR)
        embed.set_author(name="Eliza", icon_url=ELIZA_PORTRAIT)
        embed.set_thumbnail(url=user["appearance"])

        display_name = active.get("display_name") or user["name"]
        name_str = format_prestige_name(
            display_name, _active_title(active), _active_emblem_emoji(active)
        )
        embed.description = f"*{get_quip('prestige')}*\n\n**{name_str}**"

        if user["appearance"]:
            avatar_display = _avatar_label_for_url(user["appearance"]) or "Custom"
        else:
            avatar_display = "Default"

        embed.add_field(
            name="Active Cosmetics",
            value=(
                f"**Title:** {_active_title(active) or 'None'}\n"
                f"**Emblem:** {_active_emblem_label(active)}\n"
                f"**Avatar:** {avatar_display}\n"
                f"**Monument:** {active.get('monument') or 'None'}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Owned",
            value=(
                f"**Emblems:** {len(owned_emblems)}/{len(EMBLEM_CATALOG)}\n"
                f"**Avatars:** {len(owned_avatars)}"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Gold: {gold:,}g")
        return embed

    @staticmethod
    def build_prices() -> discord.Embed:
        embed = discord.Embed(title="Prestige Prices", color=DEFAULT_COLOR)
        embed.set_author(name="Eliza", icon_url=ELIZA_PORTRAIT)
        embed.set_thumbnail(url=ELIZA_THUMBNAIL)

        embed.add_field(
            name="🏷️ Title",
            value=(
                f"Custom title, A-Z / 0-9, up to 10 characters — **{TITLE_COST:,}g** per change"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔰 Emblem",
            value=(
                f"Pick from the bot's emoji collection — **{EMBLEM_COST:,}g** to unlock a new "
                "one, free to re-equip anything you already own"
            ),
            inline=False,
        )
        embed.add_field(
            name="🖼️ Avatars",
            value=(
                f"♂️ Tier — **{AVATAR_TIER_PRICES['male']:,}g**\n"
                f"♀️ Tier — **{AVATAR_TIER_PRICES['female']:,}g**\n"
                f"♀️⭐ Tier — **{AVATAR_TIER_PRICES['female_ss']:,}g**\n"
                f"Custom Avatar upload — **{AVATAR_COST:,}g** per upload\n"
                "*Presets are owned once and freely swappable after.*"
            ),
            inline=False,
        )
        embed.add_field(
            name="✏️ Rename", value=f"**{RENAME_COST:,}g** per rename", inline=False
        )
        embed.add_field(
            name="🗿 Monument",
            value=f"**{MONUMENT_COST:,}g** to unlock, free to update after",
            inline=False,
        )
        embed.set_footer(text="Gold well spent, if you ask me.")
        return embed

    @staticmethod
    async def build_hall(bot, server_id: str) -> discord.Embed:
        rows = await bot.database.prestige.get_monument_hall(server_id)
        embed = discord.Embed(title="Hall of Fame", color=DEFAULT_COLOR)
        embed.set_author(name="Eliza", icon_url=ELIZA_PORTRAIT)
        embed.set_thumbnail(url=PRESTIGE_HALL)
        if not rows:
            embed.description = "No monuments have been erected yet."
        else:
            lines = []
            for row in rows:
                name = row["prestige_display_name"] or row["name"]
                quote = row["prestige_monument"]
                title_text = row["prestige_title"]
                title_text = "" if not title_text or title_text == "none" else title_text
                emblem_key = row["prestige_emblem"] or ""
                emblem_entry = EMBLEM_CATALOG.get(emblem_key)
                emblem_emoji = emblem_entry[1] if emblem_entry else ""
                decorated = format_prestige_name(name, title_text, emblem_emoji)
                lines.append(f'**{decorated}** (Lv.{row["level"]})\n*"{quote}"*')
            embed.description = "\n\n".join(lines)
        return embed


# ---------------------------------------------------------------------------
# Hub view
# ---------------------------------------------------------------------------


class PrestigeHubView(BaseView):
    def __init__(self, bot, user_id: str, server_id: str):
        super().__init__(bot, user_id, server_id)
        self.active_tab = "overview"

        # Cached state, populated by refresh()
        self.gold = 0
        self.active: dict = {}

    async def refresh(self) -> None:
        """Re-fetch live state from DB and rebuild buttons."""
        self.gold = await self.bot.database.users.get_gold(self.user_id)
        self.active = await self.bot.database.prestige.get_active(self.user_id)
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

        # Row 0: primary actions
        for label, emoji, cb in [
            ("Avatars", "🖼️", self._handle_avatar),
            ("Titles", "🏷️", self._handle_title),
            ("Emblem", "🔰", self._handle_emblem),
            ("Monument", "🗿", self._handle_monument),
            ("Rename", "✏️", self._handle_rename),
        ]:
            btn = ui.Button(label=label, emoji=emoji, style=ButtonStyle.secondary, row=0)
            btn.callback = cb
            self.add_item(btn)

        # Row 1: navigation tabs
        for tab_id, label in [
            ("overview", "Overview"),
            ("prices", "Prices"),
            ("hall", "Hall of Fame"),
        ]:
            style = (
                ButtonStyle.primary
                if self.active_tab == tab_id
                else ButtonStyle.secondary
            )
            btn = ui.Button(label=label, style=style, custom_id=f"tab_{tab_id}", row=1)
            btn.callback = self._handle_tab
            self.add_item(btn)

        # Row 2: Close, alone on its own row (matches the Close convention used
        # by every other hub view in the bot).
        close_btn = ui.Button(label="Close", style=ButtonStyle.secondary, emoji="✖️", row=2)
        close_btn.callback = self._handle_close
        self.add_item(close_btn)

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
        elif tab_id == "prices":
            embed = PrestigeBuilder.build_prices()
        else:
            embed = await PrestigeBuilder.build_hall(self.bot, self.server_id)

        await interaction.edit_original_response(embed=embed, view=self)

    # --- Action buttons ---

    async def _handle_close(self, interaction: discord.Interaction) -> None:
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
        await interaction.response.defer()
        await interaction.delete_original_response()

    async def _handle_avatar(self, interaction: discord.Interaction) -> None:
        view = AvatarGalleryView(self.bot, self)
        await view.refresh()
        await interaction.response.defer()
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    async def _handle_emblem(self, interaction: discord.Interaction) -> None:
        view = EmblemGalleryView(self.bot, self)
        await view.refresh()
        await interaction.response.defer()
        await interaction.edit_original_response(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    async def _handle_title(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            TitleModal(self.bot, self.user_id, self.server_id, self)
        )

    async def _handle_rename(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            RenameModal(self.bot, self.user_id, self.server_id, self.gold, self)
        )

    async def _handle_monument(self, interaction: discord.Interaction) -> None:
        already_owned = await self.bot.database.prestige.owns(
            self.user_id, "monument", "unlocked"
        )
        await interaction.response.send_modal(
            MonumentModal(self.bot, self.user_id, self.gold, already_owned, self)
        )


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
        self.bot.state_manager.set_active(user_id, "prestige")
        view = PrestigeHubView(self.bot, user_id, server_id)
        await view.refresh()
        embed = await PrestigeBuilder.build_overview(self.bot, user_id, server_id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot) -> None:
    await bot.add_cog(Prestige(bot))
