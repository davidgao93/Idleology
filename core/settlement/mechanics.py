# core/settlement/mechanics.py

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from core.settlement.constants import (
    ITEM_NAMES,
    SPECIAL_MAP,
    UBER_BUILDINGS,
)
from core.settlement.plots import (
    PLOT_BONUS_TABLE,
    get_adjacent_plot_indices,
)

if TYPE_CHECKING:
    from core.settlement.models import Building, Plot


class SettlementMechanics:
    # --- CONSTANTS ---
    MAX_TIER = 5

    # Building Definitions
    # 'type': generator (creates from thin air), converter (consumes input), passive (buff)
    BUILDINGS = {
        "logging_camp": {"type": "generator", "output": "timber", "base_rate": 0.2},
        "quarry": {"type": "generator", "output": "stone", "base_rate": 0.2},
        "market": {
            "type": "generator",
            "output": "market_gold",
            "base_rate": 50,
        },  # 50 gold (currency) per worker/hr
        "foundry": {
            "type": "converter",
            "map": [
                ("iron_ore", "iron_bar"),
                ("coal_ore", "steel_bar"),
                ("gold_ore", "gold_bar"),
                ("platinum_ore", "platinum_bar"),
                ("idea_ore", "idea_bar"),
            ],
            "base_rate": 1,  # 5 conversions per worker/hr
        },
        "sawmill": {
            "type": "converter",
            "map": [
                ("oak_logs", "oak_plank"),
                ("willow_logs", "willow_plank"),
                ("mahogany_logs", "mahogany_plank"),
                ("magic_logs", "magic_plank"),
                ("idea_logs", "idea_plank"),
            ],
            "base_rate": 1,
        },
        "reliquary": {
            "type": "converter",
            "map": [
                ("desiccated_bones", "desiccated_essence"),
                ("regular_bones", "regular_essence"),
                ("sturdy_bones", "sturdy_essence"),
                ("reinforced_bones", "reinforced_essence"),
                ("titanium_bones", "titanium_essence"),
            ],
            "base_rate": 1,
        },
        "barracks": {"type": "passive", "effect": "combat_stats"},
        "temple": {"type": "passive", "effect": "propagate_bonus"},
        "town_hall": {"type": "core", "effect": "caps"},
        "apothecary": {"type": "passive", "effect": "potion_buff"},
        # Type 'special' means it has no passive production, handled via custom View
        "black_market": {"type": "special", "effect": "trading"},
        # Generates 'companion_cookie' which is auto-converted to XP on collect
        "companion_ranch": {
            "type": "generator",
            "output": "companion_cookie",
            "base_rate": 0.1,
        },  # 0.1 XP per worker/hr
        "hatchery": {"type": "special", "effect": "egg_incubation"},
        "war_camp": {
            "type": "generator",
            "output": "war_camp_stamina",
            "base_rate": 0.004167,
        },  # ~10 stamina per 24h at 100 workers; ~5h at 500 workers (tier NOT used)
        "celestial_shrine": {"type": "passive", "effect": "sigil_bonus"},
        "infernal_shrine": {"type": "passive", "effect": "infernal_sigil_bonus"},
        "void_shrine": {"type": "passive", "effect": "void_shard_bonus"},
        "twin_shrine": {"type": "passive", "effect": "gemini_sigil_bonus"},
        "corruption_shrine": {"type": "passive", "effect": "corruption_sigil_bonus"},
        # Consolidated uber shrine — replaces the five individual shrines.
        # Internal per-statue worker allocation stored as JSON in building data.
        "uber_shrine": {"type": "special", "effect": "all_sigil_bonus"},
        # New turn-based buildings
        "nursery": {"type": "special", "effect": "worker_production"},
        "idlem_foundry": {"type": "special", "effect": "idlem_production"},
        "sanctum": {"type": "passive", "effect": "kill_convert"},
    }

    @staticmethod
    def get_max_workers(tier: int) -> int:
        """Higher tier buildings can hold more workers (base formula, no bonuses)."""
        return 100 * tier

    @staticmethod
    def calculate_adjacency_bonuses(
        plots: list[Plot],
        buildings: list[Building],
    ) -> dict[int, dict]:
        """
        Computes per-plot adjacency bonuses contributed by active meta buildings.

        All meta buildings are passive (no workers required) and apply flat effects.

        Returns a dict mapping plot_index → {
            "production_mult":    float,  # Servant's Quarters (+20%) + Foreman's Post (+25%) on generators
            "converter_mult":     float,  # Supply Depot (+15%) + Foreman's Post (+25%) on converters
            "flat_stamina_per_hr": float, # Encampment flat +0.5 stamina/hr added to adjacent War Camp
            "shrine_cap_x2":      bool,   # Grand Cathedral doubles shrine worker cap
            "has_watchtower":     bool,   # Watchtower is globally present (any plot)
            "shrine_boost":       float,  # Shrine Garden +15% mult for shrine buildings
            "apothecary_boost":   float,  # Apothecary Annex +40% to flat heal
        }
        Only plots that have a building in *buildings* appear in the result.
        """
        plot_by_idx: dict[int, Plot] = {
            p.plot_index: p for p in plots if p.is_developed
        }

        # Global effect: Watchtower (passive, applies settlement-wide)
        has_watchtower = any(
            b.is_meta and b.building_type == "watchtower" and b.plot_index is not None
            for b in buildings
        )

        # Initialise a result entry for every building that has a plot.
        # Meta buildings are excluded from the Watchtower global cap.
        result: dict[int, dict] = {}
        for b in buildings:
            if b.plot_index is not None:
                result[b.plot_index] = {
                    "production_mult": 0.0,
                    "converter_mult": 0.0,
                    "flat_stamina_per_hr": 0.0,
                    "shrine_cap_x2": False,
                    "has_watchtower": has_watchtower and not b.is_meta,
                    "shrine_boost": 0.0,
                    "apothecary_boost": 0.0,
                }

        # Build a quick lookup so we can skip meta-building targets below.
        building_by_plot: dict[int, "Building"] = {
            b.plot_index: b for b in buildings if b.plot_index is not None
        }

        # Process each active meta building and apply its adjacency bonus.
        # Rule: meta buildings never affect other meta buildings.
        # All meta buildings are now passive — no staffing requirement.
        for meta_b in buildings:
            if not meta_b.is_meta or meta_b.plot_index is None:
                continue

            meta_type = meta_b.building_type
            plot_of_meta = plot_by_idx.get(meta_b.plot_index)

            # Ley Line: if the meta building's own plot has this bonus,
            # amplify every adjacency contribution by ×1.5 (additive 50%).
            ley_amp = (
                1.5 if (plot_of_meta and plot_of_meta.bonus_type == "ley_line") else 1.0
            )

            for adj_idx in get_adjacent_plot_indices(meta_b.plot_index):
                if adj_idx == 0 or adj_idx not in result:
                    continue  # TH or plot without a building

                # Meta buildings do not receive bonuses from other meta buildings
                adj_b = building_by_plot.get(adj_idx)
                if adj_b and adj_b.is_meta:
                    continue

                if meta_type == "servants_quarters":
                    result[adj_idx]["production_mult"] += 0.20 * ley_amp

                elif meta_type == "supply_depot":
                    result[adj_idx]["converter_mult"] += 0.15 * ley_amp

                elif meta_type == "grand_cathedral":
                    result[adj_idx]["shrine_cap_x2"] = True

                elif meta_type == "encampment":
                    result[adj_idx]["flat_stamina_per_hr"] += 0.5 * ley_amp

                elif meta_type == "shrine_garden":
                    result[adj_idx]["shrine_boost"] += 0.15 * ley_amp

                elif meta_type == "foremans_post":
                    result[adj_idx]["production_mult"] += 0.25 * ley_amp
                    result[adj_idx]["converter_mult"] += 0.25 * ley_amp

                elif meta_type == "apothecary_annex":
                    result[adj_idx]["apothecary_boost"] += 0.40 * ley_amp

        return result

    @staticmethod
    def calculate_production(
        building_type: str,
        tier: int,
        workers: int,
        hours_elapsed: float,
        raw_inventory: Dict[str, int] = None,
        plot_bonus_type: str | None = None,
        adj_production_mult: float = 0.0,
        adj_converter_mult: float = 0.0,
        adj_output_mult: float = 0.0,
        mastery_converter_output_mult: float = 0.0,  # From Master Quarry / Seasoned Timber
        event_generator_bonus: float = 0.0,  # From active settlement events (e.g. resource_windfall)
        event_converter_bonus: float = 0.0,  # From active settlement events (e.g. artisan_week)
    ) -> Dict[str, int]:
        """
        Calculates production for a specific building over time.
        Returns dict of changes: {'iron': -100, 'iron_bar': 100, 'timber': 50}

        Plot / adjacency bonus parameters (all additive, stacking):
          plot_bonus_type     — the roll assigned to the building's plot
          adj_production_mult — from adjacent Servant's Quarters (+20%) / Foreman's Post (+25%) on generators
          adj_converter_mult  — from adjacent Supply Depot (+15%) / Foreman's Post (+25%) on converters
          adj_output_mult     — reserved for future use
          mastery_converter_output_mult — +10% from Master Quarry / Seasoned Timber synergy nodes
        Note: Encampment flat stamina bonus (+0.5/hr) is applied by the caller after this function.
        """
        if workers <= 0 or hours_elapsed <= 0:
            return {}

        b_data = SettlementMechanics.BUILDINGS.get(building_type)
        if not b_data:
            return {}

        # Safely fetch base_rate. If 0 (passives/special), it produces nothing.
        base_rate = b_data.get("base_rate", 0)
        if base_rate == 0:
            return {}

        # --- Effectiveness multiplier (additive bonuses stacked together) ---
        effectiveness = 1.0
        btype = b_data["type"]

        if plot_bonus_type:
            bonus_data = PLOT_BONUS_TABLE.get(plot_bonus_type, {})
            applies_to = bonus_data.get("applies_to", "none")
            val = bonus_data.get("value", 0.0)
            if applies_to == "generator_mult" and btype == "generator":
                effectiveness += val
            elif applies_to == "converter_mult" and btype == "converter":
                effectiveness += val
            elif applies_to == "trade_mult" and building_type in ("market", "war_camp"):
                effectiveness += val

        if btype == "generator":
            effectiveness += adj_production_mult
            effectiveness += event_generator_bonus
        elif btype == "converter":
            effectiveness += adj_converter_mult
            effectiveness += event_converter_bonus

        changes = {}

        # War camp scales by workers only (no tier factor) to avoid 25× runaway scaling.
        # All other generators use the standard tier × workers formula.
        if building_type == "war_camp":
            production_raw = base_rate * workers * hours_elapsed * effectiveness
        else:
            production_raw = base_rate * tier * workers * hours_elapsed * effectiveness
        production_capacity = int(production_raw)

        if b_data["type"] == "generator":
            output_key = b_data["output"]
            if output_key == "war_camp_stamina":
                # Keep float precision; int-conversion and cap applied at collection time
                changes[output_key] = round(production_raw, 4)
            else:
                changes[output_key] = production_capacity

        elif b_data["type"] == "converter" and raw_inventory:
            # Each building tier unlocks the corresponding material slot:
            #   T1 → slot 0 only, T2 → slots 0-1, T3 → slots 0-2, etc.
            # All unlocked slots are processed simultaneously from independent
            # capacity pools — higher-tier (rarer) materials receive a smaller
            # weighted fraction of the total capacity.
            #
            # Weights descend from `tier` down to 1 (slot 0 is heaviest):
            #   T1: [1]          → 100% to slot 0
            #   T2: [2, 1]       → 67% / 33%
            #   T3: [3, 2, 1]    → 50% / 33% / 17%
            #   T4: [4, 3, 2, 1] → 40% / 30% / 20% / 10%
            #   T5: [5,4,3,2,1]  → 33% / 27% / 20% / 13% / 7%
            active_map = b_data["map"][:tier]
            n = len(active_map)
            weights = list(range(n, 0, -1))  # [n, n-1, ..., 1]
            total_weight = n * (n + 1) // 2  # = sum(weights)

            for i, (raw_key, refined_key) in enumerate(active_map):
                if raw_key not in raw_inventory or raw_inventory[raw_key] <= 0:
                    continue
                slot_capacity = int(production_capacity * weights[i] / total_weight)
                amount_to_convert = min(raw_inventory[raw_key], slot_capacity)
                if amount_to_convert > 0:
                    output_amount = amount_to_convert
                    if mastery_converter_output_mult > 0:
                        output_amount = int(
                            amount_to_convert * (1.0 + mastery_converter_output_mult)
                        )

                    changes[raw_key] = changes.get(raw_key, 0) - amount_to_convert
                    changes[refined_key] = changes.get(refined_key, 0) + output_amount

        return changes

    @staticmethod
    def get_converter_rates(
        building_type: str, tier: int, workers: int
    ) -> list[tuple[str, str, int]]:
        """
        Returns the per-hour processing rate for each material slot that is active
        at the given building tier, as a list of (raw_key, refined_key, rate_per_hr).

        Used by the detail view to display live rates without duplicating the
        capacity-weighting logic from calculate_production.
        """
        b_data = SettlementMechanics.BUILDINGS.get(building_type)
        if not b_data or b_data.get("type") != "converter":
            return []

        base_rate = b_data.get("base_rate", 1)
        active_map = b_data["map"][:tier]
        n = len(active_map)
        if n == 0:
            return []

        total_per_hr = base_rate * tier * workers
        weights = list(range(n, 0, -1))
        total_weight = n * (n + 1) // 2

        return [
            (raw_key, refined_key, int(total_per_hr * weights[i] / total_weight))
            for i, (raw_key, refined_key) in enumerate(active_map)
        ]

    @staticmethod
    def get_multiplier(tier: int) -> float:
        """Black Market tier bonus multiplier."""
        if tier == 1:
            return 1.0
        if tier == 2:
            return 1.2
        if tier == 3:
            return 1.3
        if tier == 4:
            return 1.4
        if tier == 5:
            return 1.5
        return 1.0

    @staticmethod
    def get_upgrade_cost(building_type: str, current_tier: int) -> dict:
        """Unified upgrade cost calculator for ALL building types."""
        target_tier = current_tier + 1

        def _round_to_thousand(n: int) -> int:
            """Round to nearest 1,000 (standard rounding)."""
            return round(n / 1000) * 1000

        # 1a. Uber Shrine building: mirrors Town Hall upgrade costs exactly
        if building_type == "uber_shrine":
            base = 20_000
            base_gold = 500_000
            cost = {
                "timber": _round_to_thousand(int(base * (target_tier**1.5))),
                "stone": _round_to_thousand(int(base * (target_tier**1.5))),
                "gold": _round_to_thousand(int(base_gold * (target_tier**1.5))),
            }
            qty = target_tier - 1  # T2=1, T3=2, T4=3, T5=4
            cost["specials"] = [
                {"key": "magma_core", "name": "Magma Core", "qty": qty},
                {"key": "life_root", "name": "Life Root", "qty": qty},
                {"key": "spirit_shard", "name": "Spirit Shard", "qty": qty},
            ]
            return cost

        # 1. Uber buildings (flat high cost)
        if building_type in UBER_BUILDINGS:
            cost = {
                "timber": _round_to_thousand(target_tier * 20_000),
                "stone": _round_to_thousand(target_tier * 20_000),
                "gold": _round_to_thousand(target_tier * 10_000_000),
            }
            special_col = SPECIAL_MAP.get(building_type)
            if special_col:
                cost.update(
                    {
                        "special_key": special_col,
                        "special_name": ITEM_NAMES.get(special_col, "Special Material"),
                        "special_qty": target_tier - 1,
                    }
                )
            return cost

        # 2. Black Market (original formula)
        if building_type == "black_market":
            base_wood = base_stone = 20_000
            base_gold = 1000000
            cost = {
                "timber": _round_to_thousand(int(base_wood * (target_tier**1.5))),
                "stone": _round_to_thousand(int(base_stone * (target_tier**1.5))),
                "gold": _round_to_thousand(int(base_gold * (target_tier**1.5))),
            }
            # NEW: Every upgrade requires ALL THREE special materials
            qty = target_tier - 1  # T2=1, T3=2, ...
            cost["specials"] = [
                {"key": "magma_core", "name": "Magma Core", "qty": qty},
                {"key": "life_root", "name": "Life Root", "qty": qty},
                {"key": "spirit_shard", "name": "Spirit Shard", "qty": qty},
            ]
            return cost

        # 3. Town Hall (now up to Tier 7 with all three specials)
        if building_type == "town_hall":
            base = 20_000
            base_gold = 500_000
            cost = {
                "timber": _round_to_thousand(int(base * (target_tier**1.5))),
                "stone": _round_to_thousand(int(base * (target_tier**1.5))),
                "gold": _round_to_thousand(int(base_gold * (target_tier**1.5))),
            }

            # Every Town Hall upgrade requires all three special materials
            qty = target_tier - 1  # T2=1, T3=2, ..., T7=6
            cost["specials"] = [
                {"key": "magma_core", "name": "Magma Core", "qty": qty},
                {"key": "life_root", "name": "Life Root", "qty": qty},
                {"key": "spirit_shard", "name": "Spirit Shard", "qty": qty},
            ]
            return cost

        # 4. Standard buildings
        base_wood = 500
        base_stone = 500
        base_gold = 50000
        cost = {
            "timber": _round_to_thousand(int(base_wood * (target_tier**1.5))),
            "stone": _round_to_thousand(int(base_stone * (target_tier**1.5))),
            "gold": _round_to_thousand(int(base_gold * (target_tier**2))),
        }

        if target_tier >= 3:
            special_col = SPECIAL_MAP.get(building_type, "magma_core")
            cost.update(
                {
                    "special_key": special_col,
                    "special_name": ITEM_NAMES.get(special_col, "Special Material"),
                    "special_qty": target_tier - 2,  # T3=1, T4=2, T5=3
                }
            )
        return cost


