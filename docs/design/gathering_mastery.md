# Design: Artisan Mastery & Rune of Nature

**Status:** Draft for Review  
**Author:** Grok (based on detailed discussion)  
**Date:** 2026-05  
**Related Systems:** Gathering (Mining/Fishing/Woodcutting), Settlement, Alchemy, Partners (Dispatch), Combat (Skiller boots), Uber/Elemental encounters, Prestige/Hematurgy sinks

---

## 1. Executive Summary

This document proposes **Artisan Mastery**, a long-term progression layer for the three gathering skills (Mining, Fishing, Woodcutting). 

The goal is to solve the core feedback that gathering becomes "solved" once the player purchases the best tool. After BiS tools, there is currently no meaningful differentiation between a player who has gathered 100 times versus 10,000 times.

**Core Fantasy:**  
Through dedicated gathering, the player accumulates **Artisan Points** over real time and deliberate investment. These points are spent into specialization trees that create permanent, noticeable differences in how that skill generates value. Players must make real trade-offs between raw volume and powerful side benefits. Respecs are possible but deliberately costly using a new scarce currency: the **Rune of Nature**.

**Key Design Pillars:**
- **Purely passive progression.** Artisan Points come exclusively from the hourly passive regeneration task. No points from active minigames or any other system.
- **Global bonuses only.** No resource provenance tracking ("personally gathered" mechanics).
- **Meaningful choice.** Heavy investment in Yield vs. Quality/Synergy branches creates visibly different playstyles.
- **Exciting offline + combat moments.** "Rich Vein / Rich Catch / Rich Felling" procs on passive ticks + rare remnant-themed world bosses make both passive collection and combat more rewarding for dedicated gatherers.
- **New side economy.** Gathering Remnants + Rune of Nature provide a mastery-gated progression sink that ties into existing high-end loops (Settlement rare currencies + Elemental of Elements).
- **Respec friction is a feature.** The Rune of Nature is rare enough that specializations feel like real, lasting decisions.

This system expands gathering from "buy 5 tools and forget" into a multi-month progression axis with ~20-25 meaningful allocation decisions across the three skills.

---

## 2. Goals & Non-Goals

### Goals
- Give dedicated gatherers a sense of mastery and identity.
- Create visible long-term progression after tool BiS.
- Generate interesting player choice (volume vs. quality/synergy).
- Provide new sinks and minor economies that feed existing systems (dispatch, refining, alchemy, respecs, prestige).
- Keep the system low-tedium and compatible with Discord's interaction model.
- Respect the "number go up" nature of the game — active minigames remain optional flavor.

### Non-Goals
- Deepening or requiring the current active minigames (fishing/forestry). These remain lightweight optional activities.
- Adding per-resource provenance or "self-gathered" tracking.
- Creating daily login chores or high-frequency decision points.
- Overpowering gathering relative to combat, settlement, or other core loops.

---

## 3. Current Problems (Why This Is Needed)

- Only progression axis = tool tier (5 purchases per skill, then nothing).
- Passive regeneration and active yields use the exact same `calculate_yield` with no player-specific modifiers.
- No way for a "master fisherman" to feel different from a casual one after buying the titanium rod.
- Skiller boot procs are a nice cross-system hook but do not scale with gathering investment.
- No new interesting outputs or sinks once the player has ideal/felling/titanium tools.

---

## 4. Proposed System Overview

### Artisan Points
- Earned slowly over real time **exclusively** via the existing hourly passive regeneration task.
- No points from active minigames, dispatch, or any external systems.
- Soft catch-up on login (capped at 24 hours).

### Specialization Trees
- Three skills, each with three branches (Yield / Quality / Synergy).
- ~7-8 nodes per skill.
- Bonuses are **global** once purchased.
- Total meaningful decisions across all skills: ~22-26.

### Gathering Remnants (New Minor Resource)
- Mining: **Geode Cores**
- Fishing: **Tide Relics**
- Woodcutting: **Heartwood Shards**
- Primarily generated via "Rich" proc events on passive ticks when the player has invested in Quality branches.
- Used mainly to **craft Rune of Nature**.

### Rune of Nature (Respec Currency)
- Used to fully reset one skill's mastery tree (or all three at higher cost).
- **Primary source:** Crafted from Gathering Remnants (high cost, reliable for dedicated players).
- **Secondary source:** Rare drop (3-5%) from the final boss of the **Elemental of Elements** encounter.
- Optional: High total mastery investment can slightly improve the Elemental drop rate via a global passive.

This creates a beautiful loop: invest in Quality branches → generate Remnants via Rich procs → craft Runes of Nature → enable respecs or chase power.

---

## 5. Point Economy (Detailed) — Concrete Numbers

