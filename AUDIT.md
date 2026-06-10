# Idleology — Security & Quality Audit Log (Grok Build)

**Audit Start Date**: 2026 (session)
**Bot Version**: ~0.91 (from AGENTS/CLAUDE)
**Scope**: Slow, deliberate, phased audit prioritizing security/game integrity (Phase 1), then perf, UI, supporting, architecture.
**Rules Followed**:
- Single one-time high-level repo mapping via git ls-files + targeted shell (no repeated broad `ls`/`tree`/`list_dir`).
- Targeted `grep` (ripgrep) with precise patterns before any full reads.
- Each focused file read **once thoroughly** (logical continuation for long files like bot.py).
- All changes follow project AGENTS.md / CLAUDE.md architecture (BaseView mandatory, cogs thin, SQL only in repos, etc.).
- Economy/balance/live-impacting changes: proposed + explicit confirmation required before edit.
- Small safe non-impacting improvements: applied directly + verify suggestion.

## One-Time Repository Mapping Summary (Only Broad Scan Performed)
- Tracked files: 299 total, 261 *.py
- Entrypoint: `bot.py`
- Cogs (30+): thin command handlers (combat, prestige, trade, partners/gacha, owner, inventory, settlement, etc.)
- Core: heavily split (combat/ with calc/turns/economy/ui/views, inventory/ as gold standard with views/ + upgrades/, partners/, settlement/ with plots/turn_engine, many others)
- Database: aiosqlite + DatabaseManager + ~30 repositories (all SQL here)
- Assets: CSV/JSON/TXT (monsters, partners, exp, items lists, system)
- Strict layering observed in most places.

**Initial Focus Declared**: Phase 1 — Security surface + game state integrity (auth/ownership, mutations, economy transfers, admin, gacha, race conditions, input, persistence).

## Reviewed Components (with dates / status)
- [x] One-time mapping + categorization (git ls-files, targeted greps for interaction.user / BaseView / dangerous funcs / DB queries / secrets / custom_id)
- [x] bot.py (entrypoint, DB init, state, error tree, logging, cog load, token handling) — read thoroughly
- [x] core/base_view.py (mandatory auth foundation) — full read
- [x] cogs/owner.py (admin surface, is_owner, reload hot-paths) — full read
- [x] core/trade/logic.py (cross-player economy transfers) — full read
- [x] core/trade/views.py (trade UI session, modals, BaseView usage) — partial + targeted
- [x] cogs/prestige.py (PrestigeHubView + costs + mutations; avatar validation offload) — targeted + partial read + greps
- [x] database/base.py (thin BaseRepository)
- [x] database/repositories/users.py (gold/currency mutations, modify_*, column whitelisting) — targeted reads + greps
- [x] Multiple cross-repo greps: state guards, random in gacha/partners, direct ui.View, transaction patterns, modify patterns

**Next Planned Units (Phase 1 cont.)**:
- Full trade confirmation flow + apex give_ transfers
- Partners gacha views + pity/roll security (concurrent protection)
- Combat victory/rewards application (core/combat/economy/)
- More repos for atomicity (equipment.transfer, apex.transfer_meta_shard, skills complex tx)
- StateManager implementation (in bot.py or separate?)
- Any raw f-string column risks + validation

## Issues Found (Severity: HIGH / MED / LOW / INFO)

### HIGH — Authorization / Ownership Bypass (Critical Exploit Surface)
- **PrestigeHubView inherits `discord.ui.View` directly** (cogs/prestige.py:370)
  - `class PrestigeHubView(ui.View):` then manually `self.user_id = ...; self.bot=...`
  - Overrides none of `interaction_check` / `on_timeout` from BaseView.
  - **Impact**: Any user who obtains a reference to (or sees) the message can invoke *all* button callbacks and modals (buy 1B titles, 750M rename, 2B monument, avatar upload, death message, etc.). Purchases debit the *stored* `self.user_id`'s gold via `modify_gold(self.user_id, -cost)` inside modals/hub callbacks.
  - Violates AGENTS.md mandatory rule: "Every new view must extend `BaseView`. Never extend `discord.ui.View` directly."
  - Recent refactoring context: other hubs (ProfileHubView, TradeRootView, Alchemy*, Ascent*, etc.) correctly use BaseView.
  - **Why dangerous in Discord**: Messages can be quoted, logged, or interacted via shared channels; no server-side re-validation of interaction.user on every callback beyond what the view provides.
  - **Status**: Identified via targeted grep. Full fix requires changing inheritance + __init__ super call + ensuring `view.message =` and on_timeout behavior. Economy-impacting → **proposal below, confirmation required before edit**.