# ---------------------------------------------------------------------------
# Resource category sets — which DB table owns each BM-tradeable resource key.
# ---------------------------------------------------------------------------

_SETTLEMENT_RESOURCE_KEYS: frozenset[str] = frozenset(["timber", "stone"])
_SETTLEMENT_MATERIAL_KEYS: frozenset[str] = frozenset(
    [
        "magma_core",
        "life_root",
        "spirit_shard",
        "celestial_stone",
        "infernal_cinder",
        "void_crystal",
        "bound_crystal",
        "diviners_rod",
        "unidentified_blueprint",
    ]
)
_SKILL_RESOURCE_KEYS: frozenset[str] = frozenset(
    [
        "iron_ore", "coal_ore", "gold_ore", "platinum_ore", "idea_ore",
        "iron_bar", "steel_bar", "gold_bar", "platinum_bar", "idea_bar",
        "oak_logs", "willow_logs", "mahogany_logs", "magic_logs", "idea_logs",
        "oak_plank", "willow_plank", "mahogany_plank", "magic_plank", "idea_plank",
        "desiccated_bones", "regular_bones", "sturdy_bones", "reinforced_bones", "titanium_bones",
        "desiccated_essence", "regular_essence", "sturdy_essence", "reinforced_essence", "titanium_essence",
    ]
)