**Core Principle:** Artisan Points are earned **exclusively** through the passive gathering system (the existing hourly regeneration task). There are no points from active minigames, partner dispatch, Slayer tasks, Codex runs, quests, events, or any other source.

### Locked Point Generation Rates
- Base: **0.6 Artisan Points per skill per day** at the lowest tool tier.
- Tool tier scaling: **+0.3 points per day** for each tier above the starting tier.
- At BiS tools (tier 5): **1.8 points per day per skill**.

**Resulting Cadence (regular collection):**
- ~54 points per month per skill at BiS.
- A "full liked tree" (~42–45 points) takes **23–25 days**.
- Full everything in one skill (~58 points) takes ~32 days.
- All three skills meaningfully progressed: ~3 months.

### Target Investment Levels (Locked)
- "Solid / liked" investment in one skill: **42–45 points**
- Heavy investment in one skill: **52–55 points**
- Everything in one skill: **58 points**

This hits the design goal of one liked tree per month and all three in roughly 3 months.

### Catch-up & Fairness
- On login (or when opening the mastery UI), award up to **24 hours** of missed passive points per skill (capped). This rewards regular play while preventing abuse after long absences.
- Points are **per-skill** (Mining Points, Fishing Points, Woodcutting Points).

### Storage
New table `gathering_mastery` (see Database section).

---

## 6. Gathering Remnants

These are the "signature output" of high Quality investment.

**Generation Rules (proposed starting point):**
- Unlocked by purchasing the Tier 3 "Quality" node in each skill's tree (the node that introduces the remnant).
- Generated **exclusively** from the hourly passive regeneration task (no active minigame or external sources).
- Small baseline chance per passive tick once unlocked (~4-6%).
- Greatly increased chance (or guaranteed) during **Rich Vein / Rich Catch / Rich Felling** events.
- Rich events themselves become more common and more rewarding with deeper investment in the Quality branch.

**Fantasy Flavor:**
- Geode Cores: Beautiful crystal formations that resonate with "idea" energy.
- Tide Relics: Strange bone-and-pearl artifacts dredged from impossible depths.
- Heartwood Shards: Fragments of wood that still seem to pulse with life.

**Primary Sink:** Crafting **Rune of Nature** (see next section).

### Additional Sinks for Gathering Remnants
Because the three gathering skills are heavily intertwined with Settlement (refining, construction, workers), the most natural additional sink is a direct conversion into rare Settlement currencies.

- **Black Market Exchange (Primary Recommended Sink)**: Players can turn in stacks of Geode Cores, Tide Relics, and/or Heartwood Shards at the Settlement's Black Market in exchange for one of the existing rare currencies:
  - Diviner's Rod
  - Unidentified Blueprint
  - Development Contract
- Conversion ratios should be expensive enough to feel like a meaningful choice (suggested starting point: 40–60 remnants for one rare currency item), but still attractive for players who have over-invested in Quality branches.
- This creates excellent synergy: players who go deep into mastery for runes can also accelerate their Settlement progression without needing to rely solely on combat or other sources for those rare items.

Other minor sinks (lower priority):
- Repeatable gold + spirit stone turn-in.
- Small temporary buffs to dispatch or refining when spent.

---

## 7. Rune of Nature

**Name:** Rune of Nature (aligns with existing Refinement Rune, Potential Rune, Shatter Rune, Imbuing Rune, etc.).

### Acquisition

**Method 1: Crafting (Primary, Reliable Path)**
- Requires significant quantities of all three Remnant types + a gold + possibly one existing rune or spirit stone cost.
- Locked crafting cost:
  - **68 Geode Cores + 68 Tide Relics + 68 Heartwood Shards**
  - 350,000 Gold
  - 2 Spirit Stones
- This is expensive enough that only dedicated mastery players can realistically respec frequently.

**Method 2: Elemental of Elements Drop (Exciting / Prestige Path)**
- When the player defeats the final boss of the Elemental of Elements encounter (the "of elements" uber resonance fight), **3-5% base chance** to receive 1 Rune of Nature.
- This is a rare, high-value drop that makes the encounter more exciting for gatherers.
- A high-investment global passive (see cross-skill nodes) can raise this to ~6-8%.

This creates excellent cross-system synergy: players who enjoy the elemental fight get a reason to care about gathering mastery, and dedicated gatherers have a prestigious way to obtain respec currency.

### Usage
- Full reset of **one skill's** mastery tree costs 1 Rune of Nature.
- Full reset of all three skills costs 3 Runes of Nature (or a slight premium).
- After spending the rune, the player gets all points back for that skill and can immediately re-allocate.

The scarcity of the rune means players will think carefully before committing deep into a branch.

---

## 8. Full Specialization Trees (Revised — Global Bonuses Only)

