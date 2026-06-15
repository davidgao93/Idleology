"""
core/hematurgy/engine.py — Combat hooks for all Hematurgy passives.

Architecture notes
------------------
Passives that affect player ATK are expressed as multiplier contributions fed into
build_attack_multiplier() each turn — NOT as bonus_atk accumulations — so they stay
idempotent and correct across multi-turn fights.

Entry points
------------
get_h(player, pid)                           → int | None
apply_hematurgy_start(player, monster, log)  — Ward Inoculation at combat start
on_haemorrhage_tick(player, monster, log)    — bleed DoT, start of player turn
on_player_hit(player, monster, damage, is_crit, log)  → extra_damage: int
on_player_miss(player, monster, miss_damage, log)     → extra_damage: int
on_ward_gained(player, amount, log)          → adjusted_amount: int
drain_ward_dmg_buffer(player, monster, log)
on_monster_turn_start(player, monster, log)  → skip_turn: bool
on_monster_turn_end(player, monster, hp_damage, is_dodged, is_blocked, log)
on_kill(player, log)
on_potion_used(player, log)
apply_reverberation(player, monster, echo_damage, log) → extra: int
--- multiplier helpers (called from build_attack_multiplier / calc_crit_damage) ---
get_iron_momentum_factor(player)             → float
get_executioners_rite_bonus(player, monster) → float
get_soul_fracture_factor(player)             → float
get_counterforce_factor(player)              → float
get_chain_reaction_crit_bonus(player)        → float
get_phantom_reflex_evasion_bonus(player)     → float
"""

from __future__ import annotations

from core.combat.models import Monster, Player
from core.hematurgy.mechanics import tier_val

# ---------------------------------------------------------------------------
# Lookup helper
# ---------------------------------------------------------------------------


def get_h(player: Player, passive_id: str) -> int | None:
    """Returns the hematurgy passive's tier (1–5), or None if not owned."""
    return player.hematurgy_passives.get(passive_id)


def _tv(pid: str, tier: int) -> float:
    return tier_val(pid, tier)


# ---------------------------------------------------------------------------
# Multiplier helpers — called from build_attack_multiplier each player turn
# ---------------------------------------------------------------------------


def get_iron_momentum_factor(player: Player) -> float:
    """Iron Momentum: returns fractional ATK bonus from current stacks (0.0 if none)."""
    tier = get_h(player, "iron_momentum")
    if tier is None or player.cs.hema_momentum_stacks == 0:
        return 0.0
    return _tv("iron_momentum", tier) * player.cs.hema_momentum_stacks


def get_executioners_rite_bonus(player: Player, monster: Monster) -> float:
    """Executioner's Rite: returns fractional bonus when monster < 30% HP."""
    tier = get_h(player, "executioners_rite")
    if tier is None:
        return 0.0
    if monster.max_hp > 0 and monster.hp / monster.max_hp < 0.30:
        return _tv("executioners_rite", tier)
    return 0.0


def get_soul_fracture_factor(player: Player) -> float:
    """Soul Fracture: returns fractional ATK bonus per 10% of max HP lost this combat."""
    tier = get_h(player, "soul_fracture")
    if tier is None or player.cs.hema_hp_lost_combat <= 0:
        return 0.0
    max_hp = max(player.total_max_hp, 1)
    chunks = int(player.cs.hema_hp_lost_combat / (max_hp * 0.10))
    if chunks <= 0:
        return 0.0
    return _tv("soul_fracture", tier) * chunks


def get_counterforce_factor(player: Player) -> float:
    """Counterforce: X% of total DEF expressed as a fractional ATK bonus."""
    tier = get_h(player, "counterforce")
    if tier is None:
        return 0.0
    atk = max(player.get_total_attack(), 1)
    def_bonus_flat = int(player.get_total_defence() * _tv("counterforce", tier))
    return def_bonus_flat / atk


def get_chain_reaction_crit_bonus(player: Player) -> float:
    """Chain Reaction: additional crit damage multiplier from consecutive crits."""
    tier = get_h(player, "chain_reaction")
    if tier is None or player.cs.hema_chain_stacks == 0:
        return 0.0
    return _tv("chain_reaction", tier) * player.cs.hema_chain_stacks


def get_phantom_reflex_evasion_bonus(player: Player) -> float:
    """Phantom Reflex: evasion fraction bonus from stacked misses."""
    tier = get_h(player, "phantom_reflex")
    if tier is None or player.cs.hema_phantom_stacks == 0:
        return 0.0
    return _tv("phantom_reflex", tier) * player.cs.hema_phantom_stacks


