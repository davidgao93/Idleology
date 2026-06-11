# Idleology RPG Bot — AUDIT2.md (Continuation Audit)

**Audit Phase:** Post-Phase 1 (Security/Integrity concerns considered fixed per user directive).  
**Focus:** Phase 2 (Performance hotspots), Phase 3 (UI/Interaction layer), Phase 4 (Supporting systems), Phase 5 (Architecture-wide issues, duplication, coupling, maintainability, code smells).  
**Date of this document:** Current session (continuation).  
**Strict Principles Applied (unchanged):**  
- Single one-time high-level repo mapping performed at the very start of the *original* audit (never repeated broad listings, `list_dir`, `find`, or full trees after t=0).  
- Prioritize by risk/impact, but now advancing phases.  
- **Targeted grep/search with precise patterns first** to locate issues (e.g. embed builders, repeated queries, loops in rewards/combat, _processing guards, message assignment, recomputed stats, tasks.loop, data loads). Only read full files for the *current focused component* (once thoroughly per file).  
- Re-reads only for clear dependencies or recent changes.  
- After every logical unit (one module, one view class family, one performance hotspot, one supporting script set, etc.): clear internal summary + append to this file before moving on.  
- Major issues added to this file immediately upon discovery.  
- All exploration of remaining folders done via **targeted path-limited greps** (e.g. `path=core/combat/...`, `path=core/inventory/views`, `path=database/repositories`, `path=scripts`, `path=tools`, `path=cogs/...`) + focused reads. This "visits" every folder without broad operations.  
- Slow, deliberate, high-quality. No rushing, no skimming. Deep understanding before any edit suggestions.  

**Previous Context:** AUDIT.md covered Phase 1 (security surface, auth via BaseView/interaction_check, economy races/TOCTOU on modify_gold vs atomic deducts, global user_id design, persistence validation, input, admin, StateManager, reward paths in partners/curios/trade/prestige/combat-econ, asset pipeline trust, etc.). Those are considered fixed/ addressed externally. This document starts fresh for the *next set*.

