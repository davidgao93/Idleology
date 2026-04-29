import random
from typing import Dict

from core.combat.calcs import get_weapon_tier
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

    idx, name = get_weapon_tier(player, "polished")
    if idx >= 0:
        pct = (idx + 1) * 0.08
        flat = int(monster.defence * pct)
        monster.defence = max(0, monster.defence - flat)
        weapon_parts.append(
            f"💫 **{name}**: strips {monster.name}'s 🛡️ DEF by **{flat}** ({int(pct * 100)}%)"
        )

    idx, name = get_weapon_tier(player, "sturdy")
    if idx >= 0:
        pct = (idx + 1) * 0.08
        flat = int(player.get_total_defence() * pct)
        player.bonus_def += flat
        weapon_parts.append(
            f"🛡️ **{name}**: defence boosted by **{flat}** ({int(pct * 100)}%)"
        )

    if weapon_parts:
        logs["Weapon Passive"] = "\n".join(weapon_parts)

    return logs
