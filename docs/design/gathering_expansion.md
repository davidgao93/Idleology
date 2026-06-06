# Design: Gathering Expansion — Tool Mastery Gates + Minigame Depth

**Status:** Draft for Discussion  
**Author:** Grok (based on user direction + prior plan)  
**Date:** 2026  
**Related Systems:** Skills/Gathering (Mining/Fishing/Woodcutting + Delve), Artisan Mastery (existing passive-only design), Settlement (converters, BM bias, War Camp stamina, workers for related systems), Combat (skiller boots, prestige gathering bosses, victory ticks), Quests (Prospector perk, zeal), Partners (dispatch yields), Profile (cooldowns + resources visibility), Black Market (gathering offers/rolls)

**For AI Implementer Note:** This builds directly on the post-settlement "next system" recommendation (gathering/skills as high-potential target for hybrid idle/active depth). Read together with `gathering_mastery.md` (which established purely passive Artisan Points + remnant economy — **do not change that core passive nature**). All active enhancements must be small accelerators only. Follow AGENTS.md / CLAUDE.md strictly: pure logic in `mechanics.py`, views extend `BaseView`, stateless builders where possible, `_processing` guards, state in repos only, profile as the central timer hub, small focused changes. Integrate minigames into the existing `GatherView` hub. Keep time-gates primary; active play provides meaningful but capped "feel-good" speed.

---

## 1. Executive Summary

This document proposes targeted expansions to the gathering system (Fishing, Woodcutting/Chop, and Delve as the three core active experiences) to make progression to BiS tools (titanium rod / felling axe / ideal pickaxe) feel like a journey of **mastery** rather than "farm gold and wait between sessions."

**Core Fantasy:**  
You don't just buy the best tool and instantly become a master. After purchasing a new tier, you spend a real-time "familiarization period" getting comfortable with it. Excellent active play in the associated minigame during (and after) this period builds "Session Quality" and "Momentum" that meaningfully shaves time off the gate for the *next* tier. Passive players progress at the normal gated pace. Dedicated active players feel the benefit of their skill without it becoming mandatory or a massive advantage.

**Two Main Pillars:**
1. **Time-Gated Tool Familiarization + Momentum System** — Tool upgrades remain gold + resource cost (with existing small mastery Synergy reduction). Each new tier purchase starts a real-time gate (hours, tunable per tier). Good-to-great performance in the matching minigame generates Momentum that reduces the remaining gate time for subsequent tiers (capped overall reduction, e.g. 20-30% max across a full path).
2. **Deeper, More Rewarding Minigames** — Fishing, Forestry (Chop), and Delve each gain light choice, risk/reward, combo/streak, and quality-rating mechanics. These improve both immediate yields *and* your Momentum contribution toward faster tool progression. All three become directly launchable from the main `/gather` hub for convenience.

The system serves three purposes:
- Make the 5-tier journey per skill feel deliberate and satisfying instead of a pure resource/time tax.
- Add engaging "filler" depth to the existing minigame loops (especially valuable during combat stamina/10min CDs or while other systems are gated).
- Reward active play in a way that feels good and accelerates progress modestly, while fully preserving the viability and pace of passive gathering + the existing purely-passive Artisan Mastery system.
- Maintain strong ties to Settlement (BM gathering bias, converters, potential new worker or zeal cross), Combat, Quests, and Profile visibility.

**Key Constraint (from user):** Still fundamentally time-gated. Active play helps you arrive at BiS tools faster, but not significantly enough that it's mandatory or feels like the only "correct" way to play.

---

## 2. Goals & Non-Goals