# ---------------------------------------------------------------------------
# Async service methods — orchestration called by view button handlers.
# Views remain responsible for interaction responses and local state caching.
# ---------------------------------------------------------------------------


async def collect_settlement_resources(bot, uid: str, sid: str, settlement, plots: list) -> dict:
    """
    Calculates passive building production, commits it to the database, and
    returns a result dict for the view to render.

    Result keys (always present):
      too_early  – bool: < 0.1 h elapsed; nothing committed
      has_output – bool: any resources were produced
      hours      – float

    Additional keys when has_output is True:
      display_changes    – dict (display-ready keys including renamed specials)
      cookie_xp          – int
      war_camp_stamina   – int (capped at 10)
      market_gold        – int
      dc_earned          – int
      collection_time    – ISO string stamped after commit
    """
    from datetime import datetime

    from core.settlement.constants import SETTLEMENT_EVENTS
    from core.skills.mastery import has_master_quarry, has_seasoned_timber

    mining = await bot.database.skills.get_data(uid, sid, "mining")
    wood = await bot.database.skills.get_data(uid, sid, "woodcutting")
    fish = await bot.database.skills.get_data(uid, sid, "fishing")

    mastery_row = await bot.database.skills.get_mastery(uid, sid)
    refining_bonus = 0.0
    if mastery_row:
        if has_master_quarry(mastery_row):
            refining_bonus += 0.10
        if has_seasoned_timber(mastery_row):
            refining_bonus += 0.10

    raw_inv: dict = {
        "iron_ore": mining["iron_ore"], "coal_ore": mining["coal_ore"],
        "gold_ore": mining["gold_ore"], "platinum_ore": mining["platinum_ore"],
        "idea_ore": mining["idea_ore"],
        "oak_logs": wood["oak_logs"], "willow_logs": wood["willow_logs"],
        "mahogany_logs": wood["mahogany_logs"], "magic_logs": wood["magic_logs"],
        "idea_logs": wood["idea_logs"],
        "desiccated_bones": fish["desiccated_bones"], "regular_bones": fish["regular_bones"],
        "sturdy_bones": fish["sturdy_bones"], "reinforced_bones": fish["reinforced_bones"],
        "titanium_bones": fish["titanium_bones"],
    }

    now = datetime.now()
    last = datetime.fromisoformat(settlement.last_collection_time)
    hours = max(0.0, (now - last).total_seconds() / 3600)

    if hours < 0.1:
        return {"too_early": True, "has_output": False, "hours": hours}

    adj_bonuses = SettlementMechanics.calculate_adjacency_bonuses(plots, settlement.buildings)
    plot_by_idx = {p.plot_index: p for p in plots}

    active_evs = await bot.database.settlement.get_active_events(uid, sid)
    event_gen_bonus = 0.0
    event_conv_bonus = 0.0
    event_market_gold_bonus = 0.0
    for ev in active_evs:
        ev_def = SETTLEMENT_EVENTS.get(ev.get("event_key", ""), {})
        ev_data = ev.get("data", {})
        effs = ev_def.get("effects", {})

        def _rb(v, _d=ev_data):
            if v == "band":
                return _d.get("band", 0.0)
            if v == "neg_band":
                return -_d.get("band", 0.0)
            return v if isinstance(v, (int, float)) else 0.0

        if "generator_bonus" in effs:
            event_gen_bonus += _rb(effs["generator_bonus"])
        if "converter_bonus" in effs:
            event_conv_bonus += _rb(effs["converter_bonus"])
        if "market_gold_bonus" in effs:
            event_market_gold_bonus += _rb(effs["market_gold_bonus"])

    total_changes: dict[str, float] = {}
    for b in settlement.buildings:
        if b.is_disabled:
            continue
        plot = plot_by_idx.get(b.plot_index) if b.plot_index is not None else None
        plot_bonus = plot.bonus_type if plot else None
        adj = adj_bonuses.get(b.plot_index, {}) if b.plot_index is not None else {}

        changes = SettlementMechanics.calculate_production(
            building_type=b.building_type,
            tier=b.tier,
            workers=b.workers_assigned,
            hours_elapsed=hours,
            raw_inventory=raw_inv,
            plot_bonus_type=plot_bonus,
            adj_production_mult=adj.get("production_mult", 0.0),
            adj_converter_mult=adj.get("converter_mult", 0.0),
            mastery_converter_output_mult=refining_bonus,
            event_generator_bonus=event_gen_bonus,
            event_converter_bonus=event_conv_bonus,
        )
        for k, v in changes.items():
            total_changes[k] = total_changes.get(k, 0) + v
            if k in raw_inv:
                raw_inv[k] = raw_inv[k] + v  # type: ignore[assignment]

        if b.building_type == "war_camp" and b.workers_assigned > 0:
            flat_stamina = adj.get("flat_stamina_per_hr", 0.0) * hours
            if flat_stamina > 0:
                total_changes["war_camp_stamina"] = (
                    total_changes.get("war_camp_stamina", 0) + flat_stamina
                )

    expedition_count = sum(
        1 for p in plots if p.is_developed and p.bonus_type == "expedition_camp"
    )
    dc_earned = int(hours / 48) * expedition_count

    if not any(v > 0 for v in total_changes.values()) and dc_earned == 0:
        return {"too_early": False, "has_output": False, "hours": hours}

    display_changes: dict = dict(total_changes)

    cookie_xp = 0
    if "companion_cookie" in total_changes:
        cookie_xp = int(total_changes.pop("companion_cookie"))
        display_changes["Companion XP"] = display_changes.pop("companion_cookie", cookie_xp)

    war_camp_stamina = 0
    if "war_camp_stamina" in total_changes:
        war_camp_stamina = min(10, int(float(total_changes.pop("war_camp_stamina"))))
        display_changes.pop("war_camp_stamina", None)

    market_gold = 0
    if "market_gold" in total_changes:
        market_gold = int(total_changes.pop("market_gold"))
        if event_market_gold_bonus:
            market_gold = max(0, int(market_gold * (1 + event_market_gold_bonus)))
        display_changes["Market Gold"] = display_changes.pop("market_gold", market_gold)

    await bot.database.settlement.commit_production(uid, sid, total_changes)
    if market_gold > 0:
        await bot.database.users.modify_gold(uid, market_gold)
    if war_camp_stamina > 0:
        await bot.database.users.add_stamina_capped(uid, war_camp_stamina)
    if dc_earned > 0:
        await bot.database.settlement.modify_development_contracts(uid, sid, dc_earned)
    await bot.database.settlement.update_collection_timer(uid, sid)
    if cookie_xp > 0:
        await bot.database.users.modify_currency(uid, "companion_pet_xp", cookie_xp)

    return {
        "too_early": False,
        "has_output": True,
        "hours": hours,
        "display_changes": display_changes,
        "cookie_xp": cookie_xp,
        "war_camp_stamina": war_camp_stamina,
        "market_gold": market_gold,
        "dc_earned": dc_earned,
        "collection_time": now.isoformat(),
    }


