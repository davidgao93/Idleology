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
    equipment_mechanics.py   → Upgrade logic (forge, refine, temper, imbue, potential)
    essence_mechanics.py     → Essence stat calculation
    essence_views.py         → Essence management UI
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
- Available repositories: `users`, `equipment`, `skills`, `social`, `settings`, `companions`, `delve`, `settlement`, `slayer`, `uber`, `essences`, `alchemy`, `ascension`, `codex`, `duels`, `trade`.

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

**Core stats:**
- `id`, `level`, `ascension`, `exp`, `current_hp`, `max_hp`, `base_attack`, `base_defence`, `potions`

**Equipped gear:**
- `equipped_weapon`, `equipped_armor`, `equipped_accessory`
- `equipped_glove`, `equipped_boot`, `equipped_helmet`

**Companions & social:**
- `active_companions: List[Companion]`
- `apothecary_workers`, `barracks_workers` (settlement)
- `active_task_species`, `slayer_emblem: dict`

**Alchemy passives:**
- `potion_passives`, `alchemy_atk_boost_pct`, `alchemy_def_boost_pct`
- `alchemy_dmg_reduction_pct`, `alchemy_overcap_hp`, `alchemy_linger_hp`, `alchemy_guaranteed_hit`

**Codex run bonuses:**
- `run_atk_penalty`, `run_def_penalty`, `run_crit_penalty`, `run_max_hp_bonus`, `bonus_rarity`, `boon_fdr`
- `codex_tomes: List[CodexTome]`

**Ascension:**
- `ascension_unlocks: set` (unlocked floor numbers)

**Combat multipliers & bonuses:**
- `bonus_atk`, `bonus_def`, `bonus_crit`, `bonus_max_hp`
- `atk_multiplier`, `def_multiplier`, `crit_multiplier`
- `flat_atk`, `flat_def` (cached immutable during combat)

**Transient combat state** (reset each combat):
- `combat_ward`, `is_invulnerable_this_combat`, `celestial_vow_used`
- `voracious_stacks`, `cursed_precision_active`, `gaze_stacks`, `hunger_stacks`
- `lucifer_pdr_burst` and other essence-specific transients

**Key methods:**
- `get_total_attack()`, `get_total_defence()` — includes all gear/companion/tome bonuses
- `get_total_pdr()`, `get_total_fdr()` — physical/flat damage reduction (hard cap 80%)
- `get_total_ward_percentage()`, `get_combat_ward_value()`
- `get_current_crit_target()` — lower is better
- `get_total_rarity()`, `get_special_drop_bonus()` (hard cap 20%)
- `get_ascension_bonuses()`, `get_tome_bonus(stat)`
- `get_weapon_passive()`, `get_armor_passive()`, etc.
- `total_max_hp` property (includes all bonuses)

### Equipment Models

All built via `core/items/factory.py`.

| Model | Notable Fields |
|---|---|
| `Weapon` | `level`, `attack`, `defence`, `rarity`, `passive`, `p_passive` (pinnacle), `u_passive` (utmost), `infernal_passive`, `forge_tier`, `refines_remaining` |
| `Armor` | `level`, `block`, `evasion`, `ward`, `pdr`, `fdr`, `passive`, `temper_remaining`, `imbue_remaining`, `celestial_passive` |
| `Accessory` | `level`, `attack`, `defence`, `rarity`, `ward`, `crit`, `passive`, `passive_lvl`, `void_passive` |
| `Glove` | `level`, `attack`, `defence`, `ward`, `pdr`, `fdr`, `passive`, `passive_lvl`, `essence_1/2/3` + values, `corrupted_essence`, `potential_remaining` |
| `Boot` | Same essence structure as Glove |
| `Helmet` | `level`, `defence`, `ward`, `pdr`, `fdr`, `passive`, essence slots, `corrupted_essence`, `potential_remaining` |

### `Companion`
- `level`, `exp`, `species`, `image_url`
- `passive_type`: `atk | def | hit | crit | ward | rarity | s_rarity | fdr | pdr`
- `passive_tier`: 1–5; `balanced_passive` + `balanced_passive_tier`
- Properties: `passive_value`, `description`, `balanced_passive_value`, `balanced_description`
- `is_active` — whether this companion is in the active slot

### `CodexTome`
- `slot`, `passive_type`, `tier`, `value: float`
- Tomes grant multiplier bonuses (Vitality, Wrath, Bastion, Bulwark, Resilience, Precision, Providence)

### `Monster`
`name, level, hp, max_hp, xp, attack, defence, modifiers, image, flavor, species, is_boss, combat_round, is_essence`

### `DungeonState`
Tracks multi-room dungeon crawls: `current_floor`, `max_regular_floors`, player HP/ward snapshot, `potions_remaining`, `dungeon_coins`, `loot_gathered`, `player_buffs`, `player_curses`, `current_room_options`, `last_action_message`

### `Settlement` / `Building`
- `Settlement`: `user_id`, `server_id`, `town_hall_tier`, `building_slots`, `timber`, `stone`, `last_collection_time`, `buildings`
- `Building`: `building_type`, `tier`, `slot_index`, `workers_assigned`, `name` (property)

---

## Combat System (`core/combat/`)

