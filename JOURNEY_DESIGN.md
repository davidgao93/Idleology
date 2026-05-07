# Journey System — Design Document

## Overview

The `/journey` command introduces two linked features:

1. **Level-gated system access** — each major system is locked behind a minimum level. Players receive a clear message when they try to access a locked feature.
2. **Milestone reward claims** — at levels 1, 10, 20, 30, 40, 50, 60, 70, 80, 90, and 100, players can claim a one-time reward bundle through the `/journey` view.

The journey view shows every milestone, which ones are reached, which rewards have been claimed, and a button to claim any pending unclaimed reward for a reached milestone.

---

## Milestone Definitions

| Level | Reward | Systems Unlocked |
|-------|--------|-----------------|
| 1 | +20 potions | combat, gathering, tavern, equipment management |
| 10 | +10 guild tickets | `/partner`, `/trade` |
| 20 | +3 curios, +50,000 gold | `/maw`, Aphrodite gate in combat (already gated in `encounters.py`) |
| 30 | +3 essences of power, +100,000 gold | Calcified (essence) monsters spawn in `/combat` |
| 40 | +3 random boss keys¹, +150,000 gold | `/companions` |
| 50 | +1 void key, +200,000 gold | `/settlement`, NEET gate in combat (already gated) |
| 60 | +1 capricious carp, +1 sparkling sprig, +1 blessed bismuth | Elemental encounters in combat² |
| 70 | +500,000 gold, +2–4 random runes³ | (no new system) |
| 80 | +1 antique tome | `/codex` (already gated, move check to level 80) |
| 90 | +500,000 gold | (no new system) |
| 100 | +1 pinnacle key | Corrupted monsters (already gated), `/ascent` (already gated) |

**¹ Random boss keys** — each of the 3 is a random pick from `{dragon_key, angel_key}`.  
**² Elemental keys** — `capricious_carp`, `sparkling_sprig`, and `blessed_bismuth` are the uber-boss materials used to fight Elemental tier bosses. They do not drop from monsters (boss or normal) before level 60.  
**³ Random runes** — roll `random.randint(2, 4)`, each rune is a random choice from `{refinement_runes, shatter_runes, potential_runes}`.

### Combat Drop Level Gates

These gates are applied inside `check_special_drops()` in `core/combat/rewards.py` and `_roll_essence_spawn()` in `core/combat/gen_mob.py`:

| Level | Items | Location |
|-------|-------|----------|
| 20 | `dragon_key`, `angel_key` | `check_special_drops` — normal mob |
| 30 | `soul_cores`, essence monsters spawn | `check_special_drops` + `_roll_essence_spawn` |
| 40 | `balance_fragment` | `check_special_drops` — normal mob |
| 50 | `void_frags` | `check_special_drops` — normal mob |
| 60 | `capricious_carp`, `sparkling_sprig`, `blessed_bismuth` | `check_special_drops` — both boss and normal mob |

Items not listed here (`shatter_rune`, `antique_tome`, `pinnacle_key`, `spirit_stone`, `magma_core`, `life_root`, `spirit_shard`) are unchanged.

---

## Database Changes

### New Table — `journey_milestones`

Add to `database/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS `journey_milestones` (
  `user_id`         TEXT    NOT NULL,
  `milestone_level` INTEGER NOT NULL,
  `claimed_at`      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`, `milestone_level`)
);
```

A row exists only when the reward has been claimed. Checking `milestone_level IN (SELECT milestone_level FROM journey_milestones WHERE user_id = ?)` is the canonical "already claimed" test.

### Guild Tickets

Guild tickets live in `user_partner_items.guild_tickets`, not the `users` table. The reward grant must call:

```python
await bot.database.partners.ensure_items_row(user_id)
await bot.database.partners.add_tickets(user_id, 10)
```

`ensure_items_row` must be called first (as done in `cogs/partners.py`) so the row exists.

### Essences of Power

Use the existing essences repository:

```python
for _ in range(3):
    await bot.database.essences.add(user_id, "power")
```

---

## New Files

### `database/repositories/journey.py`

```python
class JourneyRepository:
    MILESTONE_LEVELS = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    async def get_claimed(self, user_id: str) -> set[int]:
        """Returns the set of milestone levels already claimed by this user."""

    async def claim(self, user_id: str, milestone_level: int) -> None:
        """Inserts a claim row. Caller must verify eligibility first."""
```

Wire it into `database/__init__.py` as `self.journey = JourneyRepository(connection)`.

### `core/journey/rewards.py`

Stateless reward definitions and grant logic:

```python
MILESTONES: dict[int, dict]  # level → {label, systems_unlocked, reward_desc, grant_fn}
```

Each `grant_fn(bot, user_id)` is an async callable that performs all DB writes for that milestone. Keeps the view thin.

### `core/journey/views.py`

`JourneyView(BaseView)` — paginated or scrollable list of milestones. Each row shows:
- Lock/unlock icon (level reached or not)
- Reward description
- "Claimed" badge or "Claim" button (if reached and unclaimed)
- Systems unlocked at that tier

A single `Claim` button (or one per unclaimed-and-reachable milestone, depending on UX preference — see below).

**Recommended UX:** Show all milestones as an embed list. A single `Claim All` button claims every eligible unclaimed milestone at once; individual inline buttons are also acceptable if the list is short enough.

### `cogs/journey.py`

```python
@app_commands.command(name="journey", description="View your level milestones and claim rewards.")
async def journey(self, interaction: Interaction):
    existing_user = await self.bot.database.users.get(user_id, server_id)
    if not await self.bot.check_user_registered(interaction, existing_user):
        return
    # No is_active check needed — journey is read-only browsing + a DB write claim
    view = JourneyView(self.bot, user_id, server_id, player_level, claimed_set)
    ...