Each skill has three branches. Nodes have increasing costs (1 / 2 / 3 / 5 / 8). Most powerful effects are locked behind meaningful investment.

**Design Intent:**
- Yield branch = "I want to print more stuff."
- Quality branch = "I want exciting procs and new outputs (Remnants)."
- Synergy branch = "I want my gathering to make my other systems better (dispatch, refining, alchemy, Skiller)."

Players who go deep into one branch feel very different from those who spread out.

### 8.1 Mining Tree — "Stonebound"

**Branch 1: Deep Veins (Raw Volume) — Locked Numbers**
| Node | Cost | Effect |
|------|------|--------|
| Enduring Veins | 1 | **+8%** total ore yield from all mining sources. |
| Bountiful Veins | 2 | Yield bonus increases to **+16%**. |
| Motherlode | 5 | Yield bonus increases to **+26%**. |
| Never Empty | 4 (req. 9 pts in branch) | 12% chance per passive tick for **+70%** extra resources that tick. |

**Branch 2: Vein Memory (Quality & Procs) — Locked Numbers**
| Node | Cost | Effect |
|------|------|--------|
| Ideal Seeker | 1 | **+20%** yield to Idea Ore specifically. |
| Crystallized Insight | 2 | Idea Ore bonus → **+38%**. 6% chance to produce Idea Ore even below current tool tier. |
| Geode Cores | 3 | Unlocks **Geode Cores**. Enables Rich Vein events. |
| Worldcore Resonance | 5 (req. Geode Cores) | Rich event base chance **22%**, **2.6×** multiplier, guarantees **3–5** Geode Cores. |

**Branch 3: Stonebound Mastery (Synergy) — Locked Numbers**
| Node | Cost | Effect |
|------|------|--------|
| Tool Resonance | 1 | Tool upgrade costs reduced by **12%**. |
| Skilled Hands | 2 | Skiller procs: **+65%** chance and **+45%** extra yield. |
| Master Quarry | 3 | **Global refining bonus:** +**10%** more bars from any ore conversion. |
| Living Mountain | 5 | **+55%** Idea Ore from all sources + small independent Rich proc chance. |
| Echo of the First Vein | 8 (very high) | **Prestige Capstone.** Grants a small chance (1–2%, similar to Treasure Monsters) for a combat encounter to instead spawn the **Meridian Golem**, a special remnant-themed "treasure boss". 

**Spawn Priority**: Inserted after Treasure Monster but before Regular Monster in the encounter generation chain (Corrupted → Named Boss → Incubated → Treasure → Skilling Boss → Regular).