# ---------------------------------------------------------------------------
# Between-fight reset (ascent floors, codex waves)
# ---------------------------------------------------------------------------


def reset_hematurgy_transients(player: Player) -> None:
    """
    Resets all per-fight hematurgy state.  Call this alongside the existing
    stack resets in _next_floor and _setup_next_wave so stacks don't bleed
    between monsters.  The hematurgy_passives dict (permanent tier data) is
    intentionally NOT touched.
    """
    cs = player.cs
    cs.hema_momentum_stacks = 0
    cs.hema_bleed_total = 0
    cs.hema_chain_stacks = 0
    cs.hema_phantom_stacks = 0
    cs.hema_fevered_count = 0
    cs.hema_predators_mark = False
    cs.hema_defiance_triggered = False
    cs.hema_hp_lost_combat = 0
    cs.hema_blade_count = 0
    cs.hema_puncture_bleed = 0
    cs.hema_frost_misses = 0
    cs.hema_ward_inoculation = False  # re-applied by apply_hematurgy_start each fight
    cs.hema_ward_dmg_buffer = 0
    cs.hema_serrated_total = 0
    # Clear any freeze flag left on the monster (defensive — uses dynamic attr)
    # Nothing to clear on player side; monster is replaced each floor/wave anyway.


# ---------------------------------------------------------------------------
# Combat start
# ---------------------------------------------------------------------------


def apply_hematurgy_start(player: Player, monster: Monster, log: list[str]) -> None:
    """
    Ward Inoculation (M4): convert all starting ward to bonus DEF and double Max HP.
    Called from apply_combat_start_passives() after all other start passives have run.
    """
    tier = get_h(player, "ward_inoculation")
    if tier is None:
        return

    ward_val = player.combat_ward
    if ward_val > 0:
        player.bonus_def += ward_val
        player.combat_ward = 0
        log.append(
            f"🩸 **Ward Inoculation** — {ward_val:,} ward converted to {ward_val:,} flat DEF!"
        )

    # Double Max HP by adding the current total as bonus_max_hp
    base_total = player.total_max_hp  # read before we mutate bonus_max_hp
    player.bonus_max_hp += base_total
    player.cs.hema_ward_inoculation = True

    log.append(
        f"🩸 **Ward Inoculation** — Max HP doubled to {player.total_max_hp:,}! "
        f"Ward gains will deal damage instead."
    )


# ---------------------------------------------------------------------------
# Player turn: start-of-turn Haemorrhage bleed tick
# ---------------------------------------------------------------------------


def on_haemorrhage_tick(player: Player, monster: Monster, log: list[str]) -> None:
    """Haemorrhage: deal 10% of accumulated bleed pool as damage at start of player turn."""
    if get_h(player, "haemorrhage") is None:
        return
    if player.cs.hema_bleed_total <= 0 or monster.hp <= 0:
        return

    tick = max(1, int(player.cs.hema_bleed_total * 0.10))
    actual = min(tick, monster.hp)
    monster.hp = max(0, monster.hp - actual)
    log.append(
        f"🩸 **Haemorrhage** bleeds **{actual}** damage! (pool: {player.cs.hema_bleed_total:,})"
    )


# ---------------------------------------------------------------------------
# Player hit passives
# ---------------------------------------------------------------------------


