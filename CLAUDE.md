# Idleology — Developer Guide

Text-based Discord RPG bot built with `discord.py` and `aiosqlite`. Python 3.11.5. SQLite database.

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

**`core/base_view.py`** is the global base class that every `discord.ui.View` in the bot must inherit from. It provides uniform timeout handling, interaction ownership checks, and state cleanup.

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
- **Normal:** `BaseView(bot, user_id, server_id=...)` — top-level views
- **Child:** `BaseView(bot, parent=parent_view)` — inherits `user_id` / `server_id` from parent; use this for sub-views and upgrade views

**What it provides:**
- `self.bot`, `self.user_id`, `self.server_id`, `self.message` (set the message reference after sending)
- `interaction_check()` — silently rejects interactions from other users
- `on_timeout()` — calls `state_manager.clear_active(user_id)` and removes buttons from the message; always safe to call

**Rule:** Every new view must extend `BaseView`. Never extend `discord.ui.View` directly.

---

## View File Splitting Strategy

The gold standard for complex modules is **`core/inventory/`**. It demonstrates how to split a large module cleanly:

```
core/inventory/
├── __init__.py          (re-exports everything for clean imports)
├── inventory.py         (InventoryUI — static embed builders, no state)
├── views/
│   ├── __init__.py
│   ├── list_view.py     (InventoryListView — paginated item list)
│   ├── detail_view.py   (ItemDetailView + DiscardConfirmView)
│   ├── gear_view.py     (GearView — unified 6-slot gear management)
│   └── modals.py        (MassDiscardModal)
└── upgrades/
    ├── __init__.py
    ├── base.py          (BaseUpgradeView — go_back() creates a fresh detail view)
    ├── weapon.py        (ForgeView, RefineView, VoidforgeView, InfernalEngramView)
    ├── armor.py         (TemperView, ReinforceView, EngramView, ImbueView)
    └── accessory.py     (VoidEngramView)
```

**Splitting rules:**
- Stateless embed/component builders live in `ui.py` or a dedicated `<module>.py` file — never inside view classes.
- Each natural feature group gets its own file under `views/`.
- Upgrade flows go under `upgrades/` with `BaseUpgradeView` as parent. `go_back()` on `BaseUpgradeView` creates a fresh `ItemDetailView` to reset the timeout.
- `__init__.py` re-exports the public surface so callers import from the module, not from nested files.
- Settlement (`core/settlement/views/`) follows the same pattern: `base.py`, `construction.py`, `detail.py`, `town_hall.py`, `black_market.py`, `dashboard.py`, `research.py`.
- **When to split:** Once a module's view code would exceed ~600–800 lines in a single file, or when a second distinct sub-feature appears. Don't split prematurely.

---

## Layer Rules

### Cogs (`cogs/`)

- **No business logic.** Validate inputs, call `core/`, render output.
- **No raw SQL.** Always go through `self.bot.database.<repository>`.
- **No `wait_for()` loops.**
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

**Combat stamina system:** The `/combat` command uses a stamina pool (`MAX_STAMINA = 10`, `COMBAT_COOLDOWN = 10 min`). If the player has stamina remaining, the fight proceeds immediately (consuming 1 stamina). When stamina hits 0, the regular 10-minute cooldown is enforced. The Speedster boot passive reduces the cooldown by `passive_lvl * 60` seconds (minimum 10 seconds).

### Core Logic (`core/`)

- **`core/models.py`**: Dataclasses only. No DB calls. Computed properties (`@property`) are fine.
- **`core/[module]/mechanics.py`**: Static methods, pure functions, no I/O.
- **`core/[module]/views.py`** or **`core/[module]/views/`**: `discord.ui.View` subclasses, all extending `BaseView`. Views own their state and call mechanics/DB as needed.
- **`core/items/factory.py`**: `create_weapon(row)`, `create_armor(row)`, etc. map DB tuples to models.

### Database (`database/`)

- All SQL lives in `database/repositories/`. Never write raw SQL outside this directory.
- Access via `bot.database.<repo>`: `bot.database.users`, `bot.database.equipment`, etc.
- Call `await repo.commit()` (inherited from `BaseRepository`) after writes.
- Available repositories: `users`, `equipment`, `skills`, `social`, `settings`, `companions`, `delve`, `settlement`, `slayer`, `uber`, `essences`, `alchemy`, `ascension`, `codex`, `duels`, `trade`, `partners`, `monster_parts`, `prestige`, `maw`, `boss_party`, `paradise`, `journey`, `hematurgy`, `quests`.

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

**Partners:**
- `active_partners: List[Partner]` — partners with active combat skills contribute to combat

**Monster parts (Consume system):**
- `equipped_parts: dict` — maps slot → hp_value for all equipped monster body parts
- Contributes to `total_max_hp` via `get_parts_hp_bonus()`

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