### Goals
- Transform tool tier progression from "buy next when you have the gold" into a short mastery arc per tier with visible progress and player agency.
- Add meaningful depth and "one more cast / one more swing / one more layer" loops to Fishing, Chop (Forestry), and Delve without increasing APM requirements or tedium.
- Make the three minigames easily accessible from the central GatherView (unified hub experience).
- Provide small but noticeable active-play acceleration (via Momentum on gates + better per-session yields/procs) while keeping the base time gate dominant.
- Generate more interesting session-to-session feedback (Quality ratings, Momentum contributed, streaks, bests) that feeds both immediate rewards and long-term tool progress.
- Strengthen (but not over-centralize) cross-system loops: better gathering sessions → slightly more resources for Settlement/BM, potential minor zeal/settlement favor contributions, better mastery synergy (Quality branch already improves rich procs — extend lightly to active quality rating).
- Keep everything optional for pure idlers; respect the "active minigames are flavor" philosophy from the existing gathering_mastery design.
- Improve discoverability and flow (no more needing to remember /fish /chop /delve separately).

### Non-Goals
- Removing or heavily weakening the time-gate component of tool upgrades or minigame pacing.
- Making active play *required* or the dominant path to BiS tools (active bonuses must be modest, e.g. 15-30% total effective acceleration at perfect play across all tiers).
- Overhauling the existing passive-only Artisan Mastery system (points still only from hourly task; this expansion adds active *session quality* that helps with tool gates and immediate yields, not mastery points directly).
- Adding high-frequency chores, complex real-time mechanics that punish casual play, or provenance tracking ("only self-gathered" bonuses).
- Forcing delve/fish/chop into a single shared stamina or charge pool that creates new mandatory daily grinds.
- Significant power creep — any new bonuses should feel horizontal (better feel, more variety, slightly faster horizontal progression) rather than vertical best-in-slot.

---

## 3. Current State (What Exists Today)

**Tool Progression:**
- 5 tiers per skill (mining: iron/steel/gold/platinum/ideal; woodcutting: flimsy/carved/chopping/magic/felling; fishing: desiccated/regular/sturdy/reinforced/titanium).
- Upgrades cost a mix of the skill's raw + refined resources + gold (see `SkillMechanics.get_upgrade_cost` and the DB mapping in gather_view).
- Small (12%) gold/resource cost reduction from the 1pt "tool_resonance" Synergy node in passive Mastery.
- On successful upgrade: +1 Artisan Point (feeds the passive Mastery trees) + immediate access to better minigame timings (shorter waits, fewer swings, lower entry costs, better base yields via `calculate_yield`).
- After BiS tool there is "nothing" for the active minigame experience itself (mastery benefits continue passively).
- Result: Progression feels like a resource tax + natural pacing between gold/resource hauls. The "wait" the player experiences is mostly real-world time between productive sessions + the passive point economy.

**Current Minigames (lightweight but functional):**
- **Fishing** (`FishingView`): Cast (pay entry) → random wait (FISHING_TIMINGS per rod, 45-330s) → Bite window (fixed 60s to Reel or fish escapes). Simple state machine + async tasks. Yields via `calculate_yield` (or mastery variant on passive). No internal choices during the wait.
- **Forestry / Chop** (`ForestryView`): Buy pass → N swings (FORESTRY_SWINGS per axe, progress bar) with 25% knot chance per non-final swing (separate "Clear Knot" button tax). On final swing: fell + post-fell cooldown task (FORESTRY_COOLDOWNS 60-300s) before you can start another tree. Rhythm is implicit (you just click when ready).
- **Delve** (separate `DelveEntryView` + `DelveView`): Permit cost based on current fuel level. Procedural layers (Safe/Gravel/Gas/Magma + ore veins at depth). Fuel/stability management, pickaxe tier mitigation, sensor upgrades for reveals. Upgrades (fuel/struct/sensor) cost shards + gold. Self-contained active session; not integrated into the main `/gather` tabs.
- All three use `BaseView` + state_manager + re-entry guards. Entry costs and timings improve strictly with tool tier. Yields improve with tool + (for passive) Mastery.
- Main hub (`GatherView`): Tabbed interface for the three skills + "Artisan Mastery" + conditional "Elemental Resonance". Upgrade buttons live here. Minigames are launched via separate slash commands (`/fish`, `/chop`; delve via its own flow).

