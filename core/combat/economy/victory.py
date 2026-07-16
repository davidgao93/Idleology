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
from core.emojis import PRIMAL_ESSENCE, SLAYER_EMBLEM_ICON, ZEAL
from core.hall_of_firsts import triggers as hof_triggers
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
    # Companions only become tameable once the player reaches level 40.
    # Before that, monsters are too weak to bond with an adventurer.
    if player.level < 40:
        return

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

            if message is not None:
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
# Sanctum conversion
# ---------------------------------------------------------------------------


async def _apply_sanctum_conversion(
    bot,
    user_id: str,
    server_id: str,
    reward_data: dict,
) -> None:
    """1% per 10 workers chance to convert the killed monster into a follower."""
    try:
        sanctum = await bot.database.settlement.get_building_by_type(
            user_id, server_id, "sanctum"
        )
        if not sanctum or sanctum.is_disabled or sanctum.workers_assigned <= 0:
            return

        chance = sanctum.workers_assigned / 1000

        # Sacred Ground plot: +20% to conversion rate
        if sanctum.plot_index is not None:
            plot = await bot.database.plots.get_plot(
                user_id, server_id, sanctum.plot_index
            )
            if plot and plot["bonus_type"] == "sacred_ground":
                chance *= 1.20

        chance = min(0.95, chance)
        if random.random() >= chance:
            return

        user_row = await bot.database.users.get(user_id, server_id)
        ideology_name = (user_row["ideology"] or "") if user_row else ""
        if not ideology_name:
            return

        await bot.database.social.increment_followers(
            ideology_name, 1, server_id, user_id
        )
        follower_count = await bot.database.social.get_follower_count(ideology_name)
        await hof_triggers.check_cult_leader(bot, user_id, follower_count)
        reward_data["msgs"].append(
            "🕍 Your Sanctum converts the fallen enemy into a devoted follower!"
        )
    except Exception:
        pass  # Non-critical; never break combat


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
    from core.slayer.mechanics import (
        BOSS_TASK_COMPLETION_XP,
        BOSS_TASK_PREFIX,
        BOSS_TASK_XP_PER_KILL,
    )

    s_profile = await bot.database.slayer.get_profile(user_id, server_id)
    task_species = s_profile["active_task_species"]

    # ── Boss task branch ────────────────────────────────────────────────────
    if monster.is_boss and task_species and task_species.startswith(BOSS_TASK_PREFIX):
        boss_key = task_species[len(BOSS_TASK_PREFIX) :]
        # Match by checking if the boss key appears anywhere in the monster name
        if boss_key.lower() not in monster.name.lower():
            return  # Wrong boss

        slayer_lines = []
        per_kill_xp = BOSS_TASK_XP_PER_KILL
        await bot.database.slayer.add_rewards(
            user_id, server_id, xp=per_kill_xp, points=0
        )
        await bot.database.slayer.modify_materials(
            user_id, server_id, "violent_essence", 1
        )
        slayer_lines.append(
            f"💀 **Boss Kill!** +{per_kill_xp:,} Slayer XP | {PRIMAL_ESSENCE} +1 Violent Essence"
        )

        new_prog = s_profile["active_task_progress"] + 1
        if new_prog >= s_profile["active_task_amount"]:
            await bot.database.slayer.add_rewards(
                user_id,
                server_id,
                xp=BOSS_TASK_COMPLETION_XP,
                points=s_profile["active_task_amount"],
            )
            await bot.database.slayer.clear_task(user_id, server_id)
            try:
                from core.quests.mechanics import tick_quest_progress

                slayer_lines.extend(
                    await tick_quest_progress(
                        bot, user_id, server_id, "slayer_task_complete"
                    )
                )
            except Exception as _qe:
                print(f"[Quest tick error in slayer boss task]: {_qe}")
            slayer_lines.append(
                f"🏆 **Boss Task Complete!** +{BOSS_TASK_COMPLETION_XP:,} Slayer XP"
            )
        else:
            await bot.database.slayer.update_task_progress(user_id, server_id, 1)
            slayer_lines.append(
                f"Progress: {new_prog}/{s_profile['active_task_amount']} {boss_key.capitalize()}"
            )

        # Slayer level-up check
        total_xp_gained = per_kill_xp + (
            BOSS_TASK_COMPLETION_XP
            if new_prog >= s_profile["active_task_amount"]
            else 0
        )
        new_s_xp = s_profile["xp"] + total_xp_gained
        new_s_lvl = core.slayer.mechanics.SlayerMechanics.calculate_level_from_xp(
            new_s_xp
        )
        if new_s_lvl > s_profile["level"]:
            await bot.database.slayer.update_level(user_id, server_id, new_s_lvl)
            slayer_lines.append(
                f"🎉 **Slayer Level Up!** You are now Level {new_s_lvl}."
            )

        reward_data["msgs"].append(
            f"{SLAYER_EMBLEM_ICON} **Slayer Task**\n" + "\n".join(slayer_lines)
        )
        return

    if monster.is_boss:
        return  # No boss task active — skip slayer processing

    if task_species != monster.species:
        return

    slayer_lines = []

    # Base Slayer XP + drops
    _tree_nodes = getattr(player, "slayer_tree_nodes", {})
    per_kill_base_xp = 500 + (_tree_nodes.get("tm_4") and 250 or 0)
    await bot.database.slayer.add_rewards(
        user_id, server_id, xp=per_kill_base_xp, points=0
    )
    slayer_lines.append(f"+{per_kill_base_xp} Slayer XP")
    if _tree_nodes.get("tm_4"):
        slayer_lines[-1] += " *(+250 Relentless)*"

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

    # Zenith monster: guaranteed Imbued Heart drop (before task completion check)
    if getattr(monster, "is_zenith", False):
        await bot.database.slayer.modify_materials(
            user_id, server_id, "imbued_heart", 1
        )
        slayer_lines.append("👑 **Zenith Monster!** Guaranteed ❤️ Imbued Heart!")

    if new_prog >= s_profile["active_task_amount"]:
        task_size = s_profile["active_task_amount"]
        burst_xp, burst_pts = (
            core.slayer.mechanics.SlayerMechanics.calculate_task_rewards(task_size)
        )
        # tm_3: 50% chance to double the XP burst
        if _tree_nodes.get("tm_3") and random.random() < 0.50:
            burst_xp *= 2
            slayer_lines.append("🔥 **Executioner's High!** XP burst doubled!")
        # pu_2: +25% bonus Slayer Points
        if _tree_nodes.get("pu_2"):
            import math

            burst_pts = math.floor(burst_pts * 1.25)
        await bot.database.slayer.add_rewards(
            user_id, server_id, xp=burst_xp, points=burst_pts
        )
        task_ess = max(1, task_size // 5)
        await bot.database.slayer.modify_materials(
            user_id, server_id, "violent_essence", task_ess
        )
        await bot.database.slayer.clear_task(user_id, server_id)
        try:
            from core.quests.mechanics import tick_quest_progress

            slayer_lines.extend(
                await tick_quest_progress(
                    bot, user_id, server_id, "slayer_task_complete"
                )
            )
        except Exception as _qe:
            print(f"[Quest tick error in slayer regular task]: {_qe}")
        slayer_lines.append(
            f"🏆 **Task Complete!** +{burst_xp} Slayer XP | +{burst_pts} Slayer Pts | {PRIMAL_ESSENCE} +{task_ess} Violent Essence"
        )
    else:
        await bot.database.slayer.update_task_progress(user_id, server_id, 1)
        slayer_lines.append(
            f"Progress: {new_prog}/{s_profile['active_task_amount']} {monster.species}"
        )

    # Level-up check
    _task_xp = burst_xp if new_prog >= s_profile["active_task_amount"] else 0
    new_s_xp = s_profile["xp"] + per_kill_base_xp + _task_xp
    new_s_lvl = core.slayer.mechanics.SlayerMechanics.calculate_level_from_xp(new_s_xp)
    if new_s_lvl > s_profile["level"]:
        await bot.database.slayer.update_level(user_id, server_id, new_s_lvl)
        slayer_lines.append(f"🎉 **Slayer Level Up!** You are now Level {new_s_lvl}.")

    reward_data["msgs"].append(
        f"{SLAYER_EMBLEM_ICON} **Slayer Task**\n" + "\n".join(slayer_lines)
    )


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
    reward_data = calculate_rewards(player, monster, apply_modifier_xp_bonus=True)
    special_flags = check_special_drops(player, monster)
    reward_data["special"] = []
    # Total damage dealt to the monster (used by damage quest tracking)
    reward_data["total_damage"] = monster.max_hp

    await apply_boss_sigil_drops(
        bot, user_id, server_id, monster, reward_data, player=player
    )
    await apply_corrupted_monster_drops(
        bot, user_id, server_id, monster, reward_data, player=player
    )
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

    # Consolation cosmic dust
    # Biased toward 5 at higher monster levels.
    if (
        not reward_data.get("items")
        and not reward_data.get("special")
        and not reward_data.get("essences")
        and not reward_data.get("body_part")
        and not reward_data.get("egg")
        and not reward_data.get("curios")
    ):
        t = min(monster.level, 100) / 100
        dust = random.choices(
            [1, 2, 3, 4, 5],
            weights=[
                max(1, round(5 - 4 * t)),
                max(1, round(4 - 2 * t)),
                3,
                round(2 + 2 * t),
                round(1 + 4 * t),
            ],
            k=1,
        )[0]
        await bot.database.alchemy.modify_cosmic_dust(user_id, dust)
        reward_data["consolation_dust"] = dust

    exp_changes = await ExperienceManager.add_experience(
        bot, user_id, player, reward_data["xp"], server_id=server_id
    )
    reward_data["xp"] = exp_changes["xp_added"]
    reward_data["msgs"].extend(exp_changes["msgs"])

    if combat_logger:
        combat_logger.log_rewards(player, reward_data, monster)

    await bot.database.users.modify_gold(user_id, reward_data["gold"])

    # Flora sig: materialise the converted gold into skilling resources.
    # gold deduction already happened in calculate_rewards; here we write the skill DB.
    flora_gold = reward_data.get("flora_skilling_gold", 0)
    if flora_gold > 0:
        from core.skills.mechanics import SkillMechanics as _SM

        _skill_type = random.choice(["mining", "woodcutting", "fishing"])
        _skill_row = await bot.database.skills.get_data(user_id, server_id, _skill_type)
        if _skill_row:
            _tool_tier = _SM.get_tool_tier(_skill_type, _skill_row)
            _units = max(1, flora_gold // 1000)
            _base = _SM.calculate_yield(_skill_type, _tool_tier)
            _resources = {k: v * _units for k, v in _base.items()}
            await bot.database.skills.update_batch(
                user_id, server_id, _skill_type, _resources
            )
            # NEET boot doubles Flora skilling yield by granting the same
            # batch a second time.  update_batch is additive, so two calls
            # with the same dict produce exactly 2× resources — this is the
            # intended doubling effect, not an accidental duplicate.
            if player.get_boot_corrupted_essence() == "neet":
                await bot.database.skills.update_batch(
                    user_id, server_id, _skill_type, _resources
                )

    await _apply_companion_drops(bot, user_id, player, monster, reward_data, message)
    await _apply_slayer_rewards(bot, user_id, server_id, player, monster, reward_data)
    await _apply_sanctum_conversion(bot, user_id, server_id, reward_data)

    if player.active_partner:
        partner = player.active_partner
        lvl_msgs = apply_partner_end_rewards(player, reward_data["xp"])
        await bot.database.partners.update_exp(
            user_id, partner.partner_id, partner.exp, partner.level
        )
        await hof_triggers.check_friends_with_benefits(bot, user_id, partner.level)
        await bot.database.partners.increment_affinity(user_id, partner.partner_id)
        if lvl_msgs:
            reward_data["msgs"].append(
                f"🤝 **{partner.name}** reached level **{partner.level}**!"
            )

    # Quest progress tracking
    try:
        from core.quests.mechanics import tick_quest_progress

        quest_msgs = []

        # Combat win (all victories)
        quest_msgs += await tick_quest_progress(bot, user_id, server_id, "combat_win")

        # Damage dealt
        total_dmg = reward_data.get("total_damage", 0)
        if total_dmg > 0:
            quest_msgs += await tick_quest_progress(
                bot, user_id, server_id, "damage", total_dmg
            )

        # Named boss kills (normal multi-phase encounters; uber bosses never reach this path)
        if monster.is_boss:
            boss_name = monster.name.lower()
            if "aphrodite" in boss_name:
                quest_msgs += await tick_quest_progress(
                    bot, user_id, server_id, "boss_kill:aphrodite"
                )
            elif "lucifer" in boss_name:
                quest_msgs += await tick_quest_progress(
                    bot, user_id, server_id, "boss_kill:lucifer"
                )
            elif (
                "castor" in boss_name or "pollux" in boss_name or "gemini" in boss_name
            ):
                quest_msgs += await tick_quest_progress(
                    bot, user_id, server_id, "boss_kill:gemini"
                )
            elif "neet" in boss_name:
                quest_msgs += await tick_quest_progress(
                    bot, user_id, server_id, "boss_kill:neet"
                )
            elif "evelynn" in boss_name:
                quest_msgs += await tick_quest_progress(
                    bot, user_id, server_id, "boss_kill:evelynn"
                )

        # Calcified monsters
        if getattr(monster, "is_essence", False):
            quest_msgs += await tick_quest_progress(
                bot, user_id, server_id, "calcified_kill"
            )

        # Corrupted monsters
        if getattr(monster, "is_corrupted", False):
            quest_msgs += await tick_quest_progress(
                bot, user_id, server_id, "corrupted_kill"
            )

        # Incubated monsters (egg_release hook)
        if getattr(monster, "is_incubated", False):
            quest_msgs += await tick_quest_progress(
                bot, user_id, server_id, "egg_release"
            )

        if quest_msgs:
            reward_data["msgs"].extend(quest_msgs)
    except Exception as e:
        print(f"[Quest tick error in victory]: {e}")

    # Settlement Zeal (10 per combat win, subject to daily cap; requires level 10)
    try:
        if player.level < 10:
            return reward_data
        from core.settlement.constants import (
            ZEAL_DAILY_HARD_CAP,
            ZEAL_DAILY_SOFT_CAP,
            ZEAL_PER_COMBAT,
        )
        from core.settlement.turn_engine import compute_zeal_gain

        await bot.database.settlement.reset_daily_zeal_if_needed(user_id, server_id)
        zeal_data = await bot.database.settlement.get_zeal_data(user_id, server_id)
        earned_today = zeal_data.get("zeal_earned_today", 0)
        actual_zeal = compute_zeal_gain(ZEAL_PER_COMBAT, earned_today)
        if actual_zeal > 0:
            await bot.database.settlement.add_zeal(user_id, server_id, actual_zeal)
            if earned_today >= ZEAL_DAILY_HARD_CAP:
                zeal_note = f"{ZEAL} Settlement Zeal: capped for today"
            elif earned_today >= ZEAL_DAILY_SOFT_CAP:
                zeal_note = (
                    f"{ZEAL} +{actual_zeal} Settlement Zeal *(soft cap reached)*"
                )
            else:
                zeal_note = f"{ZEAL} +{actual_zeal} Settlement Zeal"
            reward_data["msgs"].append(zeal_note)
    except Exception:
        pass  # Zeal is non-critical; never break combat on its failure

    return reward_data
