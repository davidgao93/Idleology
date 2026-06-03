# Design: Settlement Turns Economy & Development Layer

**Status:** Draft for Discussion  
**Author:** Grok (based on user direction + codebase audit)  
**Date:** 2026  
**Related Systems:** Settlement (all buildings, plots, research, black market, town hall, workers), Combat (drops + stamina), Quests (board + horizon), Partners (dispatch), Alchemy, Hematurgy (Hatchery), Skills (gathering), Prestige sinks

**For AI Implementer Note:** This document, combined with the Black Market one, provides the full spec. Follow AGENTS.md / CLAUDE.md strictly: all SQL in database/repositories/, views extend BaseView, stateless builders in .py or ui.py files, cogs are thin, use core/images.py for assets, etc. Add new methods to repositories as needed. New currency columns go on the users or settlements table following existing patterns (direct INTEGER columns). Track total turns on the settlements table. Use transactions for "Next Turn" processing to keep state consistent.

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

## Core Turn Processing Model (Critical Concept)

One of the most important aspects of this system is how time advances:

- **Each Development Turn processes all active systems simultaneously.**
- When the player clicks **"Next Turn"**, the following all happen at once:
  - The Nursery produces workers.
  - All active construction and upgrade projects advance by 1 turn.
  - The Black Market merchant processes deals.
  - The Idlem Foundry generates Idlem.
  - Any ongoing events tick down.
  - Scheduled events may trigger.
  - Passive Zeal generation for that turn is added.

- The **main Settlement Dashboard** becomes the central hub. It shows:
  - Current status ("Settlement — Day 47")
  - What is happening **this turn**
  - What is **upcoming** in the next few turns
  - A summary of what **just happened** on the previous turn

- Sub-systems (Plot Management, Black Market, Nursery management, specific building details, resource collection) are accessed from this dashboard but the player returns to the main view to actually advance time via the "Next Turn" button.

This design creates a clear mental model: manage your settlement → review the turn summary → decide whether to advance another turn.

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

## Database Schema Changes (Required for Implementation)

### Additions to `users` table (following existing currency column pattern)
```sql
`settlement_zeal` INTEGER NOT NULL DEFAULT 0,
`idlem` INTEGER NOT NULL DEFAULT 0,
```

### Additions to `settlements` table
```sql
`total_development_turns` INTEGER NOT NULL DEFAULT 0,  -- "Settlement — Day [X]"
`pending_zeal` INTEGER NOT NULL DEFAULT 0,  -- for passive accumulation between gathers
```

### New table: `settlement_pending_deals` (for Black Market)
```sql
CREATE TABLE IF NOT EXISTS settlement_pending_deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    offer_data TEXT NOT NULL,  -- JSON of resources offered
    total_value INTEGER NOT NULL,
    turns_remaining INTEGER NOT NULL,
    active_biases TEXT NOT NULL,  -- JSON array or comma list of active bias keys
    created_turn INTEGER NOT NULL,  -- the total_development_turns at creation
    UNIQUE(user_id, server_id)
);
```

### New table or extend research for turn-based projects? 
For v1, construction/upgrades/research can be handled by storing "required_turns" and "invested_turns" on the buildings table or a new `settlement_projects` table. Recommend a simple `settlement_projects` for flexibility:

```sql
CREATE TABLE IF NOT EXISTS settlement_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    project_type TEXT NOT NULL,  -- 'construction', 'upgrade', 'research', 'nursery', etc.
    target_id INTEGER,  -- building id or research type or null
    required_turns INTEGER NOT NULL,
    invested_turns INTEGER NOT NULL DEFAULT 0,
    data TEXT,  -- JSON for extra info (e.g. building_type for new builds)
    UNIQUE(user_id, server_id, project_type, target_id)
);
```

Update repositories/settlement.py with methods for zeal/idlem, total_turns, pending deals, projects, etc.

Existing `last_collection_time` and real-time production logic remains for passive resource generators.

---

## New Buildings & Changes to BUILDINGS / CONSTRUCTION_COSTS

