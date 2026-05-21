"""
core/combat/economy/victory.py — Post-victory reward orchestration.

Extracted from core/combat/views.py so that CombatView.handle_end_state only
contains combat flow (phase transitions, embed routing) and not reward logic.

Why a new file instead of adding to rewards.py:
  drops.py already imports ``from core.combat import rewards``, so adding
  imports from drops.py back into rewards.py would create a circular dependency.
  victory.py sits above both and imports freely from each.
"""

from __future__ import annotations

import asyncio
import random

import discord

import core.slayer.mechanics
from core.combat.economy.config import (
    BOSS_PET_CHANCE,
    BOSS_PET_CHANCE_GEMINI_BOOT,
    REGULAR_PET_CHANCE,
    REGULAR_PET_CHANCE_GEMINI_BOOT,
    SLAYER_SCAVENGER_CHANCE_PER_TIER,
    SLAYER_TASKMASTER_CHANCE_PER_TIER,
)
from core.combat.economy.drops import (
    DropManager,
    apply_boss_sigil_drops,
    apply_corrupted_monster_drops,
    apply_incubated_monster_drops,
)
from core.combat.economy.experience import ExperienceManager
from core.combat.economy.rewards import (
    apply_partner_end_rewards,
    apply_special_flags,
    calculate_rewards,
    check_special_drops,
)
from core.companions.mechanics import CompanionMechanics
from core.images import (
    BOSS_APHRODITE,
    BOSS_GEMINI_PET,
    BOSS_LUCIFER,
    BOSS_NEET,
    MONSTER_EVELYNN_PRECURSOR,
)
from core.models import Monster, Player

# ---------------------------------------------------------------------------
# Companion drops
# ---------------------------------------------------------------------------


def _get_boss_pet_image(boss_name: str) -> str | None:
    if "NEET" in boss_name:
        return BOSS_NEET
    if "Aphrodite" in boss_name:
        return BOSS_APHRODITE
    if "Gemini" in boss_name:
        return BOSS_GEMINI_PET
    if "Lucifer" in boss_name:
        return BOSS_LUCIFER
    if "Evelynn" in boss_name:
        return MONSTER_EVELYNN_PRECURSOR
    return None


async def _apply_companion_drops(
    bot,
    user_id: str,
    player: Player,
    monster: Monster,
    reward_data: dict,
    message,
) -> None:
    current_pet_count = await bot.database.companions.get_count(user_id)

    _gemini_boot = player.get_boot_corrupted_essence() == "gemini"
    boss_pet_chance = BOSS_PET_CHANCE_GEMINI_BOOT if _gemini_boot else BOSS_PET_CHANCE
    regular_pet_chance = (
        REGULAR_PET_CHANCE_GEMINI_BOOT if _gemini_boot else REGULAR_PET_CHANCE
    )

    boss_img = _get_boss_pet_image(monster.name)
    boss_pet_triggered = False

    if monster.is_boss and boss_img and current_pet_count < 20:
        if random.random() < boss_pet_chance:
            boss_pet_triggered = True
            p_type, p_tier = CompanionMechanics.roll_boss_passive()
            pet_name = monster.name.split(",")[0]

            await bot.database.companions.add_companion(
                user_id,
                name=pet_name,
                species="Boss",
                image=boss_img,
                p_type=p_type,
                p_tier=p_tier,
            )
            await bot.database.users.initialize_companion_timer(user_id)

            tame_embed = discord.Embed(
                title="⚠️ ANOMALY DETECTED ⚠️",
                description=(
                    f"The spirit of **{pet_name}** refuses to fade...\n"
                    "It binds itself to your soul!"
                ),
                color=discord.Color.dark_theme(),
            )
            tame_embed.set_image(url=boss_img)
            tame_embed.add_field(
                name="LEGENDARY TAMING",
                value=f"You have obtained **{pet_name}** (Tier {p_tier} Passive)!",
                inline=False,
            )
            tame_embed.set_footer(text="A Boss Companion has joined your roster.")

            await message.edit(embed=tame_embed, view=None)
            await asyncio.sleep(5)

            reward_data["msgs"].append(
                f"👑 **LEGENDARY:** {pet_name} joined your roster!"
            )

    if (
        not boss_pet_triggered
        and not monster.is_boss
        and current_pet_count < 20
        and random.random() < regular_pet_chance
    ):
        p_type, p_tier = CompanionMechanics.roll_new_passive(is_capture=True)
        await bot.database.companions.add_companion(
            user_id,
            name=monster.name,
            species=monster.species,
            image=monster.image,
            p_type=p_type,
            p_tier=p_tier,
        )
        reward_data["msgs"].append(
            f"🕸️ Following it's defeat, the {monster.name} decides to join you on your journey!"
        )


# ---------------------------------------------------------------------------
# Slayer task rewards
# ---------------------------------------------------------------------------


