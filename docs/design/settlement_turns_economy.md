# Design: Settlement Turns Economy & Development Layer

**Status:** Draft for Discussion  
**Author:** Grok (based on user direction + codebase audit)  
**Date:** 2026  
**Related Systems:** Settlement (all buildings, plots, research, black market, town hall, workers), Combat (drops + stamina), Quests (board + horizon), Partners (dispatch), Alchemy, Hematurgy (Hatchery), Skills (gathering), Prestige sinks

---

## 1. Executive Summary

This document proposes adding a **discrete "Turns" progression layer** on top of the existing real-time Settlement economy. The goal is to transform Settlement from a mostly passive "set workers and collect hours later" background system into a living, decision-rich idle city builder that creates the addictive "just one more turn" loop while preserving strong rewards for pure offline play.

**Core Fantasy:**  
Your settlement operates on its own rhythm of **Development Turns** (virtual work days / planning cycles). You influence and accelerate this rhythm by feeding it activity from the rest of the game (combat, quests, deliberate settlement management). Buildings that don't produce passive real-time resources become interactive experiences. Periodic events force meaningful choices. Construction, Research, and special projects become multi-turn processes instead of instant or pure wall-clock timers.

**Key Pillars:**
- **Hybrid time model**: Real-time passive production for generators (timber, stone, bars, stamina, etc.) remains the backbone for fully idle players.
- **Development Turns** as the primary development/progress unit. These are purchased using a more granular Ideology-themed token.
- **Events** on turn milestones create the "just one more turn" tension.
- **Sinks & Mini-games**: Black Market becomes a proper merchant value-trading mini-game with processing time. Research and Construction become turn-gated.
- **Cross-system integration**: Combat, quests, and settlement activities all feed the turn economy.
- **Dual progression**: Active players accelerate development and optimize events. Pure idlers still get meaningful (if slower) growth via passive generation + slow real-time resources.

This keeps the current resource economy mostly intact while adding depth, frequent decisions, and long-term engagement without exploding the main power curve.

---

## 2. Goals & Non-Goals

### Goals
- Create a genuine "just one more turn" feeling inside Settlement.
- Make construction, upgrades, and research feel like meaningful multi-step projects rather than instant buys or pure timers.
- Turn "non-generator" buildings (especially Black Market) into engaging decision spaces.
- Reward both highly active players (frequent small decisions + event optimization) and fully idle players (slow but reliable passive gains).
- Create new sinks for unwanted resources/items without being simplistic 1:1 trades.
- Generate periodic excitement via events (raids, boons, opportunities) that tie back into the main game.
- Strengthen the feeling that the settlement is a living extension of the player's overall journey.

### Non-Goals
- Replacing the entire real-time resource generation system (timber/stone/bars/stamina from workers).
- Making Settlement the primary power progression path (it should stay horizontal/supportive).
- Adding high-frequency chores that punish players who check in infrequently.
- Over-complicating the existing worker assignment + adjacency minigame.

---

## 3. Current Settlement Economy Audit (Ground Truth)

### Resource Types
- **Core settlement resources**: Timber, Stone (player-collected + generated).
- **Processed materials**: Iron/Steel/Gold/Platinum/Idea bars, various Logs/Planks, Bone → Essence lines.
- **Special upgrade materials**: Magma Core, Life Root, Spirit Shard, Celestial Stone, Infernal Cinder, Void Crystal, etc. (used for T3+ building upgrades).
- **New Resource: Idlem**
  - Produced **only through Development Turns** (1–2 per turn at base, no real-time passive generation).
  - Used for the new Black Market passive tree and final-tier building upgrades.
  - Deliberately scarce and valuable.
- **Development Contracts (DCs)**: Used to develop plots and (in some contexts) Town Hall progress. Earned slowly from "Expedition Camp" plot bonuses (1 DC per 48h per such plot). Can also be awarded by events.
- **Side outputs**: War Camp Stamina, Companion Cookies (→ pet XP), Market Gold (direct to player gold).

