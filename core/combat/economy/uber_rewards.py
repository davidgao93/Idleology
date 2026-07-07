"""
core/combat/economy/uber_rewards.py — Uber boss end-state reward logic.

Extracted from core/combat/views.py to separate reward orchestration from
the combat view loop.  All public functions accept ``view`` (a duck-typed
CombatView) rather than importing CombatView directly, which would create a
circular import (views_uber → views → economy → views).
"""

from __future__ import annotations

import random

from core.combat import jewel_engine as _je
from core.combat import ui as combat_ui
from core.combat.economy.config import (
    EVELYNN_MIRAGE_RUNE_IMPERFECT_CHANCE,
    EVELYNN_MIRAGE_RUNE_PERFECTED_CHANCE,
    UBER_BLUEPRINT_CHANCE,
    UBER_ENGRAM_CHANCE,
    XP_LOSS_ON_DEFEAT,
)
from core.combat.economy.experience import ExperienceManager
from core.combat.economy.rewards import calculate_rewards
from core.combat.turns.boundary import fire_on_victory_effects
from core.combat.views.views_lucifer import InfernalContractView
from core.images import (
    VICTORY_CELESTIAL,
    VICTORY_EVELYNN,
    VICTORY_GEMINI,
    VICTORY_INFERNAL,
    VICTORY_NEET,
)

# ---------------------------------------------------------------------------
# Uber boss configuration table
# Each entry drives the generic engram / blueprint / stone reward logic.
# ---------------------------------------------------------------------------
UBER_CONFIGS: dict[str, dict] = {
    "Aphrodite": {
        "engram_fn": "increment_engrams",
        "engram_display": "Celestial Engram",
        "engram_msg": "🌌 **A Celestial Engram materializes from Aphrodite's shattered form...**",
        "blueprint_key": "celestial_blueprint_unlocked",
        "blueprint_fn": "set_blueprint_unlocked",
        "blueprint_display": "Celestial Statue Blueprint",
        "blueprint_msg": "📜 **You found the Celestial Statue Blueprint!**",
        "stone_currency": "celestial_stone",
        "stone_display": "Celestial Stone",
        "stone_msg": "🪨 **You found a Celestial Stone!**",
        "victory_image": VICTORY_CELESTIAL,
        "image_fn": "set_image",
        "embed_title": "🌌 Apex Shattered!",
    },
    "Lucifer": {
        "engram_fn": "increment_infernal_engrams",
        "engram_display": "Infernal Engram",
        "engram_msg": "🔥 **An Infernal Engram crystallises from Lucifer's shattered crown...**",
        "blueprint_key": "infernal_blueprint_unlocked",
        "blueprint_fn": "set_infernal_blueprint_unlocked",
        "blueprint_display": "Infernal Statue Blueprint",
        "blueprint_msg": "📜 **You found the Infernal Statue Blueprint!**",
        "stone_currency": "infernal_cinder",
        "stone_display": "Infernal Cinder",
        "stone_msg": "🔥 **The forge roars. You extract an Infernal Cinder.**",
        "victory_image": VICTORY_INFERNAL,
        "image_fn": "set_image",
        "embed_title": "🔥 Infernal Sovereign Defeated!",
    },
    "NEET": {
        "engram_fn": "increment_void_engrams",
        "engram_display": "Void Engram",
        "engram_msg": "⬛ **A Void Engram crystallises from the collapsing rift...**",
        "blueprint_key": "void_blueprint_unlocked",
        "blueprint_fn": "set_void_blueprint_unlocked",
        "blueprint_display": "Void Statue Blueprint",
        "blueprint_msg": "📜 **You found the Void Statue Blueprint!**",
        "stone_currency": "void_crystal",
        "stone_display": "Void Crystal",
        "stone_msg": "🔮 **The void yields a Void Crystal.**",
        "victory_image": VICTORY_NEET,
        "image_fn": "set_thumbnail",
        "embed_title": "⬛ Void Sovereign Defeated!",
    },
    "Castor": {  # Gemini twins — matched by "Castor" substring
        "engram_fn": "increment_gemini_engrams",
        "engram_display": "Gemini Engram",
        "engram_msg": "♊ **A Gemini Engram crystallises from the twins' shattered bond...**",
        "blueprint_key": "gemini_blueprint_unlocked",
        "blueprint_fn": "set_gemini_blueprint_unlocked",
        "blueprint_display": "Twin Statue Blueprint",
        "blueprint_msg": "📜 **You found the Twin Statue Blueprint!**",
        "stone_currency": "bound_crystal",
        "stone_display": "Bound Crystal",
        "stone_msg": "💎 **The twins' bond yields a Bound Crystal.**",
        "victory_image": VICTORY_GEMINI,
        "image_fn": "set_image",
        "embed_title": "♊ Bound Sovereigns Defeated!",
    },
    "Evelynn": {
        "engram_fn": "increment_corruption_engrams",
        "engram_display": "Corruption Engram",
        "engram_msg": "☠️ **A Corruption Engram crystallises from the primordial rot...**",
        "blueprint_key": "corruption_blueprint_unlocked",
        "blueprint_fn": "set_corruption_blueprint_unlocked",
        "blueprint_display": "Corrupted Statue Blueprint",
        "blueprint_msg": "📜 **You found the Corrupted Statue Blueprint!**",
        "stone_currency": "corrupted_crystal",
        "stone_display": "Corrupted Crystal",
        "stone_msg": "☠️ **The corruption yields a Corrupted Crystal.**",
        "victory_image": VICTORY_EVELYNN,
        "image_fn": "set_image",
        "embed_title": "☠️ Origin of Corruption Shattered!",
    },
}


