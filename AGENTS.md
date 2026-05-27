# Idleology — AI Agent Developer Guide

This file (AGENTS.md) provides essential architecture, strict coding rules, and context for AI coding agents (Grok, Claude, Cursor, etc.) working on the Idleology codebase.

The original detailed version lives in [CLAUDE.md](./CLAUDE.md). This AGENTS.md is a portable, agent-optimized adaptation of the same authoritative guidance.

**Core principle:** This project has a very strict, well-defined layered architecture. Deviating from the patterns described here creates technical debt and breaks maintainability. Follow the rules exactly.

---

## Project Overview

**Idleology** is a text-based Discord RPG bot built with `discord.py` and `aiosqlite`.

- **Runtime**: Python 3.11.5
- **Database**: SQLite (`database/schema.sql`)
- **Assets**: CSV/JSON/TXT files in `assets/` (monsters, items, exp tables, partner data, etc.)
- **Version**: 0.91 (see UPDATES.md for history)

---

## Architecture Overview

```
cogs/          → Discord command handlers (entry points only)
core/          → Game logic, mechanics, UI views
  base_view.py → Global base class for ALL Discord views in the bot
  models.py    → Dataclass wrappers for DB rows
  util.py
  [module]/
    mechanics.py / logic.py  → Pure math and business logic
    views.py                 → Primary discord.ui.View classes (simpler modules)
    views/                   → View subdirectory (preferred for complex modules)
      list_view.py           → Paginated list views
      detail_view.py         → Item/entity detail + action views
      gear_view.py           → Unified multi-slot views
      modals.py              → Modal dialogs
    upgrades/                → Upgrade-flow views (if module has upgrades)
      base.py                → BaseUpgradeView parent
      weapon.py / armor.py / accessory.py
    ui.py / <module>.py      → Stateless embed/component builders
    data.py                  → Asset loading and lookup tables
  items/
    factory.py               → DB tuple → dataclass constructors
    equipment_mechanics.py   → Upgrade logic (forge, refine, temper, imbue, potential)
    essence_mechanics.py     → Essence stat calculation
    essence_views.py         → Essence management UI
database/
  __init__.py  → DatabaseManager (single entry point)
  base.py      → BaseRepository
  repositories/ → All SQL lives here
assets/        → CSV/JSON/TXT game data (monsters, items, exp tables)
scripts/       → One-off maintenance scripts (image audit, reseed, upload)
```

---

## `BaseView` — Mandatory Base for All Views

**`core/base_view.py`** is the global base class that **every** `discord.ui.View` in the bot **must** inherit from.

```python
class BaseView(ui.View):
    def __init__(
        self,
        bot,
        user_id: str | None = None,
        server_id: str | None = None,
        *,
        parent: "BaseView | None" = None,
        timeout: int = 600,
    )
```

**Two initialization styles:**
- **Normal (top-level):** `BaseView(bot, user_id, server_id=...)`
- **Child / sub-view:** `BaseView(bot, parent=parent_view)` — inherits `user_id` / `server_id`

**What it provides:**
- `self.bot`, `self.user_id`, `self.server_id`, `self.message`
- `interaction_check()` — silently rejects interactions from other users
- `on_timeout()` — calls `state_manager.clear_active(user_id)` and removes buttons

**Rule:** Never extend `discord.ui.View` directly. Always extend `BaseView`.

---

## View File Splitting Strategy

The gold standard is **`core/inventory/`**:

```
core/inventory/
├── __init__.py
├── inventory.py                 # Stateless embed builders (InventoryUI)
├── views/
│   ├── __init__.py
│   ├── list_view.py
│   ├── detail_view.py
│   ├── gear_view.py
│   └── modals.py
└── upgrades/
    ├── __init__.py
    ├── base.py                  # BaseUpgradeView
    ├── weapon.py
    ├── armor.py
    └── accessory.py
```

**Rules:**
- Stateless builders live in `ui.py` or `<module>.py` — **never** inside view classes.
- Complex modules get a `views/` subdirectory.
- Upgrade flows go under `upgrades/` with `BaseUpgradeView`.
- `__init__.py` re-exports the public surface.
- Settlement follows the same pattern (`core/settlement/views/`).
- **Split when:** A single view file would exceed ~600–800 lines or a second distinct sub-feature appears.

---

## Layer Rules

### Cogs (`cogs/`)

- **No business logic.** Validate inputs, call `core/`, render output.
- **No raw SQL.** Always use `self.bot.database.<repository>`.
- **No `wait_for()` loops.**
- Defer before DB writes: `await interaction.response.defer()`.
- Check `self.bot.state_manager.is_active(user_id)` before starting interactive work.

**Correct pattern:**
```python
if self.bot.state_manager.is_active(user_id):
    return await interaction.response.send_message("You're already in an activity.", ephemeral=True)

player = await self.bot.database.users.get(...)
view = SomeView(...)
self.bot.state_manager.set_active(user_id, "activity")
await interaction.response.send_message(embed=..., view=view)
```

