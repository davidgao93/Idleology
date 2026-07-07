"""
cogs/dev_components.py
Owner-only scratch space for evaluating Discord's Components V2 layout
system (discord.ui.LayoutView / Container / Section / MediaGallery / etc)
against the bot's existing embeds. Not a player-facing feature.
"""

import discord
from discord.ext import commands

from core.images import (
    COMBAT_VICTORY,
    MONSTER_APHRODITE,
    RAGNA_PORTRAIT,
    TESSARA_THUMBNAIL,
    VALE_THUMBNAIL,
    YUNA_THUMBNAIL,
)

PAGES = {
    "profile": "🎫 Profile Card",
    "combat": "⚔️ Combat HUD",
    "prestige": "🌟 Prestige Gallery",
}


def _profile_container() -> discord.ui.Container:
    """Mockup of profile_ui_card.py's Adventurer License embed."""
    return discord.ui.Container(
        discord.ui.Section(
            "## 🎫 Adventurer License",
            "**Nyx** — Level 87 (Ascension 2)",
            accessory=discord.ui.Thumbnail(YUNA_THUMBNAIL, description="Nyx"),
        ),
        discord.ui.Separator(),
        discord.ui.TextDisplay(
            "**Experience**  182,340 / 210,000  *(86.8% to Lv.88)*\n"
            "**Ideology**  The Ashen Vow\n"
            "**Followers**  1,204\n"
            "**Gold**  4,820,150 💰"
        ),
        accent_color=discord.Color.gold(),
    )


def _combat_container() -> discord.ui.Container:
    """Mockup of combat_embed.py — adds a player thumbnail, which the
    classic combat embed currently has no room for."""
    return discord.ui.Container(
        discord.ui.Section(
            "### ⚔️ Nyx",
            "742/900 ❤️ (120 🔮)\n💎 **Surge**  6 / 10",
            accessory=discord.ui.Thumbnail(YUNA_THUMBNAIL, description="Nyx"),
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay("**Aphrodite, the Enchantress**  12,400/18,000 ❤️"),
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(media=MONSTER_APHRODITE, description="Aphrodite")
        ),
        discord.ui.Separator(spacing=discord.SeparatorSpacing.small),
        discord.ui.TextDisplay("*Nyx strikes for 1,204 damage! A critical hit!* 💥"),
        accent_color=discord.Color.red(),
    )


def _prestige_container() -> discord.ui.Container:
    """Mockup of the prestige avatar gallery idea — MediaGallery as a
    purchasable cosmetic grid."""
    return discord.ui.Container(
        discord.ui.TextDisplay("## 🌟 Prestige Avatar Gallery"),
        discord.ui.TextDisplay(
            "Spend **Glory Marks** to unlock an avatar frame. The equipped "
            "frame shows on your profile card and combat HUD."
        ),
        discord.ui.MediaGallery(
            discord.MediaGalleryItem(
                media=RAGNA_PORTRAIT, description="Fleshwright — 400 Glory Marks"
            ),
            discord.MediaGalleryItem(
                media=VALE_THUMBNAIL, description="Tower Warden — 400 Glory Marks"
            ),
            discord.MediaGalleryItem(
                media=TESSARA_THUMBNAIL, description="Lapidary — 400 Glory Marks"
            ),
            discord.MediaGalleryItem(
                media=COMBAT_VICTORY, description="Victorious — 800 Glory Marks"
            ),
        ),
        accent_color=discord.Color.purple(),
    )


_BUILDERS = {
    "profile": _profile_container,
    "combat": _combat_container,
    "prestige": _prestige_container,
}


class PageSelectRow(discord.ui.ActionRow["ComponentsMockupView"]):
    @discord.ui.select(
        placeholder="Choose a mockup page...",
        options=[
            discord.SelectOption(label=label, value=key)
            for key, label in PAGES.items()
        ],
    )
    async def page_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        chosen = select.values[0]
        new_view = ComponentsMockupView(interaction.user.id, page=chosen)
        await interaction.response.edit_message(view=new_view)


class CloseRow(discord.ui.ActionRow["ComponentsMockupView"]):
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.edit_message(view=None)


class ComponentsMockupView(discord.ui.LayoutView):
    """Not extended from core.base_view.BaseView — discord.ui.LayoutView is
    a sibling of discord.ui.View (both inherit discord.py's own internal
    BaseView), not a subclass of it, so the project's BaseView re-entry
    guard / session-token machinery doesn't attach here. Fine for this
    owner-only scratch tool; a real feature adoption would need a parallel
    BaseLayoutView mirroring core/base_view.py's logic.
    """

    def __init__(self, owner_id: int, page: str = "profile", *, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.page = page
        self.add_item(_BUILDERS[page]())
        self.add_item(PageSelectRow())
        self.add_item(CloseRow())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_id


class DevComponents(commands.Cog, name="dev_components"):
    """Owner-only Components V2 exploration tool."""

    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="components_mockup",
        description="[Owner] Preview Components V2 layout options.",
    )
    @commands.is_owner()
    async def components_mockup(self, context: commands.Context) -> None:
        view = ComponentsMockupView(context.author.id)
        await context.send(view=view)


async def setup(bot) -> None:
    await bot.add_cog(DevComponents(bot))
