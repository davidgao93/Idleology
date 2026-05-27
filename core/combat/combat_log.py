"""
Combat logging — writes per-encounter logs to logs/combat/ when enabled.

Toggle via config.json:  "combat_logging": true
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from core.models import Monster, Player

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "combat"

logger = logging.getLogger("discord_bot")


def _logging_enabled() -> bool:
    try:
        with open(_CONFIG_PATH) as f:
            return bool(json.load(f).get("combat_logging", False))
    except Exception:
        return False


class CombatLogger:
    """
    Writes turn-by-turn combat logs to a timestamped file.
    All methods are no-ops when combat_logging is disabled in config.json.
    """

    def __init__(self, player: Player, monster: Monster):
        self._file = None
        self._turn = 0
        self._total_dealt = 0
        self._total_taken = 0

        if not _logging_enabled():
            return

        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            safe_player = "".join(c if c.isalnum() else "_" for c in player.name)
            safe_monster = "".join(c if c.isalnum() else "_" for c in monster.name)
            path = _LOG_DIR / f"{ts}_{safe_player}_vs_{safe_monster}.txt"
            self._file = open(path, "w", encoding="utf-8", buffering=1)
        except Exception as e:
            logger.warning(f"CombatLogger: failed to open log file: {e}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _w(self, line: str) -> None:
        if self._file:
            self._file.write(line + "\n")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_combat_start(self, player: Player, monster: Monster) -> None:
        if not self._file:
            return

        from core.combat.calc.hit_calc import (
            _HIT_BASE,
            _HIT_SENSITIVITY,
            _MON_HIT_BASE,
            _MON_HIT_SENSITIVITY,
            calculate_crit_chance,
            calculate_hit_chance,
            calculate_monster_hit_chance,
        )

        p_atk = player.get_total_attack()
        p_def = player.get_total_defence()
        m_atk = monster.effective_attack
        m_def = monster.effective_defence

        p_hit = calculate_hit_chance(player, monster)
        m_hit = calculate_monster_hit_chance(player, monster)
        eff_crit = calculate_crit_chance(player)

        # Hit formula breakdown
        p_pct_diff = (p_atk - m_def) / m_def if m_def > 0 else float("inf")
        p_hit_base = _HIT_BASE + p_pct_diff * _HIT_SENSITIVITY if m_def > 0 else 1.0
        m_pct_diff = (m_atk - p_def) / m_atk if m_atk > 0 else 0.0
        m_hit_base = (
            _MON_HIT_BASE + m_pct_diff * _MON_HIT_SENSITIVITY if m_atk > 0 else 0.0
        )

        asc_hit = (
            player.get_ascension_bonuses().get("hit", 0)
            if player.ascension_unlocks
            else 0
        )

        self._w(f"{'=' * 60}")
        self._w(f"COMBAT: {player.name}  vs  {monster.name} (Lv.{monster.level})")
        self._w(f"{'=' * 60}")
        self._w(
            f"[START] Player : HP {player.current_hp}/{player.total_max_hp} | "
            f"Atk {p_atk} | Def {p_def} | "
            f"PDR {player.get_total_pdr()}% | FDR {player.get_total_fdr()} | "
            f"Crit {player.get_current_crit_chance()}% | Ward {player.combat_ward}"
        )
        self._w(
            f"[START] Monster: HP {monster.hp}/{monster.max_hp} | "
            f"Atk {m_atk} | Def {m_def} | "
            f"Mods: {', '.join(monster.display_modifiers) or 'None'}"
            + (f" | {['','HARD','EXTREME','NIGHTMARISH','DELIRIOUS'][monster.difficulty_level]} MODE" if monster.difficulty_level > 0 else "")
        )
        self._w(
            f"[CALC]  Player hit:   base={_HIT_BASE*100:.0f}% + ({p_atk}-{m_def})/{m_def if m_def else 1} × {_HIT_SENSITIVITY*100:.0f}% "
            f"= {p_hit_base*100:.1f}%{f' +asc={asc_hit}%' if asc_hit else ''} → capped={p_hit*100:.1f}%"
        )
        self._w(
            f"[CALC]  Monster hit:  base={_MON_HIT_BASE*100:.0f}% + ({m_atk}-{p_def})/{m_atk if m_atk else 1} × {_MON_HIT_SENSITIVITY*100:.0f}% "
            f"= {m_hit_base*100:.1f}% → capped={m_hit*100:.1f}%"
        )
        self._w(
            f"[CALC]  Eff crit:     {eff_crit:.1f}%  "
            f"(base={player.get_current_crit_chance()}%)"
        )
        self._w("")

    def log_transient_states(self, player: Player, after_label: str = "") -> None:
        """Log all active jewel/hematurgy transient states after a turn.
        Outputs nothing if all transients are at zero/inactive to keep logs clean."""
        if not self._file:
            return

        lines: list[str] = []

        # ── Paradise Jewel transients ──────────────────────────────────────
        jop = getattr(player, "jewel_of_paradise", None)
        if jop and jop.get("equipped_skill"):
            skill_key = jop["equipped_skill"]
            charges = jop.get("skill_charges", {}).get(skill_key, 0)
            if charges:
                lines.append(f"[JEWEL-{skill_key.upper()}] charges={charges}")
            if getattr(player, "jewel_cataclysm_primed", False):
                bonus_pct = getattr(player, "jewel_cataclysm_bonus_multi", 0.0) * 100
                lines.append(
                    f"[JEWEL-CATACLYSM] PRIMED  +{bonus_pct:.0f}% crit multi"
                )
            if getattr(player, "jewel_onslaught_primed", False):
                bonus_pct = getattr(player, "jewel_onslaught_bonus_pct", 0.0)
                lines.append(f"[JEWEL-ONSLAUGHT] PRIMED  +{bonus_pct:.0f}% ATK")
            dot = getattr(player, "jewel_acrimony_dot", 0)
            if dot > 0:
                dot_dmg = getattr(player, "jewel_acrimony_dot_dmg", 0)
                lines.append(
                    f"[JEWEL-ACRIMONY] DoT  {dot} turns left  {dot_dmg}/turn"
                )
            wf = getattr(player, "jewel_wardforge_bonus_dmg", 0)
            if wf:
                lines.append(f"[JEWEL-WARDFORGE] pending bonus_dmg={wf}")

        # ── Hematurgy transients ───────────────────────────────────────────
        cs = getattr(player, "cs", None)
        if cs is not None and getattr(player, "hematurgy_passives", None):
            _HEMA_FIELDS = [
                ("hema_momentum_stacks", "Iron Momentum stacks"),
                ("hema_chain_stacks",    "Chain Reaction stacks"),
                ("hema_phantom_stacks",  "Phantom Reflex stacks"),
                ("hema_blade_count",     "Spectral Waltz blades"),
                ("hema_bleed_total",     "Haemorrhage pool"),
                ("hema_puncture_bleed",  "Puncture pool"),
                ("hema_frost_misses",    "Flash Frost misses"),
                ("hema_hp_lost_combat",  "Soul Fracture HP lost"),
                ("hema_ward_dmg_buffer", "Ward Inoculation buffer"),
                ("hema_fevered_count",   "Fevered Strike potions"),
                ("hema_serrated_total",  "Serrated ATK reduced"),
            ]
            for attr, label in _HEMA_FIELDS:
                val = getattr(cs, attr, 0)
                if val:
                    lines.append(f"[HEMA-STATE] {label}: {val}")
            if getattr(cs, "hema_predators_mark", False):
                lines.append("[HEMA-STATE] Predator's Mark: ACTIVE")
            if getattr(cs, "hema_tenacity_triggered", False):
                lines.append("[HEMA-STATE] Tenacity: TRIGGERED")
            if getattr(cs, "hema_ward_inoculation", False):
                lines.append("[HEMA-STATE] Ward Inoculation: ACTIVE")

        if lines:
            prefix = f" after {after_label}" if after_label else ""
            self._w(f"  [TRANSIENTS{prefix}]")
            for line in lines:
                self._w(f"    {line}")

    def log_player_turn(self, result, monster: Monster) -> None:
        if not self._file:
            return

        self._turn += 1
        self._total_dealt += result.damage
        outcome = "CRIT" if result.is_crit else ("HIT" if result.is_hit else "MISS")

        self._w(
            f"[T{self._turn} PLAYER] {outcome} | "
            f"Damage dealt: {result.damage} | "
            f"Monster HP: {monster.hp}/{monster.max_hp}"
        )
        for line in result.log.splitlines():
            if line.strip():
                self._w(f"  {line}")
        if result.calc_detail:
            self._w("  --- calc ---")
            for line in result.calc_detail.splitlines():
                self._w(line)

        self._w("")

    def log_monster_turn(self, result, player: Player) -> None:
        if not self._file:
            return

        self._total_taken += result.hp_damage

        self._w(
            f"[T{self._turn} MONSTER] HP damage: {result.hp_damage} | "
            f"Player HP: {player.current_hp}/{player.total_max_hp} | "
            f"Ward: {player.combat_ward}"
        )
        for line in result.log.splitlines():
            if line.strip():
                self._w(f"  {line}")
        if result.calc_detail:
            self._w("  --- calc ---")
            for line in result.calc_detail.splitlines():
                self._w(line)

        # Log active transient states at end of each full round
        self.log_transient_states(player, after_label="monster turn")

        self._w("")

    def log_rewards(
        self, player: Player, reward_data: dict, monster: Monster | None = None
    ) -> None:
        if not self._file:
            return

        rarity = player.get_total_rarity()
        special_bonus = player.get_special_drop_bonus()
        rolls = reward_data.get("rolls", {})

        self._w(f"{'=' * 60}")
        self._w("REWARDS")
        self._w(f"{'=' * 60}")
        self._w(
            f"[XP/GOLD]   XP: {reward_data.get('xp', 0):,} | Gold: {reward_data.get('gold', 0):,}"
        )
        self._w(f"[PLAYER]    Rarity: {rarity}% | Special Drop Bonus: {special_bonus:.2f}%")

        # Gear drop roll
        gear_roll = rolls.get("gear_roll")
        if gear_roll is not None:
            gear_threshold = rolls.get("gear_threshold", "?")
            hit_str = "HIT" if rolls.get("gear_hit") else "MISS"
            self._w(
                f"[GEAR ROLL] {gear_roll}/100 vs threshold {gear_threshold}% → {hit_str}"
            )
            if rolls.get("gear_hit"):
                item_roll = rolls.get("item_roll", "?")
                item_slot = rolls.get("item_slot") or "inventory full / rune"
                self._w(f"[GEAR SLOT] Item roll: {item_roll}/100 → {item_slot}")

        # Body part drop roll (non-essence monsters only)
        part_chance_pct = rolls.get("part_chance_pct")
        if part_chance_pct is not None:
            part_roll_pct = rolls.get("part_roll_pct", 0.0)
            hit_str = "HIT" if rolls.get("part_hit") else "MISS"
            self._w(
                f"[PART ROLL] {part_roll_pct:.2f}% vs chance {part_chance_pct:.3f}% → {hit_str}"
            )
            if rolls.get("part_hit") and "body_part" in reward_data:
                slot, name, hp = reward_data["body_part"]
                self._w(f"[PART]      {name} ({slot}) +{hp} HP")

        # Egg drop roll (normal monsters only)
        egg_chance_pct = rolls.get("egg_chance_pct")
        if egg_chance_pct is not None:
            egg_roll_pct = rolls.get("egg_roll_pct", 0.0)
            hit_str = "HIT" if rolls.get("egg_hit") else "MISS"
            self._w(
                f"[EGG ROLL]  {egg_roll_pct:.2f}% vs chance {egg_chance_pct:.3f}% → {hit_str}"
            )
            if rolls.get("egg_hit") and "egg" in reward_data:
                self._w(f"[EGG]       Tier: {reward_data['egg']}")

        # Special drop context — show effective thresholds so rolls are interpretable
        if monster is not None:
            if not monster.is_boss:
                mod_difficulty = 0.0
                if monster.modifiers:
                    mod_difficulty = min(
                        0.05, sum(m.difficulty for m in monster.modifiers)
                    )
                spirit_thr = round((0.01 + special_bonus / 100) * 100, 3)
                material_thr = round(
                    (0.01 + mod_difficulty + special_bonus / 100) * 100, 3
                )
                ctx = (
                    f"[SPECIAL CTX] Spirit stone: {spirit_thr:.3f}%"
                    f" | Materials/keys: {material_thr:.3f}%"
                    f" | Mod difficulty pool: {mod_difficulty:.4f}"
                )
                if player.active_partner:
                    guild_thr = round((0.01 + special_bonus / 100) * 100, 3)
                    ctx += f" | Guild ticket: {guild_thr:.3f}%"
                self._w(ctx)
            else:
                rare_thr = round((0.05 + special_bonus / 100) * 100, 3)
                self._w(
                    f"[SPECIAL CTX] Boss rare drop threshold: {rare_thr:.3f}%"
                    f" (spirit stone, antique tome, pinnacle key, elemental mats)"
                )

        # Essence drop (essence monsters only)
        essences = reward_data.get("essences", [])
        if essences:
            self._w(f"[ESSENCE]   {', '.join(essences)}")

        # Gear items
        items = reward_data.get("items", [])
        for item in items:
            first_line = item.split("\n")[0].replace("**", "")
            self._w(f"[ITEM]      {first_line}")

        # Special drops (keys, runes, materials, sigils)
        special = reward_data.get("special", [])
        if special:
            self._w(f"[SPECIAL]   {', '.join(special)}")

        # Passive proc messages (XP doublers, gold doublers, equilibrium, etc.)
        for msg in reward_data.get("msgs", []):
            clean = msg.replace("**", "").replace("\n", " ").strip()
            if clean:
                self._w(f"[MSG]       {clean}")

        self._w("")

    def log_combat_end(self, player: Player, monster: Monster, outcome: str) -> None:
        if not self._file:
            return

        self._w(f"{'=' * 60}")
        self._w(
            f"END: {outcome.upper()} | Turns: {self._turn} | "
            f"Total dealt: {self._total_dealt} | Total taken: {self._total_taken}"
        )
        self._w(
            f"Player HP: {player.current_hp}/{player.total_max_hp} | "
            f"Monster HP: {monster.hp}/{monster.max_hp}"
        )
        self._w(f"{'=' * 60}")
        self.close()

    def close(self) -> None:
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None


# ---------------------------------------------------------------------------
# Debug stat summary — moved from engine.py, kept accessible as engine.log_combat_debug
# ---------------------------------------------------------------------------


def log_combat_debug(player: Player, monster: Monster, log: logging.Logger) -> None:
    """Logs a pre-combat stat summary and theoretical max damage for both sides.

    Monster damage formula (matches calculate_damage_taken):
      base_raw = 5 + level * 1.5
      surplus  = clamp((m_atk - p_def) / p_def, −0.95, ∞)
      raw      = base_raw * (1 + surplus * surplus_mult)   [surplus_mult=1.2 in hard mode]
      max_raw  = raw * 1.15 variance ceiling
    """
    p_atk = player.get_total_attack()
    p_def = player.get_total_defence()
    p_crit = player.get_current_crit_chance()

    crit_mult = player.get_weapon_crit_multi()
    if monster.has_modifier("Nullifying"):
        crit_mult *= 1 - monster.get_modifier_value("Nullifying")
    p_max_dmg = int(p_atk * crit_mult)
    if player.get_glove_passive() == "instability":
        lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
        p_max_dmg = int(p_max_dmg * (1.50 + (lvl * 0.10)))

    m_atk = monster.effective_attack
    m_def = monster.effective_defence

    # Correct formula — must mirror calculate_damage_taken exactly
    _base_raw = 5.0 + monster.level * 1.5
    _p_def_clamped = max(p_def, 1)
    _surplus = max(-0.95, (m_atk - _p_def_clamped) / _p_def_clamped)
    _DIFFICULTY_SURPLUS_MULT_LOG = [1.0, 1.2, 1.3, 1.4, 1.5]
    _surplus_mult = _DIFFICULTY_SURPLUS_MULT_LOG[monster.difficulty_level]
    raw_base = _base_raw * (1.0 + _surplus * _surplus_mult)

    # Phase 1: Use unified damage pools for theoretical max hit calculation
    monster.damage_increased_pct = 0.0
    monster.damage_more_mult = 1.0

    if monster.has_modifier("Savage"):
        monster.damage_increased_pct += monster.get_modifier_value("Savage")
    if monster.has_modifier("Hell's Fury"):
        monster.damage_increased_pct += 2.0   # +200% increased
    if monster.has_modifier("Overwhelming"):
        monster.damage_increased_pct += 1.0   # +100% increased
    if monster.has_modifier("Spectral"):
        monster.damage_increased_pct += 1.0   # on proc for max hit we assume it procs

    if monster.has_modifier("Inevitable"):
        monster.damage_more_mult = monster.get_modifier_value("Inevitable")

    # Apply unified multiplier to the raw base (before PDR/FDR for max theoretical)
    raw_base *= monster.get_total_damage_mult()

    pdr = player.get_total_pdr()
    if monster.has_modifier("Crushing"):
        pdr = max(0, int(pdr * (1 - monster.get_modifier_value("Crushing"))))
    fdr = player.get_total_fdr()
    if monster.has_modifier("Searing"):
        fdr = max(0, int(fdr * (1 - monster.get_modifier_value("Searing"))))

    m_max_dmg = max(0, int(raw_base * 1.15 * (1 - pdr / 100)) - fdr)

    _DIFF_NAMES_LOG = ["", "HARD", "EXTREME", "NIGHTMARISH", "DELIRIOUS"]
    hard_note = (
        f" [{_DIFF_NAMES_LOG[monster.difficulty_level]} MODE ×{_surplus_mult} surplus]"
        if monster.difficulty_level > 0 else ""
    )

    log.info(f"--- COMBAT DEBUG: {player.name} VS {monster.name} ---")
    log.info(
        f"PLAYER : HP {player.current_hp}/{player.max_hp} | Atk {p_atk} | Def {p_def} | "
        f"Ward {player.combat_ward} | Crit {p_crit}% | PDR {player.get_total_pdr()}% | FDR {player.get_total_fdr()}"
    )
    mod_display = ", ".join(monster.display_modifiers) if monster.modifiers else "None"
    log.info(
        f"MONSTER: HP {monster.hp}/{monster.max_hp} | Atk {m_atk} | Def {m_def} | Mods: {mod_display}"
        + hard_note
    )
    log.info(
        f"FORMULA: base={_base_raw:.1f} surplus={_surplus:+.3f} ×{_surplus_mult} → raw≈{raw_base:.1f}"
    )
    log.info(f"THEORETICAL MAX HIT -> Player: ~{p_max_dmg} | Monster: ~{m_max_dmg}{hard_note}")
    log.info("--------------------------------------------------")