**Problems (why expansion is valuable):**
- Tool tiers feel like discrete purchases rather than a mastery journey.
- Minigames have very little internal decision-making or "skill expression" during the time you're committed to the view.
- No feedback loop between "I played this minigame really well" and "my next tool tier came a bit sooner."
- Delve feels like a completely separate activity instead of the "deep mining" pillar of gathering.
- During combat CDs or while waiting on other systems (quests board, maw fights, dispatch timers, etc.), players have no convenient "go do some gathering with more interesting choices" path from the central gather screen.
- Passive players are fine (and should stay fine), but active players get no extra satisfaction or modest acceleration from executing well in the activities they are already doing.

Existing Mastery design (`gathering_mastery.md`) correctly keeps Artisan Points strictly passive/hourly. This proposal respects that boundary.

---

## 4. Proposed System Overview

### Pillar 1: Tool Familiarization Gates + Momentum (The "More Interesting Than Waiting" Part)
- Tool upgrades keep their current gold + resource cost structure (plus existing small Synergy mastery reduction).
- **New:** Purchasing a new tool tier (N) immediately starts a **Familiarization Period** for that tier — a real-time gate (suggested starting values: 4h for early tiers scaling to 12-24h for the final BiS tier; tunable in constants and further reduced by existing Synergy investment).
- During the familiarization period (and for some time after), the player can still use the new tool normally in its minigame.
- **Active Play Accelerator:** Every completed minigame session with the relevant tool is scored for **Session Quality** (0-100 or letter grade). 
  - Thresholds define "Good" / "Great" / "Masterful" sessions.
  - Each tier of quality generates **Momentum** (a small time credit, e.g. 5-20 minutes shaved off the *next* tool gate in that skill).
  - Momentum is banked per-skill and applied automatically when the player attempts the next upgrade (or shown live in the GatherView upgrade preview).
  - Total Momentum from a full path of excellent play across all 4 upgrades per skill is capped (example: 20-30% of the total theoretical gate time across the whole skill). This ensures active dedication helps but a pure gold-farming + waiting player is never left dramatically behind.
- The gate is visible in the GatherView (next tier "Familiarization: Xh Ym remaining (Momentum can reduce by up to Z%)") and in Profile cooldowns section (similar to current maw/quest board/partner dispatch lines).
- Passive players simply wait the full gate between upgrades. Active players who play the minigame well during their normal gathering sessions feel the gate melt a bit faster and get better per-session yields as a bonus.

This directly addresses "make it more interesting to get to the final tool tiers instead of waiting [x] period of time" while honoring "still time-gated" and "active play can get there faster but not significantly enough that it's mandatory."

### Pillar 2: Minigame Depth (Chop, Fish, Delve)
Each minigame gains 1-2 light systems that improve both immediate rewards *and* the Session Quality rating used for Momentum.

**Fishing (enhanced state machine in FishingView):**
- During the cast wait, add a simple "Patience / Lure" choice (or a rising "Tension" meter the player can choose to reel early or ride out).
- Successful consecutive reels (without escapes) build a small "Focus" streak that improves the next bite chance, bite window size, or final yield/quality.
- "Masterful" sessions (high Focus + perfect reel timing in the window) contribute high Momentum + occasional "Pristine Catch" bonus resources or a small temporary yield buff for the next few casts.
- Still fundamentally the same cast-wait-reel loop — just more texture and feedback inside the committed time.

**Chop / Forestry (enhanced in ForestryView):**
- Expand the 25% knot into 2-3 knot "types" or a very light timing mini-challenge on Clear (e.g. a second button press within a forgiving window, or choosing "pry" vs "cut" based on a quick visual cue).
- Add a "Rhythm" or "Stamina" meter across the tree: consistent, well-timed swings (no wasted time between clicks when not knotted) build a streak. High rhythm on a tree reduces the post-fell cooldown for the *next* tree or improves that tree's yield/quality.
- "Masterful" sustained rhythm + clean knots = high Momentum credit + rare "Old Growth" bonus log type.
- The multi-swing commitment stays; it just has more satisfying internal flow and feedback.