```

---

## Level Gates to Add

Each gate follows the exact pattern already used in `cogs/codex.py`:

```python
if existing_user[4] < REQUIRED_LEVEL:
    await interaction.response.send_message(
        "...", ephemeral=True
    )
    return
```

### `cogs/partners.py` — Level 10

```python
if existing_user[4] < 10:
    await interaction.response.send_message(
        "The Partner Guild only opens its doors to adventurers who have reached **Level 10**.",
        ephemeral=True,
    )
    return
```

Note: `existing_user` is not fetched in the current `partners.py`. Add the fetch before the level check:
```python
existing_user = await self.bot.database.users.get(user_id, server_id)
if not await self.bot.check_user_registered(interaction, existing_user):
    return
```

### `cogs/trade.py` — Level 10 (already exists, verify message matches style)

The check at line 36 already exists. Confirm the message is consistent with the new system's tone.

### `cogs/maw.py` — Level 20

```python
if existing_user[4] < 20:
    await interaction.response.send_message(
        "The Maw of Infinity does not stir for those below **Level 20**.",
        ephemeral=True,
    )
    return
```

### `cogs/companions.py` — Level 40

`companions.py` currently skips the `check_user_registered` call. Add the full standard block:

```python
existing_user = await self.bot.database.users.get(user_id, str(interaction.guild_id))
if not await self.bot.check_user_registered(interaction, existing_user):
    return
if not await self.bot.check_is_active(interaction, user_id):
    return
if existing_user[4] < 40:
    await interaction.response.send_message(
        "Companions reveal themselves only to adventurers who have reached **Level 40**.",
        ephemeral=True,
    )
    return
```

### `cogs/settlement.py` — Level 50

```python
if existing_user[4] < 50:
    await interaction.response.send_message(
        "Settlements can only be founded by those who have proven themselves at **Level 50**.",
        ephemeral=True,
    )
    return
```

### `cogs/codex.py` — Level 80 (already exists at the correct level, no change needed)

### `cogs/ascent.py` — Level 100 (already exists, no change needed)

---

## Combat Drop Gating

### Essence (Calcified) Monsters — Level 30 Gate

**Location:** `core/combat/gen_mob.py` — wherever `monster.is_essence = True` is assigned or the essence monster type is selected.

Add a player-level check so essence monsters only appear for players at level 30+:

```python
# Inside the encounter generation logic that determines monster type
if player.level < 30:
    is_essence = False  # force off; calcified monsters not yet in the world
```

The exact line depends on how `is_essence` is set in `gen_mob.py`. The check must be applied before the monster type is committed.

### Corrupted Encounter — Level 100 (already gated in `cogs/combat.py` line 142, no change needed)

### Boss Door Gates (already implemented in `core/combat/encounters.py`)

All four boss types already have `player_level >=` checks in `EncounterManager.check_boss_door`. No changes needed.

---

## Registration Change — Level 1 Potions

**Decision:** The level 1 potions are granted manually via `/journey`, not at registration. This incentivises new players to use `/journey` as their first command after registering.

**What changes in `complete_registration` (`core/character/views.py`):**
- Remove `modify_stat(user_id, "potions", 10)` — starter potions no longer given at registration.
- The 200 gold starter pack is unchanged.
- The registration completion embed now prominently directs the player to `/journey`:

> *"Your adventure begins now. Use `/journey` to claim your starter rewards and see what awaits you as you grow stronger. Each milestone unlocks new systems and grants valuable items — start there first!"*

The actual level 1 grant (inside the journey claim flow):
```python
await bot.database.users.modify_currency(user_id, "potions", 20)
await bot.database.journey.claim(user_id, 1)
```

Existing players who registered before this system ships will see Level 1 as unclaimed and can collect it.

---

## Wiring into `database/__init__.py`

```python
from database.repositories.journey import JourneyRepository

# Inside DatabaseManager.__init__ or async setup:
self.journey = JourneyRepository(self.connection)
```

---

## Implementation Order

1. `database/schema.sql` — add `journey_milestones` table
2. `database/repositories/journey.py` — `get_claimed`, `claim`
3. Wire repository into `database/__init__.py`
4. `core/journey/rewards.py` — milestone definitions + `grant_fn` per level
5. `core/journey/views.py` — `JourneyView` extending `BaseView`
6. `cogs/journey.py` — `/journey` command (thin, delegates to view)
7. Level gate additions: `cogs/partners.py`, `cogs/maw.py`, `cogs/companions.py`, `cogs/settlement.py`
8. Drop gate: `core/combat/gen_mob.py` (essence monster level 30 check)
9. Registration: add level 1 auto-claim to register flow (if Option A)
10. Verify `cogs/trade.py` message tone; `cogs/codex.py` and `cogs/ascent.py` unchanged

---

## Notes & Open Questions

- **Existing players** who are already above a milestone level when the system ships will see all their reached milestones as unclaimed and can claim them all at once. This is intentional — don't retroactively set any as claimed.
- **`doors_enabled` flag** — this already controls whether the boss door UI appears in combat. The journey system's "gate" for Aphrodite/Lucifer/Gemini/NEET is the existing level check in `EncounterManager.check_boss_door`, not `doors_enabled`. No change needed there.
- **Elemental of Elements (Level 60)** — if this refers to a future distinct encounter type not yet implemented, the journey entry for Level 60 can show the reward and a placeholder unlock description. No combat code changes are needed until that encounter is built.
- **`user_partner_items` row** — must be created before granting guild tickets. The journey repository's `grant_fn` for level 10 must call `ensure_items_row` first.