In `core/settlement/constants.py` and `mechanics.py`:

- Add "nursery": {"type": "special", "effect": "worker_production_via_turns"}
- Add "idlem_foundry": {"type": "special", "effect": "idlem_production_via_turns"}
- Merge logic for "uber_shrine" (single building_type that supports multiple internal "statues" via workers_assigned split or sub-data). Each statue type has its own worker pool effect (sigil bonuses).

Update plots.py BUILDING_CODES, EMOJIS, META_BUILDINGS if needed.

Construction costs for new buildings will use the turn system (see Projects below).

---

## Additional Major Design Decisions

### Workers Economy
Currently the primary (and almost only) way to gain workers is the `/propagate` command.

**New Building: Nursery**
- Produces workers **exclusively by spending Development Turns** (no real-time passive generation).
- Target numbers (for balancing):
  - A dedicated active player hitting the ~600 Zeal soft cap per day generates roughly **60 turns**.
  - Goal: ~**100 workers per day** from active play.
  - Starting generation target: **~1.2 workers per turn** on average.
- Excess workers beyond what buildings can use can be assigned to the Town Hall for a very small bonus to passive Zeal generation.
- **Events** can dynamically affect the worker population (e.g. a meteor strike reducing workers, or a "baby boom" suddenly increasing Nursery output for several turns). This makes the worker economy feel alive.

### Building Consolidation — Uber Shrine
The five separate Uber Shrines (celestial, infernal, void, twin, corruption) consume too much grid space.

**Proposed Merge**:
- Single building: **"Uber Shrine"**
- Inside the building are individual statues/altars for each of the five powers.
- Each statue has its own independent "worshipper" worker pool.
- This dramatically reduces grid pressure while preserving all current mechanical identity and power.

### New Resource: Idlem & Idlem Foundry
- **Name**: Idlem
- **Generator**: New dedicated building called the **Idlem Foundry**.
  - Generates Idlem **per turn tick** (roughly 1-2 per turn at base).
  - No real-time passive generation outside of turns.
- **Purpose**:
  - Primary currency for the Black Market passive tree.
  - Required for final-tier (T5) upgrades.
- **Events** can interact with Idlem (e.g. force loss of stored Idlem/timber/stone, or temporarily disable Idlem production for X turns). This creates meaningful short-term decisions.

### Assistant Character ("The Maid")
- Introduce a recurring helpful NPC (working name: "The Maid" or a more flavorful ideology-appropriate title) who acts as a tutorial/explanation guide for the settlement systems.
- Similar in role to Guildmaster Amara in the early tutorial — she can provide contextual explanations, flavor, and guidance as the player unlocks new features (Nursery, Idlem Foundry, events, etc.).
- This greatly improves onboarding for what will become one of the deepest systems in the game.

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
- **Combat**: Primary source of **Zeal**.
  - Base: **10 Zeal per combat** for the first 10 combats (aligned with the 10-stamina pool).
  - This is the main way active players generate Development Turns.
  - Strong diminishing returns apply after the daily soft target (see Caps section).
- **Quests**:
  - Difficulty-scaled rewards (examples):
    - 1★ quest → **30 Zeal** (costs 5 turns in the quest system)
    - 3★ quest → **90 Zeal** (costs 15 turns)
  - Generic/non-zeal-targeted quests still grant a small bonus of **10–30 Zeal**.
  - These rewards are **in addition** to normal quest rewards.
- **Deliberate Settlement Activity**:
  - Black Market merchant mini-game (major source + sink).
  - Running the **Nursery** and **Idlem Foundry**.
  - Partner dispatch tasks with a "Settlement Support" focus.

**Passive / Idle Sources (Secondary but Important)**
- Baseline passive generation: **~1 Development Turn per hour** (10 Zeal/hour).
- This scales up to approximately **2 turns per hour** at the highest Town Hall tier.
- Players can "Gather Zeal" / collect this passive generation on demand.
- This provides a respectable floor for players who are less active while still making active play significantly more rewarding.

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

### Event Types

