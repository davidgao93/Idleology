import random
from typing import Dict

from core.combat.calc.calcs import fmt_weapon_passive, get_weapon_tier
from core.emojis import (
    GOLD_COIN,
    HEMATURGY_ICON,
    STAT_ATK,
    STAT_DEF,
    STAT_PDR,
    STAT_WARD,
)
from core.models import Monster, Player


# ---------------------------------------------------------------------------
# DEF → ATK Conversion Helper
# ---------------------------------------------------------------------------


def compute_def_as_atk_bonus(player: Player) -> tuple[int, list[str]]:
    """Computes the combined ATK bonus from all DEF→ATK conversion sources.

    All source percentages are additive: they are summed before being applied
    to `player.flat_def` (the pre-combat baseline, consistent with Wrath tome).

    Current sources:
    - Juggernaut helmet passive: lvl × 4% of flat DEF per level

    Returns (total_bonus, description_parts) for logging.
    Add new DEF→ATK sources here as the game expands.
    """
    flat_def = player.flat_def
    if flat_def <= 0:
        return 0, []

    total_pct = 0.0
    parts: list[str] = []

    # Juggernaut: helmet passive — lvl × 4% of flat DEF as bonus ATK
    if player.get_helmet_passive() == "juggernaut":
        lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
        if lvl > 0:
            pct = lvl * 4.0
            total_pct += pct
            parts.append(f"+{int(pct)}% DEF (Juggernaut Lv.{lvl})")

    # Future DEF→ATK sources go here (e.g., codex boons, equipment passives)

    if not parts:
        return 0, []

    bonus = int(flat_def * total_pct / 100)
    return bonus, parts


# ---------------------------------------------------------------------------
# Monster Stat Effects
# Applied once at combat start via apply_stat_effects().
# ---------------------------------------------------------------------------


def apply_stat_effects(player: Player, monster: Monster) -> None:
    """Applies monster modifiers that alter player/monster state at combat start."""
    # Dispelling: reduce player ward by 80% (aphrodite helmet is immune)
    if monster.has_modifier("Dispelling"):
        if player.get_helmet_corrupted_essence() != "aphrodite":
            player.combat_ward = int(player.combat_ward * 0.20)

    # Slayer Target Defence: +2% flat def per emblem tier vs the active slayer species.
    # Uses bonus_def so it stacks additively with companion +% def and all other sources.
    if player.active_task_species and player.active_task_species == monster.species:
        slayer_def_tiers = player.get_emblem_bonus("slayer_def")
        if slayer_def_tiers > 0:
            bonus = int(player.flat_def * slayer_def_tiers * 0.02)
            player.bonus_def += bonus


# ---------------------------------------------------------------------------
# Combat-Start Passive Handlers
# ---------------------------------------------------------------------------


def _cs_transcendence(player, monster):
    total_atk = player.get_total_attack(monster)
    total_def = player.get_total_defence(monster)
    bonus = int((total_atk + total_def) * 0.20)
    player.bonus_atk += bonus
    return f"**✨ Transcendence** channels your power! ⚔️ +**{bonus}** ATK (20% of total ATK+DEF)"


def _cs_unlimited_wealth(player, monster):
    if random.random() > 0.20:
        return
    base = player.get_total_rarity()
    if base <= 0:
        return
    mult = 2 if monster.is_boss else 5
    player.bonus_rarity += base * (mult - 1)
    return f"{GOLD_COIN} **Unlimited Wealth** strikes gold! Rarity ×{mult} ({base:,} → {base * mult:,})"


def _cs_absorb(player, monster):
    if not player.equipped_accessory:
        return
    chance = player.equipped_accessory.passive_lvl * 0.10
    if random.random() <= chance:
        total = monster.effective_attack + monster.effective_defence
        if total > 0:
            amount = max(1, int(total * 0.10))
            player.bonus_atk += amount
            player.bonus_def += amount
            return f"🌀 **Absorb** increases your ⚔️/🛡️ by +**{amount}**."


def _cs_juggernaut(player, monster):
    bonus, parts = compute_def_as_atk_bonus(player)
    if bonus <= 0:
        return
    player.bonus_atk += bonus
    return f"**🪖 Juggernaut** empowers your strikes! ⚔️ +**{bonus}** ATK ({', '.join(parts)})"