**Transient combat state** (grouped in `player.cs: CombatState` — reset via `player.reset_combat_state()`):
- `player.cs.ward` (`player.combat_ward`), `player.cs.is_invulnerable` (`player.is_invulnerable_this_combat`)
- `player.cs.bonus_atk/def/crit/bonus_max_hp` — per-combat flat bonuses
- `player.cs.atk_multiplier`, `player.cs.def_multiplier`, `player.cs.crit_multiplier`
- `player.cs.voracious_stacks`, `player.cs.cursed_precision_active`, `player.cs.gaze_stacks`, `player.cs.hunger_stacks`
- `player.cs.lucifer_pdr_burst`, `player.cs.celestial_vow_used`, `player.cs.partner_special_rarity`
- All `player.cs.alchemy_*` fields (potion transient effects), all `player.cs.jewel_*` fields (Jewel unleash transients)
- All of the above are **also accessible via the old names** (`player.combat_ward`, `player.bonus_atk`, etc.) through `@property` forwarders — existing callsites need no changes.

**Per-run codex state** (grouped in `player.run: CodexRunState` — persists across waves, reset when run ends):
- `player.run.atk_penalty` (`player.run_atk_penalty`), `player.run.def_penalty`, `player.run.crit_penalty`
- `player.run.max_hp_bonus` (`player.run_max_hp_bonus`), `player.run.bonus_rarity`, `player.run.boon_fdr`

**Key methods:**
- `get_total_attack()`, `get_total_defence()` — includes all gear/companion/tome/partner bonuses
- `get_total_pdr()`, `get_total_fdr()` — physical/flat damage reduction (hard cap 80%)
- `get_total_ward_percentage()`, `get_combat_ward_value()`
- `get_current_crit_chance()` — returns flat crit chance (higher is better)
- `get_total_rarity()`, `get_special_drop_bonus()` (hard cap 20%)
- `get_ascension_bonuses()`, `get_tome_bonus(stat)`
- `get_weapon_passive()`, `get_armor_passive()`, etc.
- `total_max_hp` property (includes all bonuses including parts)
- `reset_combat_state()` — replaces `player.cs` with a fresh `CombatState()`, zeroing all transients
- `reset_combat_bonus()` — lighter reset: zeros only bonus accumulators and multipliers

### Equipment Models

All built via `core/items/factory.py`.

| Model | Notable Fields |
|---|---|
| `Weapon` | `level`, `attack`, `defence`, `rarity`, `passive`, `p_passive` (pinnacle), `u_passive` (utmost), `infernal_passive`, `forge_tier`, `refines_remaining` |
| `Armor` | `level`, `block`, `evasion`, `ward`, `pdr`, `fdr`, `passive`, `temper_remaining`, `imbue_remaining`, `celestial_passive`, `reinforcement_lvl`, `reinforces_remaining` |
| `Accessory` | `level`, `attack`, `defence`, `rarity`, `ward`, `crit`, `passive`, `passive_lvl`, `void_passive` |
| `Glove` | `level`, `attack`, `defence`, `ward`, `pdr`, `fdr`, `passive`, `passive_lvl`, `essence_1/2/3` + values, `corrupted_essence`, `potential_remaining`, `reinforcement_lvl` |
| `Boot` | Same essence structure as Glove |
| `Helmet` | `level`, `defence`, `ward`, `pdr`, `fdr`, `passive`, essence slots, `corrupted_essence`, `potential_remaining`, `reinforcement_lvl` |

### `DelveState`
Tracks an active mining expedition run. Lives in `core/delve/mechanics.py`.
- `depth`, `current_fuel`, `max_fuel`, `stability` (0–100)
- `pickaxe_tier`: `iron | steel | gold | platinum | ideal`
- `shards_found`, `curios_found`, `ore_found: Dict[str, int]`
- `hazards: List[str]` — pre-generated layer hazards
- `revealed_indices: List[int]` — sensor-revealed layers

### `Companion`
- `level`, `exp`, `species`, `image_url`
- `passive_type`: `atk | def | hit | crit | ward | rarity | s_rarity | fdr | pdr`
- `passive_tier`: 1–5; `balanced_passive` + `balanced_passive_tier`
- Properties: `passive_value`, `description`, `balanced_passive_value`, `balanced_description`
- `is_active` — whether this companion is in the active slot

### `Partner`
Named NPC allies recruited via gacha and deployed on combat/dispatch tasks.
- `id`, `partner_id`, `level`, `exp`, `portrait`
- `combat_skills: List[int]` — skill levels for 3 combat slots + 1 signature
- `dispatch_skills: List[int]` — skill levels for 3 dispatch slots + 1 signature
- `dispatch_task`, `dispatch_start_time`, `dispatch_duration` — active dispatch state
- `affinity` — encounter count; unlocks story tiers at 25/50/75/100
- Data loaded from `assets/partners.csv`; stories from `assets/partners/affinity_stories.json`