# ---------------------------------------------------------------------------
# Shared math helpers
# ---------------------------------------------------------------------------


def calc_uber_curios(dmg_frac: float) -> int:
    if dmg_frac >= 1.0:
        return 3
    if dmg_frac >= 0.66:
        return 2
    if dmg_frac >= 0.33:
        return 1
    return 0


def uber_dmg_frac(monster) -> float:
    return max(
        0.0,
        min(1.0, (monster.max_hp - max(0, monster.hp)) / monster.max_hp),
    )


# ---------------------------------------------------------------------------
# Shared async helpers (take view via duck typing)
# ---------------------------------------------------------------------------


async def _uber_defeat(
    view, message, dmg_frac: float = 0.0, curios_gained: int = 0
) -> None:
    base_loss = int(view.player.exp * XP_LOSS_ON_DEFEAT)
    xp_loss = await ExperienceManager.remove_experience(
        view.bot, view.user_id, view.player, base_loss
    )
    view.player.current_hp = 1
    embed = combat_ui.create_defeat_embed(
        view.player,
        view.monster,
        xp_loss,
        curios_gained=curios_gained,
        dmg_frac=dmg_frac,
        killing_blow=view.killing_blow,
    )
    view.post_combat_view.set_content(embed)
    await message.edit(view=view.post_combat_view)
    view.post_combat_view.message = message
    view.bot.state_manager.clear_active(view.user_id)
    await view.bot.database.users.update_from_player_object(view.player)
    await _je.save_jewel_state(view.bot, view.user_id, view.player)
    view.stop()


async def _uber_finalize_rewards(view, reward_data: dict) -> None:
    """Apply XP, gold, soulreap heal, and persist player. Mutates reward_data xp field."""
    exp_changes = await ExperienceManager.add_experience(
        view.bot,
        view.user_id,
        view.player,
        reward_data["xp"],
        server_id=view.server_id,
    )
    reward_data["xp"] = exp_changes["xp_added"]
    reward_data["msgs"].extend(exp_changes["msgs"])
    await view.bot.database.users.modify_gold(view.user_id, reward_data["gold"])
    soulreap_msgs = fire_on_victory_effects(view.player)
    reward_data["msgs"].extend(soulreap_msgs)
    await view.bot.database.users.update_from_player_object(view.player)
    await _je.save_jewel_state(view.bot, view.user_id, view.player)