async def execute_building_upgrade(bot, uid: str, sid: str, building, cost: dict) -> dict:
    """
    Deducts upgrade costs, queues the upgrade project, and reloads settlement
    state. The caller is responsible for pre-validating resource availability.

    Returns {"settlement": Settlement, "projects": list, "dt_cost": int}
    """
    from core.settlement.constants import SETTLEMENT_EVENTS
    from core.settlement.turn_engine import upgrade_dt_cost

    active_evs = await bot.database.settlement.get_active_events(uid, sid)
    event_effects: dict = {}
    for ev in active_evs:
        if ev["event_type"] == "ongoing":
            ev_def = SETTLEMENT_EVENTS.get(ev["event_key"], {})
            ev_data = ev.get("data") or {}
            for _k, _v in ev_def.get("effects", {}).items():
                if _v == "band":
                    _v = ev_data.get("band", 0)
                elif _v == "neg_band":
                    _v = -ev_data.get("band", 0)
                event_effects[_k] = _v

    changes = {"timber": -cost.get("timber", 0), "stone": -cost.get("stone", 0)}
    await bot.database.settlement.commit_production(uid, sid, changes)
    await bot.database.users.modify_gold(uid, -cost.get("gold", 0))

    if "specials" in cost:
        for s in cost["specials"]:
            await bot.database.settlement_materials.modify(uid, s["key"], -s["qty"])
    elif "special_key" in cost:
        await bot.database.settlement_materials.modify(
            uid, cost["special_key"], -cost["special_qty"]
        )

    target_tier = building.tier + 1
    dt_cost = upgrade_dt_cost(building.building_type, target_tier, event_effects)
    await bot.database.settlement.upsert_project(
        user_id=uid,
        server_id=sid,
        project_type="upgrade",
        target_id=building.id,
        required_turns=dt_cost,
        data={"building_type": building.building_type},
    )

    projects = await bot.database.settlement.get_projects(uid, sid)
    settlement = await bot.database.settlement.get_settlement(uid, sid)
    return {"settlement": settlement, "projects": projects, "dt_cost": dt_cost}


