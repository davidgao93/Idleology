"""core/hall_of_firsts/triggers.py — One check_<key> function per Hall of
Firsts category. This is the *only* place each achievement's threshold
constant lives; call sites elsewhere in the codebase just call the matching
check_* function right after their existing DB write, passing whatever value
they already have on hand.
"""

from __future__ import annotations

from core.hall_of_firsts.mechanics import try_claim_first
from core.skills.mechanics import SkillMechanics


async def check_absolute_cinema(bot, user_id: str) -> None:
    await try_claim_first(bot, user_id, "absolute_cinema")


async def check_nolife_andy(bot, user_id: str, level: int) -> None:
    if level == 100:
        await try_claim_first(bot, user_id, "nolife_andy")


async def check_looksmaxxer(bot, user_id: str) -> None:
    """Call only from the branch where the avatar was NOT already owned
    (i.e. a genuine first purchase, not a free re-equip)."""
    await try_claim_first(bot, user_id, "looksmaxxer")


async def check_really_board(bot, user_id: str, total_completions: int) -> None:
    if total_completions >= 300:
        await try_claim_first(bot, user_id, "really_board")


async def check_king(bot, user_id: str, developed_plot_count: int) -> None:
    if developed_plot_count >= 20:
        await try_claim_first(bot, user_id, "king")


async def check_mixologist(bot, user_id: str, new_level: int) -> None:
    if new_level >= 5:
        await try_claim_first(bot, user_id, "mixologist")


async def check_hunter_of_hunters(bot, user_id: str, soul_stone) -> None:
    if soul_stone is not None and all(slot.tier == 5 for slot in soul_stone.slots):
        await try_claim_first(bot, user_id, "hunter_of_hunters")


async def check_dang_yo(bot, user_id: str, refinement_lvl: int) -> None:
    if refinement_lvl >= 500:
        await try_claim_first(bot, user_id, "dang_yo")


async def check_all_in(bot, user_id: str, payout: int) -> None:
    if payout >= 1_000_000_000:
        await try_claim_first(bot, user_id, "all_in")


async def check_friends_with_benefits(bot, user_id: str, new_level: int) -> None:
    if new_level >= 100:
        await try_claim_first(bot, user_id, "friends_with_benefits")


async def check_monster_tamer(bot, user_id: str, new_level: int) -> None:
    if new_level >= 100:
        await try_claim_first(bot, user_id, "monster_tamer")


async def check_peak(bot, user_id: str, floor: int) -> None:
    if floor >= 666:
        await try_claim_first(bot, user_id, "peak")


async def check_loremaster(bot, user_id: str, codex_tomes: list) -> None:
    tier5_count = sum(1 for tome in codex_tomes if getattr(tome, "tier", 0) >= 5)
    if tier5_count >= 5:
        await try_claim_first(bot, user_id, "loremaster")


async def check_fabulous(bot, user_id: str, slot: str) -> None:
    if slot == "cheeks":
        await try_claim_first(bot, user_id, "fabulous")


async def check_the_trickster(bot, user_id: str, gold_amount: int) -> None:
    if gold_amount >= 100_000_000:
        await try_claim_first(bot, user_id, "the_trickster")


async def check_cult_leader(bot, user_id: str, follower_count: int) -> None:
    if follower_count >= 100_000:
        await try_claim_first(bot, user_id, "cult_leader")


async def check_one_with_nature(bot, user_id: str, server_id: str) -> None:
    """Fetches all 3 gathering tool rows and checks whether every tool is
    currently at its skill's top tier simultaneously."""
    for skill in ("mining", "fishing", "woodcutting"):
        row = await bot.database.skills.get_data(user_id, server_id, skill)
        if not row:
            return
        current_tier = SkillMechanics.get_tool_tier(skill, row)
        top_tier = SkillMechanics.get_tool_tiers(skill)[-1]
        if current_tier != top_tier:
            return
    await try_claim_first(bot, user_id, "one_with_nature")
