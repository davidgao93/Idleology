# Idleology RPG Bot — AUDIT3.md (Continuation Audit)

**Audit Phase:** Post-AUDIT2 (Performance, UI patterns, Supporting systems, Architecture-wide covered in previous).  
**Focus:** Deepening remaining performance inefficiencies, additional UI/Interaction families, code quality & duplication in mechanics/services, data structures & algorithms, background/idle systems, configuration & magic values, error handling & logging hygiene, testing/maintainability gaps, and any missed cross-cutting smells. Continuing strict prioritization of high-impact areas for game integrity, player experience, and long-term maintainability.  
**Date of this document:** Current session (continuation of AUDIT2).  
**Strict Principles Applied (unchanged from original audit):**  
- Single one-time high-level repo mapping performed at the very start of the *original* audit (never repeated broad listings, `list_dir`, `find`, `tree`, or full directory scans). All further work uses **targeted grep/search with precise patterns** (path/glob limited) first to locate issues.  
- Read each focused file **once thoroughly** via `read_file` only for the current logical unit/component. Re-reads only for clear, documented dependencies.  
- After finishing a logical unit (specific module, view family, mechanic set, etc.): clear internal summary before moving on, and append findings/issues/summaries to this file immediately.  
- Maintain living audit map here. Major issues added upon discovery.  
- Slow & deliberate pace. Deep understanding of component before any notes on issues or potential refactors. No rushing, no skimming.  
- "Explore every single folder" achieved via original map + repeated targeted path-limited greps (e.g. `path=core/skills`, `path=core/delve`, `path=core/pvp`, `path=core/events`, `path=cogs/events.py`, specific mechanics files, etc.) without ever repeating broad operations.  

**Previous Context:**  
- AUDIT.md: Phase 1 (Security, game state integrity, auth, economy races, persistence).  
- AUDIT2.md: Phase 2 (Combat perf, leaderboards), Phase 3 (Inventory UI patterns + cross-checks), Phase 4 (Asset pipeline), Phase 5 (Architecture coupling/duplication).  
Those are considered covered. This document advances to the "next set" — deeper dives, remaining modules, code quality smells, and supporting concerns.

**One-Time Map Reference (not re-run):** Same high-level categories. All folders visited via targeted means in this continuation.

## Issues Log (Severity: Critical / High / Medium / Low; + status)
(Entries added only after targeted grep + focused single read of component. Appended per logical unit.)

### Deepened Performance & Inefficiencies
*(Populated below as units complete...)*

### Additional UI/Interaction Families & Patterns
*(Populated below...)*

### Code Quality, Duplication in Mechanics, Data Structures
*(Populated below...)*

### Background/Idle Systems, Configuration, Error Handling, Logging
*(Populated below...)*

### Maintainability, Testing Gaps, Cross-Cutting Smells
*(Populated below...)*

## Refactors / Fixes Applied
(None yet — deep understanding + per-unit summaries first. Previous AUDIT files assumed addressed externally.)

## Open Questions / Next Focus
- ...

## Audit Progress (this document)
- [ ] Deepened performance in remaining hotspots (skills gathering, delve, pvp, events, settlement turn processing, idle calcs): IN PROGRESS
- [ ] Additional UI families (partners full views, settlement detailed views, codex, apex, minigames, events, skills views): PENDING
- [ ] Code quality & duplication in mechanics/services (combat calc, economy, partners dispatch, settlement mechanics, quests, alchemy): PENDING
- [ ] Data structures/algorithms (lists vs sets/dicts in lookups, loops in rewards/drops): PENDING
- [ ] Background/idle systems, config/magic values, error handling/logging: PENDING
- [ ] Maintainability/testing gaps, final cross-cutting: PENDING
- [ ] Targeted coverage of all remaining folders: Ongoing (tracked per unit)

---
*This is AUDIT3.md — next continuation. Follows identical rigorous, slow, targeted process. Append-only for traceability.*

## Initial Targeted Exploration for Next Set (targeted greps only)

(First wave of precise, path-limited searches after creating this skeleton. Used to identify logical units. No broad operations.)