**One-Time Map Reference (not re-run):** Same categories as before — bot.py, cogs/* (thin handlers), core/* (mechanics + views split, combat heavy, inventory, partners, settlement, etc.), database/repositories + schema, assets (data + images), scripts/tools (asset mgmt), docs/tests. All "explored" via targeted means in this continuation.

## Issues Log (Severity: Critical / High / Medium / Low; + status)
(Entries added only after targeted grep + focused single read of component. Appended per logical unit.)

### Phase 2 — Performance Hotspots
*(Populated below as units complete...)*

### Phase 3 — UI / Interaction Layer
*(Populated below...)*

### Phase 4 — Supporting Systems (Assets, Data Loading, Background, Caching)
*(Populated below...)*

### Phase 5 — Architecture-Wide (Duplication, Coupling, Docs, Maintainability)
*(Populated below...)*

## Refactors / Fixes Applied
(None yet in this document — deep understanding + per-unit summaries first. Previous AUDIT.md fixes assumed external.)

## Open Questions / Next Focus
- ...

## Audit Progress (this document)
- [ ] Phase 2 Performance (combat turns/economy, leaderboards, embed gen, gacha/rolls, settlement ticks, idle calcs): IN PROGRESS
- [ ] Phase 3 UI (BaseView usage patterns across views, re-entry guards, message refs, child/parent flows, timeouts, state in inventory/combat/settlement/partners): PENDING
- [ ] Phase 4 Supporting (core/images + scripts/audit/reseed/upload, data loaders in util/xxx_data.py, tasks.loop, caching or lack thereof, JSON/CSV loads): PENDING
- [ ] Phase 5 Arch (dupe embed builders/ui.py vs views, coupling via bot.database everywhere, magic constants still in views, docstrings/types, model computed props vs caching): PENDING
- [ ] Full coverage of all folders via targeted methods: Ongoing (tracked per unit)

---
*This is AUDIT2.md — continuation. Previous concerns in AUDIT.md treated as resolved. Append-only for traceability. Follows identical rigorous process.*

## Initial Targeted Exploration for Phase 2+ (targeted greps only, post one-time map)

(These were the first precise searches after creating this file skeleton. Used to identify logical units without broad skimming. Path-limited to specific modules/folders to "visit" them.)

**Patterns searched (examples of first wave):**
- Embed / UI builders: "build_embed", "get_.*embed", "InventoryUI", "combat_embed", "victory_screen", "defeat_screen".
- Performance in hot loops: "for .* in .*rows", "get_all", "leaderboard", "ORDER BY", "random\.", "calculate_rewards", "apply_victory", "process_player_turn", "regen_stamina_tick".
- UI state: "_processing", "self\.message =", "view\.message =", "go_back", "close_view", "on_timeout", "parent=", "BaseUpgradeView".
- Background/idle: "@tasks\.loop", "status_task", "regen_", "tick_", "turn_engine", "process_next_turn".
- Data loading/caching: "load_list", "json\.load", "csv", "assets/", "from core\.(util|images|data)", "cache", "lru_cache", "get_.*_data".
- Duplication/coupling: repeated "await self\.bot\.database\.users\.get", "Player\(", "create_.*\(row\)", long methods in views.
- Other smells: missing types, f-strings in queries (post-fix verification), magic numbers in views.

Results from these initial targeted searches (path=core/combat/*, path=core/inventory/*, path=database/repositories/*, path=cogs/*, path=core/settlement/*, path=scripts/*, path=tools/*, path=core/models.py, path=core/util.py, etc.) were used to select the first logical units below. No broad directory commands were issued.

---

## Logical Unit 1: Combat Performance Hotspot — core/combat/turns/engine.py + related (player_turn, monster_turn, passives, jewel_engine)

**Method:** Targeted grep first with patterns for turn processing, stat effects, passives, loops ("for", "apply_stat_effects", "apply_combat_start_passives", "process_player_turn", "random", "calculate_damage"). Then **single thorough read** of core/combat/turns/engine.py (focused component). Cross-referenced via additional targeted greps on sibling files (player_turn.py, monster_turn.py, passives.py, jewel_engine.py, calc/*) without re-reading full files yet (only greps for specific patterns like "def process_", "cs\.", "reset_combat_state").

**Deep Understanding (internal notes after one read + greps):**
- engine.py is the main orchestrator for a combat round: `apply_stat_effects(player, monster)` (monster modifiers reduce player), `apply_combat_start_passives(player)`.
- Delegates to player_turn.process_player_turn and monster_turn.process_monster_turn.
- Heavy use of player.cs.* (CombatState transients: ward, bonus_atk, multipliers, voracious_stacks, jewel_*, alchemy_*, etc.).
- Many per-turn recalculations: get_total_attack(), get_total_defence(), get_current_crit_chance(), get_total_pdr(), ward generation, passive applications.
- jewel_engine called for active skills/unleash.
- No obvious caching of derived stats within a fight (recomputed frequently).
- Randomness in some passive/monster effects.
- Victory path (via economy/victory.py) applies rewards, XP, companion drops, slayer, quests, zeal — called at end of successful fights.
- Combat is one of the most frequent player actions (stamina-based /combat, codex waves, ascent floors, maw, uber phases, dojo sims).

**Issues Identified (added immediately):**
- **High (Performance — Hot Path Repeated Computation):** Derived stats (attack/def/crit/pdr/ward/rarity) and many player.cs fields are recomputed or re-applied on nearly every turn via `apply_stat_effects` + passive families + jewel + alchemy transients. No intra-fight memoization or dirty-flag invalidation. In long fights (codex 20+ turns, maw, ascent), this adds up (especially with many companions/partners/tomes/modifiers). Leaderboards and post-combat embeds also rebuild full Player views.
- **Medium (Code Smell — God Orchestrator + Duplication):** engine.py + turns/* spread logic across several files. Passives are registered in calc/calcs.py but effects duplicated or re-checked in player_turn/monster_turn/passives.py. Jewel and alchemy effects have their own state in cs. Hard to reason about "what applies when".
- **Medium (Maintainability — Transient State):** player.cs (and player.run) is a big bag of per-combat/per-run flags/stacks. Reset rules are documented in comments/AGENTS but enforced in multiple places (_next_floor, _setup_next_wave, CombatView.__init__, victory). Easy to miss a field when adding new mechanics (e.g. new passive or jewel effect), leading to state leaks across fights.
- **Low (Performance — Reward Application at Scale):** Every victory calls a chain (calculate_rewards → apply_partner_end_rewards → tick_quest_progress → add_zeal etc.). For high-traffic (many players doing /combat), this is fine per-fight but compounds with embed generation and DB writes. No batching for idle/regen tasks.
- **Positive:** Pure math separated in calc/ (hit_calc, damage_calc, ward_system). Good use of dataclasses for state. Combat logging is optional (config). State reset is explicit.

**Summary for this unit (before moving on):** Combat is a core frequent operation. The turn engine correctly separates concerns to some degree but recomputes derived values constantly and spreads transient state management. This is the highest-leverage performance area for players (most common interactive loop). Cross-checked via greps that similar patterns exist in codex run_view (wave persistence) and ascent. No blocking calls found in hot path. Moved on after appending this.

**Next targeted focus selected:** Leaderboards + get_all scans in users repo + views (Phase 2).

---

## Logical Unit 2: Leaderboards + Bulk Queries — database/repositories/users.py (get_leaderboard family) + callers (cogs/character.py leaderboard_views, profile)

**Method:** Targeted grep first (path=database/repositories/users.py + path=core/character + path=cogs/character.py) with precise patterns: "get_leaderboard", "ORDER BY level", "get_all", "SELECT \* FROM users", "leaderboard", "wealth_leaderboard", "ascension_leaderboard". Then **single thorough read** of the relevant sections in users.py (already read once in prior audit for Phase 1; re-read only the leaderboard + get_all methods + callers via targeted read of specific offsets after greps confirmed locations. Per rules: re-read only when dependency clear — here the previous read was Phase 1 focused on mutations; this is new performance lens).

**Deep Understanding:**
- users.py has `get_leaderboard(limit=10)`, `get_ascension_leaderboard`, `get_wealth_leaderboard` — simple `SELECT * / name,gold FROM users ORDER BY level DESC, ascension DESC LIMIT ?` (or gold).
- `get_all()` used for "global health regen tasks" (scans entire users table).
- Called from character leaderboard views and profile commands.
- No pagination beyond small LIMIT. No caching. Full row SELECT in some cases.
- In a growing server (hundreds/thousands of registered players), these become expensive on every leaderboard command or periodic task.
- Combined with combat (which updates level/exp/gold frequently), leaderboards can be stale or costly to refresh.

**Issues Identified:**
- **High (Performance — Full Table Scans + No Caching):** `get_all()` and unindexed ORDER BY on level/ascension/gold on the whole users table on every leaderboard view or regen tick. No materialized view, no in-memory cache with invalidation on level-up/gold change, no LIMIT + OFFSET for "page 2". For a popular bot this is a classic hotspot.
- **Medium (Code Smell — Inefficient Data Access):** Leaderboard queries pull full rows or unnecessary columns when only name + metric is shown. No use of covering indexes or separate leaderboard snapshot table.
- **Medium (Coupling/Architecture):** Leaderboard logic lives in the generic users repo instead of a dedicated "social" or "ranking" service. Callers in cogs/character rebuild embeds every time.
- **Low (but compounds):** No rate limiting visible on leaderboard commands themselves (beyond global cooldowns).
- **Positive (from Phase 1 carryover):** Queries are parameterized. Some daily counters exist to limit abuse.

**Summary for this unit:** Leaderboards are a visible, frequently requested feature that hit the DB hard on every use + background tasks. This is a clear Phase 2 win area (caching layer, snapshot table, or smarter queries + invalidation on level/gold changes). Cross-referenced that similar "get_all for ticks" exists in stamina regen. Appended and moving to UI layer patterns next (to keep phases progressing while staying slow).

---

## Logical Unit 3: UI/Interaction Layer Patterns — Inventory Views Family (core/inventory/views/* + upgrades + gear) + Cross-Check with Combat/Settlement Views

**Method:** Targeted greps first with patterns limited to inventory paths and then broader for comparison: "_processing = False", "if self\._processing", "self\.message =", "view\.message =", "close_view", "go_back", "BaseUpgradeView", "add_back_button", "on_timeout", "parent=", "update_buttons", "setup_buttons". Then **single thorough reads** of the key files in turn (list_view.py, detail_view.py, gear_view.py, upgrades/base.py — each read once). Additional targeted greps (path=core/combat/views, path=core/settlement/views, path=core/partners/views) to compare patterns without full re-reads of those (to obey "read once" + "targeted only").

**Deep Understanding (after one read per file + comparison greps):**
- Inventory follows the "gold standard" split recommended in AGENTS.md: list_view (pagination + Close), detail_view (actions + Back to list), gear_view (tabs + select + Close), upgrades/ with BaseUpgradeView (go_back creates *fresh* ItemDetailView to reset timeout).
- Consistent use of `self._processing = False` re-entry guard on state-mutating buttons (excellent — prevents double-click races on forge/refine etc.).
- `close_view` usually does defer + delete_original_response + clear_active + stop.
- "Back" buttons rebuild parent state (update_buttons, get_current_embed) and edit message.
- Child views via parent= for ownership inheritance.
- Many dynamic buttons created in update_*/setup_* methods (clear_items + add_item loops).
- Message reference set after send/edit in most places.
- Similar patterns appear in combat views (many _processing, flee/close that clear state), settlement (complex dashboard with close), partners (roster/detail with back/close).