### `MonsterModifier`
Structured modifier applied to a monster instance.
- `name: str`, `tier: int` (0 for flat/boss modifiers), `value: float`, `difficulty: float`
- Defined via `ModifierDef` in `core/combat/modifier_data.py`

**Modifier pools:**
- **Common** (tiered 1–5, level-gated): Empowered, Fortified, Titanic, Savage, Lethal, Devastating, Keen, Blinding, Crushing, Searing, Stalwart, Vampiric, Mending, Thorned, Venomous, Parching, Veiled, Enraged, Jinxed, Ironclad, and more
- **Rare tiered**: Commanding, Dampening, Nullifying
- **Rare flat**: Unblockable, Unavoidable, Dispelling, Multistrike, Spectral, Executioner, Time Lord
- **Boss**: Overwhelming, Inevitable, Sundering, Unerring
- **Uber** (hardcoded per encounter): Element protections, Hell's Fury, Void Aura, Balanced Strikes
- **Ascended**: Special modifier; value = `min(20, max(1, monster.level // 10))`

### `CodexTome`
- `slot`, `passive_type`, `tier`, `value: float`
- Tomes grant multiplier bonuses (Vitality, Wrath, Bastion, Bulwark, Resilience, Precision, Providence)

### `Monster`
`name, level, hp, max_hp, xp, attack, defence, modifiers: List[MonsterModifier], image, flavor, species, is_boss, combat_round, is_essence`

### `DungeonState`
Tracks multi-room dungeon crawls: `current_floor`, `max_regular_floors`, player HP/ward snapshot, `potions_remaining`, `dungeon_coins`, `loot_gathered`, `player_buffs`, `player_curses`, `current_room_options`, `last_action_message`

### `Settlement` / `Building`
- `Settlement`: `user_id`, `server_id`, `town_hall_tier`, `building_slots`, `timber`, `stone`, `last_collection_time`, `buildings`
- `Building`: `building_type`, `tier`, `slot_index`, `workers_assigned`, `name` (property)

---

## Combat System (`core/combat/`)

```
core/combat/
├── combat_log.py       — Per-fight file logger (enabled via config.json "combat_logging")
├── models.py           — Combat-scoped dataclasses
│
├── calc/               — Pure math, no side-effects; safe to unit-test in isolation
│   ├── calcs.py        — Passive family registry, fmt_weapon_passive, get_weapon_tier; re-exports hit/damage
│   ├── hit_calc.py     — calculate_hit_chance, calculate_monster_hit_chance, calculate_crit_chance, resolve_hit/crit, build_attack_multiplier
│   ├── damage_calc.py  — roll_monster_damage, calc_crit/hit/miss_damage, apply_monster_damage_reduction, apply_damage_to_monster
│   └── ward_system.py  — add_ward, generate_player_ward_on_hit
│
├── dojo/               — Training dummy simulation (no rewards)
│   ├── dummy_engine.py — Dummy combat simulation logic
│   └── views_dojo.py   — DummyConfigView UI
│
├── economy/            — Loot, XP, and reward distribution
│   ├── config.py       — Economy constants and drop rate configuration
│   ├── drops.py        — DropManager: roll logic, essence drops
│   ├── experience.py   — ExperienceManager: XP thresholds and level-up logic
│   ├── loot.py         — Item drop tables and slot selection
│   ├── rewards.py      — calculate_rewards, apply_partner_end_rewards
│   ├── uber_rewards.py — Uber boss-specific reward handling
│   └── victory.py      — `apply_victory_rewards`: full post-victory orchestration (rewards, XP, companion drops, slayer task, quest progress ticking, settlement Zeal)
│
├── mobgen/             — Encounter setup and procedural generation
│   ├── gen_mob.py      — generate_encounter, generate_boss, generate_ascent_monster; modifier application
│   ├── encounters.py   — EncounterManager: cooldowns, zone/tier selection
│   └── modifier_data.py — ModifierDef table (all modifier definitions, tiers, level gates, difficulty values)
│
├── turns/              — Turn-by-turn processing; orchestrates calc/ modules
│   ├── engine.py       — Main orchestrator: apply_stat_effects, apply_combat_start_passives
│   ├── helpers.py      — PlayerTurnResult / MonsterTurnResult dataclasses
│   ├── player_turn.py  — process_player_turn (main player action handler + post-hit effects)
│   ├── monster_turn.py — process_monster_turn (enemy AI + modifier effects)
│   ├── passives.py     — apply_stat_effects, apply_combat_start_passives (weapon/armor/accessory/glove passives)
│   └── jewel_engine.py — Paradise Jewel active skill effects and unleash logic
│
├── ui/                 — Stateless embed builders
│   ├── combat_embed.py — build_combat_embed, stat blocks
│   ├── defeat_screen.py — Defeat embed builder
│   └── victory_screen.py — Victory embed builder
│
└── views/              — All combat UI views
    ├── views.py            — CombatView — standard combat flow
    ├── views_elemental.py  — ElementalEncounterView (skills-based elemental combat)
    ├── views_lucifer.py    — InfernalContractView / LuciferChoiceView
    ├── views_uber.py       — Uber boss entry routing
    ├── views_uber_aphrodite.py — Aphrodite encounter
    ├── views_uber_evelynn.py   — Evelynn encounter
    ├── views_uber_gemini.py    — Gemini encounter
    ├── views_uber_hub.py       — UberHubView
    ├── views_uber_lucifer.py   — Lucifer encounter
    ├── views_uber_neet.py      — NEET encounter
    └── warning_views.py    — CorruptedEncounterGateView, LowHealthWarningView
```