async def _uber_setup(view, message) -> dict | None:
    """
    Shared first step for all uber handlers.

    Rolls damage fraction → curio count → grants curios.
    Returns None after triggering defeat flow if the player is dead.
    On victory, returns a fresh reward_data dict with xp/gold doubled and
    curios pre-populated — ready for handler-specific drops.
    """
    dmg_frac = uber_dmg_frac(view.monster)
    curios = calc_uber_curios(dmg_frac)
    await view.bot.database.users.modify_currency(view.user_id, "curios", curios)

    if view.player.current_hp <= 0:
        await _uber_defeat(view, message, dmg_frac=dmg_frac, curios_gained=curios)
        return None

    reward_data = calculate_rewards(view.player, view.monster)
    reward_data["xp"] *= 2
    reward_data["gold"] *= 2
    reward_data["curios"] = curios
    reward_data["special"] = []

    # Quest progress — must run here because uber encounters skip apply_victory_rewards.
    # Note: boss_kill:* ticks are intentionally NOT here — uber kills track uber_complete only.
    # The slay_* quests are for the normal multi-phase boss encounters.
    try:
        from core.quests.mechanics import tick_quest_progress

        quest_msgs = []

        quest_msgs += await tick_quest_progress(
            view.bot, view.user_id, view.server_id, "uber_complete"
        )
        quest_msgs += await tick_quest_progress(
            view.bot, view.user_id, view.server_id, "combat_win"
        )
        total_dmg = view.monster.max_hp
        if total_dmg > 0:
            quest_msgs += await tick_quest_progress(
                view.bot, view.user_id, view.server_id, "damage", total_dmg
            )

        if quest_msgs:
            reward_data["msgs"].extend(quest_msgs)
    except Exception as e:
        print(f"[Quest tick error in uber_setup]: {e}")

    return reward_data


async def _handle_engram_and_blueprint(view, reward_data: dict, cfg: dict) -> None:
    """
    Rolls the standard 10% engram and 10% blueprint/stone drops for an uber
    boss, driven by a config entry from UBER_CONFIGS.  Mutates reward_data.
    """
    if random.random() < UBER_ENGRAM_CHANCE:
        engram_fn = getattr(view.bot.database.uber, cfg["engram_fn"])
        await engram_fn(view.user_id, view.server_id, 1)
        reward_data["special"].append(cfg["engram_display"])
        reward_data["msgs"].append(cfg["engram_msg"])

    if random.random() < UBER_BLUEPRINT_CHANCE:
        u_prog = await view.bot.database.uber.get_uber_progress(
            view.user_id, view.server_id
        )
        if not u_prog.get(cfg["blueprint_key"]):
            blueprint_fn = getattr(view.bot.database.uber, cfg["blueprint_fn"])
            await blueprint_fn(view.user_id, view.server_id, True)
            reward_data["special"].append(cfg["blueprint_display"])
            reward_data["msgs"].append(cfg["blueprint_msg"])
        else:
            await view.bot.database.settlement_materials.modify(
                view.user_id, cfg["stone_currency"], 1
            )
            reward_data["special"].append(cfg["stone_display"])
            reward_data["msgs"].append(cfg["stone_msg"])


async def _uber_complete_standard(view, message, cfg: dict, reward_data: dict) -> None:
    """
    Finalizes rewards, builds and edits the victory embed, clears state, and
    stops the view.  Used by all standard uber handlers (not Lucifer).
    """
    await _uber_finalize_rewards(view, reward_data)
    embed = combat_ui.create_victory_embed(view.player, view.monster, reward_data)
    embed.title = cfg["embed_title"]
    getattr(embed, cfg["image_fn"])(url=cfg["victory_image"])
    view.post_combat_view.set_content(embed)
    await message.edit(view=view.post_combat_view)
    view.post_combat_view.message = message
    view.bot.state_manager.clear_active(view.user_id)
    view.stop()


# ---------------------------------------------------------------------------
# Per-boss handlers
# ---------------------------------------------------------------------------


