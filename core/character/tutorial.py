import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button

from core.base_view import BaseView

# ── Asset URLs ────────────────────────────────────────────────────────────────
# Discord CDN signed URLs expire after ~90 days.  If images break, re-upload
# to the same channel and update the constants below.
# Source channel: 1334637411363323996

AMARA_PORTRAIT = (
    "https://cdn.discordapp.com/attachments/1334637411363323996"
    "/1509665755707215992/guildmaster_amara.jpg"
    "?ex=6a1a014c&is=6a18afcc"
    "&hm=0e213ea0757113d5ec7d3f6cad0ebd458b57d804e4f0a413d3146487b74ad8c5&"
)

_SCENES = [
    {
        "title": "Welcome to the Guild",
        "text": (
            "I'm Amara. I've been running this hall since before most of the names on our "
            "wall of fame were born. The world beyond those doors is vast, dangerous, and "
            "largely indifferent to whether you survive it. Monsters, dungeons, rival "
            "ideologies — all of it waiting.\n\n"
            "You're here because you think you have what it takes. "
            "Good. Now stop thinking and start proving it."
        ),
        "image": (
            "https://cdn.discordapp.com/attachments/1334637411363323996"
            "/1509665757095657512/tutorial_01.jpg"
            "?ex=6a1a014c&is=6a18afcc"
            "&hm=8ee25ed74f01a56f930cf5df4e1d4e8e4706570041cbb3f46c6da49a209cd2e1&"
        ),
        "color": 0x3D2B1F,
    },
    {
        "title": "Steel and Consequence",
        "text": (
            "Your primary job is `/combat`. Find a monster, fight it, survive. "
            "Every kill earns gold and experience, and as you grow stronger you'll find "
            "gear with passives that change how you fight — weapons that chain hits, "
            "armor that shrugs off blows.\n\n"
            "Learn what your equipment actually does. "
            "A warrior who doesn't know their own kit is just a liability with a sword."
        ),
        "image": (
            "https://cdn.discordapp.com/attachments/1334637411363323996"
            "/1509665757317828689/tutorial_02.jpg"
            "?ex=6a1a014c&is=6a18afcc"
            "&hm=739228908f2715ab9f74c7c304f0e93bdda6ba89f75fccfdc41eb0b66cb33c4c&"
        ),
        "color": 0x7B1E1E,
    },
    {
        "title": "The Trades",
        "text": (
            "Not everything worth having comes off a monster's corpse. "
            "`/gather`, to keep your tools up to date, you passively gather materials while you're away — "
            "ore from the deep, fish from cursed rivers, timber from whatever forest "
            "hasn't tried to kill someone this week.\n\n"
            "The resources feed the crafting systems. Upgrading your tools makes the work "
            "faster. The best adventurers I've known idled smart, not hard. "
        ),
        "image": (
            "https://cdn.discordapp.com/attachments/1334637411363323996"
            "/1509665757557166133/tutorial_03.jpg"
            "?ex=6a1a014c&is=6a18afcc"
            "&hm=760a2beb863aed59a9b43792f9948182f0f4869f697d4b193460f2c71848c9ab&"
        ),
        "color": 0x2D4A1E,
    },
    {
        "title": "Your Legacy",
        "text": (
            "The ideology you named isn't decoration — it's the mark you leave on this server. "
            "Spread it and others will follow. Or they'll oppose you, "
            "which is just as interesting.\n\n"
            "A strong ideology draws eyes, creates rivalries, and eventually becomes history. "
            "Use `/ideology` to see who's risen and who's already faded. "
            "Once you're strong enough, you can start collecting companions, build your own settlement.\n\n"
            "The possibilities are limitless."
        ),
        "image": (
            "https://cdn.discordapp.com/attachments/1334637411363323996"
            "/1509665757791911936/tutorial_04.jpg"
            "?ex=6a1a014c&is=6a18afcc"
            "&hm=c146fee87be260e0edd5182a5c9f2d2d4a7e8cb3e710d58ea4e320e49295c95f&"
        ),
        "color": 0x4A2370,
    },
    {
        "title": "How Far Are You Willing to Go?",
        "text": (
            "Your early days will be spent leveling, learning your gear, and getting your footing. "
            "But past a certain point the easy fights stop being enough. "
            "The Ascent goes deeper than most people are willing to follow. "
            "The Codex will test whether you actually understand this world or just stumbled through it. "
            "The Apex monsters have killed adventurers I thought were untouchable.\n\n"
            "Start with `/journey` — it hands you your first milestones and gets you moving. "
            "The rest reveals itself when you're ready for it. Or before."
        ),
        "image": (
            "https://cdn.discordapp.com/attachments/1334637411363323996"
            "/1509665758047637726/tutorial_05.jpg"
            "?ex=6a1a014c&is=6a18afcc"
            "&hm=e84bff6aa96ce4887f50991b8ce1b243af4c1589a1bb16890c30658870caee20&"
        ),
        "color": 0x1A1A2E,
    },
]