**Import conventions:**
- Always use `from core.combat.calc.calcs import get_weapon_tier` (not `core.combat.calcs`)
- Always use `from core.combat.mobgen.modifier_data import make_modifier` (not `core.combat.gen.modifier_data`)
- Always use `from core.combat.turns import engine` (not `from core.combat import engine`)
- `from core.combat import jewel_engine` and `from core.combat import rewards` work via `__init__.py` backward-compat re-exports

**Adding a new modifier:** Add a `ModifierDef` entry to `core/combat/mobgen/modifier_data.py`, then handle the effect in `turns/monster_turn.py` (or `turns/player_turn.py` if it affects the player's turn). Do not hardcode values anywhere else.

**Key functions:**
- `turns/engine.py: apply_stat_effects(player, monster)` — monster modifiers reduce player stats
- `turns/engine.py: apply_combat_start_passives(player)` — weapon/armor/accessory passives on round 1
- `calc/calcs.py: get_weapon_tier(player, key)`, `fmt_weapon_passive(passive_str)`
- `calc/hit_calc.py: calculate_hit_chance(player, monster)`, `calculate_crit_chance(player)`
- `calc/damage_calc.py: calculate_damage_taken(player, monster)`

---

## Combat State Reset Rules

These rules govern which state persists across fights and which is wiped. Always follow this matrix when adding new per-combat state.

| Encounter type | Jewel `skill_charges` | Jewel transients (primed/DoT) | Misc stacks (voracious, gaze, hunger, …) |
|---|---|---|---|
| **Normal combat** (single fight, `/combat`) | Reset at encounter start (`CombatView.__init__`) | Fresh from Player load | Fresh from Player load |
| **Phase bosses** (Aphrodite, Gemini, Lucifer, NEET) | Persist across phases | Persist across phases | Persist across phases |
| **Ascent** (floor → floor) | Reset once at session start; persist floor-to-floor | Reset between every floor (`_next_floor`) | Reset between every floor (`_next_floor`) |
| **Codex** (wave → wave) | Reset once at run start; persist wave-to-wave | Reset between every wave (`_setup_next_wave`) | Reset between every wave (`_setup_next_wave`) |

**Jewel `skill_charges`** — accumulated progress toward an unleash, stored in `player.jewel_of_paradise["skill_charges"]` and persisted to DB. Reset via `_je.reset_jewel_charges(player)`.

**Jewel transients** — mid-fight primed/DoT states in `CombatState` (`jewel_cataclysm_primed`, `jewel_onslaught_primed`, `jewel_wardforge_bonus_dmg`, `jewel_acrimony_dot/dot_dmg`). Reset via `_je.reset_jewel_transients(player)`.

**Misc stacks** — `voracious_stacks`, `cursed_precision_active`, `gaze_stacks`, `hunger_stacks`, `celestial_vow_used`. Reset explicitly by name (see `_next_floor` and `_setup_next_wave`).

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

### Inventory UI (`core/inventory/`)
The canonical inventory implementation. See the View File Splitting section above for the full layout. Import from the package root:
```python
from core.inventory import InventoryListView, GearView, ItemDetailView
from core.inventory import ForgeView, TemperView, ...
```

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

### Prestige Hall (`cogs/prestige.py`, `database/repositories/prestige.py`)
- Cosmetic customization and server monument system. No separate `core/` module — all logic lives in the cog.
- **Cosmetics** (purchased once with gold, free to swap after):
  - Titles (6 options, 1B gold each): The Gilded, Iron Warden, The Blessed, Void-Touched, Shadowborn, Ascendant
  - Flairs (3 options, 1B gold each): Casual, Heroic, Ominous
  - Custom Avatar: 100M gold per upload (URL, must be square ≤600×600px)
  - Rename: 750M gold per rename
  - Death Message: 300M gold to unlock, free to update after
  - Monument Quote: 2B gold to unlock, free to update after
- **Hall of Fame**: Displays monument quotes from the top 10 players on the server (ordered by level).
- **DB tables:** `prestige_owned`; cosmetic fields on the `users` row (`prestige_border`, `prestige_title`, `prestige_display_name`, `prestige_flair`, `prestige_death_message`, `prestige_monument`).

---

## Other Systems

### Consume (`core/consume/`, `cogs/consume.py`)
- Players loot **monster body parts** from combat and equip them to gain permanent Max HP bonuses.
- 8 body slots: head, torso, right_arm, left_arm, right_leg, left_leg, cheeks, organs.
- Inventory cap: 20 parts. Parts are destroyed on equip (slot conflict triggers confirmation).
- **DB tables:** `monster_parts`, `monster_parts_equipped`.
- Repository: `database/repositories/monster_parts.py`.

### Delve (`core/delve/`, `cogs/delve.py`)
- Mining mini-game. Players pay a permit cost (gold), then drill through procedurally generated layers.
- Each layer is one of: Safe, Gravel, Gas Pocket, Magma Flow, Ore Vein.
- Hazards deal stability damage; pickaxe tier mitigates it. Ore Vein layers yield obsidian shards.
- Three upgradeable stats tracked in `delve_progress`: `fuel_lvl`, `struct_lvl`, `sensor_lvl`.

| File | Purpose |
|---|---|
| `core/delve/mechanics.py` | `DelveState` dataclass + `DelveMechanics` static methods |
| `core/delve/delve_views.py` | `DelveEntryView`, `DelveView`, `DelveUpgradeView` |
| `database/repositories/delve.py` | `get_profile`, `modify_shards`, `add_xp`, `upgrade_stat` |

**`DelveMechanics` key methods:**
- `generate_layer(depth)` — probabilistic hazard type; Ore Vein available from depth 5 at 7%
- `calculate_damage(hazard, pickaxe_tier)` — base damage with tier mitigation + variance
- `get_entry_cost(fuel_level)` — `1000 + fuel_level * 500`
- `calculate_level_from_xp(xp)` — `sqrt(xp / 50) + 1`

### Maw (`core/maw/`, `cogs/maw.py`)
- Weekly world boss. One 7-day cycle starts every Sunday 12:00 UTC; active window is 5.5 days, then a collection window until the next cycle.
- Players "fight" to accumulate personal damage (capped at 500k). Hourly ticks roll from `[100, 1_000, 10_000]`.
- Boosts deal 10k flat damage with a 20-hour cooldown.
- Rewards scale with damage % of cap: up to 10 curio milestones and a puzzle box at ≥80%.

| File | Purpose |
|---|---|
| `core/maw/mechanics.py` | Cycle math, damage rolls, reward calculation |
| `core/maw/ui.py` | `build_maw_embed` (stateless embed builder) |
| `core/maw/views.py` | `MawView` |
| `database/repositories/maw.py` | Cycle records, participant data |

### Partners (`core/partners/`, `cogs/partners.py`)
- Gacha-recruited NPC allies. Deployed passively in combat or sent on timed dispatch tasks.

| File | Purpose |
|---|---|
| `views/roster_view.py` | Partner roster list |
| `views/detail_view.py` | Partner detail + skill management |
| `views/gacha_view.py` | Recruitment (roll) UI |
| `views/dispatch_view.py` | Dispatch task UI |
| `views/affinity_view.py` | Affinity story UI |
| `views/boss_party.py` | Boss party formation |
| `dispatch.py` | Reward calculation for combat/gathering dispatch tasks |
| `mechanics.py` | Level/skill progression, cost tables, skill definitions |
| `models.py` | Partner-scoped dataclasses |
| `ui.py` | Embed builders |
| `data.py` | Load partner metadata from `assets/partners.csv` |
| `resources.py` | Rarity colors, skill name/star display helpers |

- **Skills:** 3 combat slots + 1 combat signature; 3 dispatch slots + 1 dispatch signature.
- **Dispatch tasks:** Combat (gold + rune rewards, boss keys), Gathering (mining/fishing/woodcutting loot), Boss tasks. Accumulate up to 48 hours.
- **Affinity:** Encounter count unlocks story tiers at 25/50/75/100 thresholds.
- **DB tables:** `user_partners`, `user_partner_items`, `user_partner_shards`.
- Repository: `database/repositories/partners.py`.

### Journey (`core/journey/`, `cogs/journey.py`)
- Level milestone reward system. Players claim one-time rewards at specific level thresholds.
- Milestones defined in `core/journey/rewards.py`. UI in `core/journey/views.py`.
- Repository: `database/repositories/journey.py`.

### Hematurgy (`core/hematurgy/`, `cogs/hematurgy.py`)
- Blood-based passive upgrade system. Players unlock and tier up passive effects using Primordial blood (slot unlocks) and Evolutionary/Mutative blood (tier upgrades).
- Introduces the **Hatchery** settlement building.
- Passives include: `reverberation`, `soothing_venom`, `iron_momentum`, `serrated`, `haemorrhage`, `vital_resonance`, and more; T6–T7 are mutation-only chase tiers.
- `core/hematurgy/mechanics.py` — cost tables, tier value tables, upgrade logic.
- `core/hematurgy/engine.py` — passive effect application.
- Repository: `database/repositories/hematurgy.py`.

### Alchemy (`core/alchemy/`, `cogs/alchemy.py`)
- Potion transmutation with passive effects on potions.
- Passives stored in `alchemy_data` and `potion_passives` tables.
- Repository: `database/repositories/alchemy.py`.

### Settlement (`core/settlement/`, `cogs/settlement.py`)
- Ideology-linked settlements with buildings (Apothecary, Barracks, Temple, Hatchery, etc.).
- Views split under `core/settlement/views/`: `base.py`, `construction.py`, `detail.py`, `town_hall.py`, `black_market.py`, `dashboard.py`, `research.py`, `plot_detail.py`, `nursery_foundry.py`.
- Repository: `database/repositories/settlement.py`.

**Settlement Grid / Plot System (`core/settlement/plots.py`)**
- 5×5 grid (corners excluded); 20 developable plots + Town Hall at center. Plot indices 1–20.
- Each plot has a `bonus_type` rolled from `PLOT_BONUS_TABLE` (Fertile Ground, Rich Seam, Sacred Ground, Gold Vein, Bedrock, Trade Route, Ancient Foundation, Ley Line, Expedition Camp, Common Ground).
- `can_develop(plot_index, developed_indices)` — plot must be adjacent to an already-developed plot or TH.
- `render_grid(developed_indices, building_by_plot)` — renders the settlement grid as a monospace code block.
- `get_effective_max_workers(building_type, tier, plot_bonus_type, adj_shrine_cap_x2, has_watchtower)` — computes worker cap including plot + adjacency bonuses.
- `PlotDetailView` / `MetaBuildingConstructionView` — UI for managing plots and constructing meta buildings.

**Meta Buildings** (placed on plots alongside regular buildings):
- Up to `town_hall_tier` meta buildings allowed (T1 = 1 slot, T7 = 7 slots).
- Must be fully staffed to activate (Watchtower is passive — no workers needed).
- Meta buildings never affect other meta buildings. Ley Line plots amplify adjacency bonuses by ×1.5.

| Meta Building | Effect |
|---|---|
| Servant's Quarters | +2% generator output per 10 workers (max +20%) to adjacent generators |
| Supply Depot | +15% converter effectiveness to adjacent converters |
| Grand Cathedral | Doubles worker cap for adjacent shrine buildings |
| Watchtower | Global +1% × tier worker cap increase on all regular buildings |
| Foreman's Post | +25% output to all adjacent buildings |
| Shrine Garden | +15% effectiveness to adjacent shrine buildings |
| Encampment | +0.5 stamina/hr per 100 War Camp workers to adjacent War Camps |
| Apothecary Annex | +4% flat heal per 100 workers to adjacent Apothecary |

**Development Turns / Zeal Economy (`core/settlement/turn_engine.py`)**
- Players earn **Zeal** from combat wins (10 per win) and quest completions (30/90 for 1★/3★).
- Passive Zeal accrues each Development Turn based on Town Hall tier.
- Daily Zeal caps: soft cap 600 (gains halved above), hard cap 800.
- `ZEAL_TO_DT = 10` — 10 Zeal converts to 1 Development Turn.
- `compute_zeal_gain(base, earned_today)` — applies soft/hard cap logic.
- `process_next_turn(bot, user_id, server_id, town_hall_tier)` — orchestrates one Development Turn: advances projects, ticks Black Market deal, fires/expires events, increments total turns, awards passive Zeal.

**Settlement Projects** (turn-based; replaces instant build/upgrade):
- Construction and upgrades queue as projects with DT costs (`PROJECT_CONSTRUCTION_DT`, `PROJECT_UPGRADE_DT_PER_TIER`).
- Project types: `construction`, `upgrade`, `research`, `nursery`, `foundry_idlem`.
- `construction_dt_cost(building_type, event_effects)` — returns DT cost, halved during Inspiration Surge.
- `upgrade_dt_cost(building_type, target_tier)` — DT cost scales with tier.

**New Buildings**:
- **Nursery** — produces workers via Development Turns (~1–2 per turn). `NurseryView` in `nursery_foundry.py`. Workers increment ideology follower count on completion.
- **Idlem Foundry** — produces Idlem (~1–2 per turn). `IdlemFoundryView` in `nursery_foundry.py`. Idlem powers the Black Market passive tree.
- **Uber Shrine** — consolidated shrine replacing the five individual shrines. Internal per-statue worker allocation stored as JSON in building data.

**Black Market Passive Tree** (powered by Idlem):
- Three branches: Efficiency (−10%/−20%/−35% deal turns; Instant Deals for ≤5-turn deals), Value (+5%/+10%/+15% offer value), Biases (extra loot rolls per deal category).
- Bias nodes: `rune_bias`, `gathering_bias`, `key_bias`, `egg_bias`, `gear_bias`, `high_end_bias`, `gold_bias`.
- `calculate_offer_value(offer, tree_nodes, bm_tier)` — computes total Value score for a trade offer.
- `compute_processing_turns(value, bm_tier, tree_nodes)` — returns DT cost for a deal.
- `roll_bm_rewards(value, active_biases, player_level, tree_nodes)` — rolls loot for a completed deal.
- `BMPassiveTreeView` and `OfferBuilderView` in `black_market.py`.

**Settlement Events** (scheduled by total Development Turns):
- Opportunity events: Merchant Caravan (+25% BM value for 5 turns), Inspiration Surge (halved construction DT for 3 turns), Resource Windfall (+50% generator output for 4 turns), Ideological Rally (instant +100 Zeal), Baby Boom (Nursery ×2 for 5 turns), Foundry Surge (Idlem Foundry ×2 for 4 turns), Wandering Scholar (+3 Blueprints).
- Crisis events (with advance warning): Bandit Raid, Plague Outbreak, Void Incursion.
- Event types: `instant` (fires immediately), `ongoing` (active for N turns), `upcoming` (advanced warning before firing).
- `tick_events`, `add_event`, `remove_event` in the settlement repository.

**Settlement Repository new key methods**: `advance_projects`, `delete_project`, `upsert_project`, `get_projects`, `get_pending_deal`, `decrement_deal_turn`, `delete_pending_deal`, `get_bm_tree`, `tick_events`, `get_active_events`, `add_event`, `remove_event`, `increment_turns`, `get_turns_data`, `add_pending_zeal`, `add_zeal`, `get_zeal_data`, `reset_daily_zeal_if_needed`, `add_idlem`, `complete_research`, `upgrade_building_tier`, `build_structure`.

### Quests (`core/quests/`, `cogs/quests.py`)
- Daily contract board + long-form Horizon path system. Players earn Quest Tokens redeemable in the quest shop.
- **Daily Contracts**: 3 slots rolled from `DAILY_QUESTS`. Each slot is tier 1 or tier 3 (60/40). Reroll costs a token; cooldown 20 hours.
- **Horizon Paths**: Long-form quests (`HORIZON_PATHS`). Each path grants tokens + a unique special reward on completion.
- **Quest Tokens**: Currency for the quest shop (`shop_views.py`). Earned from contract and horizon turn-ins.
- **Perks**: `veteran_unlocked` (+1 bonus token per turn-in), `enrichment_unlocked` (+50% gold on turn-in), `prospector_unlocked` (gathering cache on turn-in), `horizon_boost_uses` (Horizon progress counts as 2 per boost use).

| File | Purpose |
|---|---|
| `data.py` | `DAILY_QUESTS`, `HORIZON_PATHS`, `get_damage_goals` |
| `mechanics.py` | `roll_board`, `reroll_slot`, `tick_quest_progress`, `grant_contract_reward`, `grant_horizon_reward` |
| `views.py` | Quest board UI, contract and horizon views |
| `shop_views.py` | Quest shop (redeem tokens) |

- **`tick_quest_progress(bot, user_id, server_id, event_type, value)`** — called from `victory.py` and other completion hooks; ticks matching contracts and the active Horizon quest.
- Event types tracked: `combat_win`, `damage`, `boss_kill:<name>`, `calcified_kill`, `corrupted_kill`, `codex_complete`, `ascent_floor`, `apex_complete`, `egg_release`, `rune_refinement`, `rune_shatter`, `rune_potential`, `casino_win`, `slayer_task_complete`.
- Quest completion also grants **Zeal** for the settlement system (30 for 1★, 90 for 3★).
- Repository: `database/repositories/quests.py`. Key methods: `ensure_meta`, `get_meta`, `get_contracts`, `tick_contract_progress`, `complete_contract`, `get_horizon`, `tick_horizon_progress`, `complete_horizon`, `add_tokens`, `decrement_horizon_boost`.

### Slayer (`core/slayer/`, `cogs/slayer.py`)
- Task-based system; completing tasks earns points and emblems.
- 5 emblem slots (`slot_1–5`), each with a `type` and `tier`.
- Repository: `database/repositories/slayer.py`.

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
| `settlement` | `get_settlement`, `get_buildings`, `build_structure`, `assign_workers`, `upgrade_building_tier`, `update_resources`, `upsert_project`, `get_projects`, `advance_projects`, `delete_project`, `get_pending_deal`, `decrement_deal_turn`, `delete_pending_deal`, `get_bm_tree`, `get_active_events`, `add_event`, `remove_event`, `tick_events`, `increment_turns`, `get_turns_data`, `add_pending_zeal`, `add_zeal`, `get_zeal_data`, `reset_daily_zeal_if_needed`, `add_idlem`, `complete_research` |
| `slayer` | `get_profile`, `update_level`, `get_emblem`, `update_emblem_slot`, `update_active_task` |
| `uber` | `get_progress`, `update_progress`, `add_sigils` |
| `essences` | `get_essence_count`, `add_essence`, `remove_essence`, `get_all_essences` |
| `alchemy` | `get_level`, `update_level`, `get_potion_passives`, `update_potion_passive` |
| `ascension` | `get_unlocked_floors`, `unlock_floor`, `get_all_unlocks` |
| `codex` | `get_chapter_progress`, `update_progress`, `record_run` |
| `partners` | `get_all`, `get_by_id`, `add_partner`, `update_skills`, `update_dispatch`, `update_affinity` |
| `monster_parts` | `get_inventory`, `add_part`, `remove_part`, `get_equipped`, `equip_part`, `bulk_discard` |
| `prestige` | `get_owned`, `add_owned`, `get_all_monuments` |
| `delve` | `get_profile`, `modify_shards`, `add_xp`, `upgrade_stat` |
| `maw` | Cycle records, participant damage, boost tracking |
| `boss_party` | Party formation and boss-party state |
| `paradise` | Paradise system data |
| `social` | Ideology and follower data |
| `settings` | User personal preferences |
| `duels` | Win/loss records |
| `journey` | Level milestone claim state |
| `hematurgy` | Blood passive unlock and tier state |
| `quests` | `ensure_meta`, `get_meta`, `get_contracts`, `tick_contract_progress`, `complete_contract`, `get_horizon`, `tick_horizon_progress`, `complete_horizon`, `add_tokens`, `decrement_horizon_boost` |

---

## Adding a New Feature — Checklist

1. **SQL changes** → `database/schema.sql` + new methods in the appropriate `database/repositories/*.py`
2. **Model changes** → `core/models.py` dataclass (or `core/<module>/mechanics.py` for run-scoped state like `DelveState`)
3. **Logic** → `core/<module>/mechanics.py` (pure functions, no I/O)
4. **UI** → Extend `BaseView`; put stateless embed builders in `ui.py` or `<module>.py`; split into `views/` subdirectory if the module is complex (follow `core/inventory/` pattern)
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

### Creating a View

```python
# Top-level view (owns the user_id)
class MyView(BaseView):
    def __init__(self, bot, user_id: str, server_id: str):
        super().__init__(bot, user_id, server_id)

# Child / sub-view (inherits from parent)
class MySubView(BaseView):
    def __init__(self, bot, parent: BaseView):
        super().__init__(bot, parent=parent)
```

Always assign `view.message` after sending so `on_timeout` can remove the buttons:
```python
msg = await interaction.followup.send(embed=embed, view=view)
view.message = msg
```

### Double-Click Race Condition Guard

All buttons that trigger state-changing operations must include a re-entry guard to prevent double-click races:

```python
class MyView(BaseView):
    def __init__(self, ...):
        ...
        self._processing = False  # re-entry guard

    @discord.ui.button(label="Confirm", style=ButtonStyle.primary)
    async def confirm(self, interaction: Interaction, button: Button):
        if self._processing:
            await interaction.response.defer()
            return
        self._processing = True
        await interaction.response.defer()
        # ... do the work
```

This guard must be present on every button that writes to the database or mutates game state.

### Loading Asset Files

```python
from core.util import load_list
names = load_list("assets/items/swords.txt")
```

### Image Assets

When building new views that display entities (items, companions, monsters, partners, etc.), flag that an image asset may be needed. Image assets live in `assets/` and are managed via `scripts/audit_images.py`, `scripts/reseed_images.py`, and `scripts/upload_new.py`. Recommend generating or sourcing an appropriate image whenever a new entity type is introduced.

---

## What NOT to Do

- Do not put SQL strings in `cogs/` or `core/`.
- Do not put game math in `cogs/`.
- Do not use `wait_for()` for multi-step user flows — use Views.
- Do not extend `discord.ui.View` directly — always use `BaseView`.
- Do not forget `clear_active` on timeout and exit paths (BaseView's `on_timeout` handles the common case, but explicit exit buttons must call it too).
- Do not skip `await interaction.response.defer()` before slow operations.
- Do not add speculative abstractions — build only what the task requires.
- Do not add error handling for impossible states; validate only at Discord interaction boundaries.
- Do not hardcode modifier values outside `core/combat/mobgen/modifier_data.py`.
- Do not add a button that mutates state without a re-entry guard (`self._processing` pattern).
- Do not add a new passive without defining it in the validated passive registry — all passives must have documented, validated behavior.

---

## Project Info

- **Version**: 0.91
- **Runtime**: Python 3.11.5, discord.py, aiosqlite
- **DB**: SQLite (`database/schema.sql`)
- **Assets**: `assets/` — CSV/JSON/TXT lookup tables (monsters, exp, item names, system config)
- **Tests**: `tests/test_combat_logic.py`, `tests/tests.py`