| File | Responsibility |
|---|---|
| `engine.py` | Main combat orchestrator, passive triggers, stat effects |
| `calcs.py` | Hit chance, damage range, crit, passive detection |
| `player_turn.py` | Player action handling, ability and passive triggers |
| `monster_turn.py` | Enemy AI, attack patterns, modifier effects |
| `combat_log.py` | Round-by-round log construction |
| `encounters.py` | Encounter setup, monster selection |
| `gen_mob.py` | Procedural monster generation (species, modifiers, scaling) |
| `passives.py` | Weapon/armor/accessory/glove/boot/helmet passive logic |
| `loot.py` / `drops.py` | Drop tables and roll logic |
| `rewards.py` | XP, gold, loot distribution |
| `experience.py` | Experience scaling |
| `helpers.py` | Utility functions |
| `views.py` | Main combat UI (64KB — all standard combat flows) |
| `ui.py` | UI component builders |
| `views_uber.py` | Uber boss-specific UI |
| `views_elemental.py` | Elemental combat variant UI |
| `warning_views.py` | Warning/alert modals |
| `dummy_engine.py` / `dummy_views.py` | Training dummy (stat testing, no rewards) |

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
await bot.database.equipment.get_all(user_id, item_type)
await bot.database.equipment.get_equipped(user_id, item_type)
await bot.database.equipment.equip(user_id, item_id, item_type)
await bot.database.equipment.upgrade(user_id, item_id, item_type, upgrade_type)
await bot.database.equipment.add_essence(user_id, item_id, item_type, slot, essence_type, value)
await bot.database.equipment.transfer(item_id, new_user_id, item_type)
```
`item_type` is a `Literal["weapon", "armor", "accessory", "glove", "boot", "helmet"]`.

### Essences (`core/items/essence_mechanics.py`)
Gloves, boots, and helmets support up to 3 regular essence slots + 1 corrupted essence slot.
- Regular essences boost stats; corrupted essences (Aphrodite, Lucifer, Gemini, Voidling) grant powerful unique effects.
- Essence inventory tracked in `database/repositories/essences.py`.

---

## Endgame Systems

### Ascent (`core/ascent/`, `cogs/ascent.py`)
- Unlocked at level 100. Players climb numbered floors (up to 666).
- Each floor cleared grants permanent stat bonuses via `ascension_unlocks`.
- Logic in `core/ascent/mechanics.py`; unlocks tracked in `database/repositories/ascension.py`.

### Codex (`core/codex/`, `cogs/codex.py`)
- Wave-based survival mode unlocked at level 100.
- Runs grant **Tomes** (`CodexTome`) that apply permanent multiplier bonuses to stats.
- Runs also feature per-run **boons** and **signatures** that modify combat.
- Progress tracked in `database/repositories/codex.py`.

### Uber Bosses (`core/combat/views_uber.py`, `cogs/uber.py`)
- Pinnacle boss challenges (Celestial, Infernal, Void, Gemini variants).
- Progress tracked in `database/repositories/uber.py`.
- Drops unique materials: `blessed_bismuth`, `sparkling_sprig`, `capricious_carp`.

---

## Other Systems

### Alchemy (`core/alchemy/`, `cogs/alchemy.py`)
- Potion transmutation with passive effects on potions.
- Passives stored in `alchemy_data` and `potion_passives` tables.
- Repository: `database/repositories/alchemy.py`.

### Settlement (`core/settlement/`, `cogs/settlement.py`)
- Ideology-linked settlements with buildings (Apothecary, Barracks, Temple, etc.).
- Workers assigned to buildings grant passive bonuses (e.g., Apothecary workers boost potion effect).
- Repository: `database/repositories/settlement.py`.

### Slayer (`core/slayer/`, `cogs/slayer.py`)
- Task-based system; completing tasks earns points and emblems.
- 5 emblem slots (`slot_1–5`), each with a `type` and `tier`.
- Repository: `database/repositories/slayer.py`.

### Delve (`core/minigames/`, `cogs/delve.py`)
- Mining mini-game with fuel, structure, and sensor upgrade tiers.
- Repository: `database/repositories/delve.py`.

### Skills (`core/skills/`, `cogs/skills.py`)
- Gathering skills: Mining (`/gather`), Fishing (`/fish`), Woodcutting (`/chop`).
- Each has its own view: `fishing_view.py`, `forestry_view.py`.

### PvP Duels (`core/pvp/`, `cogs/duels.py`)
- Player-vs-player gold duels.
- Engine in `core/pvp/engine.py`, UI in `core/pvp/views.py`.
- Records in `database/repositories/duels.py`.

---

## Database Repositories

| Repository | Key Methods |
|---|---|
| `users` | `get`, `register`, `unregister`, `update_from_player_object`, `load_player`, `add_gold`, `add_potions` |
| `equipment` | `get_all`, `get_by_id`, `add_item`, `delete_item`, `equip`, `upgrade`, `add_essence`, `remove_essence` |
| `companions` | `get_all`, `get_active`, `add_companion`, `delete_companion`, `set_active`, `level_up`, `update_passive` |
| `skills` | `get_data`, `update_batch`, `add_resources`, `upgrade_tool` |
| `settlement` | `get_settlement`, `get_buildings`, `add_building`, `update_building`, `update_resources` |
| `slayer` | `get_profile`, `update_level`, `get_emblem`, `update_emblem_slot`, `update_active_task` |
| `uber` | `get_progress`, `update_progress`, `add_sigils` |
| `essences` | `get_essence_count`, `add_essence`, `remove_essence`, `get_all_essences` |
| `alchemy` | `get_level`, `update_level`, `get_potion_passives`, `update_potion_passive` |
| `ascension` | `get_unlocked_floors`, `unlock_floor`, `get_all_unlocks` |
| `codex` | `get_chapter_progress`, `update_progress`, `record_run` |
| `social` | Ideology and follower data |
| `settings` | User personal preferences |
| `duels` | Win/loss records |

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
