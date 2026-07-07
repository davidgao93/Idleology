import json
from datetime import datetime, timezone

import discord
from discord import Interaction, app_commands
from discord.ext import commands

# player_currencies columns that can be granted via codes
_CURRENCY_COLUMNS = {
    "curios",
    "curio_puzzle_boxes",
    "refinement_runes",
    "potential_runes",
    "imbue_runes",
    "shatter_runes",
    "partnership_runes",
    "rune_of_regret",
    "runes_of_nature",
    "dragon_key",
    "angel_key",
    "void_keys",
    "pinnacle_key",
    "soul_cores",
    "void_frags",
    "balance_fragment",
    "spirit_stones",
    "antique_tome",
    "codex_fragments",
    "codex_pages",
    "codex_rerolls",
    "mirage_runes_imperfect",
    "mirage_runes_perfected",
    "companion_pet_xp",
    "passive_points",
}

_REWARD_LABELS = {
    "gold": "Gold",
    "guild_tickets": "Guild Tickets",
    "quest_tokens": "Quest Tokens",
    "curios": "Curios",
    "curio_puzzle_boxes": "Curio Puzzle Boxes",
    "refinement_runes": "Refinement Runes",
    "potential_runes": "Potential Runes",
    "imbue_runes": "Imbue Runes",
    "shatter_runes": "Shatter Runes",
    "partnership_runes": "Partnership Runes",
    "rune_of_regret": "Runes of Regret",
    "runes_of_nature": "Runes of Nature",
    "dragon_key": "Dragon Keys",
    "angel_key": "Angel Keys",
    "void_keys": "Void Keys",
    "pinnacle_key": "Pinnacle Keys",
    "soul_cores": "Soul Cores",
    "void_frags": "Void Fragments",
    "balance_fragment": "Balance Fragments",
    "spirit_stones": "Spirit Stones",
    "antique_tome": "Antique Tomes",
    "codex_fragments": "Codex Fragments",
    "codex_pages": "Codex Pages",
    "codex_rerolls": "Codex Rerolls",
    "mirage_runes_imperfect": "Imperfect Mirage Runes",
    "mirage_runes_perfected": "Perfected Mirage Runes",
    "companion_pet_xp": "Companion Pet XP",
    "passive_points": "Passive Points",
}


class Codes(commands.Cog, name="codes"):
    def __init__(self, bot) -> None:
        self.bot = bot

    def _is_admin(self, user_id: str) -> bool:
        admin_ids = [str(x) for x in self.bot.config.get("admin_user_ids", [])]
        return user_id in admin_ids

    async def _apply_rewards(self, user_id: str, rewards: dict) -> None:
        for key, amount in rewards.items():
            if key == "gold":
                await self.bot.database.users.modify_gold(user_id, amount)
            elif key == "guild_tickets":
                await self.bot.database.partners.add_tickets(user_id, amount)
            elif key == "quest_tokens":
                await self.bot.database.quests.add_tokens(user_id, amount)
            elif key in _CURRENCY_COLUMNS:
                await self.bot.database.users.modify_currency(user_id, key, amount)

    def _build_reward_lines(self, rewards: dict) -> str:
        lines = []
        for key, amount in rewards.items():
            label = _REWARD_LABELS.get(key, key.replace("_", " ").title())
            lines.append(f"**{amount:,}x** {label}")
        return "\n".join(lines)

    @app_commands.command(name="redeem_code", description="Redeem a code for rewards.")
    @app_commands.describe(code="The code to redeem.")
    async def redeem_code(self, interaction: Interaction, code: str) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild.id)

        existing_user = await self.bot.database.users.get(user_id, server_id)
        if not await self.bot.check_user_registered(interaction, existing_user):
            return

        code_upper = code.strip().upper()
        record = await self.bot.database.codes.get_code(code_upper)

        # Use a generic message for all failures to avoid probing
        invalid_msg = "That code is invalid or unavailable."

        if not record:
            return await interaction.response.send_message(invalid_msg, ephemeral=True)

        # Expiry check
        if record["expires_at"]:
            expires = datetime.fromisoformat(record["expires_at"]).replace(
                tzinfo=timezone.utc
            )
            if datetime.now(timezone.utc) > expires:
                return await interaction.response.send_message(
                    invalid_msg, ephemeral=True
                )

        # Admin-only check — same generic message so the code isn't revealed
        if record["is_admin_only"] and not self._is_admin(user_id):
            return await interaction.response.send_message(invalid_msg, ephemeral=True)

        # Global use cap
        if (
            record["max_uses"] is not None
            and record["total_uses"] >= record["max_uses"]
        ):
            return await interaction.response.send_message(
                "This code is no longer available.", ephemeral=True
            )

        # Per-user duplicate check
        if await self.bot.database.codes.has_redeemed(code_upper, user_id):
            return await interaction.response.send_message(
                "You've already redeemed this code.", ephemeral=True
            )

        rewards = json.loads(record["rewards"])
        await self._apply_rewards(user_id, rewards)
        await self.bot.database.codes.record_redemption(code_upper, user_id)

        embed = discord.Embed(
            title="Code Redeemed!",
            description=f"You redeemed **{code_upper}** and received:\n\n{self._build_reward_lines(rewards)}",
            color=0x57F287,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ----------------------------------------------------------------
    # Owner-only prefix command to create codes from the terminal.
    # Everything is captured as a single rest string to avoid discord.py's
    # quote parser choking on JSON double-quotes.
    #
    # Usage:
    #   &create_code CODE {"curios":10,"gold":200000}
    #   &create_code CODE {"gold":2000000000} --admin
    #   &create_code CODE {"curios":5} --max 100
    #   &create_code CODE {"gold":500} --admin --max 50
    # ----------------------------------------------------------------
    @commands.command(name="create_code")
    @commands.is_owner()
    async def create_code(self, ctx: commands.Context, *, rest: str) -> None:
        # Pull the JSON blob out first (everything from the first { to the last })
        json_start = rest.find("{")
        json_end = rest.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            return await ctx.send(
                "Usage: `&create_code CODE {json} [--admin] [--max N]`"
            )

        code = (
            rest[:json_start].strip().split()[0] if rest[:json_start].strip() else None
        )
        if not code:
            return await ctx.send(
                "Usage: `&create_code CODE {json} [--admin] [--max N]`"
            )

        rewards_json = rest[json_start:json_end]
        flags = rest[json_end:].split()

        try:
            rewards = json.loads(rewards_json)
        except json.JSONDecodeError:
            return await ctx.send("Invalid JSON for rewards.")

        unknown_keys = (
            set(rewards) - _CURRENCY_COLUMNS - {"gold", "guild_tickets", "quest_tokens"}
        )
        if unknown_keys:
            return await ctx.send(f"Unknown reward keys: {unknown_keys}")

        is_admin_only = "--admin" in flags
        max_uses: int | None = None
        if "--max" in flags:
            idx = flags.index("--max")
            try:
                max_uses = int(flags[idx + 1])
            except (IndexError, ValueError):
                return await ctx.send("--max requires an integer, e.g. `--max 100`")

        await self.bot.database.codes.create_code(
            code=code,
            rewards=rewards,
            max_uses=max_uses,
            is_admin_only=is_admin_only,
        )
        parts = [f"Created code **{code.upper()}**", f"rewards: {rewards_json}"]
        if max_uses:
            parts.append(f"max uses: {max_uses}")
        if is_admin_only:
            parts.append("admin-only")
        await ctx.send(" — ".join(parts))


async def setup(bot) -> None:
    await bot.add_cog(Codes(bot))