async def _handle_aphrodite(view, message) -> None:
    reward_data = await _uber_setup(view, message)
    if reward_data is None:
        return
    cfg = UBER_CONFIGS["Aphrodite"]
    await _handle_engram_and_blueprint(view, reward_data, cfg)
    await _uber_complete_standard(view, message, cfg, reward_data)


async def _handle_lucifer(view, message) -> None:
    reward_data = await _uber_setup(view, message)
    if reward_data is None:
        return
    cfg = UBER_CONFIGS["Lucifer"]
    await _handle_engram_and_blueprint(view, reward_data, cfg)
    await _uber_finalize_rewards(view, reward_data)

    embed = combat_ui.create_victory_embed(view.player, view.monster, reward_data)
    embed.title = cfg["embed_title"]
    embed.set_image(url=cfg["victory_image"])
    contract_view = InfernalContractView(
        view.bot, view.user_id, view.player, view.server_id, message
    )
    embed.add_field(
        name="🩸 An Infernal Contract materialises...",
        value=contract_view.contract_summary(),
        inline=False,
    )
    contract_view.set_content(embed)
    await message.edit(view=contract_view)
    contract_view.message = message
    view.stop()


async def _handle_neet(view, message) -> None:
    reward_data = await _uber_setup(view, message)
    if reward_data is None:
        return
    cfg = UBER_CONFIGS["NEET"]
    await _handle_engram_and_blueprint(view, reward_data, cfg)
    await _uber_complete_standard(view, message, cfg, reward_data)


async def _handle_gemini(view, message) -> None:
    reward_data = await _uber_setup(view, message)
    if reward_data is None:
        return
    cfg = UBER_CONFIGS["Castor"]
    await _handle_engram_and_blueprint(view, reward_data, cfg)
    await _uber_complete_standard(view, message, cfg, reward_data)


async def _handle_evelynn(view, message) -> None:
    """Evelynn: guaranteed Curio Puzzle Box + rare Rune of Mirage drops."""
    reward_data = await _uber_setup(view, message)
    if reward_data is None:
        return
    cfg = UBER_CONFIGS["Evelynn"]

    # Guaranteed: Curio Puzzle Box
    await view.bot.database.users.modify_currency(view.user_id, "curio_puzzle_boxes", 1)
    reward_data["special"].append("Curio Puzzle Box")
    reward_data["msgs"].append(
        "📦 **A Curio Puzzle Box materialises from Evelynn's shattered form...**"
    )

    await _handle_engram_and_blueprint(view, reward_data, cfg)

    if random.random() < EVELYNN_MIRAGE_RUNE_IMPERFECT_CHANCE:
        await view.bot.database.users.modify_currency(
            view.user_id, "mirage_runes_imperfect", 1
        )
        reward_data["special"].append("Rune of Mirage (Imperfect)")
        reward_data["msgs"].append(
            "🪞 **A Rune of Mirage (Imperfect) fractures from the Origin's corruption...**"
        )

    if random.random() < EVELYNN_MIRAGE_RUNE_PERFECTED_CHANCE:
        await view.bot.database.users.modify_currency(
            view.user_id, "mirage_runes_perfected", 1
        )
        reward_data["special"].append("Rune of Mirage (Perfected)")
        reward_data["msgs"].append(
            "🪞 **A Rune of Mirage (Perfected) crystallises from the primordial void...**"
        )

    await _uber_complete_standard(view, message, cfg, reward_data)


# ---------------------------------------------------------------------------
# Public dispatch entry point
# ---------------------------------------------------------------------------


async def handle_uber_end_state(view, message, interaction) -> None:
    """Route to the correct uber boss end-state handler based on monster name."""
    name = view.monster.name
    if "Lucifer" in name:
        await _handle_lucifer(view, message)
    elif "NEET" in name:
        await _handle_neet(view, message)
    elif "Castor" in name:
        await _handle_gemini(view, message)
    elif "Evelynn" in name:
        await _handle_evelynn(view, message)
    else:
        await _handle_aphrodite(view, message)