def _cs_inverted_edge(player, monster):
    if not player.equipped_weapon:
        return
    wep_atk, wep_def = player.equipped_weapon.attack, player.equipped_weapon.defence
    player.equipped_weapon.attack = wep_def
    player.equipped_weapon.defence = wep_atk
    return f"🔥 **Inverted Edge**: weapon ATK ↔ DEF swapped ({wep_atk} ↔ {wep_def})."


def _cs_gilded_hunger(player, monster):
    # Applied after all rarity sources are summed (equipment + companions + bonuses)
    bonus = int(player.get_total_rarity() * 0.1)
    if bonus > 0:
        player.bonus_atk += bonus
        return f"🔥 **Gilded Hunger** devours rarity! ⚔️ +**{bonus}** ATK"


def _cs_diabolic_pact(player, monster):
    # Deduct 50% of max HP from current HP, floor of 1 (max HP is unchanged)
    cost = int(player.total_max_hp * 0.5)
    player.current_hp = max(1, player.current_hp - cost)
    # +100% ATK via the shared additive atk_multiplier pool (sums with any other
    # ATK % source active this combat — Codex boons, Apex zone bonus, Enrage, etc.)
    player.atk_multiplier += 1.0
    return f"🔥 **Diabolic Pact** sealed in blood! 💀 -{cost} HP → ⚔️ ATK doubled!"


def _cs_cursed_precision(player, monster):
    player.bonus_crit += 20
    player.cursed_precision_active = True
    return "🔥 **Cursed Precision**: 🎯 Crit chance greatly increased, but crits roll for the lower result."


def _cs_entropy(player, monster):
    if not player.equipped_weapon:
        return
    atk_t = int(player.equipped_weapon.attack * 0.20)
    def_t = int(player.equipped_weapon.defence * 0.20)
    player.equipped_weapon.attack = player.equipped_weapon.attack - atk_t + def_t
    player.equipped_weapon.defence = player.equipped_weapon.defence - def_t + atk_t
    return f"⬛ **Entropy** warps the weapon! 20% ATK↔DEF transferred (±{atk_t} ATK / ±{def_t} DEF)"


def _cs_void_echo(player, monster):
    if not player.equipped_weapon:
        return
    bonus = int(player.equipped_weapon.attack * 0.15)
    if bonus > 0:
        player.bonus_atk += bonus
        return f"⬛ **Void Echo** resonates! ⚔️ +**{bonus}** ATK (15% of weapon ATK)"


_ARMOR_START_HANDLERS: dict[str, callable] = {
    "Transcendence": _cs_transcendence,
    "Unlimited Wealth": _cs_unlimited_wealth,
}
_ACCESSORY_START_HANDLERS: dict[str, callable] = {
    "Absorb": _cs_absorb,
}
_HELMET_START_HANDLERS: dict[str, callable] = {
    "juggernaut": _cs_juggernaut,
}
_INFERNAL_START_HANDLERS: dict[str, callable] = {
    # inverted_edge is NOT here — it is fired first in apply_combat_start_passives
    # so that all conversion passives (Transcendence, Juggernaut, Wrath, etc.) see
    # the already-swapped weapon values.
    "gilded_hunger": _cs_gilded_hunger,
    "diabolic_pact": _cs_diabolic_pact,
    "cursed_precision": _cs_cursed_precision,
}
_VOID_START_HANDLERS: dict[str, callable] = {
    "entropy": _cs_entropy,
    "void_echo": _cs_void_echo,
    # unravelling is NOT here — it is combined with Debilitate in apply_combat_start_passives
    # so that both sources apply additively from the same original defence value.
}