def on_player_hit(
    player: Player,
    monster: Monster,
    damage: int,
    is_crit: bool,
    log: list[str],
) -> int:
    """
    Fires after damage is applied to the monster.
    Handles: Iron Momentum (stack update), Serrated, Haemorrhage charge,
             Chain Reaction (stack update), Predator's Mark, Spectral Waltz,
             Puncture (crit accumulation).
    Returns any extra damage dealt directly (Mark consume, Waltz release).
    """
    extra = 0

    # --- Iron Momentum: update stacks (ATK factor applied in build_attack_multiplier) ---
    tier_im = get_h(player, "iron_momentum")
    if tier_im is not None:
        player.cs.hema_momentum_stacks = min(5, player.cs.hema_momentum_stacks + 1)

    # --- Serrated: permanently reduce monster ATK (Phase 3)
    tier_ser = get_h(player, "serrated")
    if tier_ser is not None and monster.effective_attack > 0:
        reduction = int(_tv("serrated", tier_ser))
        if is_crit:
            reduction *= 2
        monster.flat_attack_reduction += reduction
        player.cs.hema_serrated_total += reduction
        crit_note = " (crit ×2)" if is_crit else ""
        log.append(
            f"🔪 **Serrated**{crit_note} — monster ATK −{reduction} (now {monster.effective_attack})."
        )

    # --- Haemorrhage: add bleed charge ---
    tier_hm = get_h(player, "haemorrhage")
    if tier_hm is not None:
        charge = int(player.get_total_attack() * _tv("haemorrhage", tier_hm))
        player.cs.hema_bleed_total += charge

    # --- Chain Reaction: update stacks (crit bonus applied in calc_crit_damage) ---
    tier_cr = get_h(player, "chain_reaction")
    if tier_cr is not None:
        if is_crit:
            player.cs.hema_chain_stacks = min(5, player.cs.hema_chain_stacks + 1)
        else:
            if player.cs.hema_chain_stacks > 0:
                log.append(
                    f"⚡ **Chain Reaction** resets! ({player.cs.hema_chain_stacks} stacks lost)"
                )
                player.cs.hema_chain_stacks = 0

    # --- Predator's Mark: consume existing mark, then apply new mark on crit ---
    tier_pm = get_h(player, "predators_mark")
    if tier_pm is not None:
        if player.cs.hema_predators_mark:
            # Consume mark → bonus damage
            mark_dmg = int(damage * _tv("predators_mark", tier_pm))
            if mark_dmg > 0 and monster.hp > 0:
                actual_mark = min(mark_dmg, monster.hp)
                monster.hp = max(0, monster.hp - actual_mark)
                extra += actual_mark
                log.append(
                    f"🎯 **Predator's Mark** detonates! +{actual_mark} bonus damage!"
                )
            player.cs.hema_predators_mark = False
        if is_crit:
            player.cs.hema_predators_mark = True
            log.append("🎯 **Predator's Mark** applied!")

    # --- Spectral Waltz: +1 blade on hit; crit releases all blades at once ---
    tier_sw = get_h(player, "spectral_waltz")
    if tier_sw is not None:
        max_blades = int(_tv("spectral_waltz_max", tier_sw))
        if is_crit and player.cs.hema_blade_count > 0:
            blade_pct = _tv("spectral_waltz", tier_sw) / 100.0
            blade_dmg = int(
                player.get_total_attack() * blade_pct * player.cs.hema_blade_count
            )
            if blade_dmg > 0 and monster.hp > 0:
                actual_sw = min(blade_dmg, monster.hp)
                monster.hp = max(0, monster.hp - actual_sw)
                extra += actual_sw
                log.append(
                    f"👻 **Spectral Waltz** — {player.cs.hema_blade_count} blade(s) unleashed! "
                    f"💀 **{actual_sw}** damage!"
                )
            player.cs.hema_blade_count = 0
        elif not is_crit and player.cs.hema_blade_count < max_blades:
            player.cs.hema_blade_count += 1

    # --- Puncture: crit builds bleed pool ---
    tier_pu = get_h(player, "puncture")
    if tier_pu is not None and is_crit:
        charge = int(damage * _tv("puncture", tier_pu))
        player.cs.hema_puncture_bleed += charge

    return extra


# ---------------------------------------------------------------------------
# Player miss passives
# ---------------------------------------------------------------------------