async def _apply_slayer_rewards(
    bot,
    user_id: str,
    server_id: str,
    player: Player,
    monster: Monster,
    reward_data: dict,
) -> None:
    if monster.is_boss:
        return

    s_profile = await bot.database.slayer.get_profile(user_id, server_id)
    if s_profile["active_task_species"] != monster.species:
        return

    slayer_lines = []

    # Base Slayer XP + drops
    await bot.database.slayer.add_rewards(user_id, server_id, xp=500, points=0)
    slayer_lines.append("+500 Slayer XP")

    ess, heart = core.slayer.mechanics.SlayerMechanics.roll_drops(monster.level)
    drop_bonus_tiers = player.get_emblem_bonus("slayer_drops")
    if drop_bonus_tiers > 0 and random.random() < (
        drop_bonus_tiers * SLAYER_SCAVENGER_CHANCE_PER_TIER
    ):
        ess *= 2
        heart *= 2

    if ess > 0:
        await bot.database.slayer.modify_materials(
            user_id, server_id, "violent_essence", ess
        )
        slayer_lines.append("Found a **Violent Essence**!")
    if heart > 0:
        await bot.database.slayer.modify_materials(
            user_id, server_id, "imbued_heart", heart
        )
        slayer_lines.append("Found an **Imbued Heart**!")

    # Taskmaster passive
    prog_gain = 1
    task_tiers = player.get_emblem_bonus("task_progress")
    if task_tiers > 0 and random.random() < (
        task_tiers * SLAYER_TASKMASTER_CHANCE_PER_TIER
    ):
        prog_gain = 2
        slayer_lines.append("⚡ **Taskmaster** granted double task progress!")

    # Yvenn sig: +T bonus progress per kill
    if reward_data.get("yvenn_slayer_bonus"):
        prog_gain += reward_data["yvenn_slayer_bonus"]

    # Progress tracker
    new_prog = s_profile["active_task_progress"] + prog_gain

    if new_prog >= s_profile["active_task_amount"]:
        burst_xp, burst_pts = (
            core.slayer.mechanics.SlayerMechanics.calculate_task_rewards(
                s_profile["active_task_amount"]
            )
        )
        await bot.database.slayer.add_rewards(
            user_id, server_id, xp=burst_xp, points=burst_pts
        )
        await bot.database.slayer.clear_task(user_id, server_id)
        slayer_lines.append(
            f"🏆 **Task Complete!** +{burst_xp} Slayer XP | +{burst_pts} Slayer Pts"
        )
    else:
        await bot.database.slayer.update_task_progress(user_id, server_id, 1)
        slayer_lines.append(
            f"Progress: {new_prog}/{s_profile['active_task_amount']} {monster.species}"
        )

    # Level-up check
    new_s_xp = (
        s_profile["xp"]
        + 100
        + (burst_xp if new_prog >= s_profile["active_task_amount"] else 0)
    )
    new_s_lvl = core.slayer.mechanics.SlayerMechanics.calculate_level_from_xp(new_s_xp)
    if new_s_lvl > s_profile["level"]:
        await bot.database.slayer.update_level(user_id, server_id, new_s_lvl)
        slayer_lines.append(f"🎉 **Slayer Level Up!** You are now Level {new_s_lvl}.")

    reward_data["msgs"].append("🩸 **Slayer Task**\n" + "\n".join(slayer_lines))


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


async def apply_victory_rewards(
    bot,
    user_id: str,
    server_id: str,
    player: Player,
    monster: Monster,
    message,
    combat_logger,
) -> dict:
    """
    Orchestrates all post-victory reward steps for normal (non-uber) combat.

    Handles: base XP/gold, special drops, item/essence drops, experience,
    companion taming, slayer task progress, and partner end rewards.

    Returns reward_data ready for embed construction.
    The caller is responsible for persisting player state (update_from_player_object,
    save_jewel_state) and clearing active status.
    """
    reward_data = calculate_rewards(player, monster)
    special_flags = check_special_drops(player, monster)
    reward_data["special"] = []

    await apply_boss_sigil_drops(bot, user_id, server_id, monster, reward_data)
    await apply_corrupted_monster_drops(bot, user_id, server_id, monster, reward_data)
    await apply_incubated_monster_drops(bot, user_id, monster, reward_data)
    await apply_special_flags(bot, user_id, server_id, special_flags, reward_data)

    await DropManager.process_drops(
        bot,
        user_id,
        server_id,
        player,
        monster.level,
        reward_data,
        monster=monster,
    )

    exp_changes = await ExperienceManager.add_experience(
        bot, user_id, player, reward_data["xp"]
    )
    reward_data["xp"] = exp_changes["xp_added"]
    reward_data["msgs"].extend(exp_changes["msgs"])

    if combat_logger:
        combat_logger.log_rewards(player, reward_data)

    await bot.database.users.modify_gold(user_id, reward_data["gold"])

    # Flora sig: materialise the converted gold into skilling resources.
    # gold deduction already happened in calculate_rewards; here we write the skill DB.
    flora_gold = reward_data.get("flora_skilling_gold", 0)
    if flora_gold > 0:
        from core.skills.mechanics import SkillMechanics as _SM

        _skill_type = random.choice(["mining", "woodcutting", "fishing"])
        _skill_row = await bot.database.skills.get_data(user_id, server_id, _skill_type)
        if _skill_row:
            _tool_tier = _skill_row[2]
            _units = max(1, flora_gold // 1000)
            _base = _SM.calculate_yield(_skill_type, _tool_tier)
            _resources = {k: v * _units for k, v in _base.items()}
            await bot.database.skills.update_batch(
                user_id, server_id, _skill_type, _resources
            )
            # NEET boot doubles skilling yield from Flora too
            if player.get_boot_corrupted_essence() == "neet":
                await bot.database.skills.update_batch(
                    user_id, server_id, _skill_type, _resources
                )

    await _apply_companion_drops(bot, user_id, player, monster, reward_data, message)
    await _apply_slayer_rewards(bot, user_id, server_id, player, monster, reward_data)

    if player.active_partner:
        partner = player.active_partner
        lvl_msgs = apply_partner_end_rewards(player, reward_data["xp"])
        await bot.database.partners.update_exp(
            user_id, partner.partner_id, partner.exp, partner.level
        )
        await bot.database.partners.increment_affinity(user_id, partner.partner_id)
        if lvl_msgs:
            reward_data["msgs"].append(
                f"🤝 **{partner.name}** reached level **{partner.level}**!"
            )

    return reward_data