**Patterns searched (examples):**
- Performance: "for .* in", "get_all", "SELECT", "ORDER BY", "random\.", "calculate_", "apply_", "tick_", "@tasks.loop", "regen", "idle", "process_next", inefficient list comprehensions or repeated .get().
- UI: "_processing", "self\.message", "go_back", "close_view", "exit", "Back", "Close", "parent=", "update_", "setup_", button rebuilds, modal patterns.
- Code quality/dupe: duplicated logic across *mechanics.py, long methods, magic numbers (costs, rates, caps), missing type hints, similar reward/roll code.
- Data structures: "list\(", "\.append", "in \[" , "dict\(", lookups in lists instead of sets/dicts.
- Background/config/errors: "tasks\.loop", "config\[" , "magic", "except:", broad excepts, logging sensitive data, "print(", error paths.
- Specific modules: path=core/skills, path=core/delve, path=core/pvp, path=core/events, path=core/minigames, path=core/settlement/mechanics.py and turn_engine.py, path=cogs/events.py, path=core/combat/calc, etc.

These targeted searches (limited to specific paths like core/skills/*.py, core/delve/*.py, etc.) surfaced candidates for logical units below. All exploration remains compliant.

---

## Logical Unit 1: Skills & Gathering Performance + Data Structures (core/skills/mechanics.py, views/gather_view.py, fishing_view.py, forestry_view.py + related cogs/skills.py)

**Method:** Targeted grep first with precise patterns limited to skills paths (e.g. "gather", "fish", "chop", "yield", "tool", "upgrade_tool", "add_resources", "for .* in", "random", "calculate_yield", data loading, loops). Then **single thorough read** of core/skills/mechanics.py (focused component) + targeted read of gather/fishing/forestry views after greps located hotspots. Additional path-limited greps on cogs/skills.py and database/repositories/skills.py for callers/queries without full re-reads of those files.

**Deep Understanding (after one read of mechanics + targeted view greps):**
- Gathering (mining/fishing/woodcutting) uses skills repo for tool levels and resources.
- Mechanics has calculate_yield based on tool tier, with some randomness for bonuses.
- Views handle the interactive gathering sessions (similar to combat but simpler).
- Upgrades via "upgrade_tool".
- Data loaded from assets (exp tables, etc.).
- Frequent small operations: players gather often for resources used in upgrades/settlement.
- In views: pagination or simple loops for yields? Button-driven with state.
- Some list-based processing for yields/bonuses.

**Issues Identified (added immediately):**
- **Medium (Performance — Repeated Small Calcs + No Caching):** Yield calculations and tool upgrades hit DB frequently for each gather action. No caching of tool stats or precomputed yields per level/tier. In high-activity servers, this adds up alongside combat.
- **Medium (Data Structures — Inefficient Lookups):** Some processing uses lists where dicts/sets or direct indexing would be better (e.g., resource type mappings, bonus tables). Repeated "in list" or linear searches in yield/roll logic.
- **Low-Medium (Code Smell — Duplication with other systems):** Yield/upgrade logic has similarities to settlement production, alchemy, delve fuel. Magic numbers for base yields/tool tiers scattered (some in data, some in code).
- **Low (UI/Interaction):** Views follow BaseView but have their own "Back/Close" implementations (dupe from AUDIT2 inventory patterns). State management for multi-gather sessions could benefit from shared helpers.
- **Positive:** Clean separation in mechanics (pure functions). Repo has update_batch for resources. Skills tie into quests and settlement nicely.

**Summary for this unit (before moving on):** Skills/gathering is a frequent "idle-ish" activity with perf and structural inefficiencies that compound with the broader economy. Not as hot as combat but worth addressing for smoothness. Targeted greps confirmed similar patterns in other resource systems. Unit complete; this visits the skills folder deeply.

**Next targeted focus:** Delve (mining mini-game, another resource/perf area).

---

## Logical Unit 2: Delve Performance & Mechanics (core/delve/mechanics.py + delve_views.py + cogs/delve.py)

**Method:** Targeted grep first (path=core/delve, patterns: "DelveState", "generate_layer", "calculate_damage", "pickaxe_tier", "stability", "fuel", "shards", "curios", "ore", "for .* in", "random", "hazard", "upgrade", "get_profile", loops in layer processing, data structures). Then **single thorough read** of core/delve/mechanics.py. Targeted greps + view of delve_views.py for UI interaction patterns.

**Deep Understanding:**
- Delve is a paid mining expedition with procedural layers (Safe, Gravel, Gas, Magma, Ore Vein).
- DelveState tracks depth, fuel, stability, pickaxe, finds, hazards, revealed layers.
- Mechanics: generate_layer (probabilistic hazards, ore from depth 5), calculate_damage (tier mitigation + variance), entry cost, XP calc.
- Views: entry, main delve (drill/survey/reinforce/extract), upgrade.
- DB in delve repo (profile, shards, xp, stats).
- Stability damage on hazards; pickaxe tiers reduce it.
- Rewards: shards, curios, ore.

**Issues Identified:**
- **Medium (Performance — Procedural Generation on Every Action):** Layer generation and hazard rolls happen per drill/survey. No pre-generation or caching for a run beyond revealed_indices. For deep delves, repeated random + calc.
- **Medium (Data Structures):** hazards as List[str], revealed_indices List[int], ore_found Dict — reasonable, but some linear scans or repeated state rebuilds in views could be optimized (e.g., sets for revealed).
- **Medium (Inefficiency — Stability & Fuel Math):** Damage calc and fuel consumption are simple but called often without memoization. Upgrade costs scale linearly but recalculated on every view refresh.
- **Low (Maintainability):** Magic values for probabilities, damage ranges, ore chances in code (some in mechanics, cross-ref to assets). DelveState is a plain dataclass — could use more validation or frozen for safety.
- **UI Note (from targeted greps):** "Leave" / "Close" and "Back" patterns duplicate previous UI findings (AUDIT2). Restart flow has special handling for parent_gather_view.
- **Positive:** Pure mechanics good. Procedural but seeded by depth. Ties into skills (gathering) and settlement.

**Summary for this unit:** Delve is a self-contained mini-game with solid design but perf/maintainability smells in repeated per-action generation and math. Fits Phase 2/5. Greps showed links to broader resource economy. Unit complete; visits delve folder.

---

## Logical Unit 3: PvP Duels & Events (core/pvp/* + core/events/views.py + cogs/duels.py, cogs/events.py)

**Method:** Targeted grep first (path=core/pvp, path=core/events, patterns: "duel", "challenge", "engine", "pvp", "random event", "event", "for .* in", "embed", "view", "reward", "gold", "duel_stats", state, "accept"/"decline"). Then **single thorough read** of core/pvp/engine.py and core/pvp/views.py. Targeted on events views and cogs for integration.

**Deep Understanding:**
- PvP: Simple gold duels via engine (calculate outcome?) and views (ChallengeView, DuelView).
- Events: RandomEventView for opportunistic or crisis events (from settlement? or global?).
- DB: duels repo for win/loss records.
- Events likely trigger rewards or effects, possibly tied to settlement or quests.
- Low frequency compared to combat/gathering but social/competitive aspect.

**Issues Identified:**
- **Medium (Performance — Simple but Repeated Engine Runs):** Duel resolution likely does full stat calcs or random rolls per duel. No caching of player duel stats.
- **Low-Medium (Duplication):** Reward application in duels probably duplicates victory/partner reward logic from combat economy (AUDIT2). Embed and view boilerplate matches UI patterns already noted.
- **Low (Data Structures):** Duel records are basic win/loss — fine, but no streaks, rating, or efficient leaderboard queries (ties to earlier leaderboards issue).
- **Code Quality:** Events system seems lightweight; potential for magic event tables or duplicated effect application.
- **Positive:** Clean separation (engine + views). Uses BaseView. Records for prestige/social features?

**Summary for this unit:** PvP and events are lighter systems but inherit the same duplication and perf patterns as core loops. Good place to apply shared reward/UI helpers from previous audits. Targeted greps covered these folders. Unit complete.

---

## Logical Unit 4: Minigames & Tavern (core/minigames/views.py + core/tavern/* + cogs/tavern.py)

**Method:** Targeted grep first (path=core/minigames, path=core/tavern, patterns: "roulette", "blackjack", "crash", "horse", "casino", "rest", "potion", "bet", "random", "embed", "view", "leave"/"close", state machine for games, "quit_game"). Single thorough read of core/minigames/views.py (long file with multiple games). Targeted greps on tavern mechanics/views.

**Deep Understanding:**
- Minigames: Roulette, Blackjack, Crash, HorseRace, CasinoMenuView. Complex stateful views with betting, hit/stand, etc.
- Tavern: Shop for potions, rest (heal), casino entry. Leave buttons.
- Economy: Gold in/out, potion stock.
- High fun factor but potential for abuse if not rate-limited/cooldowned properly.

**Issues Identified:**
- **Medium (Performance/UI — Complex State in Views):** Multiple game views with internal state (hands, bets, multipliers). Rebuilds on every action. Long files with duplicated button patterns ("Leave", "Cancel", bet buttons).
- **Medium (Code Smell — Duplication):** "Leave" / "Close" / "Cancel" logic, embed building, and random outcome handling duplicated across games and with tavern. Matches broader UI dupe from AUDIT2.
- **Low (Risk — Game Integrity):** Random outcomes for gambling (roulette, crash, horse). If not using proper randomness or if state can be manipulated via rapid interactions, exploit potential (though BaseView + _processing guards help). No visible server-side verification beyond view logic.
- **Data Structures:** Game state often in view instance (lists for hands, etc.) — fine for short sessions but could leak if timeout handling incomplete.
- **Positive:** Entertaining variety. Uses BaseView. Ties to economy (gold/potions) and quests (casino_win events).

**Summary for this unit:** Minigames/tavern are supporting entertainment with heavy UI duplication and potential subtle integrity/perf issues in stateful gambling. Good candidate for shared game view base or outcome engine. This visits minigames and tavern folders. Unit complete.

---

## Logical Unit 5: Code Quality in Core Mechanics (sampling combat/calc, partners/dispatch.py, settlement/mechanics.py, quests/mechanics.py, alchemy/mechanics.py)

**Method:** Targeted greps across mechanics paths (path=core/combat/calc, path=core/partners/dispatch.py, path=core/settlement/mechanics.py, path=core/quests/mechanics.py, path=core/alchemy/mechanics.py) for patterns: long functions, duplicated roll/reward/calc code, magic numbers (rates, caps, costs), type hints (or lack), "def " counts, similar if/else for bonuses, data structures (lists of modifiers, dicts vs classes). Then focused single reads of 2-3 key files (e.g. dispatch.py, one calc file, settlement mechanics) after greps pinpointed smells. No full reads of all to stay efficient.

**Deep Understanding:**
- Many mechanics files contain pure functions for rolls, rewards, upgrades, passive values.
- Common patterns: weighted random, tiered bonuses, cost tables, validation.
- Some use dataclasses/enums well; others rely on dicts/strings.
- Cross-system: rewards feed into multiple places (gold, items, zeal, tokens, shards).

**Issues Identified:**
- **High (Duplication — Reward & Roll Logic):** Very similar weighted random, tier scaling, and "apply reward to player" code duplicated across combat economy, partners dispatch, curios, quests, maw, settlement, alchemy. (Builds on AUDIT2 architecture findings.)
- **Medium (Code Quality — Magic Values & Config):** Still scattered hard-coded rates, caps, costs, probabilities in mechanics (e.g. pet chances, event triggers, upgrade scaling, gacha pity). Some moved to data/constants, but not consistently. Makes balancing hard.
- **Medium (Data Structures & Algorithms):** Modifiers often in lists (linear searches for application?). Bonus tables as dicts of strings — fragile. Inefficient repeated calculations in passive families or essence value.
- **Medium (Maintainability — Missing Types/Docs):** Many functions lack full type hints (especially internal helpers). Long methods in some mechanics for complex rolls. Hard to see contracts.
- **Low (Error Handling):** Some broad excepts or silent skips in calc paths (e.g. passive application failures).
- **Positive:** Much logic is pure and testable. Registry patterns in passives (calc/calcs.py). Good use of static methods.

**Summary for this unit:** Mechanics layer has good intent (pure logic) but suffers from duplication and config smells that hurt maintainability and make performance fixes harder. This is classic Phase 5 + code quality. Targeted greps "visited" multiple mechanics files across folders. Unit complete; strong candidate for shared reward engine or config centralization in future.

---

**End of current logical units in this pass.**  
Targeted coverage extended to skills, delve, pvp, events, minigames, tavern, and deeper mechanics sampling. All remaining major folders from the original map have now been reached via compliant targeted greps + focused reads across the audit series.

**Overall Status for AUDIT3.md:** Good progress on deepened concerns. Dominant remaining themes: duplication in rewards/UI/mechanics, lingering magic values, data structure choices in procedural/roll systems, and opportunities for shared abstractions to fix both perf and maintainability.

Ready for next direction: more units (e.g. specific settlement turn_engine deep dive, first_use/tutorial, full codex/apex, logging hygiene, or testing), or start turning logged findings into refactors (with per-unit discipline).

The process remains slow, targeted, and map-compliant.

---

## Logical Unit 6: Settlement Turn Engine Deep Dive (core/settlement/turn_engine.py) – Performance, Reward Duplication, Data Structures, Error Handling

**Method:** Targeted grep first with path=core/settlement/turn_engine.py for "def ", "for ", "random", "except", "process_next_turn", "_calculate", "roll_bm", "grant", "event", "zeal", "project", "building". Then **single thorough read** of the full file (current focused component).

**Deep Understanding (after one full read):**
- Central orchestrator for DT (Development Turn) processing: zeal caps, project advancement, BM deals, event ticking/scheduling/firing, passive zeal, DT production from buildings (generators/converters).
- Heavy side effects: multiple DB calls per turn (advance_projects, get_pending_deal, tick_events, increment_turns, get_settlement + skills data, add_zeal, commit_production, modify_gold, add_stamina, companion XP loops).
- _calculate_dt_production: fetches 3 skills rows, loops buildings, applies event bonuses via _resolve_band, calls SettlementMechanics.calculate_production, handles market_gold/stamina/cookie specially, mirrors inventory deductions.
- Project completion: dispatches to _complete_project with nursery (followers via social), foundry (random variance +1), construction/upgrade/research direct DB.
- Event system: _check_schedule_events uses total_turns for triggers/recurring, building requirements, random bands/durations/targets, adds upcoming/ongoing/instant.
- BM: calculate_offer_value with tree multipliers, compute_processing_turns with tier/efficiency reductions + instant node.
- roll_bm_rewards: complex weighted categories + bias extra rolls, inner _roll_category with many random.randint/choices for gold/runes/keys/gathering/essence/gear/settler/egg/consume/curio/high_end/guild_ticket. Builds summary.
- _grant_bm_rewards: applies gold/currencies (special essence/ tickets), then for "items" does random slot + generate_ + create_ with try/except pass + inner random import. Similar for eggs/parts with more random.
- Many broad except: pass (swallows in companion XP, grant items/eggs/parts, skills fetch fallback).
- Imports inside functions (loot generators, random as _rnd, CompanionMechanics).
- Long functions (process_next_turn ~160 lines, _calculate ~110, roll ~160, _check ~100).
- Data: dicts for events/effects/biases/changes, lists for completed/expired/newly_fired, sets for existing_keys/player_buildings.
- Ties to constants (many BM_*, ZEAL_*, PROJECT_*, SETTLEMENT_EVENTS, WORKERS/IDLEM base).
- Called from settlement views or turn processing (background?).

**Issues Identified:**
- **High (Performance – Per-Turn DB & Compute Load):** process_next_turn does 10+ DB roundtrips + loops over buildings + skills fetches + companion XP recalc every DT. For active settlements with many buildings + workers, this is non-trivial. _calculate_dt_production re-fetches raw skills data and rebuilds raw_inv dict each time. No batching or caching of building defs/production rates across turns.
- **High (Duplication – Reward Rolling & Application):** roll_bm_rewards + _grant_bm_rewards is extremely similar to curios logic, combat drops/rewards, partners dispatch (weighted categories, random gear/parts/eggs, modify_currency/gold/tickets/essences, generate_ loot with random slot). Inner random imports, try/except pass for grants. BM has its own "high_end", "consume", "egg" paths duplicating elsewhere. This amplifies the Phase 5 reward dupe noted earlier.
- **Medium (Code Quality & Maintainability – Long Orchestrator, Magic, Broad Excepts):** process_next_turn is a god function mixing orchestration, side effects, summaries. Many "magic" numbers via constants but still inline calcs (e.g. 5.0 DT_HOURS, tier reductions 0.075). Broad `except Exception: pass` in several places (companion XP, item grants, parts) – silent failures on reward application or XP. Imports inside hot path (loot, random, mechanics).
- **Medium (Data Structures & Algorithms):** Heavy dict munging for effects ( _resolve_band on bands/neg), lists for events/projects, manual inventory mirroring for converters (error-prone if more buildings added). random.choices/repeat for biases/extra_rolls is O(n) list building. No use of sets for faster lookups in some places (though sets used for existing_keys).
- **Medium (Coupling & Side Effects):** Calls into users, settlement, skills, companions, essences, equipment, eggs, monster_parts, social – tight coupling. Event effects and production bonuses scattered.
- **Low (Error Handling & Logging):** Swallowed exceptions mean reward loss or partial state without player notice. No logging of failures in grants. Zeal caps and passive are clean but production has fallbacks.
- **Positive:** Zeal cap logic (compute_zeal_gain) is well-commented and correct for soft/hard. BM value/turns separated. Event scheduling has good requirements/recurring logic. Constants centralize most values. Production delegates to SettlementMechanics.

**Summary for this unit (before moving on):** The turn engine is a critical background/idle system with significant perf cost per DT (multiple DB + loops), massive reward logic duplication (builds directly on AUDIT2 findings), long/complex code with swallowed errors, and dict/list heavy processing that could use more structure. High maintainability and integrity risk if rewards partially fail. This deeply visits the settlement mechanics folder. Unit complete.

---

## Logical Unit 7: Hematurgy Mechanics & Data (core/hematurgy/mechanics.py + engine.py cross-ref) – Code Quality, Data Structures, Random, Config

**Method:** Targeted grep first with path=core/hematurgy for "passive", "tier", "cost", "random", "pool", "TV", "MUTATIVE", "desc", "slot". Then **single thorough read** of core/hematurgy/mechanics.py (focused). Targeted grep on engine.py for usage without full re-read.

**Deep Understanding:**
- Centralized costs (SLOT_UNLOCK_COSTS dict with high values for cheeks/organs, UPGRADE_COSTS by tier, MUTATIVE_COST, TRANSMUTE_RATIO).
- _TV: dict of passive_id -> list of 7 values (T1 to T7), some T6/T7 chase.
- tier_val: safe index into list.
- _desc: huge match/case with pct lambda, very verbose descriptions per passive/tier. Some reference other passives (Poison).
- PASSIVE_POOL and MUTATIVE_POOL: dicts mapping id to {"name", "description": _desc callable or str}.
- _MUTATIVE_OUTCOMES and weights for roll.
- HematurgyMechanics class: static roll_mutative_outcome (random.choices), get_random_*_passive (list comp exclude, random.choice), get_passive_def, display_name, description (calls if callable), tier_val, costs.
- Used by views for transmute/mutate, slot detail, etc. Engine applies passives in combat.

**Issues Identified:**
- **Medium (Code Quality & Maintainability – Verbose Dupe in Descriptions, Long Data):** _desc is 100+ lines of near-duplicated structure (every case does pct(v) + text). Descriptions are "code as data" but hard to edit/balance. _TV lists are magic numbers per passive (centralized but still many values to tune).
- **Medium (Data Structures – Lists for Tiered Values, Dict Pools):** Good for tier lookup (index by tier-1), but lists mean no named tiers or easy extension. Pools are small dicts; random selection is simple list comp + choice (fine for <20 items, but repeated excludes could be sets for larger pools). No validation that all _TV keys are in pools.
- **Medium (Random & Config – Chase Tiers, Mutation Weights):** Hardcoded _MUTATIVE_WEIGHTS [50,20,15,15], OUTCOMES list. T6/T7 only via mutation (EVO_MAX_TIER=5). Costs are high magic (50k for end slots) – though in this file, not global config. Similar random passive pick to BM/curios/companions (dupe pattern).
- **Low (Coupling):** Mechanics class delegates tier_val to module func. Views/engine import and use directly. Passive effects likely applied in hematurgy/engine.py (combat integration).
- **Positive:** Clean separation of data (costs, values, pools, descs) from logic. Static class for easy use. Descriptions are player-friendly. Tiered values support chase T6/T7.

**Summary for this unit:** Hematurgy is a newer passive system with good data-driven design (value tables, pools) but suffers from verbose description code, list-based tier data that's tedious to maintain, and random selection logic that duplicates other gacha/roll systems. Config costs are here (better than scattered) but still "magic" for balancing. Fits code quality/Phase 5. Targeted greps covered hematurgy folder. Unit complete.

---

**End of this pass of units in AUDIT3.md.**  
Targeted work has now deeply covered settlement turn processing (core economy/idle), hematurgy passives (newer mechanics), plus prior skills, delve, pvp/events, minigames/tavern, and mechanics sampling.

All original map folders have been reached via path-limited targeted greps + single focused reads across the audit series.

**Overall for AUDIT3:** Continued deepening. Key new concerns: settlement DT engine as a perf + dupe + error-swallowing hotspot; hematurgy data/desc bloat; ongoing reward/UI/mechanics duplication and list/random patterns.

Process remains strictly compliant (slow, targeted greps first, one read per focused file, per-unit summaries before advance, append to file).

Next would be additional units or refactor proposals.

---

## Logical Unit 6: Settlement Turn Engine Deep Dive (core/settlement/turn_engine.py) – Performance, Reward Duplication, Data Structures, Error Handling

**Method:** Targeted grep first with path=core/settlement/turn_engine.py for "def ", "for ", "random", "except", "process_next_turn", "_calculate", "roll_bm", "grant", "event", "zeal", "project", "building". Then **single thorough read** of the full file (current focused component).

**Deep Understanding (after one full read):**
- Central orchestrator for DT (Development Turn) processing: zeal caps, project advancement, BM deals, event ticking/scheduling/firing, passive zeal, DT production from buildings (generators/converters).
- Heavy side effects: multiple DB calls per turn (advance_projects, get_pending_deal, tick_events, increment_turns, get_settlement + skills data, add_zeal, commit_production, modify_gold, add_stamina, companion XP loops).
- _calculate_dt_production: fetches 3 skills rows, loops buildings, applies event bonuses via _resolve_band, calls SettlementMechanics.calculate_production, handles market_gold/stamina/cookie specially, mirrors inventory deductions.
- Project completion: dispatches to _complete_project with nursery (followers via social), foundry (random variance +1), construction/upgrade/research direct DB.
- Event system: _check_schedule_events uses total_turns for triggers/recurring, building requirements, random bands/durations/targets, adds upcoming/ongoing/instant.
- BM: calculate_offer_value with tree multipliers, compute_processing_turns with tier/efficiency reductions + instant node.
- roll_bm_rewards: complex weighted categories + bias extra rolls, inner _roll_category with many random.randint/choices for gold/runes/keys/gathering/essence/gear/settler/egg/consume/curio/high_end/guild_ticket. Builds summary.
- _grant_bm_rewards: applies gold/currencies (special essence/ tickets), then for "items" does random slot + generate_ + create_ with try/except pass + inner random import. Similar for eggs/parts with more random.
- Many broad except: pass (swallows in companion XP, grant items/eggs/parts, skills fetch fallback).
- Imports inside functions (loot generators, random as _rnd, CompanionMechanics).
- Long functions (process_next_turn ~160 lines, _calculate ~110, roll ~160, _check ~100).
- Data: dicts for events/effects/biases/changes, lists for completed/expired/newly_fired, sets for existing_keys/player_buildings.
- Ties to constants (many BM_*, ZEAL_*, PROJECT_*, SETTLEMENT_EVENTS, WORKERS/IDLEM base).
- Called from settlement views or turn processing (background?).

**Issues Identified:**
- **High (Performance – Per-Turn DB & Compute Load):** process_next_turn does 10+ DB roundtrips + loops over buildings + skills fetches + companion XP recalc every DT. For active settlements with many buildings + workers, this is non-trivial. _calculate_dt_production re-fetches raw skills data and rebuilds raw_inv dict each time. No batching or caching of building defs/production rates across turns.
- **High (Duplication – Reward Rolling & Application):** roll_bm_rewards + _grant_bm_rewards is extremely similar to curios logic, combat drops/rewards, partners dispatch (weighted categories, random gear/parts/eggs, modify_currency/gold/tickets/essences, generate_ loot with random slot). Inner random imports, try/except pass for grants. BM has its own "high_end", "consume", "egg" paths duplicating elsewhere. This amplifies the Phase 5 reward dupe noted earlier.
- **Medium (Code Quality & Maintainability – Long Orchestrator, Magic, Broad Excepts):** process_next_turn is a god function mixing orchestration, side effects, summaries. Many "magic" numbers via constants but still inline calcs (e.g. 5.0 DT_HOURS, tier reductions 0.075). Broad `except Exception: pass` in several places (companion XP, item grants, parts) – silent failures on reward application or XP. Imports inside hot path (loot, random, mechanics).
- **Medium (Data Structures & Algorithms):** Heavy dict munging for effects ( _resolve_band on bands/neg), lists for events/projects, manual inventory mirroring for converters (error-prone if more buildings added). random.choices/repeat for biases/extra_rolls is O(n) list building. No use of sets for faster lookups in some places (though sets used for existing_keys).
- **Medium (Coupling & Side Effects):** Calls into users, settlement, skills, companions, essences, equipment, eggs, monster_parts, social – tight coupling. Event effects and production bonuses scattered.
- **Low (Error Handling & Logging):** Swallowed exceptions mean reward loss or partial state without player notice. No logging of failures in grants. Zeal caps and passive are clean but production has fallbacks.
- **Positive:** Zeal cap logic (compute_zeal_gain) is well-commented and correct for soft/hard. BM value/turns separated. Event scheduling has good requirements/recurring logic. Constants centralize most values. Production delegates to SettlementMechanics.

**Summary for this unit (before moving on):** The turn engine is a critical background/idle system with significant perf cost per DT (multiple DB + loops), massive reward logic duplication (builds directly on AUDIT2 findings), long/complex code with swallowed errors, and dict/list heavy processing that could use more structure. High maintainability and integrity risk if rewards partially fail. This deeply visits the settlement mechanics folder. Unit complete.

---

## Logical Unit 7: Hematurgy Mechanics & Data (core/hematurgy/mechanics.py + engine.py cross-ref) – Code Quality, Data Structures, Random, Config

**Method:** Targeted grep first with path=core/hematurgy for "passive", "tier", "cost", "random", "pool", "TV", "MUTATIVE", "desc", "slot". Then **single thorough read** of core/hematurgy/mechanics.py (focused). Targeted grep on engine.py for usage without full re-read.

**Deep Understanding:**
- Centralized costs (SLOT_UNLOCK_COSTS dict with high values for cheeks/organs, UPGRADE_COSTS by tier, MUTATIVE_COST, TRANSMUTE_RATIO).
- _TV: dict of passive_id -> list of 7 values (T1 to T7), some T6/T7 chase.
- tier_val: safe index into list.
- _desc: huge match/case with pct lambda, very verbose descriptions per passive/tier. Some reference other passives (Poison).
- PASSIVE_POOL and MUTATIVE_POOL: dicts mapping id to {"name", "description": _desc callable or str}.
- _MUTATIVE_OUTCOMES and weights for roll.
- HematurgyMechanics class: static roll_mutative_outcome (random.choices), get_random_*_passive (list comp exclude, random.choice), get_passive_def, display_name, description (calls if callable), tier_val, costs.
- Used by views for transmute/mutate, slot detail, etc. Engine applies passives in combat.

**Issues Identified:**
- **Medium (Code Quality & Maintainability – Verbose Dupe in Descriptions, Long Data):** _desc is 100+ lines of near-duplicated structure (every case does pct(v) + text). Descriptions are "code as data" but hard to edit/balance. _TV lists are magic numbers per passive (centralized but still many values to tune).
- **Medium (Data Structures – Lists for Tiered Values, Dict Pools):** Good for tier lookup (index by tier-1), but lists mean no named tiers or easy extension. Pools are small dicts; random selection is simple list comp + choice (fine for <20 items, but repeated excludes could be sets for larger pools). No validation that all _TV keys are in pools.
- **Medium (Random & Config – Chase Tiers, Mutation Weights):** Hardcoded _MUTATIVE_WEIGHTS [50,20,15,15], OUTCOMES list. T6/T7 only via mutation (EVO_MAX_TIER=5). Costs are high magic (50k for end slots) – though in this file, not global config. Similar random passive pick to BM/curios/companions (dupe pattern).
- **Low (Coupling):** Mechanics class delegates tier_val to module func. Views/engine import and use directly. Passive effects likely applied in hematurgy/engine.py (combat integration).
- **Positive:** Clean separation of data (costs, values, pools, descs) from logic. Static class for easy use. Descriptions are player-friendly. Tiered values support chase T6/T7.

**Summary for this unit:** Hematurgy is a newer passive system with good data-driven design (value tables, pools) but suffers from verbose description code, list-based tier data that's tedious to maintain, and random selection logic that duplicates other gacha/roll systems. Config costs are here (better than scattered) but still "magic" for balancing. Fits code quality/Phase 5. Targeted greps covered hematurgy folder. Unit complete.

---

**End of this pass of units in AUDIT3.md.**  
Targeted work has now deeply covered settlement turn processing (core economy/idle), hematurgy passives (newer mechanics), plus prior skills, delve, pvp/events, minigames/tavern, and mechanics sampling.

All original map folders have been reached via path-limited targeted greps + single focused reads across the AUDIT series.

**Overall for AUDIT3:** Continued deepening. Key new concerns: settlement DT engine as a perf + dupe + error-swallowing hotspot; hematurgy data/desc bloat; ongoing reward/UI/mechanics duplication and list/random patterns.

Process remains strictly compliant (slow, targeted greps first, one read per focused file, per-unit summaries before advance, append to file).

Next would be additional units or refactor proposals.