- Related: Modals (AvatarModal, RenameModal, etc.) trust the `hub_view.user_id` passed in without re-checking the *current* interaction.user.

### MEDIUM-HIGH — Race Conditions / Non-Atomic Economy Mutations (Dupe / Negative Gold Vectors)
- **TradeManager.transfer_gold** (core/trade/logic.py:56-62):
  ```python
  sender_gold = await ...get_gold(sender_id)
  if sender_gold < amount: return False
  await ...modify_gold(sender_id, -amount)
  await ...modify_gold(receiver_id, amount)
  return True
  ```
  - Two separate UPDATE+COMMIT. Classic check-then-act + split credit/debit.
  - No BEGIN/ transaction wrapper spanning the pair.
  - `TradeRootView` (correctly BaseView) calls into this after confirmation.
  - **Risk**: Under concurrent trades, rapid clicks (before state clear), or if state_manager guard fails for any reason: overdraft or duplication possible. Same pattern in `transfer_resource`.
- **users.py modify_currency** (and get_currency): Use f-string for column name (`f"UPDATE ... SET {currency_column} = ..."`).
  - Has comment "# Could validate column names here to prevent SQL injection".
  - Whitelist exists in RESOURCE_MAP + some methods (update_timer validates), but modify_currency itself trusts the caller string.
  - Low practical risk today (internal maps), but future extension or refactors create injection surface + no hard enforcement at mutation point.
- **General**: BaseRepository has no `transaction()` context helper. Complex ops (trade gold+item, fusion in companions, settlement projects) do manual multi-commit or rely on repo-internal commits. Some places noted as "complex transaction" in comments (skills, settlement, companions).
- **Apex give_meta_shard** (cogs/apex.py): Player-to-player transfer path — needs same audit.
- **Status**: Identified. **Proposal required before any atomicity refactor** (will likely involve adding a context manager or BEGIN IMMEDIATE in BaseRepository + updating callers).

### MEDIUM — Inconsistent / Leaky Abstractions
- Direct `.connection.commit()` or raw access in places (e.g. cogs/character.py line ~111 from grep).
- Some views/cogs reach past the repository methods.
- Prestige costs are magic numbers at top of cogs/prestige.py (1B for titles, etc.) — should be in data/config per "Configuration & magic values" guidance. (Duplication risk if more cosmetics added.)

### LOW — Error Handling, Async Safety, Logging
- BaseView.on_timeout (core/base_view.py:53): `except (discord.NotFound, ... , Exception):` — overly broad final catch. Swallows unexpected errors during cleanup (rarely fatal, but masks bugs).
- bot.py init_db ALTERs and many except: pass / broad except in owner reload — acceptable for migrations/hot-reload but noisy.
- Avatar URL validation (prestige): correctly offloaded to `asyncio.to_thread` (urllib + PIL) — good example of avoiding blocking in event loop.
- Logging: User IDs appear in error/cooldown logs (acceptable for ops; no secrets or full PII).

### INFO / Positive Observations
- Strong consistent use of `str(interaction.user.id)` and passing to BaseView.
- `state_manager` guards in nearly all cogs before set_active + interactive views. Trade/Prestige/Combat follow this.
- All runtime SQL in repositories uses `?` params (no string concat for values). f-strings only for column names in limited internal paths (flagged above).
- Token via getenv only; .env explicitly gitignored and not tracked (`git ls-files .env` empty). Scripts fail loudly if missing.
- Trade UI properly inherits BaseView and does extra on_timeout clear.
- Gacha (partners): server-side `random` + pity counters persisted; no client randomness. stdlib random is standard for such games (not exploitable via seed without process compromise).
- Config has no secrets (only guild IDs, logging flag).