**Combat stamina note:** `/combat` uses a 10-stamina pool. Stamina bypasses the normal 10-minute cooldown. Speedster boots reduce the base cooldown.

### Core Logic (`core/`)

- `core/models.py`: Pure dataclasses + computed properties. No DB calls.
- `core/[module]/mechanics.py`: Static methods, pure functions, **no I/O**.
- `core/[module]/views.py` or `views/`: All extend `BaseView`.
- `core/items/factory.py`: Always use `create_weapon(row)`, `create_armor(row)`, etc.

### Database (`database/`)

- **All SQL lives in `database/repositories/`**. Nowhere else.
- Access via `bot.database.<repo>` (e.g. `bot.database.users`, `bot.database.equipment`).
- Always call `await repo.commit()` after writes.
- Full list of repositories is in the "Database Repositories" section below.

---

## Key Models (`core/models.py`)

### `Player`

Central dataclass. Key groups:

- Core stats + equipped gear (weapon/armor/accessory + glove/boot/helmet)
- `active_companions`, `active_partners`
- `equipped_parts` (monster body parts for HP)
- Alchemy passives + Codex run state
- `ascension_unlocks`
- **Transient combat state** lives in `player.cs` (CombatState) — reset via `reset_combat_state()`
- **Per-run Codex state** lives in `player.run` (CodexRunState)

**Important methods:**
- `get_total_attack()`, `get_total_defence()`
- `get_total_pdr()`, `get_total_fdr()` (hard cap 80%)
- `get_current_crit_chance()`, `get_total_rarity()`
- `total_max_hp` (includes parts)
- `reset_combat_state()`, `reset_combat_bonus()`

### Equipment Models

All constructed via `core/items/factory.py`:

| Model     | Key Fields |
|-----------|------------|
| `Weapon`  | level, attack, defence, rarity, passive, p_passive, u_passive, infernal_passive, forge_tier, refines_remaining |
| `Armor`   | level, block, evasion, ward, pdr, fdr, passive, temper/imbue remaining, celestial_passive, reinforcement_lvl |
| `Accessory` | level, attack, defence, ward, crit, passive, void_passive |
| `Glove/Boot/Helmet` | essence slots (1-3 + corrupted), potential_remaining, reinforcement_lvl |

### Other Important Models

- `DelveState`, `Companion`, `Partner`, `MonsterModifier`, `CodexTome`, `Monster`, `DungeonState`, `Settlement`/`Building`.

See full details in CLAUDE.md when needed.

---

## Combat System (`core/combat/`)

Highly structured:

```
calc/          → Pure math (hit_calc.py, damage_calc.py, ward_system.py, calcs.py)
turns/         → Turn processing (engine.py, player_turn.py, monster_turn.py, passives.py, jewel_engine.py)
mobgen/        → Encounter generation + modifiers (modifier_data.py is the single source of truth)
economy/       → Loot, XP, rewards
ui/            → Stateless embed builders
views/         → All combat UI views
```

**Import conventions (strict):**
- `from core.combat.calc.calcs import get_weapon_tier`
- `from core.combat.mobgen.modifier_data import make_modifier`
- `from core.combat.turns import engine`
- Never import from legacy paths like `core.combat.calcs`

**Adding modifiers:** Only define in `modifier_data.py`, then handle in `turns/monster_turn.py` (or player_turn if needed). Never hardcode values elsewhere.

---

## Combat State Reset Rules (Critical)

| Encounter type     | Jewel `skill_charges` | Jewel transients | Misc stacks (voracious, gaze, hunger, …) |
|--------------------|-----------------------|------------------|------------------------------------------|
| Normal `/combat`   | Reset at start        | Fresh            | Fresh                                    |
| Phase bosses       | Persist across phases | Persist          | Persist                                  |
| Ascent             | Reset at session      | Reset per floor  | Reset per floor                          |
| Codex              | Reset at run start    | Reset per wave   | Reset per wave                           |

See CLAUDE.md for exact reset methods (`_je.reset_jewel_charges`, `_next_floor`, `_setup_next_wave`, etc.).

---

## Equipment & Items

### Factory Functions (always use these)

```python
weapon = create_weapon(row)
armor = create_armor(row)
accessory = create_accessory(row)
glove = create_glove(row)
boot = create_boot(row)
helmet = create_helmet(row)
```

### Inventory UI

Canonical implementation: `core/inventory/`. Import from the package root:

```python
from core.inventory import InventoryListView, GearView, ItemDetailView, ForgeView, ...
```

### Essences

Gloves/boots/helmets support 3 regular + 1 corrupted essence. Corrupted essences (Aphrodite, Lucifer, Gemini, Voidling) grant powerful unique effects.

---