def on_player_miss(
    player: Player,
    monster: Monster,
    miss_damage: int,
    log: list[str],
) -> int:
    """
    Fires after a miss resolves.
    Returns any extra damage dealt (Puncture burst) + tracks Soothing Venom heal.
    """
    extra = 0

    # --- Iron Momentum: reset stacks ---
    if (
        get_h(player, "iron_momentum") is not None
        and player.cs.hema_momentum_stacks > 0
    ):
        log.append(
            f"🔥 **Iron Momentum** resets! ({player.cs.hema_momentum_stacks} stacks lost)"
        )
        player.cs.hema_momentum_stacks = 0

    # --- Chain Reaction: reset stacks on miss ---
    if get_h(player, "chain_reaction") is not None and player.cs.hema_chain_stacks > 0:
        log.append(
            f"⚡ **Chain Reaction** resets on miss! ({player.cs.hema_chain_stacks} stacks lost)"
        )
        player.cs.hema_chain_stacks = 0

    # --- Phantom Reflex: add evasion stack (max 2, displayed in status panel) ---
    tier_pr = get_h(player, "phantom_reflex")
    if tier_pr is not None and player.cs.hema_phantom_stacks < 2:
        player.cs.hema_phantom_stacks += 1

    # --- Predator's Mark: clear mark on miss ---
    if get_h(player, "predators_mark") is not None and player.cs.hema_predators_mark:
        player.cs.hema_predators_mark = False
        log.append("🎯 **Predator's Mark** fades (missed).")

    # --- Spectral Waltz: −1 blade on miss ---
    tier_sw = get_h(player, "spectral_waltz")
    if tier_sw is not None and player.cs.hema_blade_count > 0:
        player.cs.hema_blade_count -= 1
        log.append(
            f"👻 **Spectral Waltz** — a blade dissipates! ({player.cs.hema_blade_count} remaining)"
        )

    # --- Flash Frost: increment miss counter ---
    tier_ff = get_h(player, "flash_frost")
    if tier_ff is not None:
        player.cs.hema_frost_misses += 1
        threshold = int(_tv("flash_frost", tier_ff))
        if player.cs.hema_frost_misses >= threshold:
            player.cs.hema_frost_misses = 0
            log.append(
                f"❄️ **Flash Frost** — {threshold} misses reached! Monster frozen next turn!"
            )
            monster._hema_frozen = True

    # --- Puncture: burst 50% of bleed pool on miss ---
    tier_pu = get_h(player, "puncture")
    if tier_pu is not None and player.cs.hema_puncture_bleed > 0:
        burst = int(player.cs.hema_puncture_bleed * 0.50)
        if burst > 0 and monster.hp > 0:
            actual = min(burst, monster.hp)
            monster.hp = max(0, monster.hp - actual)
            extra += actual
            log.append(
                f"💉 **Puncture** bursts on miss — **{actual}** bleed damage! (pool reset)"
            )
        player.cs.hema_puncture_bleed = 0

    # --- Soothing Venom: lifesteal from poison miss-damage ---
    tier_sv = get_h(player, "soothing_venom")
    if tier_sv is not None and miss_damage > 0:
        heal = int(miss_damage * _tv("soothing_venom", tier_sv))
        if heal > 0:
            player.current_hp = min(player.total_max_hp, player.current_hp + heal)
            log.append(f"☠️ **Soothing Venom** — poison siphons **{heal}** HP!")

    return extra


# ---------------------------------------------------------------------------
# Ward generation hook (called from ward_system.add_ward)
# ---------------------------------------------------------------------------


def on_ward_gained(player: Player, amount: int, log: list[str]) -> int:
    """
    Ward Inoculation: if active, redirect ward to the damage buffer (returns 0).
    Vital Resonance: X% of ward generated → HP heal (then returns original amount).
    Called before ward is added to player.combat_ward.
    """
    if amount <= 0:
        return amount

    # Ward Inoculation takes priority — no ward is actually gained
    if player.cs.hema_ward_inoculation:
        tier = get_h(player, "ward_inoculation")
        if tier is not None:
            efficiency = _tv("ward_inoculation", tier)
            player.cs.hema_ward_dmg_buffer += int(amount * efficiency)
            return 0

    # Vital Resonance: heal a fraction of ward gained (ward still fully added)
    tier_vr = get_h(player, "vital_resonance")
    if tier_vr is not None:
        heal = int(amount * _tv("vital_resonance", tier_vr))
        if heal > 0:
            player.current_hp = min(player.total_max_hp, player.current_hp + heal)
            log.append(f"💚 **Vital Resonance** — {heal} HP restored from ward!")

    return amount


def drain_ward_dmg_buffer(player: Player, monster: Monster, log: list[str]) -> None:
    """Applies buffered Ward Inoculation damage to the monster. Call after ward-gen events."""
    if player.cs.hema_ward_dmg_buffer <= 0 or monster.hp <= 0:
        player.cs.hema_ward_dmg_buffer = 0
        return
    dmg = player.cs.hema_ward_dmg_buffer
    actual = min(dmg, monster.hp)
    monster.hp = max(0, monster.hp - actual)
    player.cs.hema_ward_dmg_buffer = 0
    log.append(f"🩸 **Ward Inoculation** — ward energy surges for **{actual}** damage!")


# ---------------------------------------------------------------------------
# Monster turn hooks
# ---------------------------------------------------------------------------


def on_monster_turn_start(player: Player, monster: Monster, log: list[str]) -> bool:
    """Flash Frost: if the monster is frozen, skip its action. Returns True to skip."""
    if getattr(monster, "_hema_frozen", False):
        monster._hema_frozen = False
        log.append(
            f"❄️ **Flash Frost** — {monster.name} is frozen and cannot act this round!"
        )
        return True
    return False


