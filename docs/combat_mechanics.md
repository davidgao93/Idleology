# Combat Mechanics — Damage Pipeline & Modifier Reference

> **Source of truth:** This document is generated from the live code.
> All values, formulas, and behaviour descriptions match `core/combat/` exactly.

---

## Table of Contents

1. [Monster → Player Damage Pipeline](#1-monster--player-damage-pipeline)
2. [Player → Monster Damage Pipeline](#2-player--monster-damage-pipeline)
3. [Modifier Reference](#3-modifier-reference)
   - [Common — Tiered](#common--tiered)
   - [Rare — Tiered](#rare--tiered)
   - [Rare — Flat](#rare--flat)
   - [Boss — Flat](#boss--flat)
   - [Uber — Hardcoded](#uber--hardcoded)

---

## 1. Monster → Player Damage Pipeline

### 1a. Pre-turn effects (start of monster's turn, before the hit roll)

These effects fire regardless of whether the monster lands its attack:

| # | Modifier | Effect |
|---|---|---|
| 1 | **Death Rattle** countdown | Decrements the 5-turn countdown; heals to 25% max HP when it reaches 0 |
| 2 | **Flashfire** charge | +1 charge; at 8 charges detonates for **X% true damage** to player max HP (resets to 0) |
| 3 | **Hemorrhage** DoT | Deals `stacks × X%` of player max HP as **true damage** |
| 4 | **Pressure Surge** check | +1 stack if player didn't crit last turn; at 10 stacks deals **X% true damage** to player max HP (resets) |
| 5 | **Soul Siphon** | Every 2nd monster turn: drains X% of player's current ward, heals monster for 50% of drained |
| 6 | **Corrosion** | Every 3rd monster turn: +1 Corrode stack (−5 effective PDR per stack) |
| 7 | **Temporal Collapse** | Every 6th monster turn: returns accumulated player damage as true damage (capped at 35% player max HP) |
| 8 | **Mending** | Every 2nd monster turn: heals monster for `sqrt(max_hp × 10 000) × X` HP (sqrt-scaled) |
| 9 | **Void Aura** | Every turn: drains 0.5% of player's base ATK and DEF permanently |
| 10 | **Origin of Corruption** | Every 3rd monster turn: drains 10% of player ward, heals Evelynn for 10× the ward drained |

---

### 1b. Hit roll

```
hit_chance = base_hit_chance(player evasion vs monster accuracy)
```

Modifiers applied to hit chance (in order):

| Modifier | Effect |
|---|---|
| **Keen T1–T5** | +5/7/10/13/15 percentage points to hit chance (cap 95% unless Inevitable) |
| **Overwhelming** | −25 percentage points to hit chance (floor 15%) |
| **Unerring** | Roll the hit die twice, take the higher result |
| **Inevitable** | Always hits (hit chance forced to 100%) |

If the roll **misses**: the **Venomous** on-miss effect fires (see §1c), then the turn ends.

---

### 1c. Miss branch — Venomous

If the monster misses **and** has Venomous:

```
venom_dmg = max(1, int(player.total_max_hp × venom_pct))
player.current_hp -= venom_dmg           ← TRUE DAMAGE (bypasses all layers)
```

Tier values: T1 0.4%, T2 0.8%, T3 1.2%, T4 1.6%, T5 2.0% of player max HP.

---

### 1d. Hit branch — pre-dodge calculations

Once the hit roll succeeds, the damage is computed **before** dodge/block are resolved:

#### Raw base damage

```
base_raw  = 5 + monster.level × 1.5
surplus   = clamp((monster.attack − player.defence) / player.defence, −0.95, +∞)
raw_roll  = base_raw × (1 + surplus) × uniform(0.85, 1.15)
raw       = max(1, int(raw_roll))
```

#### Monster damage multipliers (applied in order to `raw`)

| Step | Modifier | Formula |
|---|---|---|
| 1 | **Enraged** | `× (1 + v × stacks)` where `stacks = min(3, floor(hp_lost / 0.25))` |
| 2 | **Savage** | `× (1 + v)` |
| 3 | **Overwhelming** | `× 2` |
| 4 | **Hell's Fury** | `× 3.0` (uber) |
| 5 | **Spectral** | 20% chance `× 2` |
| 6 | **Lethal** / **Volatile Spikes** crit | Roll monster crit at `10% + Lethal_bonus + spike_stacks × v_spikes`; crit multiplies by `1.5 + Devastating_bonus` |
| 7 | **Crushing** | Reduces effective PDR by `v × PDR` before PDR step |
| 8 | **Searing** | Reduces effective FDR by `v × FDR` before FDR step |

#### Player defensive reductions (applied in order after multipliers)

```
damage = int(damage × (1 − effective_pdr / 100))   ← Physical Damage Reduction (PDR)
damage = max(0, damage − effective_fdr)              ← Flat Damage Reduction (FDR)
```

Where:
- `effective_pdr` = player's total PDR, reduced by Corrosion stacks (`−5 per stack`), increased by Celestial Fortress armor passive.
- `effective_fdr` = player's total FDR.

After PDR/FDR, the **pre-reduction** value (`pre_pdr`) is saved for Thorned and Commanding echo calculations.

#### Ongoing ATK modifications on the damage value

| Modifier | Effect |
|---|---|
| **Onslaught** (bonus_atk > 0) | `× (1 + onslaught_bonus_atk)` applied after PDR/FDR |
| **Wrathful Retaliation** | `× (1 + wrathful_stacks × 0.08)` applied after PDR/FDR |
| **Undying Resolve** ATK boost | `× 2.0` while `undying_atk_boost_turns > 0` |
| **Inevitable** | `× 0.50` (always-hit penalty, applied last before Multistrike) |
| **Commanding** echo (minions) | Separately calculated: `(pre_pdr_damage × echo_pct − fdr) × (1 − pdr/100)` — added to total |

#### Multistrike

50% chance to add a second hit: `int(raw_roll × 0.5 × (1 − pdr/100)) − fdr` (independent roll, also goes through PDR/FDR).

#### Executioner proc

1% chance proc flag is set **before** dodge/block. Damage is only applied **after** the dodge/block check (see §1f).

---

### 1e. Dodge & Block

```
dodge_chance = player.evasion / 100  (× 0.20 if Unavoidable; × 3.0 if Celestial Wind Dancer)
block_chance = player.block / 100    (× 0.20 if Unblockable; × 2.0 if Celestial Glancing Blows)
```

- **Dodged:** all damage set to 0. Volatile Spikes and Onslaught stacks reset.
- **Blocked (normal):** all damage set to 0.
- **Blocked (Celestial Glancing Blows):** damage reduced to 50% bleedthrough.

On **dodge**: Ghosted helmet passive generates ward.  
On **block**: Thorns helmet passive reflects `raw_pre_pdr × thorns_lvl` back to monster (through PDR/FDR).

---

### 1f. Sundering (ward bypass — uber boss only)

If the monster has **Sundering** and damage > 0 (not dodged, not blocked):

```
bypass    = int(total_damage × 0.25)       ← goes directly to player HP (bypasses ward)
remaining = total_damage − bypass          ← hits ward normally
```

---

### 1g. Player damage reduction layers (hit damage, not true damage)

Applied after dodge/block/Sundering resolution:

| Layer | Source | Formula |
|---|---|---|
| Alchemy Iron Skin | `alchemy_def_boost` active | `× (1 − alchemy_def_boost_pct)` per turn remaining |
| Alchemy Dulled Pain | `alchemy_dmg_reduction` active | `× (1 − alchemy_dmg_reduction_pct)` (consumed on use) |
| Partner co_damage_reduction | Partner skill | `L × 5%` chance to halve incoming damage |
| Tenacity (Codex Tome) | tome bonus | `tome_tenacity%` chance to halve incoming damage |
| Nullfield (Void accessory) | 15% chance | Absorbs the entire hit |
| Overcap Brew (Alchemy) | temp HP buffer | Absorbs up to `alchemy_overcap_hp` then shatters |

---

### 1h. Ward absorption

After all reduction layers, damage hits the **player ward** first:

- **Gemini helmet (corrupted):** Reduces incoming damage by 20%, then splits evenly between ward and HP simultaneously.
- **Standard ward:** Damage absorbs from ward first; overflow hits HP.
- **Celestial Vow armor passive:** If the overflow would kill the player (HP would reach 0), instead set HP to 1 and grant 50% max HP as ward (once per fight).
- **Lucifer helmet (corrupted):** Gaining PDR burst (+15%) when ward is fully broken.

After HP is dealt:

- **Slayer Emblem** bonus: if fighting the active task species, `× (1 − min(0.50, emblem_tiers × 0.02))`.

---

### 1i. Executioner true damage (post-dodge/block)

Fires **only if** the attack connected (not dodged, not blocked) and proc flag was set:

```
exec_dmg = int(player.current_hp × 0.90)
player.current_hp -= exec_dmg             ← TRUE DAMAGE (bypasses all layers above)
```

---

### 1j. Post-hit effects (all fire on connected hit, not on dodge)

| # | Effect | Description |
|---|---|---|
| 1 | **Volatile Spikes** stack | 30% chance +1 spike (max 10), resets on dodge/block |
| 2 | **Onslaught** stack | +v ATK bonus per consecutive hit, resets on dodge/block |
| 3 | **Vampiric** heal | `sqrt(max_hp × 10 000) × v` HP healed per hit |
| 4 | **Hemorrhage** bleed | 30% chance +1 bleed stack |
| 5 | **Impending Doom** | +1 doom stack per hit; instant-kill at 44 stacks |
| 6 | **Thorned** reflection | Player takes `player.max_hp × v` damage (after PDR/FDR; bypasses ward) |
| 7 | **Balanced Strikes** | Every even round: extra hit at 50% damage, bypasses ward, goes directly to HP |
| 8 | **Eternal Hunger** | Void accessory: +1 hunger stack per damage instance; at 10 stacks devours 10% monster max HP and restores player to full |

---

## 2. Player → Monster Damage Pipeline

### 2a. Hit chance resolution

```
hit_chance   = calculate_hit_chance(player, monster)   # (ATK vs DEF formula + weapon bonus)
crit_chance  = calculate_crit_chance(player)            # (weapon crit + accessory crit + bonuses)
```

Modifiers that affect the player's hit/crit rolls:

| Modifier | Effect |
|---|---|
| **Blinding** | −5/8/10/12/15 points from player hit roll |
| **Jinxed** | X% chance player's hit roll is disadvantaged (rolled twice, lower taken) |
| **Dampening** | −5/10/15/20/25 from player crit chance |
| **Pressure Surge** tracking | Records whether the player critted this turn |
| **Wrathful Retaliation** | On player crit: +1 stacking ATK multiplier |

---

### 2b. Player damage computation

On **hit** or **crit**, player damage is rolled from `[base_min, player.attack]`, then multiplied by the **attack_multiplier** (built from combat-start passives, jewel buffs, etc.).

- **Burning** weapon passive: raises the ceiling by `tier × 8%` of base ATK.
- **Shocking** weapon passive: raises the floor by `tier × 8%` of base ATK.
- **Adroit** glove passive: raises the normal-hit floor by `tier × 2%`.
- **Deftness** glove passive: raises the crit floor by `tier × 5%`.
- **Crit** multiplies the rolled value by the crit multiplier (base 2.0x).
- **Cursed Precision** (accessory): roll the damage range twice, apply the worse result.
- **Nullifying** monster modifier: reduces crit multiplier by `v × crit_mult`.

---

### 2c. Monster damage reduction — Layer 1 (Regular DR, additive, hard cap 80%)

```
regular_dr = Ironclad_value + colossus_dr    ← all regular sources added together
capped_dr  = min(0.80, regular_dr)
damage     = damage × (1 − capped_dr)
```

Sources:
- **Ironclad** modifier: T1–T5 = 10/15/20/25/30%
- **Colossus Protocol** (when triggered below 50% HP): +30% DR (`monster.colossus_dr = 0.30`)

**Hard cap: 80%.** Even if Ironclad T5 (30%) + Colossus (30%) = 60%, or theoretically higher, the combined rate is capped at 80% before application. The two DR sources do **not** multiply against each other.

---

### 2d. Stalwart — chance-based full nullification

After Layer 1:
```
if random() < stalwart_value:
    damage = 0          ← entire attack nullified
```

This fires **after** regular DR — so Stalwart can still nullify residual damage that survived Ironclad.

---

### 2e. Monster damage reduction — Layer 2 (Uber Protection, multiplicative)

Applied **after** Layer 1 and Stalwart:

```
damage = damage × (1 − 0.60) = damage × 0.40
```

Sources: Radiant Protection, Infernal Protection, Balanced Protection, Void Protection, Corrupted Protection.

Only **one** Protection modifier fires per hit (the first one found). This layer is entirely independent of and cannot be diluted by regular DR stacking.

**Combined example:** Ironclad T5 (30%) + Colossus (30%) + Infernal Protection on a 1000-damage hit:
```
Layer 1: 1000 × (1 − 0.60)  = 400
Layer 2:  400 × (1 − 0.60)  = 160 final
```

---

### 2f. Ward absorption (monster ward)

Remaining damage hits the monster's ward first (if any), then HP.

**Time Lord** applies at the HP-death check:
- 80% chance to survive a killing blow (HP reduced to 1 instead of 0)
- Only fires if `monster.hp > 1`

---

### 2g. True damage — bypasses all reduction layers

True damage skips all of §2c–2f entirely. It is applied directly to `monster.hp`:

| Source | Trigger | Amount |
|---|---|---|
| **Cull** (weapon passive) | Monster HP ≤ tier threshold | Entire remaining HP (instant kill) |
| **Flashfire** detonation | 8th charge | X% of player max HP |
| **Hemorrhage** DoT | Per bleed stack per monster turn | `stacks × X%` player max HP |
| **Pressure Surge** release | 10th stack | X% player max HP |
| **Temporal Collapse** | Every 6 turns | Accumulated player-to-monster damage (capped at 35% player max HP) |
| **Venomous** on-miss | Monster misses | X% player max HP |
| **Executioner** proc | 1% chance, if hit connects and not evaded/blocked | 90% of player current HP |

**Protections against true damage (player-to-monster direction):**
- **Time Lord**: 80% chance any killing blow is reduced to deal HP−1 instead (both player attacks and cull). Does NOT apply to Partner Execute if Time Lord check already triggered.
- **Undying Resolve**: On first death (hp ≤ 0), revives to 40% max HP with 2-turn immunity and 2-turn double ATK. Intercepts both normal kills and cull kills (checked after cull, before the turn ends).

**Partner Execute (`co_execute`)**: Checks Time Lord first (80% → HP 1), then Undying Resolve (revive), then kills. Also bypasses all DR layers.

---

## 3. Modifier Reference

### Common — Tiered

Rolled from the common pool for regular and boss encounters. Tier is gated by monster level.

| Modifier | Tiers (T1→T5) | Level Gates | Description |
|---|---|---|---|
| **Empowered** | +10/20/30/40/50% ATK | 1/25/50/75/100 | +X% attack |
| **Fortified** | +10/20/30/40/50% DEF | 1/25/50/75/100 | +X% defence |
| **Titanic** | 150/175/200/225/250% HP | 1/25/50/75/100 | Monster starts with X% of base HP |
| **Savage** | +20/25/30/35/40% damage | 1/25/50/75/100 | All hits deal X% more damage |
| **Lethal** | +5/10/15/20/25% crit chance | 1/25/50/75/100 | +X% monster crit chance (base 10%) |
| **Devastating** | +0.5/0.6/0.7/0.8/1.0 to crit mult | 1/25/50/75/100 | Crits deal 2.0×/2.1×/2.2×/2.3×/2.5× (base 1.5×) |
| **Keen** | +5/7/10/13/15 hit | 1/25/50/75/100 | +X percentage points to monster hit chance |
| **Blinding** | −5/8/10/12/15 hit | 1/25/50/75/100 | −X percentage points from player hit rolls |
| **Jinxed** | 10/20/30/40/50% | 1/25/50/75/100 | X% chance player's hit roll is disadvantaged |
| **Crushing** | 5/6/7/8/10% PDR ignored | 1/25/50/75/100 | Reduces effective player PDR by X% of its value |
| **Searing** | 15/20/25/30/35% FDR ignored | 1/25/50/75/100 | Reduces effective player FDR by X% of its value |
| **Stalwart** | 5/10/15/20/25% chance | 1/25/50/75/100 | X% chance to nullify **all** incoming damage each hit |
| **Ironclad** | 10/15/20/25/30% DR | 1/25/50/75/100 | X% damage reduction (additive pool, cap 80% with Colossus) |
| **Vampiric** | 0.4/0.8/1.2/1.6/2.0% | 1/25/50/75/100 | Heals `sqrt(max_hp × 10k) × v` HP per connected hit |
| **Mending** | 0.25/0.50/0.75/1.0/1.25% | 1/25/50/75/100 | Heals `sqrt(max_hp × 10k) × v` HP every other monster turn |
| **Thorned** | 1/2/3/4/5% max HP | 1/25/50/75/100 | Player takes X% of their max HP on each hit (after PDR/FDR; bypasses ward) |
| **Venomous** | 0.4/0.8/1.2/1.6/2.0% max HP | 1/25/50/75/100 | On miss: X% of player max HP as **true damage** |
| **Enraged** | +5/10/15/20/25% ATK/stack | 1/25/50/75/100 | +X% ATK per 25% HP lost (max 3 stacks, capped at 75% HP lost) |
| **Parching** | 10/20/30/40/50% | 1/25/50/75/100 | Player potions heal X% less |
| **Veiled** | 10/20/30/40/50% max HP ward | 1/25/50/75/100 | Starts the fight with X% of max HP as ward |
| **Flashfire** | 2/4/6/8/10% max HP | 1/25/50/75/100 | +1 charge per monster turn; at 8 charges: X% player max HP **true damage**, resets |
| **Hemorrhage** | 0.15/0.20/0.28/0.36/0.45% | 1/25/50/75/100 | 30% per hit: +1 bleed stack; each stack deals X% player max HP **true damage** per monster turn |
| **Volatile Spikes** | +2/3/4/5/6% crit/stack | 1/25/50/75/100 | 30% per connected hit: +1 spike (max 10, +X% monster crit/stack); evade/block resets all stacks |
| **Onslaught** | +1.5/2.0/3.0/4.0/5.0% ATK/stack | 1/25/50/75/100 | +X% ATK bonus per consecutive hit; resets on evade/block |
| **Pressure Surge** | 10/12.5/15/17.5/20% max HP | 1/25/50/75/100 | +1 stack each monster turn the player didn't crit; at 10 stacks: X% player max HP **true damage**, resets |
| **Soul Siphon** | 5/8/12/16/20% ward | 1/25/50/75/100 | Every 2 turns: drains X% of player ward, heals monster for 50% of drained |
| **Frenzied Hunger** | +5/8/12/16/20% ATK | 1/25/50/75/100 | Each potion the player consumes: +X% monster ATK (permanent for the fight) |

---

### Rare — Tiered

Rolled from the rare tiered pool; uncommon. Same 5-tier structure as common modifiers.

| Modifier | Tiers (T1→T5) | Level Gates | Description |
|---|---|---|---|
| **Commanding** | 10/20/30/40/50% echo | 1/25/50/75/100 | Minions echo X% of each hit (separate PDR/FDR calculation on pre-FDR damage) |
| **Dampening** | −5/10/15/20/25 crit | 1/25/50/75/100 | −X from player's effective crit chance |
| **Nullifying** | 30/40/50/60/70% less crit dmg | 1/25/50/75/100 | Player crits deal X% less damage (multiplied against crit multiplier) |

---

### Rare — Flat

Single value; no tiers. Rolled from the rare flat pool.

| Modifier | Value | Description |
|---|---|---|
| **Unblockable** | 0.20 | Player block chance is 80% less effective (block × 0.20) |
| **Unavoidable** | 0.20 | Player evasion is 80% less effective (evasion × 0.20) |
| **Dispelling** | 0.80 | Reduces player ward by 80% at combat start |
| **Multistrike** | 0.50 | 50% chance to strike twice; second hit at 50% damage (after PDR/FDR) |
| **Spectral** | 0.20 | 20% chance to deal double damage |
| **Executioner** | 0.90 | 1% chance: deal 90% of player current HP as **true damage** (can be evaded/blocked) |
| **Time Lord** | 0.80 | 80% chance to survive a killing blow (HP reduced to 1 instead of 0) |

| **Corrosion** | 5 | Every 3 monster turns: +1 Corrode stack (each stack permanently −5 effective PDR for this fight) |
| **Death Rattle** | 1.0 | Triggers on first time HP drops below 25%: 5-turn countdown; if monster survives, heals to 25% max HP |

---

### Boss — Flat

Applied to boss encounters. Not rolled; always present on the designated boss.

| Modifier | Value | Description |
|---|---|---|
| **Overwhelming** | 2.0 | Deals double damage; −25 percentage points to hit chance (floor 15%) |
| **Inevitable** | 0.50 | Always hits (100% hit chance); deals 50% damage |
| **Sundering** | 0.25 | 25% of damage bypasses player ward, going directly to HP |
| **Unerring** | — | Hit rolls always take the higher of two dice |
| **Impending Doom** | — | +1 doom stack per hit; **instant kill** at 44 stacks |
| **Wrathful Retaliation** | 0.08 | Each player crit: +8% monster ATK permanently (stacking, no cap) |
| **Colossus Protocol** | 0.60 | Below 50% HP (triggers once): monster ATK +60%, gains +30% DR (adds to Ironclad pool) |
| **Temporal Collapse** | — | Every 6 turns: returns all damage dealt in the window as **true damage** (capped at 35% player max HP) |
| **Undying Resolve** | 0.40 | First death: revives to 40% max HP, immune for 2 turns, ATK doubled for 2 turns |

---

### Uber — Hardcoded

Hardcoded per uber encounter; not rolled from any pool.

| Modifier | Boss | Description |
|---|---|---|
| **Radiant Protection** | Aphrodite | 60% damage reduction (Layer 2 — multiplicative after regular DR) |
| **Infernal Protection** | Lucifer | 60% damage reduction (Layer 2 — multiplicative after regular DR) |
| **Void Protection** | NEET | 60% damage reduction (Layer 2 — multiplicative after regular DR) |
| **Balanced Protection** | Gemini | 60% damage reduction (Layer 2 — multiplicative after regular DR) |
| **Corrupted Protection** | Corrupted variants | 60% damage reduction (Layer 2 — multiplicative after regular DR) |
| **Hell's Fury** | Lucifer | Deals 3× damage (applied as a multiplier after Savage/Overwhelming in damage roll) |
| **Void Aura** | NEET | Every monster turn: drains 0.5% of player base ATK and DEF (permanent) |
| **Balanced Strikes** | Gemini | Every other monster turn: second strike at 50% damage (PDR/FDR applied), bypasses ward |
| **Origin of Corruption** | Evelynn | Every 3 monster turns: drains 10% player ward, heals Evelynn for 10× drained |

---

## Modifier Category Summary

| Category | Pool | Count | Notes |
|---|---|---|---|
| Common tiered | `common` | 26 | Randomly rolled for all encounters; tier gated by monster level |
| Rare tiered | `rare_tiered` | 3 | Lower roll weight than common; same tier system |
| Rare flat | `rare_flat` | 10 | Single value; no tier; rolled with low probability |
| Boss flat | `boss` | 10 | Assigned to specific bosses; not rolled from pool |
| Uber hardcoded | `uber` | 9 | Per uber encounter; never rolled; always present |
| Special | — | 1 | **Ascended**: value = `min(20, max(1, monster.level // 10))` — adds levels |

---

## Quick Reference: Damage Types

| Type | PDR | FDR | Ward | Regular DR (Ironclad/Colossus) | Uber Protection | Notes |
|---|---|---|---|---|---|---|
| **Regular hit damage** | ✅ | ✅ | ✅ | ✅ | ✅ | Full pipeline |
| **Thorned reflection** | ✅ | ✅ | ❌ (bypasses) | N/A (player→monster direction) | N/A | Applied to player directly |
| **Venomous on-miss** | ❌ | ❌ | ❌ | N/A | N/A | True damage to player |
| **Executioner proc** | ❌ | ❌ | ❌ | N/A | N/A | True damage to player; can be evaded/blocked |
| **Flashfire / Hemorrhage / Pressure Surge / Temporal Collapse** | ❌ | ❌ | ❌ | N/A | N/A | True damage to player |
| **Balanced Strikes** (uber Gemini) | ✅ | ✅ | ❌ (bypasses) | N/A | N/A | Goes through PDR/FDR, skips ward |
| **Soul Siphon** | N/A | N/A | Drains ward | N/A | N/A | Ward drain, not HP damage |
| **Player → monster normal** | N/A | N/A | ✅ | ✅ | ✅ | Full monster DR pipeline |
| **Player → monster cull** | ❌ | ❌ | ❌ | ❌ | ❌ | True damage; Time Lord / Undying Resolve can intercept |
| **Partner execute** | ❌ | ❌ | ❌ | ❌ | ❌ | True damage; Time Lord / Undying Resolve checked inline |
