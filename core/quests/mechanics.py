"""
core/quests/mechanics.py — Quest Board game logic (pure + async with DB calls).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from core.emojis import (
    ANGEL_KEY,
    DRAGON_KEY,
    GOLD_COIN,
    SOUL_CORE,
    SPIRIT_STONE,
    VOID_FRAG,
)
from core.hall_of_firsts import triggers as hof_triggers
from core.quests.data import DAILY_QUESTS, HORIZON_PATHS, get_damage_goals

BOARD_COOLDOWN_HOURS = 20
CHECKIN_COOLDOWN_HOURS = 18

_SETTLEMENT_MATERIAL_MAP = {
    "magma_core": "Magma Core",
    "life_root": "Life Root",
    "spirit_shard": "Spirit Shard",
    "unidentified_blueprint": "Unidentified Blueprint",
    "diviners_rod": "Diviner's Rod",
}

# Gold rewards per completion
_GOLD_REWARDS = {1: 25_000, 3: 75_000}

# Monster names for glutton reward
_MONSTER_NAMES_FOR_PARTS = [
    "Ironhide Drake",
    "Stoneback Brute",
    "Voidtouched Stalker",
    "Ember Fiend",
    "Glacial Colossus",
]
_PART_SLOTS = ["head", "torso", "right_arm", "left_arm", "right_leg", "left_leg"]


def get_eligible_quests(level: int) -> list:
    """Returns daily quest templates the player can receive."""
    return [q for q in DAILY_QUESTS if level >= q["level_required"]]


_QUALITY_WEIGHTS = ["normal"] * 89 + ["gilded"] * 10 + ["marvelous"] * 1


def _roll_quality() -> str:
    return random.choice(_QUALITY_WEIGHTS)


def roll_board(level: int) -> list:
    """Roll 3 quest slots. Returns list of (quest_id, tier, quality)."""
    eligible = get_eligible_quests(level)
    if not eligible:
        eligible = DAILY_QUESTS[:3]

    num_slots = min(3, len(eligible))
    chosen = random.sample(eligible, num_slots)

    result = []
    for quest in chosen:
        tier = (
            3
            if quest.get("tier_3_only")
            else random.choices([1, 3], weights=[60, 40], k=1)[0]
        )
        result.append((quest["id"], tier, _roll_quality()))
    return result


def reroll_slot(level: int, exclude_quest_ids: list) -> tuple:
    """Roll a new quest for a slot. Returns (quest_id, tier, quality)."""
    eligible = get_eligible_quests(level)
    available = [q for q in eligible if q["id"] not in exclude_quest_ids]
    if not available:
        available = list(eligible)
    if not available:
        available = list(DAILY_QUESTS)
    quest = random.choice(available)
    tier = (
        3
        if quest.get("tier_3_only")
        else random.choices([1, 3], weights=[60, 40], k=1)[0]
    )
    return (quest["id"], tier, _roll_quality())


def get_board_cooldown_remaining(locked_at_iso: str) -> timedelta:
    """Returns timedelta until board refresh is available (0 if available)."""
    if not locked_at_iso:
        return timedelta(0)
    try:
        locked_at = datetime.fromisoformat(locked_at_iso)
        available_at = locked_at + timedelta(hours=BOARD_COOLDOWN_HOURS)
        remaining = available_at - datetime.now()
        if remaining.total_seconds() <= 0:
            return timedelta(0)
        return remaining
    except Exception:
        return timedelta(0)


def compute_goal_for_quest(quest_id: str, tier: int, level: int) -> int:
    """Compute the goal value for a quest+tier given player level."""
    quest_def = next((q for q in DAILY_QUESTS if q["id"] == quest_id), None)
    if quest_def is None:
        return 5
    if quest_def["goals"] == "banded":
        g1, g3 = get_damage_goals(level)
        return g1 if tier == 1 else g3
    return quest_def["goals"].get(tier, 5)


def format_goal_description(quest_id: str, tier: int, goal: int) -> str:
    """Return a human-readable objective string."""
    quest_def = next((q for q in DAILY_QUESTS if q["id"] == quest_id), None)
    if quest_def is None:
        return f"Complete {goal} times"
    event = quest_def.get("event_type", "")
    if event == "damage":
        return f"Deal {goal:,} total damage"
    elif event == "combat_win":
        return f"Win {goal} combat{'s' if goal > 1 else ''}"
    elif event.startswith("boss_kill:"):
        boss = event.split(":")[1].capitalize()
        return f"Defeat {boss} {goal} time{'s' if goal > 1 else ''}"
    elif event == "calcified_kill":
        return f"Defeat {goal} calcified monster{'s' if goal > 1 else ''}"
    elif event == "corrupted_kill":
        return f"Defeat {goal} corrupted monster{'s' if goal > 1 else ''}"
    elif event == "codex_complete":
        return f"Complete {goal} Codex run{'s' if goal > 1 else ''}"
    elif event == "ascent_floor":
        return f"Clear {goal} Ascent floor{'s' if goal > 1 else ''}"
    elif event == "apex_complete":
        return f"Complete {goal} Apex hunt{'s' if goal > 1 else ''}"
    elif event == "egg_release":
        return f"Release {goal} incubated egg{'s' if goal > 1 else ''}"
    elif event == "rune_refinement":
        return f"Use {goal} Refinement Rune{'s' if goal > 1 else ''}"
    elif event == "rune_shatter":
        return f"Use {goal} Shatter Rune{'s' if goal > 1 else ''}"
    elif event == "rune_potential":
        return f"Use {goal} Potential Rune{'s' if goal > 1 else ''}"
    elif event == "slayer_task_complete":
        return f"Complete {goal} Slayer task{'s' if goal > 1 else ''}"
    elif event == "settlement_event_complete":
        return f"Resolve {goal} Settlement crisis event{'s' if goal > 1 else ''}"
    elif event == "zeal_spent":
        return f"Spend {goal:,} Zeal on Development Turns"
    elif event == "partner_recruit":
        return f"Recruit {goal} time{'s' if goal > 1 else ''} at the Partner Guild"
    elif event == "casino_win":
        return f"Win {goal:,} gold from the casino"
    return f"Complete {goal} time{'s' if goal > 1 else ''}"


async def tick_quest_progress(
    bot, user_id: str, server_id: str, event_type: str, value: int = 1
) -> list:
    """
    Called from victory/completion hooks. Ticks matching contracts and horizon quest.
    Returns list of display strings for the victory embed Quests field.
    """
    if not server_id:
        return []

    msgs = []

    try:
        # Ensure meta exists
        await bot.database.quests.ensure_meta(user_id)
        meta = await bot.database.quests.get_meta(user_id)

        # Find contracts matching this event_type
        contracts = await bot.database.quests.get_contracts(user_id, server_id)
        for contract in contracts:
            if contract["turned_in"] or contract["completed"]:
                continue
            quest_def = next(
                (q for q in DAILY_QUESTS if q["id"] == contract["quest_id"]), None
            )
            if quest_def is None:
                continue
            if quest_def["event_type"] != event_type:
                continue

            # Some events use the raw value (damage amount, gold won, runes used, etc.)
            _VALUE_EVENTS = {
                "damage",
                "casino_win",
                "rune_refinement",
                "rune_shatter",
                "rune_potential",
                "zeal_spent",
                "partner_recruit",
            }
            tick_amount = value if event_type in _VALUE_EVENTS else 1
            updated = await bot.database.quests.tick_contract_progress(
                user_id, server_id, contract["quest_id"], tick_amount
            )
            for row in updated:
                if row["slot"] != contract["slot"]:
                    continue
                label = quest_def["label"]
                progress = min(row["progress"], row["goal"])
                if row["completed"]:
                    msgs.append(f"📋 {label}  ✅ Complete!")
                else:
                    msgs.append(f"📋 {label}  {progress}/{row['goal']}")

        # Horizon quest
        horizon = await bot.database.quests.get_horizon(user_id, server_id)
        if horizon and not horizon["turned_in"] and not horizon["completed"]:
            path_def = HORIZON_PATHS.get(horizon["path_id"])
            if path_def and path_def["event_type"] == event_type:
                # Horizon boost: count as 2
                tick_amount = 1
                boost_uses = meta.get("horizon_boost_uses", 0)
                if boost_uses > 0:
                    tick_amount = 2
                    await bot.database.quests.decrement_horizon_boost(user_id)

                updated_h = await bot.database.quests.tick_horizon_progress(
                    user_id, server_id, tick_amount
                )
                if updated_h:
                    path_name = path_def["name"]
                    progress = min(updated_h["progress"], updated_h["goal"])
                    if updated_h["completed"]:
                        msgs.append(f"🌀 {path_name}  ✅ Complete!")
                    else:
                        msgs.append(f"🌀 {path_name}  {progress}/{updated_h['goal']}")

    except Exception as e:
        print(f"[tick_quest_progress error]: {e}")

    return msgs


async def send_quest_complete_notice(interaction, msgs: list) -> None:
    """Ephemeral followup surfacing any freshly-completed contract/horizon lines.

    Call after tick_quest_progress() in views that have no natural embed field
    to append progress to (upgrade panels, gacha, etc). Safe no-op if msgs is
    empty, nothing completed, or the interaction response isn't usable.
    """
    if not interaction or not msgs:
        return
    completed = [m for m in msgs if "Complete!" in m]
    if not completed:
        return
    try:
        await interaction.followup.send(
            "📋 " + "  |  ".join(completed) + "\nTurn in your reward at `/quests`!",
            ephemeral=True,
        )
    except Exception:
        pass


async def grant_contract_reward(bot, user_id: str, server_id: str, slot: int) -> list:
    """Grant the reward for a completed contract. Returns display strings."""
    contracts = await bot.database.quests.get_contracts(user_id, server_id)
    contract = next((c for c in contracts if c["slot"] == slot), None)
    if not contract or not contract["completed"] or contract["turned_in"]:
        return []

    meta = await bot.database.quests.get_meta(user_id)
    tier = contract["tier"]
    quality = contract.get("quality", "normal")

    # Base tokens
    base_tokens = 1 if tier == 1 else 3

    # Veteran perk: +1 token on every turn-in
    veteran_bonus = 1 if meta.get("veteran_unlocked") else 0

    # Streak passive: +1 token on 3★ turn-in when streak >= 5
    streak_bonus = 1 if (tier == 3 and meta.get("streak", 0) >= 5) else 0

    total_tokens = base_tokens + veteran_bonus + streak_bonus

    # Quality modifiers (applied after other bonuses)
    quality_bonus_msg = None
    if quality == "marvelous":
        total_tokens *= 2
        quality_bonus_msg = "🌟 Marvelous — token reward doubled!"
    elif quality == "gilded":
        total_tokens += 1
        quality_bonus_msg = "✨ Gilded — +1 bonus token!"

    base_gold = _GOLD_REWARDS.get(tier, 25_000)

    # Enrichment perk: +50% gold on quest turn-in
    if meta.get("enrichment_unlocked"):
        gold = int(base_gold * 1.5)
    else:
        gold = base_gold

    await bot.database.quests.complete_contract(user_id, server_id, slot)
    total_completions = await bot.database.quests.increment_lifetime_completions(user_id)
    await hof_triggers.check_really_board(bot, user_id, total_completions)
    await bot.database.quests.add_tokens(user_id, total_tokens)
    await bot.database.users.modify_gold(user_id, gold)

    msgs = [f"🎫 +{total_tokens} Quest Token{'s' if total_tokens > 1 else ''}"]
    if veteran_bonus:
        msgs.append("  *(+1 Quest Veteran bonus)*")
    if streak_bonus:
        msgs.append("  *(+1 Streak bonus — tier 3)*")
    if quality_bonus_msg:
        msgs.append(f"  *({quality_bonus_msg})*")
    gold_note = " *(+50% Enrichment)*" if meta.get("enrichment_unlocked") else ""
    msgs.append(f"{GOLD_COIN} +{gold:,} Gold{gold_note}")

    # Prospector perk: grant a small gathering cache on every turn-in
    if meta.get("prospector_unlocked"):
        try:
            import random as _random

            skill_type = _random.choice(["mining", "woodcutting", "fishing"])
            skill_row = await bot.database.skills.get_data(
                user_id, server_id, skill_type
            )
            if skill_row:
                from core.skills.mechanics import SkillMechanics

                tool_tier = SkillMechanics.get_tool_tier(skill_type, skill_row)
                base = SkillMechanics.calculate_yield(skill_type, tool_tier)
                resources = {k: v * 3 for k, v in base.items()}
                await bot.database.skills.update_batch(
                    user_id, server_id, skill_type, resources
                )
                msgs.append(f"⛏️ Prospector's Cache: +{skill_type.title()} materials")
        except Exception as e:
            print(f"[Prospector perk error]: {e}")

    # Grant Zeal for quest completion (30 for 1★, 90 for 3★)
    try:
        from core.settlement.turn_engine import compute_zeal_gain

        _zeal_base = 30 if tier == 1 else 90
        await bot.database.settlement.reset_daily_zeal_if_needed(user_id, server_id)
        _zeal_data = await bot.database.settlement.get_zeal_data(user_id, server_id)
        _earned = _zeal_data.get("zeal_earned_today", 0)
        _actual = compute_zeal_gain(_zeal_base, _earned)
        if _actual > 0:
            await bot.database.settlement.add_zeal(user_id, server_id, _actual)
            msgs.append(f"🔥 +{_actual} Zeal")
    except Exception:
        pass

    return msgs


async def check_and_apply_streak(bot, user_id: str, server_id: str) -> list:
    """
    Called after every contract claim. If all contracts are now turned in and
    the board had no abandons and at least one was tier 3, increments streak
    and applies any milestone reward. Returns display strings (empty if no change).
    """
    meta = await bot.database.quests.get_meta(user_id)
    if meta.get("board_had_abandon"):
        return []

    contracts = await bot.database.quests.get_contracts(user_id, server_id)
    active = [c for c in contracts if not c["turned_in"]]
    if active:
        return []  # board not fully cleared yet

    had_tier3 = any(c["tier"] == 3 for c in contracts)
    if not had_tier3:
        return []

    new_streak = await bot.database.quests.increment_streak(user_id)
    msgs = [f"🔥 Streak: **{new_streak}**"]

    if new_streak % 5 == 0:
        milestone_tokens = new_streak
        await bot.database.quests.add_tokens(user_id, milestone_tokens)
        msgs.append(
            f"🏆 Streak milestone! **+{milestone_tokens} Quest Tokens** (streak {new_streak})"
        )
        if new_streak == 5:
            msgs.append("⚡ Streak 5 unlocked — +1 token on all future 3★ turn-ins!")

    return msgs


async def grant_horizon_reward(bot, user_id: str, server_id: str, player) -> list:
    """Grant the reward for a completed horizon quest. Returns display strings."""
    horizon = await bot.database.quests.get_horizon(user_id, server_id)
    if not horizon or not horizon["completed"] or horizon["turned_in"]:
        return []

    path_id = horizon["path_id"]
    path_def = HORIZON_PATHS.get(path_id)
    if not path_def:
        return []

    meta = await bot.database.quests.get_meta(user_id)
    token_reward = path_def["token_reward"]
    bonus_tokens = 1 if meta.get("veteran_unlocked") else 0
    total_tokens = token_reward + bonus_tokens

    await bot.database.quests.complete_horizon(user_id, server_id)
    total_completions = await bot.database.quests.increment_lifetime_completions(user_id)
    await hof_triggers.check_really_board(bot, user_id, total_completions)
    await bot.database.quests.add_tokens(user_id, total_tokens)

    msgs = [f"🎫 +{total_tokens} Quest Token{'s' if total_tokens > 1 else ''}"]
    if bonus_tokens:
        msgs.append("  *(+1 Quest Veteran bonus)*")

    # Path-specific special reward
    try:
        if path_id == "settlers_oath":
            mat_key = random.choice(list(_SETTLEMENT_MATERIAL_MAP.keys()))
            mat_label = _SETTLEMENT_MATERIAL_MAP[mat_key]
            await bot.database.settlement_materials.modify(user_id, mat_key, 1)
            msgs.append(f"🏗️ +1 {mat_label}")

        elif path_id == "celestial_calling":
            key = random.choice(["dragon_key", "angel_key"])
            await bot.database.users.modify_currency(user_id, key, 1)
            label = "Draconic Key" if key == "dragon_key" else "Angelic Key"
            key_emoji = DRAGON_KEY if key == "dragon_key" else ANGEL_KEY
            msgs.append(f"{key_emoji} +1 {label}")

        elif path_id == "infernal_pact":
            await bot.database.users.modify_currency(user_id, "soul_cores", 1)
            msgs.append(f"{SOUL_CORE} +1 Soul Core")

        elif path_id == "twin_accord":
            await bot.database.users.modify_currency(user_id, "balance_fragment", 1)
            msgs.append("⚖️ +1 Fragment of Balance")

        elif path_id == "void_threshold":
            await bot.database.users.modify_currency(user_id, "void_frags", 1)
            msgs.append(f"{VOID_FRAG} +1 Void Fragment")

        elif path_id == "alchemist":
            await bot.database.users.modify_currency(user_id, "spirit_stones", 1)
            msgs.append(f"{SPIRIT_STONE} +1 Spirit Stone")

        elif path_id == "glutton":
            # Find highest consumed part level
            equipped_parts = await bot.database.monster_parts.get_equipped_parts(
                user_id
            )
            max_hp = 0
            if equipped_parts:
                for slot_data in equipped_parts.values():
                    hp_val = (
                        slot_data.get("hp", 30) if isinstance(slot_data, dict) else 30
                    )
                    if hp_val > max_hp:
                        max_hp = hp_val
            reward_hp = max_hp + 10 if max_hp > 0 else 30
            reward_ilvl = max(1, reward_hp // 3)
            slot = random.choice(_PART_SLOTS)
            monster_name = random.choice(_MONSTER_NAMES_FOR_PARTS)
            await bot.database.monster_parts.add_part(
                user_id, slot, monster_name, reward_ilvl, reward_hp
            )
            msgs.append(
                f"🦴 +1 Monster Part ({monster_name} — {slot.replace('_', ' ').title()})"
            )

        elif path_id == "slayer":
            await bot.database.slayer.modify_materials(
                user_id, server_id, "violent_essence", 3
            )
            msgs.append("⚔️ +3 Violent Essence")

        elif path_id == "antiquarian":
            await bot.database.users.modify_currency(user_id, "codex_fragments", 50)
            msgs.append("📚 +50 Codex Fragments")

        elif path_id == "blood_compact":
            await bot.database.hematurgy.modify_blood(user_id, "primordial", 250)
            msgs.append("🩸 +250 Primordial Blood")

        elif path_id == "elemental":
            # Grant gathering resources
            for skill_type in ("mining", "woodcutting", "fishing"):
                skill_row = await bot.database.skills.get_data(
                    user_id, server_id, skill_type
                )
                if skill_row:
                    from core.skills.mechanics import SkillMechanics

                    tool_tier = SkillMechanics.get_tool_tier(skill_type, skill_row)
                    base = SkillMechanics.calculate_yield(skill_type, tool_tier)
                    # Multiply by 10 for a decent reward
                    resources = {k: v * 10 for k, v in base.items()}
                    await bot.database.skills.update_batch(
                        user_id, server_id, skill_type, resources
                    )
            msgs.append("⛏️ +Gathering Resources (all skills)")

        elif path_id == "apex":
            meta_keys = [
                "sharpened_fang",
                "engorged_heart",
                "condensed_blood",
                "primal_essence",
                "soul_vessel",
            ]
            key = random.choice(meta_keys)
            await bot.database.apex.modify_meta_shard(user_id, server_id, key, 1)
            msgs.append("💠 +1 Random Meta Shard")

        elif path_id == "ascent":
            rune = random.choice(
                ["refinement_runes", "potential_runes", "shatter_runes"]
            )
            await bot.database.users.modify_currency(user_id, rune, 1)
            msgs.append(f"🔮 +1 {rune.replace('_', ' ').title()}")

        elif path_id == "sovereign":
            sigil_funcs = {
                "celestial_sigils": bot.database.uber.increment_sigils,
                "infernal_sigils": bot.database.uber.increment_infernal_sigils,
                "void_sigils": bot.database.uber.increment_void_shards,
                "gemini_sigils": bot.database.uber.increment_gemini_sigils,
            }
            chosen_key = random.choice(list(sigil_funcs.keys()))
            fn = sigil_funcs[chosen_key]
            await fn(user_id, server_id, 2)
            label = chosen_key.replace("_", " ").title()
            msgs.append(f"✨ +2 {label}")

    except Exception as e:
        print(f"[grant_horizon_reward special reward error for {path_id}]: {e}")

    return msgs