**Delve (integrate + deepen):**
- Bring Delve entry and play into the main GatherView (under the Mining tab as "Deep Delve" or a dedicated fourth focus button alongside the three skills).
- Layer choices: At certain revealed layers, offer a quick risk/reward (e.g. "Push deeper for better ore chance but higher hazard exposure" vs safe path). Good hazard mitigation (using current pickaxe + any new "instinct" from mastery) improves the Session Quality score.
- "Stability as a resource": Strong play (avoiding or perfectly handling hazards, good sensor use) preserves more stability for longer/more profitable runs. Excellent runs contribute high Momentum toward the next pickaxe tier.
- Sensor upgrades already exist; add one or two more flavorful choices (e.g. "Broad Survey" vs "Targeted Deep Scan") that trade information for risk/reward.

All three minigames continue to award their normal yields. The new systems primarily improve the *feeling* of the session and the Momentum they feed into tool gates. Passive gathering (hourly) is completely unaffected.

### Pillar 3: Unified Gathering Hub
- In `GatherView`, the existing tab row (Mining / Woodcutting / Fishing) gains (or the action row below gets) clear "Start Fishing", "Start Chopping", "Start Delve" (or "Deep Mining") buttons.
- Clicking launches the corresponding sub-View (FishingView, ForestryView, or Delve flow) as a child view with a reliable "Back to Gathering" that returns to the parent GatherView (following the exact parent/child + rebuild pattern already used for Mastery sub-view and settlement child views).
- After a minigame session completes, the sub-view can return to the hub with a nice one-line summary ("Great session! +12 Momentum toward next rod.").
- This makes the three experiences feel like facets of one system rather than three separate commands.

---

## 5. Detailed Mechanics & Tuning Notes (Starting Points)

**Familiarization Gate (in `SkillMechanics` + gather view upgrade flow):**
- Add `FAMILIARIZATION_BASE_HOURS` map per tier/skill (or a simple formula: early tiers 4-6h, final tier 18-24h).
- After successful `upgrade_*` call in the repo, store a `last_tool_upgrade_time` (or per-skill familiarization_end timestamp) in the skills table (or a small new JSON column / dedicated field following settlement pending patterns).
- On upgrade preview / button: compute remaining = max(0, familiarization_end - now). Show "Ready for next tier in Xh Ym" or "Familiarizing... (ready in Xh)".
- Momentum application: When the player has enough gold/resources for the *next* tier and the familiarization has remaining time, apply banked Momentum (minutes) to reduce the remaining gate. Cap total reduction per tier path (e.g. never more than 25-30% of the sum of all gates in that skill).
- Momentum sources: Defined quality thresholds in each minigame's completion logic. Example targets (tunable):
  - Fishing: 0 escapes + Focus streak ≥3 → "Great" (10 min Momentum). Perfect reel windows on top → "Masterful" (extra 5-10 min).
  - Forestry: 0 missed knots + rhythm streak covering ≥70% of swings → Great. Near-perfect timing on all swings → Masterful.
  - Delve: High % layers without stability loss + good ore/curio haul relative to depth → Great/Masterful.
- Momentum is soft-capped per tier or per full skill path so a single godlike 2-hour session can't trivialize the next 3 upgrades.

**Session Quality / Momentum (new lightweight structs or returns from minigame completion):**
- Each minigame completion returns (yield_dict, quality_score 0-100, momentum_minutes).
- Quality score can also lightly affect the immediate yield (e.g. +5-15% on Great/Masterful sessions) for satisfying feedback.
- Track recent "best session" or lifetime great/masterful counts per skill (for profile flavor or minor achievements, optional).

**Minigame-Specific Additions (keep lightweight):**
- Fishing: Add a simple internal state or rising meter during wait. One extra button choice ("Steady" vs "Aggressive" approach) that trades safety for reward size. Consecutive successes build Focus (shown in embed).
- Forestry: 2-3 knot varieties with slightly different "cost" to clear (time or a second click). Rhythm meter as a progress bar that fills on timely swings between knots; full rhythm on a tree = cooldown reduction for next tree + quality bonus.
- Delve: 1-2 choice points per longer run (risk/reward layer). Stability as a visible resource bar. "Instinct" (light passive from Quality mastery or just tool tier) gives small mitigation or reveal bonuses that improve quality score.