**Boss Design**: Created via the normal monster generation flow in `core/combat/mobgen/gen_mob.py` (exact same HP/level/stat scaling as a regular monster of the player's level). We then manually attach one custom gimmick modifier.

- Gimmick: **+15% additional Percent Damage Reduction**.
- Implementation: Add a new unrollable "uber"-pool modifier in `core/combat/mobgen/modifier_data.py` (similar to "Radiant Protection", "Infernal Protection", or "Origin of Corruption"). It will never roll naturally. The special generation function for the Meridian Golem will explicitly add it via `make_modifier(...)`.

The boss is intentionally not very threatening beyond its high DR — it is a rare "treasure boss" treat.

**Defeat Reward**: 
- Custom post-combat view (new file under `core/combat/views/`, e.g. `views_skilling_bosses.py` or individual files).
- One-time harvest action: Roll **2–5 Geode Cores** (completely unaffected by any other bonuses, mastery, or modifiers for now).
- +10 to the Mining Tripled Passive Ticks counter (per-skill DB counter, additive).
- **Normal combat victory rewards still apply** (Skiller procs, experience, etc.).

The node description will explicitly state: "Grants a chance to encounter the Meridian Golem during combat." This makes the mechanic obvious when purchased. The capstone significantly increases the spawn rate. |

### 8.2 Fishing Tree — "Tidebound"

**Branch 1: Patient Waters (Raw Volume) — Locked Numbers**
- Same structure as Mining: **+8% → +16% → +26%** total bone yield + 4pt proc node for +70% spikes.

**Branch 2: Abyssal Memory (Quality & Procs) — Locked Numbers**
- Parallel to Vein Memory.
- 1pt: **+20%** Titanium Bones
- 2pt: **+38%** + 6% below-tier chance
- 3pt: Unlocks **Tide Relics**
- 5pt: Rich Catch **22%** base, **2.6×**, 3–5 guaranteed remnants

**Branch 3: Tidebound Mastery (Synergy) — Locked Numbers**
| Node | Cost | Effect |
|------|------|--------|
| Lighter Bait | 1 | Bait cost reduced by **12%**. |
| Favored by the Currents | 2 | Skiller: **+65%** chance and **+45%** extra yield. |
| Master Baiter | 3 | **Global alchemy bonus:** One-step better transmutation ratio, usable **once per day**. |
| The Old One's Favor | 5 | **+55%** Titanium Bones + small Rich proc chance. |
| Lord of the Deep | 8 (very high) | **Prestige Capstone.** Grants a small chance (1–2%, similar to Treasure Monsters) for a combat encounter to instead spawn the **Drowned Leviathan**, a special remnant-themed "treasure boss".

**Spawn Priority**: Same as above (after Treasure Monster, before Regular).

**Boss Design**: Normal generation pipeline in `gen_mob.py`. One gimmick modifier:

- **50% frequency** to deal **1% of the player's current Max HP as true damage** (bypasses everything) on the monster's turn.
- Implementation: Add a new custom unrollable modifier in `modifier_data.py` (modeled after existing minion / true damage effects like "Minion Army" or "Soul Siphon", but as a periodic independent bite rather than on-hit). The special generation function will attach it explicitly.

Again, this is meant to be a rare treasure encounter rather than a dangerous fight.

**Defeat Reward**: 
- Custom view in the skilling bosses views file.
- One-time harvest: Roll **2–5 Tide Relics** (unaffected by other mechanics for now).
- +10 to the Fishing Tripled Passive Ticks counter.
- Normal combat victory rewards apply.

Node text will clearly state the encounter chance. The capstone raises the rate. |

### 8.3 Woodcutting Tree — "Rootbound"

Symmetric structure to the above two.

**Branch 3: Rootbound Mastery (Synergy) — Locked Numbers**
| Node | Cost | Effect |
|------|------|--------|
| Forester's Eye | 1 | Forestry pass cost reduced by **12%**. |
| Skilled Forester | 2 | Skiller: **+65%** chance and **+45%** extra yield. |
| Seasoned Timber | 3 | **Global refining bonus:** +**10%** more planks from any wood conversion. |
| The Forest Remembers | 5 | **+55%** Idea Logs + small Rich proc chance. |
| Elderheart | 8 (very high) | **Prestige Capstone.** Grants a small chance (1–2%, similar to Treasure Monsters) for a combat encounter to instead spawn the **Verdant Colossus**, a special remnant-themed "treasure boss".

**Spawn Priority**: Inserted after Treasure Monster but before Regular Monster.

**Boss Design**: Normal generation pipeline in `gen_mob.py`. One gimmick:

- **10% snare chance** per turn: The player becomes snared (status on the player object) and cannot act until they free themselves.
- A "Free Yourself" button is present for this encounter (added greyed out at the start of the fight). It becomes enabled only when the player is currently snared by this boss.
- When the player clicks the button, the snare is removed and an additional monster turn is processed immediately (similar to how the Heal button currently triggers a monster turn).

**Implementation Note (Colossus snare)**: 
- New custom unrollable modifier in `modifier_data.py`.
- Snare status tracked directly on the player object.
- UI approach: The "Free Yourself" button is added as part of the combat view for this specific encounter (greyed out at the start). It becomes enabled only when the player is currently snared by this boss. This avoids risky dynamic add/remove of components.
- Turn skipping: When the player clicks the button, clear the snare status and immediately process one additional monster turn (modeled after current Heal button behavior that triggers a monster response).
- No other mechanics in the current game skip a player's turn, so this is new but contained logic.

This is deliberately lightweight — still intended as a rare treasure encounter.

**Defeat Reward**: 
- Custom view (in the new skilling bosses views file).
- One-time harvest: Roll **2–5 Heartwood Shards** (unaffected by other mechanics for now).
- +10 to the Woodcutting Tripled Passive Ticks counter.
- Normal combat victory rewards apply.

The node description will explicitly say it grants a chance to encounter the Verdant Colossus during combat. The capstone raises the rate. |

These three prestige capstones (**Meridian Golem** / **Drowned Leviathan** / **Verdant Colossus**) give players who fully invest in one or more skills exciting, combat-tied power spikes that directly enhance the fantasy of that gathering discipline. 

**Spawn & Buff Rules (all three bosses):**
- **Spawn**: 1–2% chance when initiating a combat encounter (Treasure Monster style check). Inserted after Treasure Monster but before Regular Monster in the encounter priority chain. **Scope is limited to normal combat only** (not Codex, Ascent, Dojo, or other special modes).
- **Design**: Generated through the existing `core/combat/mobgen/gen_mob.py` system (standard HP/level/stat scaling). One thematic gimmick modifier is manually attached:
  - Golem: Pure +15% Physical Damage Reduction (exact same behavior as other DR modifiers).
  - Leviathan: Swarm of fish dealing minion-style damage (1% player Max HP true damage at 50% frequency per monster turn).
  - Colossus: 10% snare chance (detailed above).
- **Custom Modifiers**: All three gimmicks will be implemented as new unrollable "uber"-style entries in `core/combat/mobgen/modifier_data.py` (internal names to be chosen during implementation). They are never randomly rolled.
- **Defeat Flow**: Triggers a custom view (single class in a new file under `core/combat/views/`). One-time harvest rolls exactly **2–5** of the matching remnant (unaffected by any other mechanics). Normal combat victory rewards still apply.
- **Buff (Tripled Passive Ticks)**: 
  - Stored in the per-skill DB columns on `gathering_mastery`.
  - When the hourly scheduled skill task runs: Read the DB, check each skill's counter individually. If > 0 for a skill, multiply the **entire yield** for that skill by 3 for this tick, then decrement the counter.
  - Stacks additively across multiple defeats.
- **Visibility**: Only shown in the custom defeat view ("Your next 10 passive skilling ticks for [Skill] are now tripled"). No persistent UI indicator elsewhere.
- **Node Text**: Explicitly states "Grants a chance to encounter the [Boss Name] during combat."

These bosses are meant to feel like exciting, occasional windfalls for dedicated mastery investment rather than high-stakes content. Flavor text and exact messaging are deferred to implementation.

### 8.4 Cross-Skill / "Gathering Lore" Capstones

These live in a small shared section (requires points spent across multiple skills). There is **no friction** for maxing all three skills — they are intended to be progressed at a similar pace. Dumping all points into one tree is allowed but not optimal.

- **Versatile Gatherer** (3 pts, req. 8+ in two skills): +5% yield to all three gathering skills.
- **Synergistic Refiner** (4 pts): Further improves the global settlement refining bonuses from the three "Master" nodes.
- **Skilled Survivor** (5 pts): General improvement to Skiller proc rates and yields across all skills.
- **Nature's Attunement** (requires owning all three prestige capstones — i.e. at least 11 points invested in each of the three trees): Unlocks a global passive that increases the chance of receiving a **Rune of Nature** from the Elemental of Elements encounter (bringing the total from 3% base up to 8%). This is the primary way to improve the rare drop rate. Also grants a small permanent gathering yield bonus. No cosmetics are tied to this node (prestige cosmetics can be handled separately if desired).

---

## 8.5 Concrete Numbers (Locked)

All values below are proposed as final for implementation unless playtesting shows major issues.

### Point Rates (Locked)
- Tier 1: 0.6 pts/day
- +0.3 per tier
- Tier 5 (BiS): **1.8 pts/day per skill**

### Target Investment
- Solid liked tree: **42–45 points** (~23–25 days at BiS)
- Heavy investment: 52–55 points
- Everything in one skill: 58 points

### Node Costs (Locked Pattern)
1 / 2 / 3 / 5 / 8 (with some 4pt proc nodes)

### Yield Branch (Deep Veins / Patient Waters / Strong Arm) — Locked
- 1 pt: **+8%** total yield
- 2 pt: **+16%** total yield
- 5 pt: **+26%** total yield
- 4 pt (proc node, req. 9 pts in branch): 12% chance per passive tick for **+70%** extra resources that tick

### Quality Branch (Vein Memory / Abyssal Memory / Heartwood Memory) — Locked
- 1 pt: **+20%** to signature resource (Idea Ore / Titanium Bones / Idea Logs)
- 2 pt: **+38%** to signature + 6% chance to produce signature resource below tool tier
- 3 pt: Unlocks remnants + Rich events for that skill
- 5 pt: Rich event base chance **22%**, multiplier **2.6×**, guarantees **3–5** remnants

**Remnant Generation (when Quality 3pt+ owned):**
- Baseline: **5.5%** per passive tick
- During Rich event: 100% chance, average **4 remnants** per event

### Synergy Branch Examples (Locked Values)
- Tool/Entry cost reduction: **12%**
- Skiller synergy: **+65%** proc chance and **+45%** extra yield
- Settlement refining: **+10%** more refined output
- Alchemy (Master Baiter equivalent): One-step better ratio, usable **once per day**
- 5pt capstone: **+55%** to signature resource + small independent Rich proc chance

### Prestige Capstones (8pt)
- Boss encounter rate: **1–2%** (Treasure Monster style)
- Triple tick award on defeat: **+10** ticks
- Harvest on defeat: **2–5** remnants (fixed, no modifiers)

### Rune of Nature Crafting Cost (Locked Starting Point)
- **68 Geode Cores + 68 Tide Relics + 68 Heartwood Shards**
- 350,000 gold
- 2 Spirit Stones

**Expected cadence for a Quality-focused player:** One Rune of Nature every **5–7 weeks**.

### Settlement Black Market Exchange (Locked Starting Point)
- **55 remnants** (any combination of the three types, or single type) = 1 rare Settlement currency (Diviner's Rod / Unidentified Blueprint / Development Contract).

These numbers are designed so that:
- Yield players feel powerful at raw generation.
- Quality players become the main source of Rune of Nature and rare Settlement items.
- Synergy players meaningfully improve dispatch, refining, alchemy, and Skiller procs.
- The system hits the 1-month / 3-month target.

---

## 9. Mechanical Integration Points (What Actually Changes)

### Core Logic
- `core/skills/mechanics.py`: Extend `calculate_yield` (or add a wrapper) that accepts mastery data and applies global multipliers + remnant procs + Rich event logic. Also add logic to check the per-skill tripled tick counters and multiply the entire yield by 3 when active.
- New `core/skills/mastery.py`: Stateless helpers for point calculations, node effects, remnant generation, and embed builders.

### Combat System Changes (New)
- `core/combat/mobgen/modifier_data.py`: Add three new unrollable "uber"-pool custom modifiers:
  - One for +15% PDR (Golem).
  - One for 50% frequency 1% Max HP true damage bites (Leviathan).
  - One for 10% snare chance (Colossus — this one will also drive UI/turn logic).
- New file(s) under `core/combat/views/`: Custom defeat views for the three skilling bosses (harvest action that awards 2-5 remnants + the +10 tick buff message).
- `core/combat/turns/` + relevant combat view: Snare status on player + "Free Yourself" button (added greyed out for the encounter, enabled on snare) + processing one extra monster turn when clicked (modeled on current Heal button behavior). No dynamic component add/remove.
- The special bosses will be generated via new helper functions (similar to `generate_uber_*` functions) that call the normal flow and then attach the custom modifier.
- Hourly scheduled skill task (`cogs/skills.py` + `SkillMechanics`): Read the three tripled tick counters from DB, apply 3x to the entire yield for any skill that has remaining ticks, then decrement.

### Passive Regeneration
- `cogs/skills.py` (`schedule_skills` task): After calculating base yield (with mastery modifiers and any active tripled tick multipliers), award the daily Artisan Points (1.5 at BiS per skill). Also handle remnant generation from Rich events.

### Dispatch
- `core/partners/dispatch.py` + `_helpers.py`: When calculating gathering dispatch rewards, read the player's mastery levels in the relevant skill and apply a small `skilling_mult` bonus (or direct extra yield) if the player has invested in that skill's Synergy or Yield nodes.

### Settlement Refining
- `core/settlement/mechanics.py`: In `calculate_production` (converter path), apply the global "Master Quarry / Master Baiter / Seasoned Timber" bonuses if the player owns the corresponding nodes. This is a simple multiplier on the output side — very clean.

### Alchemy
- `core/alchemy/` (views + repository): When performing transmutations, check for the "Master Baiter" (or equivalent) node and apply the improved ratio (with appropriate rate limiting if needed).

### Skiller Boots
- `core/combat/economy/drops.py` (`proc_skiller`): After calculating base resources, apply the "Skilled Hands / Favored by the Currents" bonuses if owned. Already a single contained function — very easy win.

### Elemental of Elements
- `core/combat/views/views_elemental.py` (or the relevant uber reward path): On final boss defeat, roll for Rune of Nature drop (3-5% base). Apply any global passive modifiers from high total mastery.

### New Mastery UI
- New file: `core/skills/views/mastery_view.py` (child of `BaseView`).
- Opened from the existing `GatherView` via a new "Mastery" / "Specialize" button.
- Uses Select menus for node purchases (excellent mobile UX).
- Shows current points, branch progress, and remnant counts.
- Respec flow uses a confirmation + Rune cost display.

### Database
- New table `gathering_mastery` (see below).
- Add `artisan_runes` (or specifically `runes_of_nature`) to `users` table or a small currency table.

---

## 10. Database Changes

```sql
CREATE TABLE IF NOT EXISTS gathering_mastery (
    user_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    mining_points INTEGER DEFAULT 0,
    fishing_points INTEGER DEFAULT 0,
    woodcutting_points INTEGER DEFAULT 0,
    mining_alloc TEXT DEFAULT '{}',      -- JSON of purchased nodes per branch
    fishing_alloc TEXT DEFAULT '{}',
    woodcutting_alloc TEXT DEFAULT '{}',
    last_point_claim TEXT,               -- ISO timestamp for catch-up

    -- Per-skill counters for the special remnant boss triple-yield buffs (additive stacking)
    mining_tripled_ticks INTEGER DEFAULT 0,
    fishing_tripled_ticks INTEGER DEFAULT 0,
    woodcutting_tripled_ticks INTEGER DEFAULT 0,

    total_mastery_invested INTEGER DEFAULT 0, -- for cross-skill passives & drop rate
    PRIMARY KEY (user_id, server_id)
);

-- Currency
ALTER TABLE users ADD COLUMN runes_of_nature INTEGER DEFAULT 0;
```

Repository methods needed in `SkillRepository` (or a small new `mastery.py` repo):
- `get_mastery(user_id, server_id)`
- `add_points(...)`
- `purchase_node(...)` (atomic, validates cost)
- `respec_skill(user_id, server_id, skill, cost_in_runes)`
- `add_runes_of_nature(...)`
- `get_tripled_tick_counter(skill)`
- `add_tripled_ticks(skill, amount)`  -- used when a remnant boss is defeated
- `consume_tripled_tick(skill)`   -- called during the hourly passive task if the counter > 0 (applies 3x yield and decrements)

---

## 11. Balance Philosophy & Player Choice

The tree is deliberately designed so that going "all in on Yield" feels different from "Quality + Synergy".

- Pure Yield players become extremely efficient resource printers.
- Quality investors get exciting "while you were away" moments and become the main producers of Rune of Nature (enabling respecs and chasing other power).
- Synergy investors make their partners, settlement, alchemy, and Skiller procs noticeably better.

Because respecs cost a scarce rune, these choices feel permanent for long stretches of time. This is intended.

The system should **not** make gathering strictly better than combat or settlement. It should make gathering feel like a deep, worthwhile long-term investment.

---

## 12. Implementation Scoping (Detailed)

This section provides a realistic breakdown of the work required to deliver the Artisan Mastery system, based on all locked decisions.

### Recommended MVP Scope (Phase 1 – High Value, Contained Risk)

**Goal:** Deliver the core fantasy (long-term passive progression + meaningful choices) as quickly as possible while deferring the most complex combat work.

**Included in MVP:**
- Full point economy (pure passive only, 1.8 pts/day at BiS)
- Complete 3-branch trees per skill with all locked numbers
- Basic Mastery UI (tab in `/gather` + node purchase via Selects)
- DB table + all repository methods
- Global Yield / Quality / Synergy bonuses applied to passive regeneration
- Rich events + basic remnant generation (no bosses yet)
- Rune of Nature crafting (from remnants) + respec flow
- Settlement Black Market remnant exchange

**Explicitly Deferred from MVP:**
- All three special remnant bosses (Meridian Golem, etc.)
- Triple-tick buff system and snare logic
- Nature's Attunement (the cross-skill drop rate passive)
- Profile / embed updates showing mastery investment
- Polish, flavor text, and advanced messaging

This MVP would already feel like a substantial new long-term system.

### Work Breakdown by Area

| Area | Effort | Key Files / Changes | Notes |
|------|--------|---------------------|-------|
| **Database & Repository** | Medium | `database/repositories/skills.py`<br>New table `gathering_mastery` + columns<br>~10-12 new methods | Includes tripled tick counters and mastery allocation JSON handling |
| **Point Accrual & Hourly Task** | Small-Medium | `cogs/skills.py`<br>`core/skills/mechanics.py` | Pure passive points + Rich event remnant generation. Must be clean and testable |
| **Mastery Logic Layer** | Medium | New: `core/skills/mastery.py` (or extend mechanics) | Node effects, point validation, remnant calc, yield modifiers |
| **Mastery UI** | Medium-Large | New: `core/skills/views/mastery_view.py`<br>Update `core/skills/views.py` (GatherView) | Biggest new UI surface. Must follow BaseView + Select patterns |
| **Yield Integration** | Medium | `core/skills/mechanics.py` (calculate_yield wrapper)<br>Updates in passive task | Apply all global bonuses + Rich events |
| **Synergy Integrations** | Small-Medium | `core/settlement/mechanics.py`<br>`core/alchemy/`<br>`core/partners/dispatch.py`<br>`core/combat/economy/drops.py` | Refining %, alchemy ratio, dispatch skilling_mult, Skiller boosts |
| **Rune of Nature + Respec** | Medium | New logic in mastery layer<br>UI in MasteryView<br>Update to users table | Crafting, spending, validation |
| **Settlement Remnant Exchange** | Small | Black Market views + settlement repository | Simple conversion UI |
| **Custom Modifiers (Bosses)** | Medium | `core/combat/mobgen/modifier_data.py` | 3 new unrollable "uber" modifiers (Golem DR, Leviathan swarm, Colossus snare chance) |
| **Boss Generation** | Medium | `core/combat/mobgen/gen_mob.py` (new helpers) | 3 new generation functions + spawn priority insertion |
| **Custom Defeat Views + Harvest** | Medium-Large | New file(s) under `core/combat/views/` | One class with 3 harvest actions (2-5 remnants each) |
| **Snare Logic (Colossus)** | Large | `core/combat/turns/`<br>Relevant combat view(s) | Player status, button enable/disable, extra monster turn on click |
| **Triple Tick Buff System** | Medium | Hourly task + mastery layer<br>DB columns already planned | Per-skill counters, 3x entire yield, decrement |
| **Elemental Drop Rate Passive** | Small | Nature's Attunement unlock check + modifier application | Requires all 3 capstones |

### Recommended Implementation Order

1. **DB + Repository layer** (foundation)
2. **Point accrual + basic passive yield modifiers** (core loop)
3. **Mastery logic + simple MasteryView** (MVP UI)
4. **Synergy integrations** (Settlement, Alchemy, Dispatch, Skiller)
5. **Rune crafting + respec + Black Market exchange** (first real sink + respec fantasy)
6. **Custom modifiers + boss generation** (combat side)
7. **Custom defeat views + harvest + triple tick system**
8. **Snare button + turn logic** (hardest combat piece)
9. **Polish, Nature's Attunement, profile updates, flavor**

### Effort Estimate (Rough)

- **MVP (steps 1-5)**: 4–6 weeks for one experienced developer (assuming good familiarity with the codebase)
- **Full feature including bosses (steps 1-9)**: 8–11 weeks
- **With testing + iteration**: Add 30-40%

### Key Technical Risks / Unknowns

- **Snare button + turn skipping** is the single largest unknown. No existing precedent for dynamically enabling a button mid-fight or forcing an extra monster turn on button press.
- How cleanly the hourly task can read mastery state + triple tick counters without performance issues.
- Whether the new MasteryView can comfortably live inside the existing GatherView tab system or needs to be a separate view stack.
- Balance tuning speed once real remnant generation data exists.

### Suggested Next Steps After Design Sign-off

1. Lock the final numbers (currently proposed in 8.5).
2. Create a task breakdown / ticket list from the table above.
3. Prototype the DB schema + repository methods first (lowest risk, highest leverage).
4. Build the point accrual + basic yield modifier logic next.

This scoping is intentionally realistic and accounts for the full complexity of the special bosses and snare mechanic that were added late in the design process.

---

## 13. Risks & Mitigations

- **Power creep:** All numbers start conservative. Global multipliers are easy to tune.
- **UI complexity in Discord:** Heavy use of Selects + clean multi-page or tabbed embeds. Follow existing patterns from settlement research and hematurgy.
- **Rune scarcity frustration:** Make the crafting recipe achievable for dedicated players while keeping the Elemental drop as exciting rare loot.
- **Active minigame neglect:** Explicitly document that we are not deepening them in this feature. If they are ever improved, it will be a separate project.
- **Invisible state:** Because bonuses are global, the mastery UI must do an excellent job surfacing "what your points are actually doing."
- **Combat boss bloat:** The special remnant bosses (Meridian Golem etc.) must be implemented carefully so they don't feel like mandatory content or dilute the existing encounter pool. They should feel like exciting, occasional rewards for mastery investment.

---

## 14. Open Questions for Review

All major design decisions and concrete numbers are now locked. The remaining items are almost entirely implementation or tuning related:

1. **Playtesting & Tuning** (post-launch):
   - Do the locked values (1.8 pts/day, 42–45 points per liked tree, 68 remnants per rune, etc.) feel good after real data?
   - Rich event frequency and remnant output rates will almost certainly need small adjustments.

2. **Implementation unknowns** (see detailed Scoping section above):
   - Exact difficulty of the snare button + extra monster turn logic.
   - Cleanest way to wire triple tick consumption into the hourly task.
   - How the new MasteryView interacts with the existing GatherView tab system.

Everything else (node effects, spawn rules, boss gimmicks, harvest amounts, respec flow, etc.) is considered finalized.

---

## Appendix A: Example Player Paths

**"The Printer"** (Heavy Yield focus)
- Dumps almost everything into the three Yield branches.
- Becomes an absolute monster at raw resource generation.
- Rarely needs to respec.

**"The Remnant Baron"** (Quality focus)
- Goes deep into all three Quality branches.
- Generates large amounts of Geode Cores / Tide Relics / Heartwood Shards.
- Crafts Runes of Nature regularly and can experiment with different builds or help friends.

**"The Synergist"** (Support focus)
- Spreads points across Synergy nodes + some Yield.
- Their partners bring back noticeably better gathering hauls.
- Their settlement refining and alchemy are more efficient.
- Skiller procs feel much stronger.

**"The True Artisan"** (Long-term completionist)
- Eventually buys almost everything + the big cross-skill capstones.
- Has cosmetic prestige + the best possible passive gathering experience.

---

**End of Design Document**

This document is intended as a complete, reviewable artifact. Once we align on the details above (especially rune costs, exact node values, and Phase 1 scope), we can move to implementation with high confidence.

Ready for detailed review and iteration.