**Issues Identified:**
- **High (Maintainability — Duplication of Close/Back/Exit Boilerplate):** Almost every view duplicates very similar `close_view` / `exit` / `leave` implementations (defer + delete + clear_active + stop, sometimes with slight variations in message handling). "Back" logic is also repeated (rebuild parent embed + edit). This is classic copy-paste across 100+ view classes.
- **Medium (UI Robustness — Message Reference & Timeout Safety):** Many places do set `self.message`, but it's easy to miss in complex flows (nested modals, multi-step upgrades, post-combat views). If missed, on_timeout can't clean buttons → users see dead interactions. Some "Close" still use danger style inconsistently (though previous audit touched some).
- **Medium (Performance — Rebuild on Every Navigation):** Inventory/gear list and detail views fully rebuild buttons + fetch data on every page change, Back, or tab switch. For large inventories (25+ items) this means repeated DB calls + embed generation on simple pagination.
- **Medium (Code Smell — Long update_ methods + Magic Rows):** update_components / setup_buttons have lots of row arithmetic and conditional button creation. Hard to maintain as new item types or essence slots are added.
- **Low (but visible):** Some "Back to X" labels are specific while others are generic "Back". "Close" vs "Exit" vs "Leave" vs "Done" still not 100% unified post-prior audit.
- **Positive:** Re-entry guards are widespread and correctly placed on mutating buttons. Parent= inheritance works well. Fresh detail view on upgrade go_back is smart for timeout reset. Inventory split is a model other modules should copy more (settlement is trying).