def on_monster_turn_end(
    player: Player,
    monster: Monster,
    hp_damage: int,
    is_dodged: bool,
    is_blocked: bool,
    log: list[str],
) -> None:
    """
    Called after all monster damage is resolved.
    Handles: Soul Fracture HP tracking, Tenacity trigger, Phantom Reflex stack consume,
             Regenerative Tissue heal.
    """
    # --- Soul Fracture: accumulate HP lost during combat ---
    if get_h(player, "soul_fracture") is not None and hp_damage > 0:
        player.cs.hema_hp_lost_combat += hp_damage

    # --- Defiance: one-shot trigger when HP drops below 40% ---
    tier_ten = get_h(player, "defiance")
    if (
        tier_ten is not None
        and not player.cs.hema_defiance_triggered
        and player.current_hp > 0
        and player.current_hp < (player.total_max_hp * 0.40)
    ):
        player.cs.hema_defiance_triggered = True
        pct = _tv("defiance", tier_ten)
        atk_bonus = int(player.flat_atk * pct)
        def_bonus = int(player.flat_def * pct)
        player.bonus_atk += atk_bonus
        player.bonus_def += def_bonus
        log.append(
            f"💪 **Defiance** ignites! HP below 40% — "
            f"+{atk_bonus} ATK and +{def_bonus} DEF for this fight!"
        )

    # --- Phantom Reflex: consume 1 stack when an actual hit lands ---
    tier_pr = get_h(player, "phantom_reflex")
    if (
        tier_pr is not None
        and not is_dodged
        and not is_blocked
        and hp_damage > 0
        and player.cs.hema_phantom_stacks > 0
    ):
        player.cs.hema_phantom_stacks -= 1

    # --- Regenerative Tissue: heal after a round with zero HP damage ---
    tier_rt = get_h(player, "regenerative_tissue")
    if tier_rt is not None and hp_damage == 0 and player.current_hp > 0:
        heal = int(player.total_max_hp * _tv("regenerative_tissue", tier_rt))
        if heal > 0:
            player.current_hp = min(player.total_max_hp, player.current_hp + heal)
            log.append(
                f"🌿 **Regenerative Tissue** — zero damage taken, healing {heal} HP!"
            )


# ---------------------------------------------------------------------------
# Kill hook
# ---------------------------------------------------------------------------


def on_kill(player: Player, log: list[str]) -> None:
    """Called when a monster dies. Crimson Feast HP restore + Haemorrhage kill burst."""
    tier_bt = get_h(player, "crimson_feast")
    if tier_bt is not None:
        heal = int(player.total_max_hp * _tv("crimson_feast", tier_bt))
        if heal > 0:
            player.current_hp = min(player.total_max_hp, player.current_hp + heal)
            log.append(
                f"🩸 **Crimson Feast** — kill restores **{heal}** HP "
                f"({int(_tv('crimson_feast', tier_bt) * 100)}% Max HP)!"
            )

    if get_h(player, "haemorrhage") is not None and player.cs.hema_bleed_total > 0:
        log.append(
            f"🩸 **Haemorrhage** — full bleed pool ({player.cs.hema_bleed_total:,}) discharges!"
        )
        player.cs.hema_bleed_total = 0


# ---------------------------------------------------------------------------
# Potion hook
# ---------------------------------------------------------------------------


def on_potion_used(player: Player, log: list[str]) -> None:
    """Fevered Strike: permanent ATK% per potion consumed this fight."""
    tier = get_h(player, "fevered_strike")
    if tier is None:
        return
    player.cs.hema_fevered_count += 1
    bonus = int(player.flat_atk * _tv("fevered_strike", tier))
    player.bonus_atk += bonus
    log.append(
        f"🔥 **Fevered Strike** ({player.cs.hema_fevered_count} potions) — +{bonus} ATK!"
    )


# ---------------------------------------------------------------------------
# Reverberation (echo re-echo chain)
# ---------------------------------------------------------------------------


def apply_reverberation(
    player: Player,
    monster: Monster,
    base_echo_damage: int,
    log: list[str],
) -> int:
    """
    Rolls a re-echo chain for Reverberation after the initial echo fires.
    Starting chance = tier value; each successive re-echo loses 10%.
    Returns total extra damage dealt.
    """
    import random

    tier = get_h(player, "reverberation")
    if tier is None or base_echo_damage <= 0 or monster.hp <= 0:
        return 0

    chance = _tv("reverberation", tier)
    total_extra = 0
    while chance > 0.05 and random.random() < chance:
        actual = min(base_echo_damage, monster.hp)
        if actual <= 0:
            break
        monster.hp = max(0, monster.hp - actual)
        total_extra += actual
        log.append(f"🎶 **Reverberation** re-echoes! +{actual} damage!")
        chance -= 0.10
        if monster.hp <= 0:
            break

    return total_extra