class TutorialView(BaseView):
    """
    Five-scene onboarding narrated by Guildmaster Amara.

    Triggered automatically after registration, and available standalone via /tutorial.

    Parameters
    ----------
    finish_embed : discord.Embed | None
        Embed displayed when the tutorial ends (registration flow).
        When None (tutorial command flow), a short dismissal embed is shown instead.
    """

    def __init__(
        self,
        bot,
        user_id: str,
        server_id: str,
        *,
        finish_embed: discord.Embed | None = None,
    ):
        super().__init__(bot, user_id, server_id)
        self.index = 0
        self.finish_embed = finish_embed
        self._rebuild()

    # ── Embed ─────────────────────────────────────────────────────────────────

    def build_embed(self) -> discord.Embed:
        scene = _SCENES[self.index]
        embed = discord.Embed(
            title=scene["title"],
            description=scene["text"],
            color=scene["color"],
        )
        embed.set_author(name="Guildmaster Amara", icon_url=AMARA_PORTRAIT)
        embed.set_image(url=scene["image"])
        embed.set_footer(text=f"Scene {self.index + 1} of {len(_SCENES)}")
        return embed

    # ── View construction ─────────────────────────────────────────────────────

    def _rebuild(self):
        self.clear_items()
        last = len(_SCENES) - 1

        prev_btn = Button(
            label="← Back",
            style=ButtonStyle.secondary,
            disabled=(self.index == 0),
            row=0,
        )
        prev_btn.callback = self._on_prev
        self.add_item(prev_btn)

        if self.index < last:
            next_btn = Button(label="Next →", style=ButtonStyle.primary, row=0)
            next_btn.callback = self._on_next
            self.add_item(next_btn)

            skip_btn = Button(label="Skip Tutorial", style=ButtonStyle.danger, row=0)
            skip_btn.callback = self._on_finish
            self.add_item(skip_btn)
        else:
            finish_btn = Button(
                label="Begin Adventure ⚔️", style=ButtonStyle.success, row=0
            )
            finish_btn.callback = self._on_finish
            self.add_item(finish_btn)

    # ── Callbacks ─────────────────────────────────────────────────────────────

    async def _on_prev(self, interaction: Interaction):
        self.index -= 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_next(self, interaction: Interaction):
        self.index += 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_finish(self, interaction: Interaction):
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()

        if self.finish_embed:
            await interaction.response.edit_message(embed=self.finish_embed, view=None)
        else:
            # Standalone /tutorial flow — brief Amara dismissal
            embed = discord.Embed(
                description='*Amara waves you toward the doors.*\n"Good. Now go."',
                color=0x3D2B1F,
            )
            embed.set_author(name="Guildmaster Amara", icon_url=AMARA_PORTRAIT)
            await interaction.response.edit_message(embed=embed, view=None)
