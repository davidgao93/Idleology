# Idleology — Developer Guide

Text-based Discord RPG bot built with `discord.py` and `aiosqlite`. Python 3.11.5. SQLite database.

---

## Architecture Overview

```
cogs/          → Discord command handlers (entry points only)
core/          → Game logic, mechanics, UI views
  models.py    → Dataclass wrappers for DB rows
  [module]/
    mechanics.py / logic.py  → Pure math and business logic
    views.py                 → discord.ui.View classes
  items/
    factory.py               → DB tuple → dataclass constructors
database/
  __init__.py  → DatabaseManager (single entry point)
  base.py      → BaseRepository
  repositories/ → All SQL lives here
assets/        → CSV/JSON/TXT game data (monsters, items, exp tables)
```

---

## Layer Rules

### Cogs (`cogs/`)

- **No business logic.** Validate inputs, call `core/`, render output.
- **No raw SQL.** Always go through `self.bot.database.<repository>`.
- **No `wait_for()` loops.** All multi-step interactions must use `discord.ui.View`.
- Defer interactions before any database write: `await interaction.response.defer()`.
- Always check `self.bot.state_manager.is_active(user_id)` before starting an interactive operation.

```python
# Correct cog pattern
@app_commands.command()
async def combat(self, interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if self.bot.state_manager.is_active(user_id):
        return await interaction.response.send_message("You're already in an activity.", ephemeral=True)
    player = await self.bot.database.users.get(user_id, str(interaction.guild_id))
    view = CombatView(player, self.bot)
    self.bot.state_manager.set_active(user_id, "combat")
    await interaction.response.send_message(embed=..., view=view)
```

### Core Logic (`core/`)

- **`core/models.py`**: Dataclasses only. No DB calls. Computed properties (`@property`) are fine.
- **`core/[module]/mechanics.py`**: Static methods, pure functions, no I/O.
- **`core/[module]/views.py`**: `discord.ui.View` subclasses. Views own their state and call mechanics/DB as needed.
- **`core/items/factory.py`**: `create_weapon(row)`, `create_armor(row)`, etc. map DB tuples to models.

### Database (`database/`)

- All SQL lives in `database/repositories/`. Never write raw SQL outside this directory.
- Access via `bot.database.<repo>`: `bot.database.users`, `bot.database.equipment`, etc.
- Call `await repo.commit()` (inherited from `BaseRepository`) after writes.
- Available repositories: `users`, `equipment`, `skills`, `social`, `settings`, `companions`, `delve`, `settlement`, `slayer`, `uber`.

---

## State Management

`bot.state_manager` prevents race conditions (e.g., starting combat while a trade is open).

```python
# Start an operation
self.bot.state_manager.set_active(user_id, "combat")

# Guard against double-entry
if self.bot.state_manager.is_active(user_id):
    return await interaction.response.send_message("Already in an activity.")

# Cleanup — ALWAYS do this in on_timeout and stop/exit buttons
self.bot.state_manager.clear_active(user_id)
```

**Rule:** Every `View` that calls `set_active` must call `clear_active` in:
- `async def on_timeout(self)`
- Any "exit", "cancel", or final-state button callback

States auto-expire after 10 minutes, but explicit cleanup is required.

---

## Key Models (`core/models.py`)

### `Player`
Central character dataclass. Built from a DB row plus optional equipped gear.

Important fields:
- `base_attack`, `base_defence`, `current_hp`, `max_hp`, `potions`
- `equipped_weapon`, `equipped_armor`, `equipped_accessory`, `equipped_glove`, `equipped_boot`, `equipped_helmet`
- `active_companions: List[Companion]`
- Transient combat state: `combat_ward`, `is_invulnerable_this_combat`, `celestial_vow_used`, etc. (reset each combat)

Key methods:
- `get_total_attack()`, `get_total_defence()` — includes all gear bonuses
- `get_total_pdr()`, `get_total_fdr()` — physical/flat damage reduction (hard cap 80%)
- `get_total_ward_percentage()`, `get_combat_ward_value()`
- `get_current_crit_target()` — lower is better
- `get_total_rarity()`, `get_special_drop_bonus()` (hard cap 20%)
- `get_weapon_passive()`, `get_armor_passive()`, etc.

### Equipment Models
`Weapon`, `Armor`, `Accessory`, `Glove`, `Boot`, `Helmet` — all built via `core/items/factory.py`.

### `Companion`
- `passive_type`: `atk | def | hit | crit | ward | rarity | s_rarity | fdr | pdr`
- `passive_tier`: 1–5
- `passive_value` property computes numerical bonus; `description` formats it for display.