def _apply_partner_combat_start(
    player: Player, monster: Monster, logs: Dict[str, str]
) -> None:
    """Applies active combat partner's combat-start skill effects."""
    partner = player.active_partner
    if not partner:
        return

    parts = []

    for key, lvl in partner.combat_skills:
        if not key:
            continue
        if key == "co_stat_transfer":
            atk_bonus = int(partner.total_attack * lvl * 0.10)
            def_bonus = int(partner.total_defence * lvl * 0.10)
            hp_bonus = int(partner.total_hp * lvl * 0.10)
            player.bonus_atk += atk_bonus
            player.bonus_def += def_bonus
            player.bonus_max_hp += hp_bonus
            parts.append(
                f"**Stat Transfer Lv.{lvl}** — ⚔️ +{atk_bonus} ATK, "
                f"🛡️ +{def_bonus} DEF, ❤️ +{hp_bonus} Max HP"
            )
        elif key == "co_atk_from_def":
            bonus = int(partner.total_defence * lvl * 0.25)
            player.bonus_atk += bonus
            parts.append(
                f"**Def→Atk Lv.{lvl}** — ⚔️ +{bonus} ATK (from {partner.name}'s DEF)"
            )
        elif key == "co_def_from_atk":
            bonus = int(partner.total_attack * lvl * 0.20)
            player.bonus_def += bonus
            parts.append(
                f"**Atk→Def Lv.{lvl}** — 🛡️ +{bonus} DEF (from {partner.name}'s ATK)"
            )
        elif key == "co_monster_debuff":
            atk_red = max(1, int(monster.effective_attack * lvl * 0.02))
            def_red = max(1, int(monster.effective_defence * lvl * 0.02))
            monster.flat_attack_reduction += atk_red
            monster.flat_defence_reduction += def_red
            parts.append(
                f"**Monster Debuff Lv.{lvl}** — {monster.name} loses "
                f"**{atk_red}** ATK and **{def_red}** DEF"
            )
        elif key == "co_curse_damage":
            reduction = max(1, int(monster.effective_attack * lvl * 0.02))
            monster.flat_attack_reduction += reduction
            parts.append(
                f"**Curse: Damage Lv.{lvl}** — {monster.name} loses **{reduction}** ATK 🩸"
            )
        elif key == "co_curse_taken":
            parts.append(
                f"**Curse: Taken Lv.{lvl}** — {monster.name} cursed! Your damage dealt is increased by {lvl * 2}% 🩸"
            )
        elif key == "co_special_rarity":
            player.partner_special_rarity = lvl * 0.1
            parts.append(
                f"**Special Find Lv.{lvl}** — +{lvl * 0.1:.1f}% special drop rate"
            )

    sig_key = partner.sig_combat_key
    sig_lvl = partner.sig_combat_lvl
    if sig_key and sig_lvl >= 1:
        if sig_key == "sig_co_skol":
            from core.partners.mechanics import _SKOL_SIG_BUFFS

            n = _SKOL_SIG_BUFFS.get(sig_lvl, 1)
            buff_indices = random.sample(range(4), min(n, 4))
            buff_msgs = []
            for i in buff_indices:
                if i == 0:
                    bonus = int(player.flat_atk * 0.15)
                    player.bonus_atk += bonus
                    buff_msgs.append(f"{STAT_ATK} +{bonus} ATK")
                elif i == 1:
                    ward = int(player.total_max_hp * 0.15)
                    player.combat_ward += ward
                    buff_msgs.append(f"{STAT_WARD} +{ward} Ward")
                elif i == 2:
                    bonus = int(player.flat_def * 0.15)
                    player.bonus_def += bonus
                    buff_msgs.append(f"{STAT_DEF} +{bonus} DEF")
                elif i == 3:
                    player.lucifer_pdr_burst += 10
                    buff_msgs.append(f"{STAT_PDR} +10% PDR burst")
            parts.append(
                f"💀 **Essence Communion Lv.{sig_lvl}** — "
                f"{n} essence buff(s): {', '.join(buff_msgs)}"
            )
        elif sig_key == "sig_co_yvenn":
            player.active_task_species = monster.species
            parts.append(
                f"🗡️ **Apex Hunter Lv.{sig_lvl}** — "
                f"All monsters treated as slayer targets!"
            )

    if parts:
        logs[f"🤝 {partner.name}"] = "\n".join(parts)


