from __future__ import annotations

import random
from datetime import datetime, timezone

from core.base_view import BaseView
from core.models import Partner
from core.partners.dispatch import calculate_rewards, calculate_sigmund_rewards
from core.partners.mechanics import grant_xp as _grant_xp

# ---------------------------------------------------------------------------
# Dispatch item routing constants
# ---------------------------------------------------------------------------

_MINING_ITEMS = frozenset({"iron", "coal", "gold", "platinum", "idea"})
_WOODCUTTING_ITEMS = frozenset(
    {"oak_logs", "willow_logs", "mahogany_logs", "magic_logs", "idea_logs"}
)
_FISHING_ITEMS = frozenset(
    {
        "desiccated_bones",
        "regular_bones",
        "sturdy_bones",
        "reinforced_bones",
        "titanium_bones",
    }
)
_GATHERING_ITEMS = _MINING_ITEMS | _WOODCUTTING_ITEMS | _FISHING_ITEMS

_RUNE_CURRENCY_MAP = {
    "refinement_rune": "refinement_runes",
    "potential_rune": "potential_runes",
    "shatter_rune": "shatter_runes",
}
_BOSS_KEY_TYPES = {
    "draconic_key": "dragon_key",
    "angelic_key": "angel_key",
    "soul_core": "soul_cores",
    "void_frag": "void_frags",
    "balance_fragment": "balance_fragment",
}

_TASK_LABELS = {"combat": "⚔️ Combat", "gathering": "⛏️ Gathering"}


# ---------------------------------------------------------------------------
# Base class for all partner views — deletes message on timeout
# ---------------------------------------------------------------------------


class PartnerBaseView(BaseView):
    async def on_timeout(self):
        if self.user_id:
            self.bot.state_manager.clear_active(self.user_id)
        if self.message:
            try:
                await self.message.delete()
            except Exception:
                pass
        self.stop()


# ---------------------------------------------------------------------------
# Shared dispatch reward applicator
# ---------------------------------------------------------------------------


async def _apply_dispatch_rewards(
    bot, user_id: str, server_id: str, partner: Partner
) -> list:
    """Apply all dispatch reward DB side-effects. Returns a list of result lines."""
    is_sigmund = (
        partner.sig_combat_key == "sig_co_sigmund"
        and partner.sig_dispatch_lvl >= 1
        and partner.dispatch_task_2 is not None
    )
    if is_sigmund:
        result = calculate_sigmund_rewards(partner)
    else:
        result = calculate_rewards(partner, partner.dispatch_start_time or "")

    gold = result.get("gold", 0)
    exp = result.get("exp", 0)
    rolls = result.get("rolls", 0)
    items_got = result.get("items", {})

    if gold > 0:
        await bot.database.users.modify_gold(user_id, gold)
    if exp > 0:
        new_level, new_exp, _ = _grant_xp(partner.level, partner.exp, exp)
        partner.level = new_level
        partner.exp = new_exp
        await bot.database.partners.update_exp(
            user_id, partner.partner_id, new_exp, new_level
        )

    if items_got:
        mining_batch: dict = {}
        woodcutting_batch: dict = {}
        fishing_batch: dict = {}

        for item_key, qty in items_got.items():
            if item_key in _MINING_ITEMS:
                mining_batch[item_key] = mining_batch.get(item_key, 0) + qty
            elif item_key in _WOODCUTTING_ITEMS:
                woodcutting_batch[item_key] = woodcutting_batch.get(item_key, 0) + qty
            elif item_key in _FISHING_ITEMS:
                fishing_batch[item_key] = fishing_batch.get(item_key, 0) + qty
            elif item_key in ("magma_core", "life_root", "spirit_shard"):
                await bot.database.users.modify_currency(user_id, item_key, qty)
            elif item_key == "celestial_sigils":
                await bot.database.uber.increment_sigils(user_id, server_id, qty)
            elif item_key == "infernal_sigils":
                await bot.database.uber.increment_infernal_sigils(
                    user_id, server_id, qty
                )
            elif item_key == "void_shards":
                await bot.database.uber.increment_void_shards(user_id, server_id, qty)
            elif item_key == "gemini_sigils":
                await bot.database.uber.increment_gemini_sigils(user_id, server_id, qty)
            elif item_key == "boss_key":
                for _ in range(qty):
                    for key_type in _BOSS_KEY_TYPES:
                        if random.random() < 0.20:
                            await bot.database.users.modify_currency(
                                user_id, _BOSS_KEY_TYPES[key_type], 1
                            )
            elif item_key in _RUNE_CURRENCY_MAP:
                await bot.database.users.modify_currency(
                    user_id, _RUNE_CURRENCY_MAP[item_key], qty
                )
            elif item_key == "guild_ticket":
                await bot.database.partners.add_tickets(user_id, qty)
            elif item_key in ("antique_tome", "pinnacle_key"):
                await bot.database.users.modify_currency(user_id, item_key, qty)
            elif item_key == "blessed_bismuth":
                await bot.database.uber.increment_blessed_bismuth(
                    user_id, server_id, qty
                )
            elif item_key == "sparkling_sprig":
                await bot.database.uber.increment_sparkling_sprig(
                    user_id, server_id, qty
                )
            elif item_key == "capricious_carp":
                await bot.database.uber.increment_capricious_carp(
                    user_id, server_id, qty
                )
            elif item_key == "spirit_stone":
                await bot.database.users.modify_currency(user_id, "spirit_stones", qty)
            elif item_key == "essence":
                from database.repositories.essences import (
                    COMMON_ESSENCE_TYPES,
                    RARE_ESSENCE_TYPES,
                )

                pool = list(COMMON_ESSENCE_TYPES) + list(RARE_ESSENCE_TYPES)
                for _ in range(qty):
                    await bot.database.essences.add(user_id, random.choice(pool), 1)
            elif item_key == "slayer_drop":
                try:
                    await bot.database.slayer.add_rewards(user_id, server_id, 0, qty)
                except Exception:
                    pass

        if mining_batch:
            try:
                await bot.database.skills.update_batch(
                    user_id, server_id, "mining", mining_batch
                )
            except Exception:
                pass
        if woodcutting_batch:
            try:
                await bot.database.skills.update_batch(
                    user_id, server_id, "woodcutting", woodcutting_batch
                )
            except Exception:
                pass
        if fishing_batch:
            try:
                await bot.database.skills.update_batch(
                    user_id, server_id, "fishing", fishing_batch
                )
            except Exception:
                pass

    now_str = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    await bot.database.partners.reset_dispatch_timer(
        user_id, partner.partner_id, now_str
    )
    if is_sigmund:
        await bot.database.partners.reset_dispatch_timer_2(
            user_id, partner.partner_id, now_str
        )

    lines = []
    if gold:
        lines.append(f"💰 **{gold:,}** gold")
    if exp:
        lines.append(f"📚 **{exp:,}** Partner EXP")
    for item_key, qty in items_got.items():
        lines.append(f"📦 {qty}× **{item_key.replace('_', ' ').title()}**")
    return lines