Events are tied to specific turn ticks and come in three main flavors:

1. **Upcoming / Scheduled** ("Will occur after X turns")
   - Player receives advance notice.
   - Primarily used for defensive events so the player can prepare (reassign workers, stock resources, etc.).

2. **Ongoing / Active Window** ("Happening for the next X turns")
   - The event is currently active and affecting the settlement.
   - Player can (and often should) make decisions during this window.

3. **Instant**
   - One-time effects with no player reaction window (pure flavor or immediate consequence).

**Initial Scope**: Design and implement a roster of **8–10 solid events** for launch rather than trying to create dozens immediately. More can be added over time.

Defensive events in particular will use the normal combat system with custom monster generation, modifiers, and custom loot tables (similar to how Uber bosses currently work), and will reward special settler materials on victory.

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

## Final Implementation Notes for AI Agent

(See the detailed "Implementation Guidance for AI Agent" section earlier in this document for DB schema, Next Turn flow, projects, events, new buildings, The Maid, tuning parameters, and testing checklist.)

This design + the Black Market merchant document together form a complete, self-contained spec. The agent should be able to:

- Implement the Zeal/Idlem currencies and turn tracking.
- Build the core "Next Turn" simultaneous processing engine.
- Add Nursery, Idlem Foundry, and the merged Uber Shrine.
- Wire in the initial events (8-10 with the three types).
- Integrate the full Black Market mini-game (value calc, offering with toggles, pending deals, processing on turn, reward rolls using the category breakdowns).
- Update all affected views and the main dashboard to the new "manage then Next Turn" pattern.
- Introduce the helpful Maid NPC for onboarding.
- Preserve all existing real-time generator behavior.

All per the project's strict layered architecture. 

The two documents are now ready for full implementation, testing, and review by an AI agent with access to the entire codebase.

### 6. Event Design Depth
- How many events do we want in the first release?
- Full table of "Scheduled" vs "Active Window" events with their DT triggers.

### 7. UI & Player Communication (Resolved Direction)
- **"Settlement — Day [X]"** lives in the **main dashboard embed title**.
- The main dashboard is the "command center": shows current turn effects, upcoming events, and recent history.
- Sub-views handle detailed management (plots, Black Market, specific buildings, resource collection).
- "Next Turn" button on the main dashboard advances all systems simultaneously.
- Passive resource collection is moved to its own view so the main screen stays focused on turn planning and events.

### 8. Black Market (High Priority Separate Doc)
- Value calculation formula (this will make or break the system).
- Risk/reward structure.
- Full passive tree design.

### 9. Long-term Grid & Building Roster
- After the Uber Shrine consolidation, what is the realistic future plan for the 20-plot grid?
- Are there plans for more regular buildings that would require grid expansion mechanics?

---

## 10. Implementation Guidance for AI Agent

### Core Flow: "Next Turn"
- In `SettlementDashboardView` (main view in `core/settlement/views/dashboard.py`):
  - Add "Next Turn" button (primary action).
  - On click (with _processing guard):
    1. Load current total_turns, zeal, idlem, projects, pending deals, active events.
    2. Compute passive zeal for the "hour" equivalent if using time, but primarily advance by 1 turn using stored total.
    3. For each active project: invested_turns += 1. If invested >= required, complete it (build building, finish research, add workers from nursery, add idlem from foundry, etc.).
    4. Process Black Market pending deals (see Black Market doc): decrement turns_remaining. If 0, roll rewards using current biases + value, grant them, delete deal.
    5. Tick any ongoing events (decrement duration, apply effects like worker loss, production pause, or trigger completion rewards).
    6. Check for new events based on the new total_turns (see Events section below). Add upcoming/scheduled to state or a pending_events structure.
    7. Update total_development_turns += 1.
    8. Add any passive zeal generation for this turn (based on Town Hall + meta buildings).
    9. Commit in a single transaction where possible.
    10. Rebuild embed with new "Day X", "This turn summary", "Upcoming", recent log.
  - All sub views (plot detail, black market, nursery detail, etc.) should have "Back to Dashboard" that returns without advancing time.