**Summary for this unit:** UI layer is functional and follows the mandated BaseView contract well, with good race guards. However, massive duplication of navigation/close logic and repeated full rebuilds on navigation are the main maintainability + minor perf smells. This is a prime Phase 3 target (extract BaseCloseView / NavigationMixin or standard "go_back" + "close" helpers in BaseView). Compared via greps to combat (similar guards but more complex post-combat views) and settlement (more dashboard-style closes). Unit complete.

---

## Logical Unit 4: Supporting — Asset / Image Pipeline (scripts/ + tools/ + core/images.py)

**Method:** Targeted greps first (path=scripts, path=tools, path=core/images.py) with patterns for upload, reseed, audit, discord URLs, json maps, local index, "upload_file", "patch_images_py", "load_images_module". Then **single thorough read** of the main scripts (audit_images.py, reseed_images.py, upload_new.py) and one tool (seed_discord_images.py) — each once. Greps on other scripts/tools for coverage without full reads.

**Deep Understanding:**
- Core/images.py is the source of truth for all embed thumbnails (monsters, ui, partners, curios, etc.) — mostly hard-coded URLs (Discord CDN after seeding).
- Scripts maintain sync between local assets/images/ and the URLs in images.py + CSVs (monsters.csv, partners.csv, curios.csv).
- Flow: audit (check local copies exist for every declared URL), download from imgur (initial), seed/upload to Discord channel via bot client (get permanent CDN URLs), apply/replace in images.py + CSVs, reseed (for expired CDN links — re-upload local file and patch).
- upload_new handles "new art" drop in upload/ dir.
- All are maintenance/offline tools (run by devs/owner), use discord.py Client (not the main bot), batching, rate limiting, dedup, url_map.json + discord_url_map.json.
- Also special handling for corrupted_monsters.

**Issues Identified:**
- **Medium (Maintainability + Ops — Fragile Asset Pipeline):** Multiple scripts/tools with overlapping logic (load_images_module via importlib, build_local_index with rglob, upload via Client + attachments, patching with string replace or CSV rewrite). Easy to get out of sync. upload_log.txt + done/ subdir for state. No single "asset manager" class or CLI entrypoint.
- **Medium (Reliability — No Atomicity/Transactions on Patch):** Patching images.py and multiple CSVs + json maps happens in steps. Partial failure (network, Discord rate limit, file write) can leave the bot with broken image URLs in embeds.
- **Low (Security/Trust — same as prior audit but noted for Phase 4):** Scripts run with Discord token and write to assets/ + source files. Assumes trusted operator and clean input dirs. No verification of image content/size beyond filename.
- **Low (Performance — not runtime but dev):** Sequential uploads with sleeps; no parallel for large batches.
- **Positive:** Clear separation (local source → Discord CDN → patched constants). Audit script is useful for catching missing art. Dedup logic in reseed is smart. Used heavily for the "text-based" RPG's visual flavor.

**Summary for this unit:** Asset pipeline is essential supporting infrastructure (Phase 4) that keeps the game pretty but is a pile of scripts rather than a robust system. Duplication and step-wise patching are the main smells. Not a runtime perf issue but hurts long-term maintainability as art volume grows (588+ monster images, etc.). Unit complete; this "visits" the scripts/tools folders.