All new mechanics must be forgiving on timing (Discord interaction latency) — use generous windows and clear visual feedback in embeds.

**Integration & Visibility:**
- GatherView becomes the single entry point. Update its embed to show current tool + familiarization status + quick "Recent Momentum" summary.
- Profile `build_cooldowns` gains a small "Gathering" subsection or lines under Daily/Horizon (e.g. "Mining next tier gate: Xh (Momentum: +Y min)").
- `build_resources` can optionally surface "Recent best session quality" or just leave it.

**Cross-System Touches (light):**
- Excellent gathering sessions (Masterful) can optionally tick a very small amount of zeal or "settlement favor" (consistent with how quests already grant zeal).
- BM gathering bias already exists — high Momentum / recent quality could be a soft signal for slightly better gathering rolls on deals (nice-to-have, low priority).
- Leverage existing passive Mastery Quality branch to raise the ceiling on achievable Session Quality (Quality investment = higher chance of Masterful runs = more Momentum per hour of active play).

---

## 6. Database & Repository Changes

Light additions only (follow settlement pattern):
- In the per-skill tables (mining/fishing/woodcutting) or a small new `gathering_progress` table / JSON field: `last_tool_upgrade_time` (or per-skill familiarization_end), `banked_momentum_minutes` (or a small dict).
- Optional: `session_quality_log` or just ephemeral per-session (no need to persist every run; bank the Momentum aggregate).
- Repo methods in `database/repositories/skills.py`: `get_familiarization_state`, `apply_momentum_to_gate`, `record_session_momentum`, `get_upgrade_preview_with_momentum` (or compute in mechanics + view).
- Add at the bottom of `schema.sql` with the usual migration comment block.

No changes to the core passive Mastery tables or point economy.

---

## 7. UI / View Changes

- `core/skills/views/gather_view.py`: Add launch buttons for the three activities. Handle child view returns and refresh state on back. Show familiarization / Momentum in the main embed and upgrade preview.
- `core/skills/fishing_view.py` + `forestry_view.py`: Extend state machines + embeds with the new internal mechanics (Focus, Rhythm, quality result). On completion, compute and return quality + momentum to the caller (or persist via a small helper before returning to parent).
- Delve: Minor updates to `DelveEntryView` / main delve view for quality scoring + "Back to Gathering" when launched from hub. Possibly move or alias the permit/launch flow.
- New or extended stateless helpers in `core/skills/mechanics.py` for `calculate_session_quality(...)`, `get_momentum_from_quality(...)`, `get_familiarization_remaining(...)`, `apply_momentum(...)`.
- Follow existing patterns exactly: `BaseView`, `_processing`, async task cleanup on timeout, parent references for navigation, embed rebuild on state change.

Launch the sub-views with a callback or by editing the original response + passing the parent GatherView for clean return (exact pattern already used for Mastery and many settlement children).

---

## 8. Implementation Notes & File Guidance (for AI Agent)

Follow the project's strict layered architecture (see AGENTS.md / CLAUDE.md and the prior plan).

Priority order:
1. **Mechanics first** (`core/skills/mechanics.py`): Add all new constants (FAMILIARIZATION_*, QUALITY_THRESHOLDS, MOMENTUM_VALUES), pure calculation functions for gates, quality scoring, momentum, and any minigame-specific helpers (calculate_rhythm, focus_from_reels, etc.). Update `get_upgrade_cost` preview paths if needed. Keep Mastery integration points clean.
2. **Repository** (`database/repositories/skills.py`): New getters/setters for familiarization + momentum state. Keep all SQL here.
3. **Views**:
   - `core/skills/views/gather_view.py` — hub integration and launch points.
   - `fishing_view.py`, `forestry_view.py` — depth + quality/Momentum return.
   - Delve views — integration + quality scoring.