### `Monster`
`name, level, hp, xp, attack, defence, modifiers, image, flavor, species, is_boss`

### `DungeonState`
Tracks floor progression, room options, buffs/curses for multi-room dungeon crawls.

---

## Combat System (`core/combat/`)

| File | Responsibility |
|---|---|
| `engine.py` | Passive triggers, stat effects, per-round logic |
| `calcs.py` | Hit chance, damage range, crit, passive detection |
| `encounters.py` | Encounter setup, monster selection |
| `gen_mob.py` | Procedural monster generation |
| `loot.py` / `drops.py` | Drop tables and roll logic |
| `rewards.py` | XP, gold, loot distribution |
| `views.py` | Main combat UI |
| `views_uber.py` | Boss-specific UI |
| `dummy_engine.py` / `dummy_views.py` | Training dummy (stat testing) |

Key functions in `engine.py`:
- `apply_stat_effects(player, monster)` — monster modifiers reduce player stats
- `apply_combat_start_passives(player)` — weapon/armor/accessory passives on round 1

Key functions in `calcs.py`:
- `calculate_hit_chance(player, monster)`
- `calculate_damage_taken(player, monster)`
- `get_player_passive_indices(player)` — returns which passives are active

---

## Equipment & Items

### Item Tables (DB)
`items` (weapons), `armor`, `accessories`, `gloves`, `boots`, `helmets`

### Factory Functions (`core/items/factory.py`)
Always use these to construct models from DB tuples:
```python
weapon = create_weapon(row)
armor = create_armor(row)
accessory = create_accessory(row)
glove = create_glove(row)
boot = create_boot(row)
helmet = create_helmet(row)
```

### Equipment Repository (`database/repositories/equipment.py`)
```python
await bot.database.equipment.get_all(user_id, item_type)   # List[Tuple]
await bot.database.equipment.get_equipped(user_id, item_type)  # Optional[Tuple]
await bot.database.equipment.equip(user_id, item_id, item_type)
await bot.database.equipment.transfer(item_id, new_user_id, item_type)
```
`item_type` is a `Literal["weapon", "armor", "accessory", "glove", "boot", "helmet"]`.

---

## Adding a New Feature — Checklist

1. **SQL changes** → `database/schema.sql` + new methods in the appropriate `database/repositories/*.py`
2. **Model changes** → `core/models.py` dataclass
3. **Logic** → `core/<module>/mechanics.py` (pure functions, no I/O)
4. **UI** → `core/<module>/views.py` (`discord.ui.View` subclass)
5. **Command** → `cogs/<module>.py` (thin handler only)
6. **State guard** → `set_active` / `clear_active` if the feature is interactive

---

## Common Patterns

### Fetching a Player with Gear

```python
row = await self.bot.database.users.get(user_id, guild_id)
weapon_row = await self.bot.database.equipment.get_equipped(user_id, "weapon")
player = Player(...)  # build from row
if weapon_row:
    player.equipped_weapon = create_weapon(weapon_row)
```

### View Lifecycle

```python
class MyView(discord.ui.View):
    def __init__(self, player: Player, bot):
        super().__init__(timeout=120)
        self.player = player
        self.bot = bot

    @discord.ui.button(label="Action")
    async def action(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # ... do work ...
        await interaction.edit_original_response(embed=..., view=self)

    @discord.ui.button(label="Exit")
    async def exit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.bot.state_manager.clear_active(str(interaction.user.id))
        self.stop()
        await interaction.response.edit_message(view=None)

    async def on_timeout(self):
        self.bot.state_manager.clear_active(str(self.player.id))
```

### Loading Asset Files

```python
from core.util import load_list
names = load_list("assets/items/swords.txt")
```

---

## What NOT to Do

- Do not put SQL strings in `cogs/` or `core/`.
- Do not put game math in `cogs/`.
- Do not use `wait_for()` for multi-step user flows — use Views.
- Do not forget `clear_active` on timeout and exit paths.
- Do not skip `await interaction.response.defer()` before slow operations.
- Do not add speculative abstractions — build only what the task requires.
- Do not add error handling for impossible states; validate only at Discord interaction boundaries.

---

## Project Info

- **Version**: v0.73
- **Runtime**: Python 3.11.5, discord.py, aiosqlite
- **DB**: SQLite (`database/schema.sql`)
- **Assets**: `assets/` — CSV/JSON/TXT lookup tables (monsters, exp, item names, system config)
- **Tests**: `tests/test_combat_logic.py`, `tests/tests.py`