## Endgame & Major Systems

- **Ascent**: Level 100+ floor climbing (up to 666). Permanent bonuses via `ascension_unlocks`.
- **Codex**: Wave survival. Grants permanent Tomes + per-run boons/signatures.
- **Uber Bosses**: Celestial/Infernal/Void/Gemini pinnacle fights. Special materials.
- **Prestige Hall**: Purely cosmetic (titles, flairs, custom avatars, death messages, monuments). Logic lives entirely in `cogs/prestige.py`.
- **Consume**: Monster body parts (8 slots) for permanent Max HP.
- **Delve**: Mining mini-game with procedural layers and stability.
- **Maw**: Weekly world boss (Sunday 12:00 UTC cycle).
- **Partners**: Gacha + dispatch + affinity stories.
- **Hematurgy**: Blood-based passive upgrades (Hatchery building).
- **Alchemy**: Potion transmutation + passives.
- **Settlement**: Ideology buildings + workers.
- **Slayer**: Task/emblem system.
- **Journey**: One-time level milestone rewards.
- **PvP Duels**: Gold duels.

Full file locations and repository methods are documented in CLAUDE.md.

---

## Database Repositories

All access via `bot.database.<name>`:

`users`, `equipment`, `companions`, `skills`, `settlement`, `slayer`, `uber`, `essences`, `alchemy`, `ascension`, `codex`, `partners`, `monster_parts`, `prestige`, `delve`, `maw`, `boss_party`, `paradise`, `social`, `settings`, `duels`, `journey`, `hematurgy`.

See CLAUDE.md for the full method table.

---

## Adding a New Feature — Checklist

1. **SQL** → `database/schema.sql` + new methods in `database/repositories/*.py`
2. **Models** → `core/models.py` (or run-scoped state in `core/<module>/mechanics.py`)
3. **Logic** → `core/<module>/mechanics.py` (pure functions only)
4. **UI** → Extend `BaseView`. Stateless builders in `ui.py` or `<module>.py`. Split into `views/` + `upgrades/` when complex (follow inventory pattern)
5. **Command** → Thin handler in `cogs/<module>.py`
6. **State** → `set_active` / `clear_active` for any interactive feature

---

## Common Patterns

### Fetching a Player with Gear

```python
row = await self.bot.database.users.get(user_id, guild_id)
weapon_row = await self.bot.database.equipment.get_equipped(user_id, "weapon")
player = Player(...)  # construct
if weapon_row:
    player.equipped_weapon = create_weapon(weapon_row)
```

### Creating Views

```python
# Top-level
class MyView(BaseView):
    def __init__(self, bot, user_id: str, server_id: str):
        super().__init__(bot, user_id, server_id)

# Child
class MySubView(BaseView):
    def __init__(self, bot, parent: BaseView):
        super().__init__(bot, parent=parent)
```

Always set `view.message = msg` after sending.

### Double-Click / Re-entry Guard (Mandatory on mutating buttons)

```python
self._processing = False

@discord.ui.button(...)
async def confirm(self, interaction, button):
    if self._processing:
        await interaction.response.defer()
        return
    self._processing = True
    await interaction.response.defer()
    # ... work
```

### Asset Loading

```python
from core.util import load_list
names = load_list("assets/items/swords.txt")
```

### Image Assets

When adding entities that need images, note that assets are managed via `scripts/audit_images.py`, `scripts/reseed_images.py`, and `scripts/upload_new.py`.

---

## What NOT to Do (Strict)

- Do **not** put SQL strings in `cogs/` or `core/`.
- Do **not** put game math/business logic in `cogs/`.
- Do **not** use `wait_for()` for multi-step flows — use Views.
- Do **not** extend `discord.ui.View` directly — always use `BaseView`.
- Do **not** forget to clear active state on timeout/exit paths.
- Do **not** skip `await interaction.response.defer()` before slow operations.
- Do **not** add speculative abstractions — build exactly what the task requires.
- Do **not** add error handling for impossible states (validate only at interaction boundaries).
- Do **not** hardcode modifier values outside `core/combat/mobgen/modifier_data.py`.
- Do **not** add a state-mutating button without the `_processing` re-entry guard.
- Do **not** add a new passive without registering it in the validated passive system.

---

## Additional Notes for AI Agents

- The system prompt for Grok in this environment automatically injects the content of `CLAUDE.md` for context.
- When in doubt about architecture or patterns, re-read the relevant section of this file or CLAUDE.md.
- The `core/inventory/` module and `core/combat/` structure are the two best "reference implementations" in the codebase.
- Always prefer small, focused changes that follow existing patterns over large refactors unless explicitly asked.

---

**Last updated**: Based on CLAUDE.md (authoritative source). When CLAUDE.md is updated, consider syncing the most critical rules here.

For the most complete reference (including every table and long example), always consult [CLAUDE.md](./CLAUDE.md).