### Current Progression Gates
- **Research**: 20-hour real-time gate using Unidentified Blueprints (combat drop). One active at a time. Unlocks certain buildings for construction.
- **Construction**: Instant (pay resources + short animation). Some buildings require prior research.
- **Building Upgrades**: Instant pay (timber + stone + gold + special material depending on building).
- **Black Market**: Direct trades (gold/runes/keys for caches, 1 blueprint for 1-3 random special materials). Tier gives loot quantity bonus. No processing time.
- **Plot Development**: Costs Development Contracts + assigns a random bonus type (can be rerolled with Diviner's Rod — combat drop).
- **Town Hall**: Upgrades cost resources + (sometimes) special materials. Improves meta building slots and other bonuses. DCs are crafted here with a daily cap.

### Current Problems
- Most interaction is "assign workers → come back much later."
- Research and construction feel like tax timers rather than projects.
- Black Market is just another vendor with good rates.
- Very few reasons to return to the settlement screen between big collection moments.
- Limited "heartbeat" or surprise.

---

## Additional Major Design Decisions

### Workers Economy
Currently the primary (and almost only) way to gain workers is the `/propagate` command.

**New Building: Nursery**
- Produces workers **exclusively by spending Development Turns** (no real-time passive generation).
- This becomes the main long-term growth path for active settlement players.
- Thematically perfect as a dedicated facility for raising and training new settlers loyal to the ideology.

### Building Consolidation — Uber Shrine
The five separate Uber Shrines (celestial, infernal, void, twin, corruption) consume too much grid space.

**Proposed Merge**:
- Single building: **"Uber Shrine"**
- Inside the building are individual statues/altars for each of the five powers.
- Each statue has its own independent "worshipper" worker pool.
- This dramatically reduces grid pressure while preserving all current mechanical identity and power.

### New Resource: Idlem
- **Name**: Idlem
- Production: 1–2 per Development Turn only. **No real-time passive generation**.
- Purpose:
  - Primary currency for the future Black Market passive tree.
  - Required for final-tier (T5) upgrades on many buildings.
- This resource is deliberately meant to feel scarce and prestigious.

---

## 4. Proposed Development Turns Economy

### Core Currencies

**Development Turns (DT)**  
This is the main "progress unit" for the settlement (the "day" or "work cycle").

- 1 Development Turn = 10 base tokens (see below).
- Used for: Construction, Upgrades, Research, Black Market processing, Nursery worker production, special projects, and resolving certain events.
- The player advances their settlement by spending these turns.

**Base Token: Zeal** (proposed name)  
**Working Name**: **Zeal** (internal: `settlement_zeal`).

- **Fantasy**: Zeal represents the raw ideological drive, fervor, and conviction your followers pour into the settlement. It is the granular resource earned from the wider world.
- Earned primarily from **combat** (small amounts per victory, with strong diminishing returns).
- Also earned from quest completions, certain settlement activities, and events.
- **Conversion**: 10 Zeal = 1 Development Turn.
- This granularity makes diminishing returns clean and fair (you don't suddenly go from "getting turns" to "getting nothing").

**Rationale for "Zeal"**:
- Strongly tied to the Ideology theme of the game.
- Short, punchy, and evocative ("Your actions generate Zeal for your cause").
- Feels like a token you can "spend" or "invest" into your settlement's future.
- Alternatives considered: Fervor, Conviction, Mandate, Devotion, Allegiance. "Zeal" won for brevity and thematic strength.

#### Sources (Tunable — start conservative)

**Active / Semi-Active Sources (Primary)**
- **Combat**: Primary source of **Zeal**. Small amounts per victory with strong diminishing returns. Goal: ~600 Zeal should be reasonably achievable for active players in a day, after which returns drop sharply.
- **Quests**: Reliable injections of Zeal on contract and Horizon completions.
- **Deliberate Settlement Activity**:
  - Black Market merchant mini-game (major source + sink).
  - Running the new **Nursery** building (see Workers section).
  - Partner dispatch tasks with a "Settlement Support" focus.

**Passive / Idle Sources (Secondary but Important)**
- Modest baseline passive Zeal generation.
- Each Town Hall tier grants a linear **+10%** increase to passive generation.
- At maximum tier (currently 7), this results in a 70% increase over baseline. This is meaningful but deliberately not competitive with active play.
- Expedition Camp plot bonus continues to award Development Contracts (with potential future synergy to Zeal).

**Event Sources**
- Many events award Zeal or full Development Turns on resolution.

**Caps (Hard + Soft)**
- **Hard daily cap**: Approximately 80 Development Turns (~800 Zeal) per 24-hour period before further gains become negligible (1-2 Zeal per encounter at the extreme end).
- 600 Zeal per day should be a realistic target for dedicated active play.
- After ~600 Zeal the returns become heavily diminished (soft wall), eventually hitting the hard wall.
- This structure protects the economy while still rewarding high activity up to a healthy point. Exact numbers will be refined in playtesting.

#### Sinks (The Heart of the Design)

**Major Sinks**
1. **New Construction** (replaces or heavily modifies current instant cost)
   - Base cost: Mix of Timber/Stone/Gold + a number of Development Turns (e.g. Logging Camp = 8 DT, Market = 18 DT, Barracks = 25 DT).
   - Higher-tier or special buildings cost significantly more turns.
   - Construction now takes multiple turns to complete (see "Project System" below).

2. **Building Upgrades** (T2–T5)
   - Each tier upgrade costs DTs + the existing resource/special material costs.
   - Higher tiers cost disproportionately more DTs (encourages spreading investment).

3. **Research**
   - Instead of (or in addition to) the 20h blueprint timer, research now costs a large number of DTs (e.g. 40–80 DT per building) + 1 Blueprint.
   - Can be done "instantly" by dumping turns, or accelerated gradually.
   - Still limited to one active research project at a time for focus.

4. **Black Market Merchant Mini-Game** (Major New Sink + Fun) — **Requires its own dedicated design document**
   - Player offers a mixed bundle of resources.
   - System calculates opaque but fair "Value".
   - Deal takes a variable number of Development Turns to process.
   - **Future Passive Tree** (primarily powered by Idlem):
     - Processing time reduction
     - Base value multipliers
     - Toggleable targeted reward biases (more runes, skilling materials, gold, curios, gear, monster eggs, Consume body parts, etc.)
     - High-tier nodes for exciting outcomes (rare eggs, mysterious flesh for Consume, etc.)
   - This will be one of the deepest and most replayable systems in the settlement.

5. **Special Projects / Long-term Investments** (New Tab)
   - Things like "Expand Grid" (+2–4 plots), "Improve Passive Generation", "Unlock New Building Category", "Permanent Worker Efficiency", etc.
   - These are the big multi-hundred DT projects that feel like real settlement milestones.

6. **Event Resolution**
   - Some events (especially defensive ones) can be resolved faster/better by spending DTs.

**Soft / Supporting Sinks**
- Rerolling plot bonuses with Diviner's Rod could have a small DT cost in addition to the rod.
- Certain high-tier meta building effects could require ongoing DT "maintenance."

---

## 5. Project System (Construction, Upgrades, Research, Black Market Deals)

All major development actions become **Projects**:

- A project has:
  - Total Development Turn cost
  - Current investment
  - Status (In Progress / Paused / Completed)
  - Optional resource costs

- **Unlimited simultaneous projects** are allowed. There is no artificial limit on how many projects the player can have running at once.
- The player can freely allocate Development Turns across any active projects from the main Settlement interface.
- A visible **"Settlement — Day [X]"** tracker is shown prominently. This represents the total number of Development Turns the settlement has advanced since founding and provides excellent long-term context for events and progression.

This design strongly enables the "just one more turn" fantasy. After a productive combat session, the player can immediately decide where to invest their new turns across multiple projects.

---

## 6. Events — The "Just One More Turn" Engine

Events trigger based on the total **Settlement — Day [X]** counter (cumulative Development Turns advanced by the settlement).

### Two Event Types

**1. Scheduled / Upcoming Events** ("Will occur after X turns")
- The player is given advance warning.
- They can prepare (reassign workers, stock resources, spend turns on defenses, etc.).
- Creates planning and anticipation.

**2. Active Window Events** ("Happening for the next X turns")
- The event is currently active.
- The player has a limited window to respond optimally (e.g. defeat a raid, take advantage of a production surge, trade during a special market window).
- Creates urgency and "just one more turn" decisions.

This distinction is important for player agency and satisfaction.

**Event Categories** (examples):

**Crises (Risk + Decision)**
- **Defensive Events** should be implemented as proper **Settlement-specific boss encounters**, using generation logic similar to the gathering monster system (scaled appropriately to the settlement's power).
- Failure: The targeted building is **disabled** until repaired with Development Turns + resources. It does **not** get destroyed.
- Success: The player earns special high-value "settler materials" (new reward type).
- These are a core source of both tension and exciting rewards.

**Opportunities (Positive but Time-Sensitive)**
- "Merchant Caravan": Temporary excellent trade rates at Black Market (or a special one-time merchant event). Expires after X turns.
- "Inspiration Surge": Next Research or Project gets a big discount if started within X turns.
- "Resource Windfall": One generator produces massively for the next Y turns.

**Narrative / Flavor Events**
- Random small stories with light choices that give small permanent or long-duration bonuses (or just flavor + minor resources).

**Frequency**
- Start conservative: An event chance or guaranteed minor event every 8–15 cumulative turns advanced, with bigger events every 40–60 turns.
- Events can be "queued" so offline players don't miss everything.

---

## 7. Integration Points & Balance Philosophy

**Combat**
- Primary active source of DTs.
- Certain settlement buildings/passives can improve DT gain from combat (or give "settlement favor" that converts to DTs).

**Quests**
- Reliable medium-large DT injections on completion.
- Some quest rewards or Horizon paths can give bonus DTs or event rerolls.

**Partners (Dispatch)**
- New dispatch focus: "Settlement Liaison" — slower but generates DTs + special materials over time.

**Alchemy / Hematurgy**
- Some potions or blood passives could temporarily boost DT generation or event quality.

**Plot System**
- Certain strong plot bonuses (e.g. "Ley Line", "Ancient Ruins") could give passive DT generation or event advantages.
- Diviner's Rod remains the way to chase good bonuses, now with even more value.

**Development Contracts**
- Keep the current slow generation from Expedition Camps.
- Add events that can award batches of DCs.
- Possibly allow spending DTs to craft extra DCs (expensive conversion sink).

**Offline Play**
- Passive DT generation (small but real).
- Real-time resource production continues unchanged.
- Events that occurred while offline are summarized on next login with "Resolve" options.

---

## 8. Risks & Mitigations

- **DT Inflation**: Aggressive daily caps + heavy diminishing returns on combat income.
- **Feeling Punished for Being Offline**: Strong passive floor + "missed events are summarized, not lost."
- **Too Many Systems**: Phase the rollout (Research + Construction first, Black Market second, full Events third).
- **UI Complexity**: New "Projects" dashboard + clear "Advance Turns" / "Invest in X" buttons. Everything must be very scannable.
- **Economy Leak (Special Materials)**: The new Black Market merchant game should be tuned as the *primary* healthy sink for excess materials rather than pure generation.

---

## 9. Phased Implementation Roadmap (Recommended)

**Phase 1: Foundation**
- Add Development Turns currency + tracking.
- Convert Research to DT cost (keep or shorten the time gate as hybrid).
- Convert new building construction to DT + resource cost + short project.

**Phase 2: Depth**
- Building upgrades also cost DTs + become projects.
- Introduce basic event system (mostly positive opportunities at first).

**Phase 3: The Fun Hook**
- Full Black Market merchant mini-game with value calculation and turn processing.
- More dangerous/interesting events (raids etc.).
- Passive DT generation improvements via Town Hall and meta buildings.

**Phase 4: Polish & Expansion**
- Special projects (grid expansion, powerful permanent upgrades).
- Deeper Partner + Alchemy integration.
- Possible "Settlement Log" of past turns and events for flavor.

---

**This document is intended as the living draft.**

---

## Elements to Nail Down Before Scoping / Implementation

Before we move into detailed technical scoping, the following areas need clear decisions:

### 1. Zeal Economy Tuning
- Exact Zeal per combat victory at different player levels.
- Precise diminishing return curve (how many Zeal at 100 combats? 300? 600?).
- How much Zeal should come from quests vs combat vs other activities?

### 2. Passive Generation Baseline
- What is the actual baseline passive Zeal per hour at Town Hall Tier 1?
- How does this interact with the daily hard cap?

### 3. Nursery Building
- Cost per worker in Development Turns?
- Any worker cap or soft limits?
- Does it have tiers?

### 4. Idlem Generation & Uses
- Exact generation rate per turn (1? 1.5? 2?).
- Full list of things that will eventually cost Idlem (beyond Black Market tree and T5 upgrades).

### 5. Defensive Event Boss System
- Should these use the normal combat system with modified monsters, or a lighter settlement-specific resolution system?
- What are the "special settler materials" they reward?

### 6. Event Design Depth
- How many events do we want in the first release?
- Full table of "Scheduled" vs "Active Window" events with their DT triggers.

### 7. UI & Player Communication
- How is the "Settlement — Day [X]" counter displayed?
- How do players see upcoming/predicted events?
- Project management UI (list of active projects, easy investment buttons).

### 8. Black Market (High Priority Separate Doc)
- Value calculation formula (this will make or break the system).
- Risk/reward structure.
- Full passive tree design.

### 9. Long-term Grid & Building Roster
- After the Uber Shrine consolidation, what is the realistic future plan for the 20-plot grid?
- Are there plans for more regular buildings that would require grid expansion mechanics?

Once we have solid answers on the above (especially Zeal economy numbers, Nursery costs, and the two-event-type philosophy), we can move to a scoped implementation plan with clear milestones.