def apply_combat_start_passives(player: Player, monster: Monster) -> Dict[str, str]:
    """Applies player passives that trigger at the start of combat. Returns UI log strings."""
    player.is_invulnerable_this_combat = False
    logs: Dict[str, str] = {}

    # Artefact: Sad One's Gamble — d6 rolled once at combat start.
    if player.has_artefact("sad_ones_gamble"):
        import random as _random

        player.gamble_roll = _random.randint(1, 6)
        if player.gamble_roll == 1:
            logs["Artefact"] = (
                "🎲 **Sad One's Gamble** rolls a 1 — no effect this combat."
            )
        elif player.gamble_roll == 6:
            logs["Artefact"] = (
                "🎲 **Sad One's Gamble** rolls a 6 — Unlucky effects become Lucky, "
                "and Lucky effects roll 3x!"
            )
        else:
            logs["Artefact"] = (
                f"🎲 **Sad One's Gamble** rolls a {player.gamble_roll} — "
                "Unlucky effects become Lucky!"
            )

    def _dispatch(registry, key, log_key):
        handler = registry.get(key)
        if handler and (msg := handler(player, monster)):
            logs[log_key] = msg

    # Inverted Edge fires first — before all conversion passives (Transcendence,
    # Juggernaut, Wrath tome, etc.) so they all see the already-swapped weapon values.
    if player.get_weapon_infernal() == "inverted_edge":
        msg = _cs_inverted_edge(player, monster)
        if msg:
            logs["Infernal Passive"] = msg

    _dispatch(_ARMOR_START_HANDLERS, player.get_armor_passive(), "Armor Passive")
    _dispatch(
        _ACCESSORY_START_HANDLERS, player.get_accessory_passive(), "Accessory Passive"
    )
    _dispatch(_HELMET_START_HANDLERS, player.get_helmet_passive(), "Helmet Passive")
    _dispatch(
        _INFERNAL_START_HANDLERS, player.get_weapon_infernal(), "Infernal Passive"
    )
    _dispatch(_VOID_START_HANDLERS, player.get_accessory_void_passive(), "Void Passive")

    weapon_parts = []

    # --- Monster DEF reduction: Debilitate + Unravelling stack ADDITIVELY ---
    # Both percentages are summed before applying to the original defence value.
    def_strip_pct = 0.0
    def_strip_parts: list[str] = []

    idx, name = get_weapon_tier(player, "debilitate")
    if idx >= 0:
        pct = (idx + 1) * 0.08
        def_strip_pct += pct
        def_strip_parts.append(f"💫 **{fmt_weapon_passive(name)}** ({int(pct * 100)}%)")

    if player.get_accessory_void_passive() == "unravelling":
        def_strip_pct += 0.20
        def_strip_parts.append("⬛ **Unravelling** (20%)")
        logs["Void Passive"] = logs.get(
            "Void Passive", ""
        )  # ensure key exists for later merge

    if def_strip_pct > 0 and monster.effective_defence > 0:
        flat = int(monster.effective_defence * def_strip_pct)
        monster.flat_defence_reduction += flat
        if len(def_strip_parts) == 1:
            weapon_parts.append(
                f"{def_strip_parts[0]}: strips {monster.name}'s 🛡️ DEF by **{flat}** ({int(def_strip_pct * 100)}%)"
            )
        else:
            sources = " + ".join(def_strip_parts)
            weapon_parts.append(
                f"{sources}: strips {monster.name}'s 🛡️ DEF by **{flat}** ({int(def_strip_pct * 100)}% combined)"
            )
        # If unravelling was the only void passive, clear the placeholder log key
        void_p = player.get_accessory_void_passive()
        if void_p == "unravelling" and logs.get("Void Passive") == "":
            del logs["Void Passive"]

    idx, name = get_weapon_tier(player, "sturdy")
    if idx >= 0:
        pct = (idx + 1) * 0.08
        flat = int(player.get_total_defence(monster) * pct)
        player.bonus_def += flat
        weapon_parts.append(
            f"🛡️ **{fmt_weapon_passive(name)}**: defence boosted by **{flat}** ({int(pct * 100)}%)"
        )

    if weapon_parts:
        logs["Weapon Passive"] = "\n".join(weapon_parts)

    _apply_partner_combat_start(player, monster, logs)

    # --- Hematurgy: Ward Inoculation start effect (runs last, after ward is settled) ---
    if player.hematurgy_passives:
        from core.hematurgy.engine import apply_hematurgy_start

        hema_log: list[str] = []
        apply_hematurgy_start(player, monster, hema_log)
        if hema_log:
            logs[f"{HEMATURGY_ICON} Hematurgy"] = "\n".join(hema_log)

    # --- Soul Stone combat-start passives ---
    if player.soul_stone:
        ss_log = _apply_soul_stone_start(player, monster)
        if ss_log:
            logs["💎 Soul Stone"] = "\n".join(ss_log)

    return logs