4. **Cogs** (`cogs/skills.py`): Thin updates if command entry points change; the hub should reduce the need for separate /fish etc. in many cases.
5. **Profile** (`core/character/profile_ui.py`): Add gathering gate lines in `build_cooldowns` (reuse existing _fmt helpers). Optional flavor in resources.
6. **Cross** (small): Light hooks in victory.py or settlement if we add tiny zeal/favor from masterful sessions (use the same try/except non-critical pattern as existing zeal grants).
7. **Constants & tuning**: Put everything tunable in `mechanics.py` (or a small new section). Existing `gathering_mastery.md` and current SKILL_CONFIG / TIMINGS / COOLDOWNS stay authoritative for their domains.
8. **Images**: May need minor new icons or reuse existing (mastery icons, tool images). Add to `core/images.py` if new constants are introduced.
9. **No changes** to the passive Artisan Point / remnant / Rune of Nature economy defined in `gathering_mastery.md`.

**Edge Cases to Handle:**
- Buying multiple tiers while a gate is running (bank Momentum across gates).
- Switching tools or skills mid-familiarization.
- Very long absences (gates should be real wall-clock and not punish offline players beyond the intended gate).
- Zero-Momentum playthroughs must still be fully viable (just slower on the final 1-2 tiers).
- State cleanup on view timeout for the sub-minigames.
- Mastery tool cost reduction still applies on top of the new system.

---

## 9. Risks, Mitigations & Tuning Guidance

- **Risk: Active feels mandatory.** Mitigation: Hard cap on total Momentum reduction per skill path (20-30% example). Base gate times should be the "normal" experience. Document in-game that "dedicated active play can meaningfully shorten the later gates."
- **Risk: Adds too much complexity to simple minigames.** Mitigation: Keep additions very lightweight (one extra meter or choice per game, generous timing windows, clear embed feedback). The core loop (cast-wait-reel, swing-until-fell, layer-by-layer) must remain instantly understandable.
- **Risk: Time-gate feels bad.** Mitigation: Show clear countdown + "your recent play has already saved you X minutes" messaging. Allow the gate to be ignored (you can keep using the new tool while familiarizing).
- **Risk: Delve integration breaks its self-contained feel.** Mitigation: Keep delve's upgrade/progression loop intact; the hub is just a convenient launch + quality scoring on top.
- **Tuning starting points (adjust after playtesting):**
  - Familiarization: 4h / 6h / 10h / 18h for the four gates per skill (or per-tier formula).
  - Max Momentum benefit: 25% of total gate time across the skill.
  - Per great session: 8-15 minutes credit. Masterful: +50% more.
  - Quality thresholds should be achievable with normal attentive play, not frame-perfect execution.

---

## 10. Testing & Verification Checklist

- Fresh player path: Buy first few tool tiers → observe familiarization timers and Momentum preview. Do several minigame runs of varying quality → see Momentum bank and gate reduction on next upgrade preview.
- Active vs passive comparison: Two parallel characters. One does only gold farming + waits full gates. One plays the minigames well. The active one should reach BiS 15-30% "calendar time" sooner but the passive one is never blocked or heavily disadvantaged.
- Unified UI: From /gather, launch fish/chop/delve directly, complete a session, return cleanly to the hub with summary.
- Cross-system: Masterful runs produce slightly better yields + any small zeal/settlement favor (if implemented). BM offers and settlement converters continue to work with the new resources.
- Profile & visibility: New gate lines appear correctly with remaining time and Momentum credit. No breakage of existing combat/rest/quest/maw/partner lines.
- Edge: Buy tool while gate is running, long offline, switching between skills, zero-quality runs (still get normal tool + 1 artisan point), full Mastery Synergy investment (still gets the 12% cost reduction on top of Momentum).
- Architecture: All new logic in mechanics (or pure helpers), views only drive UI + call mechanics, state via repo, BaseView + guards everywhere, no new mandatory daily chores.
- Performance / Discord fit: Async tasks still clean up on timeout. Embeds update responsively. No high-frequency required clicks.

This design keeps the soul of gathering (time + resources + satisfying active loops when you feel like it) while making the tool journey feel like a progression system worthy of the rest of the game's depth.

---

**Implementation Readiness**
This doc + the prior plan + `gathering_mastery.md` + existing code provide a complete picture. The active enhancements are deliberately modest in power and scope so they enhance the existing fantasy rather than replace the passive core.

Ready for review and iterative implementation following the project's architecture.