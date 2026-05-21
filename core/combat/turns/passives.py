import random
from typing import Dict

from core.combat.calc.calcs import fmt_weapon_passive, get_weapon_tier
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
    total_atk = player.get_total_attack()
    total_def = player.get_total_defence()
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
    return f"💰 **Unlimited Wealth** strikes gold! Rarity ×{mult} ({base:,} → {base * mult:,})"


def _cs_absorb(player, monster):
    if not player.equipped_accessory:
        return
    chance = player.equipped_accessory.passive_lvl * 0.10
    if random.random() <= chance:
        total = monster.attack + monster.defence
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
    # Deduct 90% of max HP from current HP, floor of 1 (max HP is unchanged)
    cost = int(player.total_max_hp * 0.9)
    player.current_hp = max(1, player.current_hp - cost)
    # Double the player's total attack via the combat-start multiplier
    player.atk_multiplier *= 2.0
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


def _cs_unravelling(player, monster):
    if monster.defence <= 0:
        return
    strip = int(monster.defence * 0.20)
    monster.defence = max(0, monster.defence - strip)
    return f"⬛ **Unravelling** strips {monster.name}'s 🛡️ DEF by **{strip}** (20%)"


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
            atk_red = max(1, int(monster.attack * lvl * 0.02))
            def_red = max(1, int(monster.defence * lvl * 0.02))
            monster.attack = max(0, monster.attack - atk_red)
            monster.defence = max(0, monster.defence - def_red)
            parts.append(
                f"**Monster Debuff Lv.{lvl}** — {monster.name} loses "
                f"**{atk_red}** ATK and **{def_red}** DEF"
            )
        elif key == "co_curse_damage":
            reduction = max(1, int(monster.attack * lvl * 0.02))
            monster.attack = max(0, monster.attack - reduction)
            parts.append(
                f"**Curse: Damage Lv.{lvl}** — {monster.name} loses **{reduction}** ATK 🩸"
            )
        elif key == "co_curse_taken":
            bonus = int(player.flat_atk * lvl * 0.02)
            player.bonus_atk += bonus
            parts.append(f"**Curse: Vulnerability Lv.{lvl}** — ⚔️ +{bonus} ATK")
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
                    buff_msgs.append(f"⚔️ +{bonus} ATK")
                elif i == 1:
                    ward = int(player.total_max_hp * 0.15)
                    player.combat_ward += ward
                    buff_msgs.append(f"🔮 +{ward} Ward")
                elif i == 2:
                    bonus = int(player.flat_def * 0.15)
                    player.bonus_def += bonus
                    buff_msgs.append(f"🛡️ +{bonus} DEF")
                elif i == 3:
                    player.lucifer_pdr_burst += 10
                    buff_msgs.append("🛡️ +10% PDR burst")
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
        logs["Void Passive"] = logs.get("Void Passive", "")  # ensure key exists for later merge

    if def_strip_pct > 0 and monster.defence > 0:
        flat = int(monster.defence * def_strip_pct)
        monster.defence = max(0, monster.defence - flat)
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
        flat = int(player.get_total_defence() * pct)
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
            logs["🩸 Hematurgy"] = "\n".join(hema_log)

    return logs