def _apply_soul_stone_start(player, monster) -> list[str]:
    """Applies soul stone passives that trigger once at combat start."""
    from core.apex.mechanics import ApexMechanics
    from core.apex.data import SOUL_STONE_TIER_VALUES as _SST

    log: list[str] = []

    # Transcendence (soul stone): T1=4% → T5=20% of (ATK+DEF) as bonus ATK
    ss_transcendence = player.get_soul_stone_passive("transcendence")
    if ss_transcendence and not (
        player.equipped_armor and player.equipped_armor.passive == "Transcendence"
    ):
        pct = _SST["transcendence"][ss_transcendence - 1]
        total_atk = player.get_total_attack(monster)
        total_def = player.get_total_defence(monster)
        bonus = int((total_atk + total_def) * pct / 100)
        player.bonus_atk += bonus
        log.append(
            f"✨ **Soul Transcendence T{ss_transcendence}** — "
            f"⚔️ +**{bonus}** ATK ({pct}% of ATK+DEF)"
        )

    # Juggernaut (soul stone): T1=4% → T5=20% of flat DEF as bonus ATK
    ss_juggernaut = player.get_soul_stone_passive("juggernaut")
    if ss_juggernaut and not (
        player.equipped_helmet and player.get_helmet_passive() == "juggernaut"
    ):
        pct = ss_juggernaut * 4.0
        bonus = int(player.flat_def * pct / 100)
        if bonus > 0:
            player.bonus_atk += bonus
            log.append(
                f"🪖 **Soul Juggernaut T{ss_juggernaut}** — ⚔️ +**{bonus}** ATK ({int(pct)}% of DEF)"
            )

    # Unlimited Wealth (soul stone): 20% chance for T1=+40% → T5=+200% rarity
    ss_unlimited = player.get_soul_stone_passive("unlimited wealth")
    if ss_unlimited and not (
        player.equipped_armor and player.equipped_armor.passive == "Unlimited Wealth"
    ):
        if random.random() < 0.20:
            base = player.get_total_rarity()
            if base > 0:
                bonus_pct = _SST["unlimited wealth"][ss_unlimited - 1]
                bonus = int(base * bonus_pct / 100)
                player.bonus_rarity += bonus
                log.append(
                    f"{GOLD_COIN} **Soul Unlimited Wealth T{ss_unlimited}** — "
                    f"+{bonus_pct}% Rarity! (+{bonus})"
                )

    # Absorb (soul stone): 2:1 tier mapping → T1=20% chance → T5=100% chance
    ss_absorb = player.get_soul_stone_passive("absorb")
    if ss_absorb and not (
        player.equipped_accessory and player.get_accessory_passive() == "Absorb"
    ):
        equiv_lvl = ss_absorb * 2
        if random.random() <= equiv_lvl * 0.10:
            total = monster.effective_attack + monster.effective_defence
            if total > 0:
                amount = max(1, int(total * 0.10))
                player.bonus_atk += amount
                player.bonus_def += amount
                log.append(f"🌀 **Soul Absorb T{ss_absorb}** — ⚔️/🛡️ +**{amount}** each.")

    # Treasure Hunter (soul stone): T1=+0.6 → T5=+3.0 special rarity
    ss_treasure = player.get_soul_stone_passive("treasure hunter")
    if ss_treasure and not (
        player.equipped_armor and player.equipped_armor.passive == "Treasure Hunter"
    ):
        bonus = _SST["treasure hunter"][ss_treasure - 1]
        player.bonus_rarity += bonus
        log.append(
            f"🗺️ **Soul Treasure Hunter T{ss_treasure}** — +**{bonus:.1f}** Special Rarity"
        )

    # Tyr Resonance (mixed_2 or mixed_3): redistribute ATK+DEF at combat start
    if player.soul_stone:
        res = ApexMechanics.get_resonance_multipliers(player.soul_stone)
        tyr_pct = res.get("tyr_pct", 0.0)
        if tyr_pct > 0:
            # Current effective totals (after all other bonuses)
            cur_atk = player.get_total_attack(monster)
            cur_def = player.get_total_defence(monster)
            combined = int((cur_atk + cur_def) * (1 + tyr_pct))
            half = combined // 2
            # Bonus needed: (half - cur_atk) added as bonus_atk, etc.
            atk_bonus = max(0, half - cur_atk)
            def_bonus = max(0, half - cur_def)
            if atk_bonus > 0:
                player.bonus_atk += atk_bonus
            if def_bonus > 0:
                player.bonus_def += def_bonus
            res_name = "Tyr's Adjudication" if tyr_pct >= 0.20 else "Tyr's Ruling"
            log.append(
                f"⚖️ **{res_name}** — ATK+DEF combined +{int(tyr_pct * 100)}%, redistributed equally!"
            )

    return log
