import random
from typing import Dict

from core.combat.calcs import fmt_weapon_passive, get_weapon_tier
from core.combat.helpers import _add_ward
from core.models import Monster, Player

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


# ---------------------------------------------------------------------------
# Combat-Start Passive Handlers
# ---------------------------------------------------------------------------


def _cs_invulnerable(player, monster):
    if random.random() < 0.2:
        player.is_invulnerable_this_combat = True
        return (
            f"**🛡️ Invulnerable** activates! {player.name} receives divine protection."
        )


def _cs_omnipotent(player, monster):
    if random.random() < 0.5:
        total_atk = player.get_total_attack()
        total_def = player.get_total_defence()
        player.bonus_atk += total_atk
        player.bonus_def += total_def
        ward_added = _add_ward(player, player.total_max_hp, [], "Omnipotent")
        return f"**🛡️ Omnipotent** increases your ⚔️ +**{total_atk}** ATK, 🛡️ +**{total_def}** DEF, and 🔮 +**{ward_added}** Ward."


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
    lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if lvl <= 0:
        return
    bonus = int(player.get_total_defence() * (lvl * 0.04))
    player.bonus_atk += bonus
    return f"**🪖 Juggernaut** empowers your strikes! ⚔️ +**{bonus}** ATK"


def _cs_inverted_edge(player, monster):
    if not player.equipped_weapon:
        return
    wep_atk, wep_def = player.equipped_weapon.attack, player.equipped_weapon.defence
    player.equipped_weapon.attack = wep_def
    player.equipped_weapon.defence = wep_atk
    return f"🔥 **Inverted Edge**: weapon ATK ↔ DEF swapped ({wep_atk} ↔ {wep_def})."


def _cs_gilded_hunger(player, monster):
    if not player.equipped_weapon:
        return
    bonus = int(player.equipped_weapon.rarity * 0.1)
    if bonus > 0:
        player.bonus_atk += bonus
        return f"🔥 **Gilded Hunger** devours rarity! ⚔️ +**{bonus}** ATK"


def _cs_diabolic_pact(player, monster):
    cost = int(player.total_max_hp * 0.9)
    player.bonus_max_hp -= cost
    if player.current_hp > player.total_max_hp:
        player.current_hp = player.total_max_hp
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
    if not player.equipped_accessory:
        return
    bonus = int(player.equipped_weapon.attack * 0.15)
    if bonus > 0:
        player.equipped_accessory.attack += bonus
        return f"⬛ **Void Echo** resonates! Accessory ⚔️ +**{bonus}** ATK"


def _cs_unravelling(player, monster):
    if monster.defence <= 0:
        return
    strip = int(monster.defence * 0.20)
    monster.defence = max(0, monster.defence - strip)
    return f"⬛ **Unravelling** strips {monster.name}'s 🛡️ DEF by **{strip}** (20%)"


_ARMOR_START_HANDLERS: dict[str, callable] = {
    "Invulnerable": _cs_invulnerable,
    "Omnipotent": _cs_omnipotent,
}
_ACCESSORY_START_HANDLERS: dict[str, callable] = {
    "Absorb": _cs_absorb,
}
_HELMET_START_HANDLERS: dict[str, callable] = {
    "juggernaut": _cs_juggernaut,
}
_INFERNAL_START_HANDLERS: dict[str, callable] = {
    "inverted_edge": _cs_inverted_edge,
    "gilded_hunger": _cs_gilded_hunger,
    "diabolic_pact": _cs_diabolic_pact,
    "cursed_precision": _cs_cursed_precision,
}
_VOID_START_HANDLERS: dict[str, callable] = {
    "entropy": _cs_entropy,
    "void_echo": _cs_void_echo,
    "unravelling": _cs_unravelling,
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
            parts.append(f"**Def→Atk Lv.{lvl}** — ⚔️ +{bonus} ATK (from {partner.name}'s DEF)")
        elif key == "co_def_from_atk":
            bonus = int(partner.total_attack * lvl * 0.20)
            player.bonus_def += bonus
            parts.append(f"**Atk→Def Lv.{lvl}** — 🛡️ +{bonus} DEF (from {partner.name}'s ATK)")
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
            parts.append(f"**Curse: Damage Lv.{lvl}** — {monster.name} loses **{reduction}** ATK 🩸")
        elif key == "co_curse_taken":
            bonus = int(player.flat_atk * lvl * 0.02)
            player.bonus_atk += bonus
            parts.append(f"**Curse: Vulnerability Lv.{lvl}** — ⚔️ +{bonus} ATK")
        elif key == "co_special_rarity":
            player.partner_special_rarity = lvl * 0.1
            parts.append(f"**Special Find Lv.{lvl}** — +{lvl * 0.1:.1f}% special drop rate")

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
                f"💀 **Skol's Sig Lv.{sig_lvl}** — "
                f"{n} essence buff(s): {', '.join(buff_msgs)}"
            )
        elif sig_key == "sig_co_yvenn":
            player.active_task_species = monster.species
            parts.append(
                f"🗡️ **Yvenn's Sig Lv.{sig_lvl}** — "
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

    idx, name = get_weapon_tier(player, "debilitate")
    if idx >= 0:
        pct = (idx + 1) * 0.08
        flat = int(monster.defence * pct)
        monster.defence = max(0, monster.defence - flat)
        weapon_parts.append(
            f"💫 **{fmt_weapon_passive(name)}**: strips {monster.name}'s 🛡️ DEF by **{flat}** ({int(pct * 100)}%)"
        )

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

    return logs