---

## Logical Unit 5: Architecture-Wide — Duplication, Coupling, and Data Loading (core/util.py + data patterns across core/*/data.py + models + cogs)

**Method:** Targeted greps across multiple paths for coupling (".bot.database", "await self\.bot\.database", "load_player", "Player\("), duplication ("build_embed" defs, "from core\.(combat|items|partners|settlement)\.models"), data loading ("load_list", "json\.load", "csv\.reader", "assets/.*\.csv", "partners\.csv", "monsters\.csv"). Then **single thorough read** of core/util.py + core/combat/models.py (Player) + samples of data modules via targeted reads/greps. This unit spans folders to catch cross-cutting issues.

**Deep Understanding:**
- Heavy coupling: Almost every cog and many views do `self.bot.database.users.get(...)`, then `load_player(...)`, then pass Player + bot around. Repos are the only place with SQL, but the "load full player with gear + companions + ... " logic is spread.
- Data loading: core/util.py has `load_list` (for item name txt files). Individual data.py (partners/data.py, quests/data.py, codex, apex, paradise, settlement/constants.py) load CSVs/JSON at import or on demand. Some use csv.DictReader, some manual.
- Player model (in combat/models.py, re-exported): massive dataclass with ~dozens of fields, many @property computed (total_max_hp, get_total_attack etc.), cs/run nested state objects, lots of passive/gear/partner/tome/ascension/settlement/alchemy bonuses. reset_combat_state() etc.
- Embed builders duplicated per domain (inventory/inventory.py, combat/ui/*, maw/ui.py, partners/ui.py, settlement views, etc.).
- Magic / balance numbers still in some constants + views (despite data files for core content).

**Issues Identified:**
- **High (Architecture — Tight Coupling + God Object):** Player is the central mutable state carrier passed everywhere. Cogs/views reach deep into `bot.database.X` for almost everything. Hard to test in isolation, hard to add new systems (every new table = new repo + wiring). "load_player" (factory + gear + active companions + partners + parts + alchemy + codex + soulstone + ...) is a big hidden fan-out.
- **High (Duplication — Embed & UI Builders):** Every major feature has its own static embed functions or view classes rebuilding similar stat blocks, resource lines, "Close" buttons. No shared "player stat embed component" or base embed builder.
- **Medium (Performance + Coupling — Repeated Full Loads):** On nearly every command/interaction: get user row + load full Player (which does multiple equipment/companions/partners/settlement queries). No session-level or per-interaction caching of the Player object.
- **Medium (Maintainability — Data Loading Fragmentation):** CSV/JSON loading scattered (some at module level, some lazy, different parsers). No central "GameData" registry or validation on load. Asset images decoupled via the pipeline but still many manual entries.
- **Medium (Code Smell — Massive Player + Computed Everything):** Player has enormous surface (cs.*, run.*, equipped_*, active_*, get_*, total_*). Many computed properties re-walk gear/companions every time. Good for correctness, bad for perf in hot paths (combat).
- **Low (Documentation):** AGENTS.md/CLAUDE.md are excellent, but runtime code has uneven docstrings on complex methods. Balance constants scattered.
- **Positive:** Strict "no SQL outside repos", "always BaseView", "mechanics pure" rules are followed in the sampled code. Models are split by domain now (good evolution). Re-exports for backward compat.

**Summary for this unit (Phase 5 focus):** The architecture is opinionated and mostly successful at layering (cogs thin, repos for SQL, mechanics for logic), but suffers from classic "anemic domain + heavy service" problems plus a god Player and duplicated presentation logic. This is the root cause of many Phase 2/3 issues (repeated loads, rebuilds, state spread). High-value area for future refactoring (e.g. Player builder with caching, shared UI components, a thin ApplicationService layer). This unit spanned multiple folders via targeted greps + focused reads and is complete.

---

**End of current logical units in this pass.**  
All major folders have now been visited via the combination of the original one-time map + the targeted path greps performed for each unit above (cogs, every core/ subdir, database, scripts, tools, assets references).

**Overall Status for AUDIT2.md:** Phase 2, 3, 4, and 5 have initial coverage with several concrete High/Medium issues logged. Combat perf, leaderboards, UI boilerplate duplication, asset script sprawl, and cross-cutting coupling/Player bloat are the dominant themes.

Ready for user direction: more units, specific deep dives (e.g. full read of settlement/turn_engine or specific view families), or beginning actual refactors based on these findings (now that per-unit summaries are documented).

Next step in process would be additional targeted greps + next focused component if continuing, or exit to implementation.