## Proposed / Completed Changes

### 1. HIGH — Fix PrestigeHubView to use BaseView (Proposed — Confirmation Needed)
**Why**: Direct inheritance completely bypasses the project's uniform ownership check and timeout/state cleanup. Allows unauthorized interactions on high-value economy actions (billions of gold cosmetics, renames, monuments). Breaks the "one owner per interactive session" invariant that state_manager + BaseView enforce everywhere else.
**Benefit**: Restores mandatory auth for all prestige actions. Consistent with TradeRootView, ProfileHubView, every other complex hub. Eliminates a clear exploit vector.
**Risk/Impact**: Low if done carefully (prestige is mostly cosmetic + gold sink); changes only the view class. Will also improve timeout behavior for prestige sessions.
**Proposed diff sketch** (after full class review):
```diff
- class PrestigeHubView(ui.View):
+ class PrestigeHubView(BaseView):
      def __init__(self, bot, user_id: str, server_id: str):
-         super().__init__(timeout=600)
-         self.bot = bot
-         self.user_id = user_id
-         self.server_id = server_id
+         super().__init__(bot, user_id, server_id)  # inherits check + timeout clear
          ...
      # Remove manual on_timeout if present; rely on or extend BaseView's
      # Ensure every button path still works (they use self.user_id which will be set by super)
```
**Also**: Update any direct `ui.View()` clear patterns are fine; this is the owned hub.
**Action**: Awaiting explicit user confirmation before applying search_replace + testing the /prestige flow.

### 2. MED — Harden TradeManager for Atomicity (Proposed — Confirmation Needed)
**Why**: Split get/check/deduct/credit across commits is a textbook source of economy bugs (negative balances, duped gold, failed transfers leaving money in limbo).
**Benefit**: Prevents real or perceived dupes/exploits. Makes transfer_gold a true atomic unit.
**Proposal**:
- Add a simple `async with self.connection.execute("BEGIN IMMEDIATE"):` or a `BaseRepository.transaction()` helper.
- Or make `modify_gold` / currency methods not auto-commit, and have a higher-level `transfer_gold_atomic` that does the pair inside one tx + single commit.
- Update TradeManager + any other direct two-step callers (apex give, etc.).
- Add basic balance-after checks or RETURNING if possible.
**Action**: Present + confirm before edit (touches live economy).

### 3. Small Safe Improvements (Applied or Ready)
- **BaseView timeout except tightening** (safe, non-economy): Change broad `except Exception` to specific + log unexpected. (Will apply in this session if not done.)
- Column validation: Enforce the known whitelist inside `modify_currency` / `get_currency` (defensive, low risk).
- Add type hints / docstrings where thin (future).
- After any edit: run black/ruff/mypy suggestion.

## Open Questions (for user clarification if needed)
- Is StateManager (self.state_manager in bot) defined in bot.py or a separate util? (Need to locate for full race analysis.)
- Are gold/currency intended to be per-user global (not per-server)? (Affects multi-guild trade/transfer design.)
- Any known recent incidents or player reports of trade/prestige glitches that should guide deeper search?
- Preference on gacha RNG: keep stdlib random, or move to secrets.SystemRandom for "more secure" feel (no functional change)?

## Completed Refactors This Session
- (None yet — initial discovery + proposals only. First safe edit pending.)

## Session Notes
- Followed "slow & deliberate": multiple targeted greps across 100s of lines before reading full focused files.
- All proposals include "why" + risk level.
- Will suggest formatters (black, ruff) + relevant tests/manual verification after edits.
- Will update CLAUDE/AGENTS or inline docs if architecture patterns clarified by fixes.
- Commit messages will reference specific AUDIT finding (e.g. "audit: fix PrestigeHubView ownership bypass (HIGH)").

Next step after user input: either apply confirmed fixes, or move to next focused unit (e.g. partners gacha concurrent safety + roll predictability, or victory reward application paths).