### Projects System
- Use `settlement_projects` table.
- When starting construction/upgrade/research/nursery work/idlem production: insert project row with required_turns (calculated from building costs or fixed).
- On Next Turn, advance all projects for the user.
- Completion logic in a central `SettlementMechanics.process_project_completion` or similar pure-ish function, then repo updates.
- For new builds: data contains building_type + plot_index. On complete, call existing build_structure but without immediate resource cost (costs paid when queuing? or part upfront).
- Research: similar to current but turn-based instead of 20h timer. Remove or deprecate time-based research start_time for turn projects.

### Events
- Track total_turns on settlements.
- Define events in `core/settlement/mechanics.py` or a new events.py as a list of dicts with:
  - trigger_turn (or range/modulo for recurring)
  - type: 'upcoming', 'ongoing', 'instant'
  - duration_turns (for ongoing)
  - effects: dict (e.g. {"disable_building": "some_type", "worker_loss": 50, "add_zeal": 20})
  - message templates for dashboard.
- On Next Turn, check if any events should trigger based on total_turns.
- Store active/pending events per user (new table `settlement_active_events` or JSON on settlements for simplicity in v1).
- "Upcoming" events are shown in dashboard with countdown turns.
- Defensive events: when triggered, create a special combat encounter (use existing combat flow but with custom monster from settlement context + modifiers). On win, grant special materials + resolve event. On loss or flee, disable building.

### New Buildings Processing (on Next Turn or dedicated)
- Nursery: if project invested, add ~1.2 workers (use float accumulator or per-turn roll for variance) to available workforce (but workers are assigned per building; perhaps add to a global pool and player assigns).
- Idlem Foundry: add Idlem directly.
- Worker assignment remains via existing UI, but now workers can come from Nursery turns.

### Assistant ("The Maid")
- Add a button "Ask the Maid" or contextual help on dashboard.
- Simple view or embed updates with flavor text explaining current systems, recent events, tips.
- Store a small state for "seen tutorials" if needed.
- Portrait: add to `core/images.py` as e.g. `SETTLEMENT_MAID`.

### Other
- Zeal collection: "Gather Zeal" button on dashboard that adds pending_zeal to main zeal and resets timer/accumulator.
- Update all relevant views (construction, detail, town_hall, plot_detail, research, black_market) to integrate with turn/project system instead of instant or time.
- In cogs/settlement.py: no logic changes, just route to updated views.
- Follow BaseView for all interactive views.
- Add new repo methods in `database/repositories/settlement.py` and possibly `users.py` for the new currencies and structures.
- Update `core/settlement/mechanics.py` with pure functions for production-per-turn, event effects, value calcs if shared.
- For Uber Shrine merge: treat as one building_type="uber_shrine", use workers_assigned for total, but store per-statue workers in a JSON or additional columns/sub-table. Effects apply based on per-statue counts.

### Tuning Parameters (put in constants.py or mechanics)
- Zeal per combat base (10 for first 10)
- Quest zeal rewards by difficulty
- Passive zeal per turn baseline (10), +10% per TH tier
- Daily hard cap 800 zeal
- Nursery workers per turn ~1.2
- Idlem per turn 1-2
- Event roster size for v1: 8-10

### Testing Checklist for Agent
- Fresh player (level 1): can access settlement, basic buildings, earn zeal from combat, advance turns.
- "Next Turn" processes multiple projects + deals + events atomically.
- Passive real-time collection still works for generators.
- Black Market (details in its doc) integrates.
- Events of all three types trigger correctly.
- Worker economy flows (propagate + nursery + assignment + events).
- No economy breakage (use existing sinks, no new infinite loops).
- UI remains responsive, uses BaseView patterns.

---

Many of the above points have now been resolved. The design is ready for full implementation following the project's layered architecture.

The companion Black Market design document provides the details for the merchant mini-game, pending deals processing on Next Turn, passive tree with toggles, value/roll system, and Madame Vespera NPC.