async def execute_diviners_rod(
    bot, uid: str, sid: str, plot_index: int, old_bonus: str | None
) -> dict:
    """
    Consumes one Diviner's Rod, rolls a new terrain bonus, and commits the
    result. Reloads and returns updated Plot objects.

    Returns {"changed": bool, "new_bonus": str, "plots": list[Plot]}
    """
    from core.settlement.models import Plot
    from core.settlement.plots import roll_plot_bonus

    new_bonus = roll_plot_bonus()
    await bot.database.settlement_materials.modify(uid, "diviners_rod", -1)

    if new_bonus != old_bonus:
        await bot.database.plots.reroll_bonus(uid, sid, plot_index, new_bonus)

    plot_rows = await bot.database.plots.get_plots(uid, sid)
    plots = [
        Plot(
            plot_index=r["plot_index"],
            is_developed=bool(r["is_developed"]),
            bonus_type=r["bonus_type"],
        )
        for r in plot_rows
    ]
    return {"changed": new_bonus != old_bonus, "new_bonus": new_bonus, "plots": plots}


async def execute_bm_offer(
    bot,
    uid: str,
    sid: str,
    offer: dict,
    active_biases: list,
    building_tier: int,
) -> dict:
    """
    Deducts offered resources, calculates offer value (with event bonuses),
    and either completes the deal instantly or creates a pending deal.

    The caller is responsible for live inventory validation before this call.

    Returns one of:
      {"error": "no_value"}
      {"instant": True,  "value": int, "raw_value": int, "turns": 0, "rewards": dict}
      {"instant": False, "value": int, "raw_value": int, "turns": int}
    """
    from core.settlement.constants import SETTLEMENT_EVENTS
    from core.settlement.turn_engine import (
        calculate_offer_value,
        complete_bm_deal_instant,
        compute_processing_turns,
    )
    from core.settlement.bm_log import BMLogger

    settlement_changes: dict = {}
    user_currency_changes: dict = {}
    for res, qty in offer.items():
        if res in _SETTLEMENT_RESOURCE_KEYS or res in _SKILL_RESOURCE_KEYS:
            settlement_changes[res] = settlement_changes.get(res, 0) - qty
        else:
            user_currency_changes[res] = user_currency_changes.get(res, 0) - qty

    if settlement_changes:
        await bot.database.settlement.commit_production(uid, sid, settlement_changes)
    for cur, delta in user_currency_changes.items():
        try:
            if cur in _SETTLEMENT_MATERIAL_KEYS:
                await bot.database.settlement_materials.modify(uid, cur, delta)
            else:
                await bot.database.users.modify_currency(uid, cur, delta)
        except Exception:
            pass

    tree_nodes = await bot.database.settlement.get_bm_tree(uid, sid)

    active_events = await bot.database.settlement.get_active_events(uid, sid)
    event_value_bonus = 0.0
    for ev in active_events:
        if ev["event_type"] == "ongoing":
            ev_def = SETTLEMENT_EVENTS.get(ev["event_key"], {})
            raw_val = ev_def.get("effects", {}).get("bm_value_bonus", 0.0)
            ev_data = ev.get("data") or {}
            if raw_val == "band":
                raw_val = ev_data.get("band", 0.0)
            elif raw_val == "neg_band":
                raw_val = -ev_data.get("band", 0.0)
            if isinstance(raw_val, (int, float)):
                event_value_bonus += raw_val

    raw_value = calculate_offer_value(offer, tree_nodes, building_tier)
    raw_value = int(raw_value * (1 + event_value_bonus))
    value = raw_value // 100
    turns = compute_processing_turns(value, building_tier, tree_nodes)

    bm_submit_log = BMLogger(uid, value, turns)
    bm_submit_log.log_offer(offer, raw_value, event_value_bonus)
    bm_submit_log.log_tree(tree_nodes, active_biases)
    bm_submit_log.close()

    if value <= 0:
        return {"error": "no_value"}

    if turns == 0:
        user_row = await bot.database.users.get(uid, sid)
        player_level = user_row["level"] if user_row else 1
        rewards = await complete_bm_deal_instant(
            bot, uid, sid, value, active_biases, player_level, tree_nodes
        )
        return {
            "instant": True,
            "value": value,
            "raw_value": raw_value,
            "turns": 0,
            "rewards": rewards,
        }

    turns_data = await bot.database.settlement.get_turns_data(uid, sid)
    current_turn = turns_data.get("total_development_turns", 0)
    await bot.database.settlement.create_pending_deal(
        uid, sid,
        offer_data=offer,
        total_value=value,
        turns_required=turns,
        active_biases=active_biases,
        current_turn=current_turn,
    )
    return {"instant": False, "value": value, "raw_value": raw_value, "turns": turns}
