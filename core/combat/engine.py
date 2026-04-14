import logging
import random
from dataclasses import dataclass
from typing import Dict

from core.combat.calcs import (
    calculate_damage_taken,
    calculate_hit_chance,
    calculate_monster_hit_chance,
    get_weapon_tier,
)
from core.models import Monster, Player

logger = logging.getLogger("discord_bot")


# ---------------------------------------------------------------------------
# Turn Result Types
#
# Both turn functions return a result dataclass rather than a plain str.
# __str__ returns the log so all existing callers that store the result as a
# Discord embed field value continue to work without modification.
# The numeric fields are used by DummyEngine to collect simulation stats
# without duplicating any combat logic.
# ---------------------------------------------------------------------------


@dataclass
class PlayerTurnResult:
    log: str
    damage: int  # actual damage dealt to monster this turn (0 on full miss/block)
    is_hit: bool  # True for both normal hits and crits
    is_crit: bool  # True only for crits (subset of is_hit)

    def __str__(self) -> str:
        return self.log


@dataclass
class MonsterTurnResult:
    log: str
    hp_damage: (
        int  # net HP lost by the player this turn (0 if dodged/blocked/invulnerable)
    )

    def __str__(self) -> str:
        return self.log


# ---------------------------------------------------------------------------
# Ward addition helper
# All combat_ward increments should go through this so the NEET helmet
# corrupted essence (ward gains doubled) is applied consistently.
# ---------------------------------------------------------------------------


def _add_ward(player: Player, amount: int, log: list, label: str = "") -> int:
    """
    Adds ward to the player, doubling if the NEET helmet corrupted essence is active.
    Returns the final amount added. Logs only if label is provided.
    """
    if amount <= 0:
        return 0
    if player.get_helmet_corrupted_essence() == "neet":
        amount *= 2
        if label:
            log.append(
                f"🌑 **Void Resonance** doubles ward gain! ({label}: +{amount} 🔮)"
            )
    player.combat_ward += amount
    return amount


# ---------------------------------------------------------------------------
# Monster Stat Effects
# Applied once at combat start via apply_stat_effects().
# ---------------------------------------------------------------------------

_MONSTER_STAT_EFFECTS: dict[str, callable] = {
    "Shield-breaker": lambda p, m: setattr(p, "combat_ward", 0),
    "Impenetrable": lambda p, m: setattr(
        p, "base_crit_chance", max(0, p.base_crit_chance - 5)
    ),
    "Enfeeble": lambda p, m: setattr(p, "base_attack", int(p.base_attack * 0.9)),
}


def apply_stat_effects(player: Player, monster: Monster) -> None:
    """Applies monster modifiers that alter player stats at the start of combat."""
    for modifier in monster.modifiers:
        if modifier in _MONSTER_STAT_EFFECTS:
            # Aphrodite helmet: ward cannot be forcibly disabled by monster modifiers
            if (
                modifier == "Shield-breaker"
                and player.get_helmet_corrupted_essence() == "aphrodite"
            ):
                continue
            _MONSTER_STAT_EFFECTS[modifier](player, monster)


# ---------------------------------------------------------------------------
# Combat-Start Passive Handlers
#
# Source slots covered:
#   Armor       → get_armor_passive()
#   Accessory   → get_accessory_passive()
#   Helmet      → get_helmet_passive()
#   Infernal    → get_weapon_infernal()
#   Void        → get_accessory_void_passive()
#   Weapon tier → get_weapon_passive() / get_weapon_pinnacle() / get_weapon_utmost()
#                 (polished and sturdy families only; all others apply mid-turn)
#
# Each handler receives (player, monster) and returns a log string or None.
# ---------------------------------------------------------------------------


def _cs_invulnerable(player, monster):
    if random.random() < 0.2:
        player.is_invulnerable_this_combat = True
        return f"**Invulnerable** armor activates! {player.name} receives divine protection."


def _cs_omnipotent(player, monster):
    if random.random() < 0.5:
        total_atk = player.get_total_attack()
        total_def = player.get_total_defence()
        player.base_attack += total_atk
        player.base_defence += total_def
        ward_added = _add_ward(player, player.max_hp, [], "Omnipotent")
        return (
            f"**Omnipotent** empowers you! "
            f"⚔️ +**{total_atk}** ATK, 🛡️ +**{total_def}** DEF, 🔮 +**{ward_added}** Ward"
        )


def _cs_absorb(player, monster):
    if not player.equipped_accessory:
        return
    chance = player.equipped_accessory.passive_lvl * 0.10
    if random.random() <= chance:
        total = monster.attack + monster.defence
        if total > 0:
            amount = max(1, int(total * 0.10))
            player.base_attack += amount
            player.base_defence += amount
            return (
                f"🌀 **Absorb ({player.equipped_accessory.passive_lvl})** activates! "
                f"⚔️ +**{amount}** ATK, 🛡️ +**{amount}** DEF"
            )


def _cs_juggernaut(player, monster):
    lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if lvl <= 0:
        return
    bonus = int(player.get_total_defence() * (lvl * 0.04))
    player.base_attack += bonus
    return f"**Juggernaut ({lvl})** empowers your strikes! ⚔️ +**{bonus}** ATK"


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
        player.base_attack += bonus
        return f"🔥 **Gilded Hunger** devours rarity! ⚔️ +**{bonus}** ATK"


def _cs_diabolic_pact(player, monster):
    cost = int(player.max_hp * 0.9)
    player.max_hp = max(1, player.max_hp - cost)
    if player.current_hp > player.max_hp:
        player.current_hp = player.max_hp
    player.base_attack *= 2
    return f"🔥 **Diabolic Pact** sealed in blood! 💀 -{cost} HP → ⚔️ ATK doubled!"


def _cs_cursed_precision(player, monster):
    player.base_crit_chance += 20
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

    # Tiered weapon passives that resolve at combat start
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
        player.base_defence += flat
        weapon_parts.append(
            f"🛡️ **{name}**: defence boosted by **{flat}** ({int(pct * 100)}%)"
        )

    if weapon_parts:
        logs["Weapon Passive"] = "\n".join(weapon_parts)

    return logs


# ---------------------------------------------------------------------------
# Healing
# ---------------------------------------------------------------------------


