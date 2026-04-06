import random
from dataclasses import dataclass
from core.models import Player, Monster
from core.combat.calcs import (
    calculate_hit_chance,
    calculate_monster_hit_chance,
    calculate_damage_taken,
    check_for_echo_bonus,
    check_for_poison_bonus,
    get_player_passive_indices,
)


@dataclass
class SimulationResult:
    # --- Outgoing ---
    total_damage: int
    hits: int
    misses: int
    crits: int
    max_hit: int
    min_hit: int
    average_damage: float
    turns: int
    # --- Incoming ---
    total_damage_taken: int
    avg_damage_taken: float
    max_damage_taken: int
    is_max_lethal: bool


class DummyEngine:
    @staticmethod
    def run_simulation(player: Player, monster: Monster, turns: int = 100) -> SimulationResult:
        # ------------------------------------------------------------------ #
        # Pre-simulation setup                                                 #
        # ------------------------------------------------------------------ #

        # Cache passives (read-only; never mutate player permanently)
        glove_passive  = player.get_glove_passive()
        glove_lvl      = player.equipped_glove.passive_lvl if player.equipped_glove else 0
        acc_passive    = player.get_accessory_passive()
        acc_lvl        = player.equipped_accessory.passive_lvl if player.equipped_accessory else 0
        armor_passive  = player.get_armor_passive()
        helmet_passive = player.get_helmet_passive()
        helmet_lvl     = player.equipped_helmet.passive_lvl if player.equipped_helmet else 0
        celestial      = player.get_celestial_armor_passive()
        void_passive   = player.get_accessory_void_passive()
        infernal       = player.get_weapon_infernal()

        # Passive lists (weapon)
        burning_passives  = ["burning",   "flaming",      "scorching",   "incinerating", "carbonising"]
        sparking_passives = ["sparking",  "shocking",     "discharging", "electrocuting","vapourising"]
        crit_passives     = ["piercing",  "keen",         "incisive",    "puncturing",   "penetrating"]
        accuracy_passives = ["accurate",  "precise",      "sharpshooter","deadeye",      "bullseye"]

        # Emblem bonuses
        is_boss          = getattr(monster, 'is_boss', False)
        is_slayer        = (player.active_task_species == monster.species
                            and player.active_task_species is not None)
        combat_dmg_tiers = player.get_emblem_bonus("combat_dmg") if not is_boss else 0
        boss_dmg_tiers   = player.get_emblem_bonus("boss_dmg")   if is_boss     else 0
        slayer_dmg_tiers = player.get_emblem_bonus("slayer_dmg") if is_slayer   else 0
        crit_dmg_tiers   = player.get_emblem_bonus("crit_dmg")
        emblem_acc       = player.get_emblem_bonus("accuracy")
        slayer_def_mit   = (min(0.50, player.get_emblem_bonus("slayer_def") * 0.02)
                            if is_slayer else 0.0)

        # Base attack multiplier from emblems (applied every turn)
        emblem_mult = 1.0
        if combat_dmg_tiers > 0: emblem_mult *= (1 + combat_dmg_tiers * 0.02)
        if boss_dmg_tiers   > 0: emblem_mult *= (1 + boss_dmg_tiers   * 0.05)
        if slayer_dmg_tiers > 0: emblem_mult *= (1 + slayer_dmg_tiers * 0.05)

        # Codex tome bonuses
        tenacity_pct = player.get_tome_bonus('tenacity')

        # Incoming-damage mitigation (static over the run)
        effective_pdr = player.get_total_pdr()
        effective_fdr = player.get_total_fdr()

        # Block / dodge base chances
        block_chance = player.equipped_armor.block   / 100 if player.equipped_armor else 0
        dodge_chance = player.equipped_armor.evasion / 100 if player.equipped_armor else 0
        if celestial == 'celestial_glancing_blows': block_chance *= 2.0
        if celestial == 'celestial_wind_dancer':    dodge_chance *= 3.0

        # Weapon crit bonus (static)
        crit_indices = get_player_passive_indices(player, crit_passives)
        weapon_crit_bonus = (max(crit_indices) + 1) * 5 if crit_indices else 0

        # Accuracy weapon passive (static additive bonus to roll)
        acc_indices = get_player_passive_indices(player, accuracy_passives)
        weapon_acc_bonus = (max(acc_indices) + 1) * 4 if acc_indices else 0

        # Burn / Spark passive indices (static)
        burn_indices  = get_player_passive_indices(player, burning_passives)
        spark_indices = get_player_passive_indices(player, sparking_passives)

        # Apply combat-start stat effects that persist (save/restore player mutable fields)
        saved_base_attack  = player.base_attack
        saved_base_defence = player.base_defence
        saved_crit_target  = player.base_crit_chance_target

        # Enfeeble: -10% base ATK at combat start
        if "Enfeeble" in monster.modifiers:
            player.base_attack = int(player.base_attack * 0.90)

        # Shield-breaker: start with 0 ward
        sim_ward = 0 if "Shield-breaker" in monster.modifiers else player.get_combat_ward_value()

        # Voracious stacks (track without persisting to player object)
        voracious_stacks = 0

        # Celestial Vow (one-time save per simulation)
        celestial_vow_used = False

        # ------------------------------------------------------------------ #
        # Result accumulators                                                  #
        # ------------------------------------------------------------------ #
        total_damage      = 0
        hits              = 0
        misses            = 0
        crits             = 0
        max_hit           = 0
        min_hit           = float('inf')

        total_damage_taken = 0
        max_damage_taken   = 0

        try:
            for turn in range(turns):
                # ============================================================
                # PLAYER TURN — outgoing DPS
                # ============================================================
                attack_multiplier = emblem_mult

                # --- Per-turn multiplier passives ---
                if glove_passive == "instability" and glove_lvl > 0:
                    if random.random() < 0.5:
                        attack_multiplier *= 0.5
                    else:
                        attack_multiplier *= 1.50 + (glove_lvl * 0.10)

                if acc_passive == "Obliterate" and random.random() <= (acc_lvl * 0.02):
                    attack_multiplier *= 2.0

                if armor_passive == "Mystical Might" and random.random() < 0.2:
                    attack_multiplier *= 10.0

                if helmet_passive == "frenzy" and helmet_lvl > 0 and player.max_hp > 0:
                    missing_hp_pct   = (1 - (player.current_hp / player.max_hp)) * 100
                    multiplier_bonus = missing_hp_pct * (0.005 * helmet_lvl)
                    attack_multiplier *= (1 + multiplier_bonus)

                # --- Hit chance ---
                hit_chance = calculate_hit_chance(player, monster)
                if "Dodgy" in monster.modifiers:
                    hit_chance = max(0.05, hit_chance - 0.10)

                acc_value_bonus = emblem_acc * 2 + weapon_acc_bonus

                if acc_passive == "Lucky Strikes" and random.random() <= (acc_lvl * 0.10):
                    r1, r2 = random.randint(0, 100), random.randint(0, 100)
                    attack_roll = max(r1, r2)
                else:
                    attack_roll = random.randint(0, 100)
                attack_roll += acc_value_bonus

                if "Suffocator" in monster.modifiers and random.random() < 0.2:
                    r1, r2 = random.randint(0, 100), random.randint(0, 100)
                    attack_roll = min(r1 + acc_value_bonus, r2 + acc_value_bonus)

                if "Shields-up" in monster.modifiers and random.random() < 0.1:
                    attack_multiplier = 0

                final_miss_threshold = 100 - int(hit_chance * 100)
                is_hit = (attack_multiplier > 0 and attack_roll >= final_miss_threshold)

                damage = 0

                if is_hit:
                    # --- Voracious stacks adjust crit target ---
                    crit_target = player.get_current_crit_target() - weapon_crit_bonus
                    if infernal == "voracious" and voracious_stacks > 0:
                        crit_target = max(1, crit_target - (voracious_stacks * 5))

                    if random.randint(0, 100) > crit_target and "Impenetrable" not in monster.modifiers:
                        # CRIT
                        crits += 1
                        hits  += 1

                        max_atk    = player.get_total_attack()
                        crit_floor = 0.5
                        if glove_passive == "deftness" and glove_lvl > 0:
                            crit_floor = min(0.75, crit_floor + (glove_lvl * 0.05))

                        c_min     = max(1, int(max_atk * crit_floor))
                        c_max     = max(c_min, max_atk)
                        base_dmg  = int(random.randint(c_min, c_max) * 2.0)

                        if crit_dmg_tiers > 0:
                            base_dmg = int(base_dmg * (1 + crit_dmg_tiers * 0.05))
                        if helmet_passive == "insight" and helmet_lvl > 0:
                            base_dmg = int(base_dmg * (1 + helmet_lvl * 0.1))
                        if "Smothering" in monster.modifiers:
                            base_dmg = int(base_dmg * 0.80)

                        # Cursed precision: take lower roll
                        if infernal == "cursed_precision":
                            alt = int(random.randint(c_min, c_max) * 2.0)
                            if alt < base_dmg:
                                base_dmg = alt

                        damage = int(base_dmg * attack_multiplier)

                        # Voracious: reset stacks on crit
                        if infernal == "voracious":
                            voracious_stacks = 0

                    else:
                        # NORMAL HIT
                        hits += 1
                        base_max = player.get_total_attack()
                        base_min = 1

                        if glove_passive == "adroit" and glove_lvl > 0:
                            base_min = max(base_min, int(base_max * (glove_lvl * 0.02)))

                        if burn_indices:
                            burn_bonus = int(player.get_total_attack() * ((max(burn_indices) + 1) * 0.08))
                            base_max  += burn_bonus

                        if spark_indices:
                            spark_pct = (max(spark_indices) + 1) * 0.08
                            base_min  = max(base_min, int(base_max * spark_pct))

                        rolled  = random.randint(min(base_min, base_max), base_max)
                        damage  = int(rolled * attack_multiplier)
                        damage, _, _ = check_for_echo_bonus(player, damage)

                        # Voracious: increment stacks on non-crit
                        if infernal == "voracious":
                            voracious_stacks += 1

                else:
                    # MISS
                    misses += 1
                    # Perdition: 75% weapon ATK on miss
                    if infernal == "perdition" and player.equipped_weapon:
                        damage += int(player.equipped_weapon.attack * 0.75)
                    damage += check_for_poison_bonus(player, attack_multiplier)
                    if infernal == "voracious":
                        voracious_stacks += 1

                # --- Outgoing damage reductions ---
                if "Radiant Protection" in monster.modifiers and damage > 0:
                    damage = max(0, damage - int(damage * 0.60))
                if "Titanium" in monster.modifiers and damage > 0:
                    damage = max(0, damage - int(damage * 0.10))

                if damage > 0:
                    total_damage += damage
                    if damage > max_hit: max_hit = damage
                    if damage < min_hit: min_hit = damage

                # ============================================================
                # MONSTER TURN — incoming damage
                # ============================================================

                # Void Aura: drain player ATK/DEF before damage roll
                if "Void Aura" in monster.modifiers:
                    drain_atk = max(1, int(player.base_attack  * 0.05))
                    drain_def = max(0, int(player.base_defence * 0.05))
                    player.base_attack  = max(1, player.base_attack  - drain_atk)
                    player.base_defence = max(0, player.base_defence - drain_def)

                # Monster hit chance
                m_hit = calculate_monster_hit_chance(player, monster)
                if "Prescient"        in monster.modifiers: m_hit = min(0.95, m_hit + 0.10)
                if "All-seeing"       in monster.modifiers: m_hit = min(0.95, m_hit * 1.10)
                if "Celestial Watcher" in monster.modifiers: m_hit = 1.0

                m_roll = random.random()
                if "Lucifer-touched" in monster.modifiers and random.random() < 0.5:
                    m_roll = min(m_roll, random.random())

                turn_hp_damage = 0

                if m_roll <= m_hit:
                    # --- Incoming damage roll helper ---
                    def roll_incoming(eff_pdr=effective_pdr, eff_fdr=effective_fdr):
                        dmg = calculate_damage_taken(player, monster)
                        if "Celestial Watcher" in monster.modifiers: dmg = int(dmg * 1.2)
                        if "Hellborn"          in monster.modifiers: dmg += 2
                        if "Hell's Fury"       in monster.modifiers: dmg += 5
                        if "Mirror Image"      in monster.modifiers and random.random() < 0.2:
                            dmg *= 2
                        if "Unlimited Blade Works" in monster.modifiers:
                            dmg *= 2

                        pdr = eff_pdr
                        if "Penetrator" in monster.modifiers: pdr = max(0, pdr - 20)
                        dmg = max(0, int(dmg * (1 - pdr / 100)))

                        fdr = eff_fdr
                        if "Clobberer" in monster.modifiers: fdr = max(0, fdr - 5)
                        dmg = max(0, dmg - fdr)

                        minions = 0
                        if "Summoner"       in monster.modifiers: minions = max(0, int(dmg / 3) - fdr)
                        if "Infernal Legion" in monster.modifiers: minions = max(0, dmg - fdr)

                        return dmg + minions

                    total_incoming = roll_incoming()

                    # Celestial Sanctity: take lower of two rolls
                    if celestial == 'celestial_sanctity':
                        total_incoming = min(total_incoming, roll_incoming())

                    # Multistrike: extra 50% hit
                    if "Multistrike" in monster.modifiers and random.random() <= m_hit:
                        extra = max(0, int(calculate_damage_taken(player, monster) * 0.5) - effective_fdr)
                        total_incoming += extra

                    # Executioner: 1% chance for 90% HP
                    if "Executioner" in monster.modifiers and random.random() < 0.01:
                        total_incoming = max(total_incoming, int(player.max_hp * 0.90))

                    # Dodge
                    if "Unavoidable" not in monster.modifiers and random.random() <= dodge_chance:
                        total_incoming = 0

                    # Block
                    elif "Unblockable" not in monster.modifiers and random.random() <= block_chance:
                        if celestial == 'celestial_glancing_blows':
                            total_incoming = int(total_incoming * 0.5)
                        else:
                            total_incoming = 0

                    if total_incoming > 0:
                        # Tenacity: chance to halve
                        if tenacity_pct > 0 and random.random() < (tenacity_pct / 100):
                            total_incoming = max(1, total_incoming // 2)
                        # Nullfield: 15% absorb
                        if void_passive == "nullfield" and random.random() < 0.15:
                            total_incoming = 0

                    if total_incoming > 0:
                        # Slayer def mitigation
                        if slayer_def_mit > 0:
                            total_incoming = int(total_incoming * (1 - slayer_def_mit))

                        # Ward absorption
                        if sim_ward > 0:
                            if total_incoming <= sim_ward:
                                sim_ward -= total_incoming
                                total_incoming = 0
                            else:
                                total_incoming -= sim_ward
                                sim_ward = 0

                        # Celestial Vow: once per simulation, survive lethal blow
                        if total_incoming > 0:
                            if (celestial == 'celestial_vow'
                                    and not celestial_vow_used
                                    and total_incoming >= player.max_hp):
                                ward_gain = int(player.max_hp * 0.5)
                                sim_ward += ward_gain
                                total_incoming = 0
                                celestial_vow_used = True

                        turn_hp_damage = total_incoming

                elif "Venomous" in monster.modifiers:
                    turn_hp_damage = 1

                # Twin Strike: every second turn, an extra coordinated blow
                if "Twin Strike" in monster.modifiers and (turn + 1) % 2 == 0:
                    twin_raw = calculate_damage_taken(player, monster)
                    pdr = effective_pdr
                    if "Penetrator" in monster.modifiers: pdr = max(0, pdr - 20)
                    twin_raw = max(0, int(twin_raw * (1 - pdr / 100)))
                    fdr = effective_fdr
                    if "Clobberer" in monster.modifiers: fdr = max(0, fdr - 5)
                    twin_dmg = max(1, int(max(0, twin_raw - fdr) * 0.5))
                    if sim_ward > 0:
                        if twin_dmg <= sim_ward:
                            sim_ward -= twin_dmg
                            twin_dmg = 0
                        else:
                            twin_dmg -= sim_ward
                            sim_ward = 0
                    turn_hp_damage += twin_dmg

                total_damage_taken += turn_hp_damage
                if turn_hp_damage > max_damage_taken:
                    max_damage_taken = turn_hp_damage

        finally:
            # Restore mutated player fields
            player.base_attack            = saved_base_attack
            player.base_defence           = saved_base_defence
            player.base_crit_chance_target = saved_crit_target

        if min_hit == float('inf'):
            min_hit = 0

        return SimulationResult(
            total_damage=total_damage,
            hits=hits,
            misses=misses,
            crits=crits,
            max_hit=max_hit,
            min_hit=min_hit,
            average_damage=total_damage / turns,
            turns=turns,
            total_damage_taken=total_damage_taken,
            avg_damage_taken=total_damage_taken / turns,
            max_damage_taken=max_damage_taken,
            is_max_lethal=(max_damage_taken >= player.max_hp),
        )

    # ---------------------------------------------------------------------- #
    # Readiness assessments for Uber boss lobbies                              #
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _make_uber_proxy(ref_lvl: int, modifiers: list[str]) -> Monster:
        """Build a proxy Monster using the same stat pipeline as the real generators."""
        from core.combat.gen_mob import calculate_monster_stats
        proxy = Monster(
            name="Proxy", level=ref_lvl, hp=999_999, max_hp=999_999, xp=0,
            attack=0, defence=0, modifiers=modifiers,
            image="", flavor="",
        )
        return calculate_monster_stats(proxy)

    @staticmethod
    def assess_readiness(player: Player, target: str) -> str:

        ref_lvl = player.level + player.ascension + 20

        if target == "aphrodite_uber":
            proxy = DummyEngine._make_uber_proxy(ref_lvl, ["Radiant Protection", "Absolute"])
            # Absolute flat boost (mirrors generate_uber_aphrodite)
            proxy.attack  += 25
            proxy.defence += 25
            proxy.is_boss = True

            res = DummyEngine.run_simulation(player, proxy, turns=50)
            avg_taken   = res.avg_damage_taken
            time_to_die = player.max_hp / avg_taken if avg_taken > 0 else 999
            if time_to_die < 5:
                return "You feel as if you are **not ready**. The aura alone crushes you."
            elif res.average_damage < (player.max_hp * 0.1) and time_to_die < 15:
                return "You feel this would be a **tough battle**. Survival is uncertain."
            return "You are **filled with determination**. Press onwards."

        if target == "lucifer_uber":
            proxy = DummyEngine._make_uber_proxy(ref_lvl, ["Hell's Fury", "Absolute"])
            # Lucifer: 1.3× ATK, 0.3× DEF, Absolute +25/+25, heavy per-level ATK
            proxy.attack  = int(proxy.attack  * 1.3)
            proxy.defence = int(proxy.defence * 0.3)
            proxy.attack  += 25
            proxy.defence += 25
            proxy.attack  += int(ref_lvl * 1.0)
            proxy.defence += int(ref_lvl * 0.2)
            proxy.is_boss = True

            res = DummyEngine.run_simulation(player, proxy, turns=50)
            avg_taken   = res.avg_damage_taken
            time_to_die = player.max_hp / avg_taken if avg_taken > 0 else 999
            if time_to_die < 3:
                return "You feel as if you are **not ready**. His strikes alone would end you."
            elif res.average_damage < (player.max_hp * 0.1) and time_to_die < 10:
                return "You feel this would be a **tough battle**. Survival is uncertain."
            return "You are **filled with determination**. Press onwards."

        if target == "neet_uber":
            proxy = DummyEngine._make_uber_proxy(ref_lvl, ["Void Aura", "Absolute"])
            # NEET: Absolute +25/+25, per-level ATK/DEF scaling
            proxy.attack  += 25
            proxy.defence += 25
            proxy.attack  += int(ref_lvl * 0.8)
            proxy.defence += int(ref_lvl * 0.5)
            proxy.is_boss = True

            res = DummyEngine.run_simulation(player, proxy, turns=50)
            avg_taken   = res.avg_damage_taken
            time_to_die = player.max_hp / avg_taken if avg_taken > 0 else 999
            if res.average_damage < (player.max_hp * 0.05):
                return "You feel as if you are **not ready**. The void would consume you before you land a dent."
            elif time_to_die < 5:
                return "You feel as if you are **not ready**. Its strikes alone would end you."
            elif res.average_damage < (player.max_hp * 0.10) and time_to_die < 12:
                return "You feel this would be a **tough battle**. The void slowly drains everything."
            return "You are **filled with determination**. The void beckons."

        if target == "gemini_uber":
            proxy = DummyEngine._make_uber_proxy(ref_lvl, ["Twin Strike", "Absolute"])
            # Gemini: Absolute +25/+25, balanced per-level scaling
            proxy.attack  += 25
            proxy.defence += 25
            proxy.attack  += int(ref_lvl * 0.65)
            proxy.defence += int(ref_lvl * 0.65)
            proxy.is_boss = True

            res = DummyEngine.run_simulation(player, proxy, turns=50)
            avg_taken   = res.avg_damage_taken
            time_to_die = player.max_hp / avg_taken if avg_taken > 0 else 999
            if res.average_damage < (player.max_hp * 0.05):
                return "You feel as if you are **not ready**. The twins would outlast you entirely."
            elif time_to_die < 4:
                return "You feel as if you are **not ready**. Their Twin Strike would end you too quickly."
            elif res.average_damage < (player.max_hp * 0.10) and time_to_die < 10:
                return "You feel this would be a **tough battle**. The twins' rhythm is relentless."
            return "You are **filled with determination**. The constellation awaits."

        return "Unknown target."
