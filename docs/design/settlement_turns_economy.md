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
- **Development Turns** as the new active/semi-active development currency.
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
- **Development Contracts (DCs)**: Used to develop plots and (in some contexts) Town Hall progress. Earned slowly from "Expedition Camp" plot bonuses (1 DC per 48h per such plot).
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

## 4. Proposed Development Turns Economy

### Core Currency: Development Turns (DT)
**Working Name**: Development Turns (internal: `settlement_development_turns`).

**Fantasy**: These represent cycles of focused planning, labor direction, and settlement momentum. The player "spends" their personal attention and external activity to generate this momentum.

#### Sources (Tunable — start conservative)

**Active / Semi-Active Sources (Primary)**
- **Combat**: Small base amount per victory (e.g. 1–3 DT base, scaled lightly by player level or settlement Town Hall tier). Bonus for killing monsters near settlement level or using certain settlement passives.
- **Quests**: Fixed amount on contract/Horizon completion (e.g. 5–15 DT depending on tier). Bonus from "Prospector's License" or other quest-related unlocks.
- **Deliberate Settlement Activity**:
  - Using the Black Market merchant mini-game (see below).
  - Certain worker "focus" actions (temporarily assign extra workers to a "Planning Hall" meta building for DT generation).
  - Partner dispatch tasks with a new "Settlement Support" focus.

**Passive / Idle Sources (Secondary but Important)**
- Very slow background generation (e.g. 1 DT every 4–8 real hours, improved significantly by Town Hall tier and specific meta buildings like a future "Council Archives" or "Labor Exchange").
- Expedition Camp plot bonus could give a chance at DTs in addition to (or instead of some) DCs.

**Event Sources**
- Many turn-based events will award DTs on resolution (see Events section).

**Caps & Anti-Farming**
- Daily soft cap on combat/quest DT income (resets on a rolling 24h or server daily).
- Diminishing returns on very high activity (e.g. after 50–80 DT from combat in a day, further gains are heavily reduced).
- This prevents no-lifers from completely breaking the pace while still letting dedicated players pull ahead.

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

4. **Black Market Merchant Mini-Game** (Major New Sink + Fun)
   - Player offers a bundle of resources (timber, stone, bars, runes, keys, gear, bones, etc.).
   - The system calculates a "Value" based on rarity, quantity, and current settlement tier.
   - Higher value = better possible rewards + more turns required to process the deal.
   - Processing takes 3–25+ DTs (player can choose to "rush" by spending extra DTs for better results or accept the base time).
   - On completion, player returns to collect a randomized but value-appropriate reward (caches, special materials, rare plot bonuses, temporary buffs, etc.).
   - This becomes the primary sink for "junk" the player doesn't want while feeling like a proper shady merchant negotiation.

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

All major time-gated actions become **Projects**:

- A project has:
  - Total DT cost
  - Current DT invested
  - Status (In Progress / Paused / Completed)
  - (Optional) Resource costs paid upfront or over time

- Player can contribute any number of their current DTs to any active project at any time (from the main Settlement dashboard or a new "Projects" tab).
- Multiple projects can run in parallel, but with soft limits (e.g. only 2–3 active major projects at once, more for small ones).
- When a project reaches 100%, it completes on the next "turn advance" or immediately if the player forces it.

This creates the beautiful loop: "I just got 12 DT from that big combat session. Do I finish the Market now, push the Foundry upgrade, or save for the next Research?"

---

## 6. Events — The "Just One More Turn" Engine

Events trigger based on **cumulative turns advanced** by the player (global counter per settlement, not per project).

**Event Categories** (examples):

**Crises (Risk + Decision)**
- "Raiding Party": A building (or random plot) is attacked. Spend DTs + possibly fight a special encounter (or use settlement defenses) to resolve. Failure = building disabled until repaired with DTs + resources.
- "Worker Unrest": Temporary production penalty unless you spend DTs on morale or accept a resource cost.

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

## 10. Open Questions for Discussion

1. Exact name for the currency ("Development Turns", "Settlement Momentum", "Civic Labor", "Progress Tokens")?
2. How generous should passive DT generation be at different Town Hall tiers?
3. Should there be a hard daily cap on total DTs earnable, or only soft diminishing returns?
4. How many simultaneous active projects should the player be allowed?
5. Should failing defensive events ever destroy buildings, or only disable them temporarily?
6. Do we want a "Rush" mechanic (spend extra DTs or gold to complete projects faster)?
7. How visible should the "total turns advanced" counter be to the player?

---

**This document is intended as the living draft.** Once we align on the high-level economy and event philosophy, we can move to detailed spec for individual features (Black Market value formula, exact DT costs per building, event tables, etc.).

Next steps after alignment: Detailed Black Market mini-game spec + first-pass DT economy numbers + DB schema changes.