def process_heal(player: Player, monster=None) -> str:
    """Handles the logic of a player using a potion.
    Pass *monster* so venomous_tincture can deal damage to it.
    """
    if player.potions <= 0:
        return f"{player.name} has no potions left to use!"

    if player.current_hp >= player.max_hp:
        return f"{player.name} is already full HP!"

    heal_pct = 0.30
    if player.equipped_boot and player.equipped_boot.passive == "cleric":
        heal_pct += player.equipped_boot.passive_lvl * 0.10

    potion_passives_by_type = {
        p["passive_type"]: p["passive_value"] for p in player.potion_passives
    }

    # --- Alchemy: Fermented Brew (bonus heal %) ---
    fermented = potion_passives_by_type.get("fermented_brew", 0)
    if fermented:
        heal_pct += fermented / 100.0

    heal_amount = int((player.max_hp * heal_pct) + random.randint(1, 6))

    # --- Alchemy: Unstable Mixture (50% double / 50% halve) ---
    if potion_passives_by_type.get("unstable_mixture"):
        if random.random() < 0.5:
            heal_amount *= 2
            _unstable_result = "doubled"
        else:
            heal_amount = max(1, heal_amount // 2)
            _unstable_result = "halved"
    else:
        _unstable_result = None

    if player.apothecary_workers > 0:
        flat_bonus = int(player.apothecary_workers * 0.2)
        heal_amount += flat_bonus

    # --- Overcap Brew: can we store overheal as temp HP? ---
    overcap = potion_passives_by_type.get("overcap_brew", 0)
    overcap_cap = int(player.max_hp * (overcap / 100.0)) if overcap else 0

    potential_hp = player.current_hp + heal_amount
    overheal = 0
    if potential_hp > player.max_hp:
        excess = potential_hp - player.max_hp
        helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
        overheal = excess * helmet_lvl  # Divine helmet

        if overcap_cap > 0:
            stored = min(excess, overcap_cap)
            player.alchemy_overcap_hp = stored
        player.current_hp = player.max_hp
    else:
        player.current_hp = potential_hp

    player.potions -= 1

    msg = f"{player.name} uses a potion and heals for **{heal_amount - overheal}** HP!"
    if player.apothecary_workers > 0:
        msg += f" (Apothecary: +{int(player.apothecary_workers * 0.2)})"

    if _unstable_result:
        icon = "🌀" if _unstable_result == "doubled" else "🌀"
        msg += f"\n🌀 **Unstable Mixture** — heal was {_unstable_result}!"

    if player.get_helmet_passive() == "divine" and overheal > 0:
        added = _add_ward(player, overheal, [], "Divine")
        msg += f"\n**Divine** converts **{added}** overheal into 🔮 Ward!"

    if overcap_cap > 0 and getattr(player, "alchemy_overcap_hp", 0) > 0:
        msg += (
            f"\n💥 **Overcap Brew** — stored **{player.alchemy_overcap_hp}** temp HP!"
        )

    # --- Alchemy: Ward Infusion (% of heal amount as Ward) ---
    ward_inf = potion_passives_by_type.get("ward_infusion", 0)
    if ward_inf:
        ward_gain = int(heal_amount * (ward_inf / 100.0))
        added = _add_ward(player, ward_gain, [], "Ward Infusion")
        msg += f"\n🔮 **Ward Infusion** generates **{added}** Ward!"

    # --- Alchemy: Lingering Remedy ---
    linger = potion_passives_by_type.get("lingering_remedy", 0)
    if linger:
        player.alchemy_linger_hp = int(linger)
        player.alchemy_linger_turns = 3
        msg += f"\n🌿 **Lingering Remedy** — +{player.alchemy_linger_hp} HP/turn for 3 turns!"

    # --- Alchemy: Bottled Courage ---
    if potion_passives_by_type.get("bottled_courage"):
        player.alchemy_guaranteed_hit = True
        msg += "\n⚔️ **Bottled Courage** — your next attack cannot miss!"

    # --- Alchemy: Warrior's Draft (next attack only) ---
    draft = potion_passives_by_type.get("warriors_draft", 0)
    if draft:
        player.alchemy_atk_boost_pct = draft / 100.0
        msg += f"\n💪 **Warrior's Draft** — +{draft:.0f}% ATK on next attack!"

    # --- Alchemy: Iron Skin (+DEF for 2 monster turns) ---
    iron = potion_passives_by_type.get("iron_skin", 0)
    if iron:
        player.alchemy_def_boost_pct = iron / 100.0
        player.alchemy_def_boost_turns = 2
        msg += f"\n🛡️ **Iron Skin** — +{iron:.0f}% DEF for 2 monster turns!"

    # --- Alchemy: Dulled Pain (next monster attack) ---
    dulled = potion_passives_by_type.get("dulled_pain", 0)
    if dulled:
        player.alchemy_dmg_reduction_pct = dulled / 100.0
        player.alchemy_dmg_reduction_turns = 1
        msg += f"\n🩹 **Dulled Pain** — -{dulled:.0f}% damage from next monster attack!"

    # --- Alchemy: Venom Cure (deal N× heal as damage) ---
    venom_mult = potion_passives_by_type.get("venom_cure", 0)
    if venom_mult and monster is not None and monster.hp > 0:
        venom_dmg = int(heal_amount * venom_mult)
        monster.hp = max(0, monster.hp - venom_dmg)
        msg += (
            f"\n🐍 **Venom Cure** courses through the enemy for **{venom_dmg}** damage!"
        )

    msg += f"\n**{player.potions}** potions left."
    return msg


# ---------------------------------------------------------------------------
# Player Turn — Phase Helpers
#
# Each helper appends its own messages to `log` and returns a value needed
# by the next phase. process_player_turn() calls them in sequence.
#
# Source slots active during the player turn:
#   Glove       → get_glove_passive()                (multiplier, hit floors, ward gen, pending)
#   Accessory   → get_accessory_passive()            (multiplier, hit roll)
#   Armor       → get_armor_passive()                (multiplier)
#   Helmet      → get_helmet_passive()               (multiplier, crit dmg, leech)
#   Infernal    → get_weapon_infernal()              (crit stack, miss dmg, crit triggers)
#   Void        → get_accessory_void_passive()       (crit triggers, miss dmg)
#   Weapon tier → get_weapon_tier(player, family)    (accuracy, crit, burn, spark, echo, poison, cull)
#   Emblem      → get_emblem_bonus(key)              (multiplier, accuracy, crit dmg)
#   Codex tomes → get_tome_bonus(key)               (bloodthirst)
#   Celestial   → get_celestial_armor_passive()      (ghostreaver ward regen)
# ---------------------------------------------------------------------------


def _pt_attack_multiplier(player: Player, monster: Monster, log: list[str]) -> float:
    """Phase 1 — compute the pre-hit attack multiplier from emblems and passive sources."""
    mult = 1.0

    if not monster.is_boss:
        tiers = player.get_emblem_bonus("combat_dmg")
        if tiers > 0:
            mult *= 1 + tiers * 0.02
    if monster.is_boss:
        tiers = player.get_emblem_bonus("boss_dmg")
        if tiers > 0:
            mult *= 1 + tiers * 0.05
    if player.active_task_species == monster.species:
        tiers = player.get_emblem_bonus("slayer_dmg")
        if tiers > 0:
            mult *= 1 + tiers * 0.05

    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    if glove_passive == "instability" and glove_lvl > 0:
        if random.random() < 0.5:
            mult *= 0.5
        else:
            mult *= 1.50 + (glove_lvl * 0.10)
        log.append(
            f"**Instability ({glove_lvl})** gives you {int(mult * 100)}% damage."
        )

    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0
    if acc_passive == "Obliterate" and random.random() <= (acc_lvl * 0.02):
        log.append(f"**Obliterate ({acc_lvl})** activates, doubling 💥 damage dealt!")
        mult *= 2.0

    if player.get_armor_passive() == "Mystical Might" and random.random() < 0.2:
        mult *= 10.0
        log.append(
            "The **Mystical Might** armor imbues with power, massively increasing damage!"
        )

    # --- Alchemy: Warrior's Draft (one-shot, reset after this attack) ---
    if player.alchemy_atk_boost_pct > 0:
        mult *= 1 + player.alchemy_atk_boost_pct
        log.append(
            f"💪 **Warrior's Draft** boosts damage! (+{int(player.alchemy_atk_boost_pct * 100)}% ATK)"
        )
        player.alchemy_atk_boost_pct = 0.0

    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if helmet_passive == "frenzy" and helmet_lvl > 0:
        missing_pct = (1 - (player.current_hp / player.max_hp)) * 100
        bonus = missing_pct * (0.005 * helmet_lvl)
        mult *= 1 + bonus
        log.append(
            f"**Frenzy ({helmet_lvl})** rage increases damage by {int(bonus * 100)}%!"
        )

    return mult


def _pt_resolve_hit(
    player: Player, monster: Monster, attack_multiplier: float, log: list[str]
) -> tuple[bool, float]:
    """Phase 2 — hit chance roll. Returns (is_hit, attack_multiplier).
    Multiplier may be zeroed by Shields-up, which propagates to miss-phase damage."""
    hit_chance = calculate_hit_chance(player, monster)
    if "Dodgy" in monster.modifiers:
        hit_chance = max(0.05, hit_chance - 0.10)
        log.append("The monster's **Dodgy** nature makes it harder to hit!")

    acc_bonus = player.get_emblem_bonus("accuracy") * 2

    idx, name = get_weapon_tier(player, "accuracy")
    if idx >= 0:
        wep_acc = (idx + 1) * 4
        acc_bonus += wep_acc
        log.append(f"The **{name}** weapon boosts 🎯 accuracy roll by **{wep_acc}**!")

    acc_passive = player.get_accessory_passive()
    acc_lvl = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0
    attack_roll = random.randint(0, 100)

    if acc_passive == "Lucky Strikes" and random.random() <= (acc_lvl * 0.10):
        attack_roll = max(attack_roll, random.randint(0, 100))
        log.append(
            f"**Lucky Strikes ({acc_lvl})** activates! Hit chance is now 🍀 lucky!"
        )

    if "Suffocator" in monster.modifiers and random.random() < 0.2:
        log.append(
            f"The {monster.name}'s **Suffocator** aura stifles your attack! Hit chance is now 💀 unlucky!"
        )
        attack_roll = min(attack_roll, random.randint(0, 100))

    if "Shields-up" in monster.modifiers and random.random() < 0.1:
        attack_multiplier = 0
        log.append(f"{monster.name} projects a magical barrier, nullifying the hit!")

    miss_threshold = 100 - int(hit_chance * 100)
    is_hit = (attack_multiplier > 0) and ((attack_roll + acc_bonus) >= miss_threshold)

    # --- Alchemy: Bottled Courage (guaranteed hit override) ---
    if not is_hit and player.alchemy_guaranteed_hit and attack_multiplier > 0:
        is_hit = True
        player.alchemy_guaranteed_hit = False
        log.append("⚔️ **Bottled Courage** forces the hit!")

    return is_hit, attack_multiplier


def _pt_resolve_crit(
    player: Player, monster: Monster, is_hit: bool, log: list[str]
) -> bool:
    """Phase 3 — crit check. Rolls 0-100; result must exceed (100 - crit_chance)."""
    if not is_hit:
        return False

    idx, _ = get_weapon_tier(player, "crit")
    crit_chance = player.get_current_crit_chance() + ((idx + 1) * 5 if idx >= 0 else 0)

    infernal = player.get_weapon_infernal()
    if infernal == "voracious" and player.voracious_stacks > 0:
        crit_chance += player.voracious_stacks * 5

    if crit_chance >= 100:
        return True
    return random.randint(0, 100) > (100 - crit_chance)


def _pt_crit_damage(
    player: Player, monster: Monster, attack_multiplier: float, log: list[str]
) -> int:
    """Phase 4a — crit damage. Returns pre-reduction damage."""
    max_atk = player.get_total_attack()

    crit_floor = 0.5
    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    if glove_passive == "deftness" and glove_lvl > 0:
        crit_floor = min(0.75, crit_floor + (glove_lvl * 0.05))
        log.append(f"**Deftness ({glove_lvl})** hones your crits!")

    crit_min = max(1, int(max_atk * crit_floor) + 1)
    crit_max = max(crit_min, max_atk)
    base_dmg = int(random.randint(crit_min, crit_max) * 2.0)

    crit_dmg_tiers = player.get_emblem_bonus("crit_dmg")
    if crit_dmg_tiers > 0:
        base_dmg = int(base_dmg * (1 + crit_dmg_tiers * 0.05))

    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if helmet_passive == "insight" and helmet_lvl > 0:
        extra = helmet_lvl * 0.1
        base_dmg = int(base_dmg * (1 + extra))
        log.append(
            f"**Insight ({helmet_lvl})** exposes a weak point! (Crit Dmg +{int(extra * 100)}%)"
        )

    if "Smothering" in monster.modifiers:
        base_dmg = int(base_dmg * 0.80)
        log.append("The monster's **Smothering** aura dampens your critical hit!")

    if player.cursed_precision_active:
        alt = int(random.randint(crit_min, crit_max) * 2.0)
        if alt < base_dmg:
            base_dmg = alt
        log.append("**Cursed Precision** — the weaker roll applies!")

    damage = int(base_dmg * attack_multiplier)

    infernal = player.get_weapon_infernal()
    if infernal == "last_rites" and monster.hp > 0:
        bonus = int(monster.hp * 0.10)
        damage += bonus
        log.append(f"**Last Rites** seals {monster.name}'s fate! (+{bonus})")

    if infernal == "voracious":
        if player.voracious_stacks > 0:
            log.append(
                f"**Voracious** resets after a crit! ({player.voracious_stacks} stacks lost)"
            )
        player.voracious_stacks = 0

    void_passive = player.get_accessory_void_passive()
    if void_passive == "void_gaze" and player.gaze_stacks < 30 and monster.attack > 0:
        player.gaze_stacks += 1
        reduction = max(1, int(monster.attack * 0.03))
        monster.attack = max(0, monster.attack - reduction)
        log.append(
            f"⬛ **Void Gaze** ({player.gaze_stacks}/30) — {monster.name}'s ATK -{reduction}!"
        )

    if (
        void_passive == "fracture"
        and not getattr(monster, "is_uber", False)
        and random.random() < 0.05
    ):
        damage = monster.hp
        log.append("💀 **Fracture** tears open a void rift — **instant kill!**")

    # Lucifer glove: bonus flat damage equal to 15% of current ward
    if player.get_glove_corrupted_essence() == "lucifer" and player.combat_ward > 0:
        ward_bonus = int(player.combat_ward * 0.15)
        if ward_bonus > 0:
            damage += ward_bonus
            log.append(f"🔥 **Soul Burn** — ward fuels the crit! (+{ward_bonus})")

    # Gemini glove: second strike at 40-60% of crit damage
    if player.get_glove_corrupted_essence() == "gemini":
        second_pct = random.uniform(0.40, 0.60)
        second_hit = int(damage * second_pct)
        if second_hit > 0:
            damage += second_hit
            log.append(f"⚖️ **Twin Strike** — a second blow lands! (+{second_hit})")

    idx, _ = get_weapon_tier(player, "crit")
    if idx >= 0:
        log.append("The weapon glimmers with power!")
    log.append(f"Critical Hit! Damage: 🗡️ **{damage}**")
    return damage


def _pt_hit_damage(
    player: Player, monster: Monster, attack_multiplier: float, log: list[str]
) -> int:
    """Phase 4b — normal hit damage. Returns pre-reduction damage."""
    base_max = player.get_total_attack()
    base_min = 1

    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    if glove_passive == "adroit" and glove_lvl > 0:
        base_min = max(base_min, int(base_max * (glove_lvl * 0.02)))
        log.append(f"**Adroit ({glove_lvl})** sharpens your technique!")

    idx, name = get_weapon_tier(player, "burn")
    if idx >= 0:
        bonus = int(player.get_total_attack() * ((idx + 1) * 0.08))
        base_max += bonus
        log.append(
            f"The **{name}** weapon 🔥 burns bright!\nAttack damage potential boosted by **{bonus}**."
        )

    idx, name = get_weapon_tier(player, "spark")
    if idx >= 0:
        base_min = max(base_min, int(base_max * ((idx + 1) * 0.08)))
        log.append(
            f"The **{name}** weapon surges with ⚡ lightning, ensuring solid impact!"
        )

    rolled = random.randint(min(base_min, base_max), base_max)
    damage = int(rolled * attack_multiplier)

    echo_idx, _ = get_weapon_tier(player, "echo")
    echo_damage = 0
    if echo_idx >= 0:
        echo_damage = int(damage * (echo_idx + 1) * 0.10)
        damage += echo_damage

    infernal = player.get_weapon_infernal()
    if infernal == "voracious":
        player.voracious_stacks += 1
        log.append(
            f"**Voracious** charges! ({player.voracious_stacks} stack{'s' if player.voracious_stacks != 1 else ''})"
        )

    # Lucifer glove: bonus flat damage equal to 15% of current ward
    if player.get_glove_corrupted_essence() == "lucifer" and player.combat_ward > 0:
        ward_bonus = int(player.combat_ward * 0.15)
        if ward_bonus > 0:
            damage += ward_bonus
            log.append(f"🔥 **Soul Burn** — ward fuels the strike! (+{ward_bonus})")

    log.append(f"Hit! Damage: 💥 **{damage - echo_damage}**")
    if echo_damage:
        log.append(f"The hit is 🎶 echoed!\nEcho damage: 💥 **{echo_damage}**")
    return damage


def _pt_miss_damage(
    player: Player, monster: Monster, attack_multiplier: float, log: list[str]
) -> int:
    """Phase 4c — miss, any on-miss damage sources. Returns total miss damage."""
    damage = 0
    miss_parts = []

    infernal = player.get_weapon_infernal()
    if infernal == "perdition" and player.equipped_weapon:
        perdition_dmg = int(player.equipped_weapon.attack * 0.75)
        if perdition_dmg > 0:
            damage += perdition_dmg
            miss_parts.append(f"**Perdition** tears through for 🔥 **{perdition_dmg}**")

    idx, _ = get_weapon_tier(player, "poison")
    if idx >= 0:
        poison_pct = (idx + 1) * 0.08
        poison_dmg = int(
            random.randint(1, int(player.get_total_attack() * poison_pct))
            * attack_multiplier
        )
        if poison_dmg > 0:
            damage += poison_dmg
            miss_parts.append(f"poison 🐍 deals **{poison_dmg}**")

    void_passive = player.get_accessory_void_passive()
    if void_passive == "oblivion":
        glove_p = player.get_glove_passive()
        glove_l = player.equipped_glove.passive_lvl if player.equipped_glove else 0
        base_max = player.get_total_attack()
        base_min = (
            max(1, int(base_max * (glove_l * 0.02)))
            if glove_p == "adroit" and glove_l > 0
            else 1
        )
        oblivion_dmg = max(1, int(base_min * 0.5))
        damage += oblivion_dmg
        miss_parts.append(f"**Oblivion** phases through for ⬛ **{oblivion_dmg}**")

    if infernal == "voracious":
        player.voracious_stacks += 1

    if miss_parts:
        log.append("Miss! But " + ", ".join(miss_parts) + " damage.")
    else:
        log.append("Miss!")
    return damage


def _pt_apply_reductions(monster: Monster, damage: int, log: list[str]) -> int:
    """Phase 5 — apply monster damage-reduction modifiers."""
    if "Radiant Protection" in monster.modifiers and damage > 0:
        reduction = int(damage * 0.60)
        damage = max(0, damage - reduction)
        log.append(f"✨ **Radiant Protection** mitigates {reduction} damage!")

    if "Titanium" in monster.modifiers and damage > 0:
        reduction = int(damage * 0.10)
        damage = max(0, damage - reduction)
        log.append(
            f"{monster.name}'s **Titanium** plating reduces damage by {reduction}."
        )

    return damage


def _pt_generate_ward(
    player: Player, raw_damage: int, is_crit: bool, log: list[str]
) -> None:
    """Phase 6 — glove ward generation on hit (uses pre-reduction damage, matching original)."""
    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0

    if (
        not is_crit
        and glove_passive == "ward-touched"
        and glove_lvl > 0
        and raw_damage > 0
    ):
        ward = int(raw_damage * (glove_lvl * 0.01))
        if ward > 0:
            added = _add_ward(player, ward, log)
            log.append(f"**Ward-Touched ({glove_lvl})** generates 🔮 **{added}** ward!")

    if is_crit and glove_passive == "ward-fused" and glove_lvl > 0 and raw_damage > 0:
        ward = int(raw_damage * (glove_lvl * 0.02))
        if ward > 0:
            added = _add_ward(player, ward, log)
            log.append(f"**Ward-Fused ({glove_lvl})** generates 🔮 **{added}** ward!")


def _pt_apply_to_monster(
    player: Player, monster: Monster, damage: int, log: list[str]
) -> int:
    """Phase 7 — apply damage to monster HP, respecting Time Lord. Returns damage actually dealt."""
    if damage >= monster.hp:
        if (
            "Time Lord" in monster.modifiers
            and random.random() < 0.80
            and monster.hp > 1
        ):
            damage = monster.hp - 1
            log.append(
                f"A fatal blow was dealt, but **{monster.name}** cheated death via **Time Lord**!"
            )
        else:
            damage = monster.hp
    monster.hp -= damage
    return damage


def _pt_post_hit_effects(
    player: Player, monster: Monster, damage: int, is_crit: bool, log: list[str]
) -> None:
    """Phase 8 — effects that fire after damage lands: leech, bloodthirst, ward regen."""
    if damage <= 0:
        return

    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    if helmet_passive == "leeching" and helmet_lvl > 0:
        heal = int(damage * (0.02 * helmet_lvl))
        if heal > 0:
            player.current_hp = min(player.max_hp, player.current_hp + heal)
            log.append(f"**Leeching** drains life, healing you for **{heal}** HP.")

    if is_crit:
        bloodthirst_pct = player.get_tome_bonus("bloodthirst")
        if bloodthirst_pct > 0:
            heal = max(1, int(damage * (bloodthirst_pct / 100)))
            player.current_hp = min(player.max_hp, player.current_hp + heal)
            log.append(
                f"**Bloodthirst** siphons **{heal}** HP from the critical strike."
            )

    if player.get_celestial_armor_passive() == "celestial_ghostreaver":
        regen = random.randint(50, 200)
        added = _add_ward(player, regen, log)
        log.append(f"✨ **Celestial Ghostreaver** restores **{added}** 🔮 Ward!")


def _pt_track_pending(player: Player, damage: int, log: list[str]) -> None:
    """Phase 9 — accumulate pending XP/gold from glove passives (no log output)."""
    if damage <= 0:
        return
    glove_passive = player.get_glove_passive()
    glove_lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
    if glove_passive == "equilibrium" and glove_lvl > 0:
        player.equilibrium_bonus_xp_pending += int(damage * (glove_lvl * 0.05))
    if glove_passive == "plundering" and glove_lvl > 0:
        player.plundering_bonus_gold_pending += int(damage * (glove_lvl * 0.10))


def _pt_check_cull(player: Player, monster: Monster, log: list[str]) -> None:
    """Phase 10 — culling strike: if monster HP is below threshold, reduce to 1."""
    if monster.hp <= 0:
        return
    idx, _ = get_weapon_tier(player, "cull")
    if idx >= 0:
        threshold = (idx + 1) * 0.08
        if monster.hp <= (monster.max_hp * threshold):
            cull_dmg = monster.hp - 1
            if cull_dmg > 0:
                monster.hp = 1
                log.append(
                    f"{player.name}'s weapon culls the weakened {monster.name}, "
                    f"dealing an additional 🪓 __**{cull_dmg}**__ damage!"
                )


def process_player_turn(player: Player, monster: Monster) -> PlayerTurnResult:
    """Executes the player's turn, applying damage to the monster and returning the combat log."""
    log: list[str] = []

    # --- Alchemy: Lingering Remedy (tick at start of player's turn) ---
    if player.alchemy_linger_turns > 0:
        player.current_hp = min(
            player.max_hp, player.current_hp + player.alchemy_linger_hp
        )
        log.append(
            f"🌿 **Lingering Remedy** restores **{player.alchemy_linger_hp}** HP! "
            f"({player.alchemy_linger_turns - 1} turn{'s' if player.alchemy_linger_turns - 1 != 1 else ''} left)"
        )
        player.alchemy_linger_turns -= 1

    attack_multiplier = _pt_attack_multiplier(player, monster, log)
    is_hit, attack_multiplier = _pt_resolve_hit(player, monster, attack_multiplier, log)
    is_crit = _pt_resolve_crit(player, monster, is_hit, log)

    # NEET glove: all normal hits are treated as misses; crits are unaffected
    if is_hit and not is_crit and player.get_glove_corrupted_essence() == "neet":
        is_hit = False
        log.append("🌑 **Void Form** — the strike phases through as nothingness!")

    if is_crit:
        raw_damage = _pt_crit_damage(player, monster, attack_multiplier, log)
    elif is_hit:
        raw_damage = _pt_hit_damage(player, monster, attack_multiplier, log)
    else:
        raw_damage = _pt_miss_damage(player, monster, attack_multiplier, log)

    actual_damage = _pt_apply_reductions(monster, raw_damage, log)
    _pt_generate_ward(player, raw_damage, is_crit, log)  # ward uses pre-reduction value
    final_hit = _pt_apply_to_monster(player, monster, actual_damage, log)
    _pt_post_hit_effects(player, monster, final_hit, is_crit, log)
    _pt_track_pending(player, final_hit, log)
    _pt_check_cull(player, monster, log)

    return PlayerTurnResult(
        log="\n".join(log),
        damage=final_hit,
        is_hit=is_hit,
        is_crit=is_crit,
    )


# ---------------------------------------------------------------------------
# Monster Turn
#
# Source slots active during the monster turn:
#   Celestial   → get_celestial_armor_passive()   (fortress PDR, sanctity re-roll, vow, ghostreaver)
#   Armor       → equipped_armor.block / .evasion  (block/dodge chance)
#   Helmet      → get_helmet_passive()             (ghosted, thorns, volatile)
#   Void        → get_accessory_void_passive()     (nullfield, eternal_hunger)
#   Codex tomes → get_tome_bonus('tenacity')
#   Emblem      → get_emblem_bonus('slayer_def')
# ---------------------------------------------------------------------------


def _roll_monster_damage(
    player: Player, monster: Monster, effective_pdr: int, effective_fdr: int
) -> tuple[int, int, int]:
    """Rolls a single monster damage hit including modifiers, PDR, FDR, and minions.
    Returns (total_damage, base_damage, minion_damage)."""
    dmg = calculate_damage_taken(player, monster)

    if "Celestial Watcher" in monster.modifiers:
        dmg = int(dmg * 1.2)
    if "Hellborn" in monster.modifiers:
        dmg += 2
    if "Hell's Fury" in monster.modifiers:
        dmg += 5
    if "Mirror Image" in monster.modifiers and random.random() < 0.2:
        dmg *= 2
    if "Unlimited Blade Works" in monster.modifiers:
        dmg *= 2

    pdr = max(0, effective_pdr - (20 if "Penetrator" in monster.modifiers else 0))
    dmg = max(0, int(dmg * (1 - pdr / 100)))

    fdr = max(0, effective_fdr - (5 if "Clobberer" in monster.modifiers else 0))
    dmg = max(0, dmg - fdr)

    minions = 0
    if "Summoner" in monster.modifiers:
        minions += int(dmg * (1 / 3))
    if "Infernal Legion" in monster.modifiers:
        minions += dmg
    minions = max(0, minions - fdr)

    return dmg + minions, dmg, minions


def process_monster_turn(player: Player, monster: Monster) -> MonsterTurnResult:
    """Executes the monster's turn, applies damage to player, and returns combat log."""
    if player.is_invulnerable_this_combat:
        return MonsterTurnResult(
            log=f"The **Invulnerable** armor protects {player.name}, absorbing all damage from {monster.name}!",
            hp_damage=0,
        )

    monster.combat_round += 1
    prev_hp = player.current_hp
    log: list[str] = []

    celestial = player.get_celestial_armor_passive()
    helmet_passive = player.get_helmet_passive()
    helmet_lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
    previous_ward = player.combat_ward

    # --- Hit chance ---
    hit_chance = calculate_monster_hit_chance(player, monster)
    if "Prescient" in monster.modifiers:
        hit_chance = min(0.95, hit_chance + 0.10)
    if "All-seeing" in monster.modifiers:
        hit_chance = min(0.95, hit_chance * 1.10)
    if "Celestial Watcher" in monster.modifiers:
        hit_chance = 1.0

    monster_roll = random.random()
    if "Lucifer-touched" in monster.modifiers and random.random() < 0.5:
        monster_roll = min(monster_roll, random.random())

    # --- Void Aura drain (regardless of hit) ---
    if "Void Aura" in monster.modifiers:
        drain_atk = max(1, int(player.base_attack * 0.05))
        drain_def = max(0, int(player.base_defence * 0.05))
        player.base_attack = max(1, player.base_attack - drain_atk)
        player.base_defence = max(0, player.base_defence - drain_def)
        log.append(
            f"🌑 **Void Drain** siphons **{drain_atk}** ATK and **{drain_def}** DEF!"
        )

    if monster_roll <= hit_chance:
        # --- PDR / FDR setup ---
        effective_pdr = player.get_total_pdr()
        if celestial == "celestial_fortress":
            missing_pct = (1 - (player.current_hp / player.max_hp)) * 100
            effective_pdr += int(missing_pct / 5.0)
        effective_fdr = player.get_total_fdr()

        # --- Base damage roll (Celestial Sanctity takes the lower of two) ---
        total_damage, dmg_base, minion_dmg = _roll_monster_damage(
            player, monster, effective_pdr, effective_fdr
        )
        if celestial == "celestial_sanctity":
            alt_total, alt_base, alt_minion = _roll_monster_damage(
                player, monster, effective_pdr, effective_fdr
            )
            if alt_total < total_damage:
                total_damage, dmg_base, minion_dmg = alt_total, alt_base, alt_minion

        # --- Multistrike & Executioner ---
        multistrike_damage = 0
        if "Multistrike" in monster.modifiers and random.random() <= hit_chance:
            multistrike_damage = max(
                0, int(calculate_damage_taken(player, monster) * 0.5) - effective_fdr
            )
            total_damage += multistrike_damage

        is_executed = False
        if "Executioner" in monster.modifiers and random.random() < 0.01:
            total_damage = max(total_damage, int(player.current_hp * 0.90))
            is_executed = True

        # --- Dodge & Block ---
        is_dodged = False
        is_blocked = False
        equipped_armor = player.equipped_armor

        if "Unavoidable" not in monster.modifiers:
            dodge_chance = player.get_total_evasion() / 100
            if celestial == "celestial_wind_dancer":
                dodge_chance *= 3.0
            if random.random() <= dodge_chance:
                is_dodged = True

        if not is_dodged and "Unblockable" not in monster.modifiers:
            block_chance = player.get_total_block() / 100
            if celestial == "celestial_glancing_blows":
                block_chance *= 2.0
            if random.random() <= block_chance:
                is_blocked = True

        # --- Resolve mitigation states ---
        if is_dodged:
            total_damage = 0
            log.append(
                f"{monster.name} {monster.flavor}, but you 🏃 nimbly step aside!"
            )
            if helmet_passive == "ghosted" and helmet_lvl > 0:
                ward_gain = helmet_lvl * 10
                added = _add_ward(player, ward_gain, log)
                log.append(
                    f"**Ghosted ({helmet_lvl})** manifests **{added}** 🔮 Ward from the movement!"
                )

        elif is_blocked:
            if celestial == "celestial_glancing_blows":
                total_damage = int(total_damage * 0.5)
                log.append(
                    f"{monster.name} {monster.flavor}, but your armor 🛡️ partially blocks it (Bleedthrough: {total_damage})!"
                )
            else:
                total_damage = 0
                log.append(
                    f"{monster.name} {monster.flavor}, but your armor 🛡️ blocks all damage!"
                )

            if helmet_passive == "thorns" and helmet_lvl > 0:
                reflect = int(dmg_base * helmet_lvl)
                monster.hp -= reflect
                log.append(
                    f"**Thorns ({helmet_lvl})** reflects **{reflect}** damage back!"
                )

        # --- Apply damage to ward / HP ---
        # --- Alchemy: Iron Skin (+DEF for N monster turns) ---
        if player.alchemy_def_boost_turns > 0 and total_damage > 0:
            reduction = int(total_damage * player.alchemy_def_boost_pct)
            total_damage = max(0, total_damage - reduction)
            player.alchemy_def_boost_turns -= 1
            if reduction > 0:
                log.append(
                    f"🛡️ **Iron Skin** absorbs **{reduction}** damage! "
                    f"({player.alchemy_def_boost_turns} turn{'s' if player.alchemy_def_boost_turns != 1 else ''} left)"
                )
            if player.alchemy_def_boost_turns <= 0:
                player.alchemy_def_boost_pct = 0.0

        # --- Alchemy: Dulled Pain (% reduction on next monster attack only) ---
        if player.alchemy_dmg_reduction_turns > 0 and total_damage > 0:
            reduction = int(total_damage * player.alchemy_dmg_reduction_pct)
            total_damage = max(0, total_damage - reduction)
            player.alchemy_dmg_reduction_turns = 0
            player.alchemy_dmg_reduction_pct = 0.0
            if reduction > 0:
                log.append(f"🩹 **Dulled Pain** reduces damage by **{reduction}**!")

        if total_damage > 0 and not is_dodged:
            damage_dealt = 0

            if player.get_tome_bonus("tenacity") > 0 and random.random() < (
                player.get_tome_bonus("tenacity") / 100
            ):
                total_damage = max(1, total_damage // 2)
                log.append("**Tenacity** braces the impact, halving the damage!")

            void_passive = player.get_accessory_void_passive()
            if void_passive == "nullfield" and random.random() < 0.15:
                log.append("⬛ **Nullfield** absorbs the strike into the void!")
                total_damage = 0

            # --- Alchemy: Overcap Brew (temp HP absorbs damage first, then is lost) ---
            if player.alchemy_overcap_hp > 0 and total_damage > 0:
                absorbed = min(player.alchemy_overcap_hp, total_damage)
                player.alchemy_overcap_hp = 0  # always fully lost on any hit
                total_damage -= absorbed
                log.append(
                    f"💥 **Overcap Brew** temp HP absorbs **{absorbed}** damage and shatters!"
                )

            glove_corrupted = player.get_glove_corrupted_essence()
            helmet_corrupted = player.get_helmet_corrupted_essence()

            # --- Gemini helmet: split damage evenly between ward and HP simultaneously ---
            if (
                helmet_corrupted == "gemini"
                and player.combat_ward > 0
                and total_damage > 0
            ):
                ward_half = total_damage // 2
                hp_half = total_damage - ward_half
                ward_absorbed = min(ward_half, player.combat_ward)
                player.combat_ward -= ward_absorbed
                damage_dealt = ward_absorbed
                if not is_blocked:
                    log.append(
                        f"{monster.name} {monster.flavor}.\n"
                        f"**Twin Balance** splits the blow — 🔮 {ward_absorbed} to ward, 💔 {hp_half} bleeds through!"
                    )
                total_damage = hp_half  # remaining leaks to HP unconditionally

            elif player.combat_ward > 0 and total_damage > 0:
                # Standard ward absorption
                if total_damage <= player.combat_ward:
                    damage_dealt = total_damage
                    player.combat_ward -= total_damage
                    if not is_blocked:
                        log.append(
                            f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {total_damage} damage!"
                        )
                    total_damage = 0
                else:
                    damage_dealt = player.combat_ward
                    if not is_blocked:
                        log.append(
                            f"{monster.name} {monster.flavor}.\nYour ward absorbs 🔮 {player.combat_ward} damage, but shatters!"
                        )
                    total_damage -= player.combat_ward
                    player.combat_ward = 0

                    # Lucifer helmet: gain flat PDR burst when ward fully breaks
                    if helmet_corrupted == "lucifer" and player.lucifer_pdr_burst == 0:
                        player.lucifer_pdr_burst = 15
                        log.append(
                            "🔥 **Infernal Resilience** — ward shattered, gaining **+15%** PDR for this combat!"
                        )

            if total_damage > 0:
                if player.active_task_species == monster.species:
                    tiers = player.get_emblem_bonus("slayer_def")
                    if tiers > 0:
                        total_damage = int(total_damage * (1 - min(0.50, tiers * 0.02)))

                if (
                    celestial == "celestial_vow"
                    and (player.current_hp - total_damage <= 0)
                    and not getattr(player, "celestial_vow_used", False)
                ):
                    player.current_hp = 1
                    ward_gain = int(player.max_hp * 0.5)
                    added = _add_ward(player, ward_gain, log)
                    player.celestial_vow_used = True
                    damage_dealt += player.current_hp - 1
                    log.append(
                        f"\n✨ **Celestial Vow** activates! You survive the fatal blow and gain {added} 🔮 Ward!"
                    )
                else:
                    damage_dealt += total_damage
                    player.current_hp -= total_damage
                    if not is_blocked or celestial != "celestial_glancing_blows":
                        log.append(
                            f"{monster.name} {monster.flavor}. You take 💔 **{total_damage}** damage!"
                        )

            if void_passive == "eternal_hunger" and damage_dealt > 0:
                player.hunger_stacks += 1
                if player.hunger_stacks >= 10:
                    hunger_dmg = int(monster.max_hp * 0.10)
                    monster.hp = max(0, monster.hp - hunger_dmg)
                    player.current_hp = player.max_hp
                    player.hunger_stacks = 0
                    log.append(
                        f"⬛ **Eternal Hunger** consumes the pain!\n"
                        f"💀 Devoured **{hunger_dmg}** HP ({monster.name}'s max × 10%)!\n"
                        f"❤️ Wounds consumed — HP restored to full!"
                    )
                else:
                    log.append(
                        f"⬛ **Eternal Hunger** feeds ({player.hunger_stacks}/10 stacks)."
                    )

            # Volatile: normal trigger (ward fully drained this turn)
            # Aphrodite glove extends this to fire whenever ward was touched at all
            ward_was_hit = damage_dealt > 0 and previous_ward > 0
            aphrodite_glove_active = (
                glove_corrupted == "aphrodite"
                and ward_was_hit
                and player.combat_ward > 0
            )
            if helmet_passive == "volatile" and helmet_lvl > 0:
                if previous_ward > 0 and (
                    player.combat_ward == 0 or aphrodite_glove_active
                ):
                    boom = int(player.max_hp * helmet_lvl)
                    monster.hp -= boom
                    if player.combat_ward == 0:
                        log.append(
                            f"\n💥 **Volatile** Shield shatters, dealing **{boom}** damage to {monster.name}!"
                        )
                    else:
                        log.append(
                            f"\n💥 **Volatile** (Aphrodite) — ward struck, dealing **{boom}** damage to {monster.name}!"
                        )

            if "Vampiric" in monster.modifiers and damage_dealt > 0:
                heal = damage_dealt * 10
                monster.hp = min(monster.max_hp, monster.hp + heal)
                log.append(
                    f"The monster's **Vampiric** essence siphons life, healing it for **{heal}** HP!"
                )

            if is_executed:
                log.append(
                    f"The {monster.name}'s **Executioner** ability cleaves through you!"
                )
            if minion_dmg > 0:
                log.append(
                    f"Their minions strike for an additional {minion_dmg} damage!"
                )
            if multistrike_damage > 0:
                log.append(
                    f"{monster.name} strikes again for {multistrike_damage} damage!"
                )

            if "Twin Strike" in monster.modifiers and monster.combat_round % 2 == 0:
                twin_raw, _, _ = _roll_monster_damage(
                    player, monster, effective_pdr, effective_fdr
                )
                twin_dmg = max(1, int(twin_raw * 0.5))
                player.current_hp = max(0, player.current_hp - twin_dmg)
                log.append(
                    f"⚡ **Twin Strike!** The bound sovereigns strike as one for **{twin_dmg}** damage!"
                )

        if not log:
            log.append(
                f"{monster.name} {monster.flavor}, but you mitigate all its damage."
            )

    else:  # Miss
        if "Venomous" in monster.modifiers:
            player.current_hp = max(1, player.current_hp - 1)
            log.append(
                f"{monster.name} misses, but their **Venomous** aura deals **1** 🐍 damage!"
            )
        else:
            log.append(f"{monster.name} misses!")

    player.current_hp = max(0, player.current_hp)
    return MonsterTurnResult(
        log="\n".join(log),
        hp_damage=max(0, prev_hp - player.current_hp),
    )


# ---------------------------------------------------------------------------
# Debug Logging
# ---------------------------------------------------------------------------


def log_combat_debug(player: Player, monster: Monster, logger: logging.Logger) -> None:
    """Calculates and logs the final stats and theoretical maximum damage of both entities."""
    p_atk = player.get_total_attack()
    p_def = player.get_total_defence()
    p_crit = player.get_current_crit_chance()

    crit_mult = 2.0
    if player.get_helmet_passive() == "insight":
        lvl = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
        crit_mult += lvl * 0.1
    if "Smothering" in monster.modifiers:
        crit_mult *= 0.8
    p_max_dmg = int(p_atk * crit_mult)
    if player.get_glove_passive() == "instability":
        lvl = player.equipped_glove.passive_lvl if player.equipped_glove else 0
        p_max_dmg = int(p_max_dmg * (1.50 + (lvl * 0.10)))

    m_atk = monster.attack
    m_def = monster.defence
    diff = max(0, m_atk - p_def)

    if m_atk <= 3:
        base_m = 5
    elif m_atk <= 20:
        base_m = 6
    else:
        base_m = 9 + int(monster.level // 10)
    base_m += int(diff / 10) * 3

    if "Celestial Watcher" in monster.modifiers:
        base_m = int(base_m * 1.2)
    if "Hellborn" in monster.modifiers:
        base_m += 2
    if "Hell's Fury" in monster.modifiers:
        base_m += 5

    pdr = player.get_total_pdr()
    if "Penetrator" in monster.modifiers:
        pdr = max(0, pdr - 20)
    fdr = player.get_total_fdr()
    if "Clobberer" in monster.modifiers:
        fdr = max(0, fdr - 5)

    m_max_dmg = max(0, int(base_m * (1 - pdr / 100)) - fdr)
    if (
        "Mirror Image" in monster.modifiers
        or "Unlimited Blade Works" in monster.modifiers
    ):
        m_max_dmg *= 2

    logger.info(f"--- COMBAT DEBUG: {player.name} VS {monster.name} ---")
    logger.info(
        f"PLAYER : HP {player.current_hp}/{player.max_hp} | Atk {p_atk} | Def {p_def} | Ward {player.combat_ward} | Crit {p_crit}% | PDR {player.get_total_pdr()}% | FDR {player.get_total_fdr()}"
    )
    logger.info(
        f"MONSTER: HP {monster.hp}/{monster.max_hp} | Atk {m_atk} | Def {m_def} | Mods: {monster.modifiers}"
    )
    logger.info(f"THEORETICAL MAX HIT -> Player: ~{p_max_dmg} | Monster: ~{m_max_dmg}")
    logger.info("--------------------------------------------------")
