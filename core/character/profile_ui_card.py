"""
core/character/profile_ui_card.py
Embed builders for the card and cooldowns tabs of the Profile Hub.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import discord

from core.items.factory import load_player


class CardProfileBuilder:
    """Embed builders for the card and cooldowns profile tabs."""

    @staticmethod
    async def build_card(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        followers = await bot.database.social.get_follower_count(user["ideology"])

        embed = discord.Embed(title="Adventurer License", color=discord.Color.gold())
        embed.set_thumbnail(url=user["appearance"])

        embed.add_field(name="Name", value=f"**{user['name']}**", inline=True)
        embed.add_field(
            name="Level", value=f"{user['level']} (Ascension {user['ascension']})", inline=True
        )
        _lvl, _exp = user["level"], user["experience"]
        try:
            _exp_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "assets", "exp.json"
            )
            with open(_exp_path, encoding="utf-8") as _f:
                _exp_table = json.load(_f)["levels"]
            _needed = _exp_table.get(str(_lvl), 0)
            if _lvl >= 100 or _needed <= 0:
                _exp_str = f"{_exp:,} *(MAX)*"
            else:
                _pct = min(99.9, _exp / _needed * 100)
                _exp_str = f"{_exp:,} / {_needed:,}\n*({_pct:.1f}% to Lv.{_lvl + 1})*"
        except Exception:
            _exp_str = f"{_exp:,}"
        embed.add_field(name="Experience", value=_exp_str, inline=True)

        embed.add_field(name="Ideology", value=f"{user['ideology']}", inline=True)
        embed.add_field(name="Followers", value=f"{followers:,}", inline=True)
        embed.add_field(name="Gold", value=f"{user['gold']:,} 💰", inline=True)

        return embed

    @staticmethod
    async def build_cooldowns(bot, user_id: str, server_id: str) -> discord.Embed:
        user = await bot.database.users.get(user_id, server_id)
        p = await load_player(user_id, user, bot.database)

        embed = discord.Embed(title="Active Timers & Cooldowns", color=0xBEBEFE)
        embed.set_thumbnail(url=user["appearance"])

        player_level = user["level"]

        def _fmt_ms(time_str, cooldown_td: timedelta) -> str:
            if not time_str:
                return "Ready!"
            try:
                total = int(
                    (
                        cooldown_td
                        - (datetime.now() - datetime.fromisoformat(time_str))
                    ).total_seconds()
                )
                if total <= 0:
                    return "Ready!"
                m = total // 60
                return f"{m}m"
            except Exception:
                return "Ready!"

        def _fmt_hms(time_str, cooldown_td: timedelta) -> str:
            if not time_str:
                return "Ready!"
            try:
                total = int(
                    (
                        cooldown_td
                        - (datetime.now() - datetime.fromisoformat(time_str))
                    ).total_seconds()
                )
                if total <= 0:
                    return "Ready!"
                h, r = divmod(total, 3600)
                m = r // 60
                return f"{h}h {m:02d}m"
            except Exception:
                return "Ready!"

        def _secs_to_hm(secs: int) -> str:
            h, r = divmod(max(0, secs), 3600)
            m = r // 60
            return f"{h}h {m:02d}m"

        # ── Combat ───────────────────────────────────────────────────────────
        combat_lines = []

        # Stamina
        MAX_STAMINA = 10
        stamina_data = await bot.database.users.get_stamina(user_id)
        stamina = stamina_data["combat_stamina"]
        last_regen_str = stamina_data["last_stamina_regen"]

        if stamina >= MAX_STAMINA:
            combat_lines.append(f"⚡ **Stamina** — {stamina}/{MAX_STAMINA} (full)")
        else:
            regen_suffix = ""
            if last_regen_str:
                try:
                    next_regen = datetime.fromisoformat(last_regen_str) + timedelta(
                        hours=1
                    )
                    rem_secs = int((next_regen - datetime.now()).total_seconds())
                    if rem_secs > 0:
                        regen_suffix = f" · next in {rem_secs // 60}m"
                except Exception:
                    pass
            combat_cd_mins = 10
            if p.equipped_boot and p.equipped_boot.passive == "speedster":
                combat_cd_mins -= p.equipped_boot.passive_lvl
            cd_str = _fmt_ms(user["last_combat"], timedelta(minutes=combat_cd_mins))
            combat_lines.append(
                f"⚡ **Stamina** — {stamina}/{MAX_STAMINA}{regen_suffix}"
            )
            if stamina == 0:
                combat_lines.append(f"  ↳ Cooldown: {cd_str}")

        # Rest
        combat_lines.append(f"🛏️ **Rest** — {_fmt_hms(user['last_rest_time'], timedelta(hours=2))}")

        # Maw
        try:
            from core.maw.mechanics import (
                MAX_FIGHTS_PER_CYCLE,
                fight_available,
                fight_remaining_seconds,
                get_current_cycle_id,
                is_cycle_active,
            )

            now_utc = datetime.now(timezone.utc)
            now_ts = int(now_utc.timestamp())
            maw_cycle_id = get_current_cycle_id(now_utc)

            if player_level >= 20:
                if is_cycle_active(maw_cycle_id, now_ts):
                    maw_record = await bot.database.maw.get_record(
                        user_id, maw_cycle_id
                    )
                    if maw_record:
                        fights_done = maw_record["fights_this_cycle"]
                        last_fight_ts = maw_record["last_fight_ts"]
                        fights_left = max(0, MAX_FIGHTS_PER_CYCLE - fights_done)
                        if fights_done >= MAX_FIGHTS_PER_CYCLE:
                            maw_str = f"All fights used (0/{MAX_FIGHTS_PER_CYCLE} left)"
                        elif fight_available(last_fight_ts, fights_done, now_ts):
                            maw_str = (
                                f"Ready! ({fights_left}/{MAX_FIGHTS_PER_CYCLE} left)"
                            )
                        else:
                            maw_str = (
                                f"{_secs_to_hm(fight_remaining_seconds(last_fight_ts, now_ts))}"
                                f" ({fights_left}/{MAX_FIGHTS_PER_CYCLE} left)"
                            )
                    else:
                        maw_str = f"Not participated · {MAX_FIGHTS_PER_CYCLE} fights available"
                else:
                    maw_str = "No active cycle"
                combat_lines.append(f"🌑 **Maw** — {maw_str}")
        except Exception:
            pass

        # Hatchery
        try:
            incubation = await bot.database.eggs.get_incubation(user_id, server_id)
            if incubation:
                start_dt = datetime.fromisoformat(incubation["start_time"])
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                duration = incubation["duration_seconds"]
                elapsed_secs = (datetime.now(timezone.utc) - start_dt).total_seconds()
                remaining = max(0.0, duration - elapsed_secs)
                if remaining > 0:
                    rh, r = divmod(int(remaining), 3600)
                    rm = r // 60
                    pct = int(min(100, elapsed_secs / max(duration, 1) * 100))
                    combat_lines.append(
                        f"🥚 **Hatchery** — {incubation['monster_name']}: {rh}h {rm:02d}m ({pct}%)"
                    )
                else:
                    combat_lines.append(
                        f"🥚 **Hatchery** — {incubation['monster_name']}: Ready to hatch!"
                    )
        except Exception:
            pass

        # Apex Hunts
        if player_level >= 90:
            try:
                from core.apex.mechanics import MAX_CHARGES, ApexMechanics
                from core.apex.models import profile_from_db

                apex_row = await bot.database.apex.get_or_create_profile(
                    user_id, server_id
                )
                apex_profile = profile_from_db(apex_row)
                charges, _ = ApexMechanics.calculate_charges(apex_profile)
                if charges >= MAX_CHARGES:
                    apex_str = f"{charges}/{MAX_CHARGES} (full)"
                else:
                    next_secs = ApexMechanics.seconds_until_next_charge(apex_profile)
                    rh, r = divmod(next_secs, 3600)
                    rm = r // 60
                    apex_str = f"{charges}/{MAX_CHARGES} · next in {rh}h {rm:02d}m"
                combat_lines.append(f"🏹 **Apex Hunts** — {apex_str}")
            except Exception:
                pass

        embed.add_field(name="Combat", value="\n".join(combat_lines), inline=False)

        # ── Daily ─────────────────────────────────────────────────────────────
        daily_lines = []

        quest_meta: dict = {}
        try:
            await bot.database.quests.ensure_meta(user_id)
            quest_meta = await bot.database.quests.get_meta(user_id)
        except Exception:
            pass
        checkin_last = quest_meta.get("checkin_last_time") if quest_meta else None

        if player_level >= 10:
            daily_lines.append(
                f"🛖 **Check-in** — {_fmt_hms(checkin_last, timedelta(hours=18))}"
            )

        # Quest Board
        try:
            from core.quests.mechanics import get_board_cooldown_remaining

            all_contracts = await bot.database.quests.get_contracts(user_id, server_id)
            if all_contracts:
                latest = max(
                    all_contracts, key=lambda c: c.get("locked_at", ""), default=None
                )
                if latest and latest.get("locked_at"):
                    rem = get_board_cooldown_remaining(latest["locked_at"])
                    if rem.total_seconds() > 0:
                        rh, rr = divmod(int(rem.total_seconds()), 3600)
                        rm = rr // 60
                        board_str = f"{rh}h {rm:02d}m"
                    else:
                        board_str = "Ready!"
                else:
                    board_str = "Ready!"
            else:
                board_str = "Ready!"
            daily_lines.append(f"📋 **Quest Board** — {board_str}")
        except Exception:
            pass

        if daily_lines:
            embed.add_field(name="Daily", value="\n".join(daily_lines), inline=False)

        # ── Settlement ────────────────────────────────────────────────────────
        settlement_lines = []

        if player_level >= 10:
            try:
                settlement = await bot.database.settlement.get_settlement(
                    user_id, server_id
                )
                if settlement:
                    # Production
                    if settlement.last_collection_time:
                        s_last = datetime.fromisoformat(settlement.last_collection_time)
                        blocks = max(
                            0, int((datetime.now() - s_last).total_seconds() // 3600)
                        )
                        settlement_lines.append(
                            f"🏭 **Production** — {blocks} block(s) of production completed"
                        )

                    # Zeal
                    try:
                        from core.settlement.constants import (
                            PASSIVE_ZEAL_PER_HOUR_BASE,
                            ZEAL_GATHER_CAP,
                        )
                        from core.settlement.turn_engine import passive_zeal_for_period

                        turns_data = await bot.database.settlement.get_turns_data(
                            user_id, server_id
                        )
                        pending_zeal = turns_data.get("pending_zeal", 0)
                        tier = settlement.town_hall_tier
                        rate = PASSIVE_ZEAL_PER_HOUR_BASE + (tier - 1) * 9
                        _gather_ts = (
                            settlement.last_zeal_gather_time
                            or settlement.last_collection_time
                        )
                        _time_based = 0
                        if _gather_ts:
                            _hours = (
                                datetime.now() - datetime.fromisoformat(_gather_ts)
                            ).total_seconds() / 3600
                            _time_based = passive_zeal_for_period(_hours, tier)
                        available = min(pending_zeal + _time_based, ZEAL_GATHER_CAP)
                        hours_to_cap = max(0.0, (ZEAL_GATHER_CAP - available) / rate)
                        if available >= ZEAL_GATHER_CAP:
                            zeal_str = (
                                f"**{available}/{ZEAL_GATHER_CAP}** — ready to collect!"
                            )
                        elif hours_to_cap < 1.0:
                            zeal_str = f"**{available}/{ZEAL_GATHER_CAP}** — cap in <1h"
                        else:
                            h = int(hours_to_cap)
                            zeal_str = (
                                f"**{available}/{ZEAL_GATHER_CAP}** — cap in ~{h}h"
                            )
                        settlement_lines.append(f"🔥 **Zeal** — {zeal_str}")
                    except Exception:
                        pass

                    # Development Contracts
                    try:
                        dc_crafted_today = (
                            await bot.database.settlement.get_dc_crafted_today(
                                user_id, server_id
                            )
                        )
                        _dc_now = datetime.now()
                        _next_midnight = _dc_now.replace(
                            hour=0, minute=0, second=0, microsecond=0
                        ) + timedelta(days=1)
                        _dc_secs = int((_next_midnight - _dc_now).total_seconds())
                        _dch, _dcr = divmod(_dc_secs, 3600)
                        _dcm = _dcr // 60
                        _dc_remaining = max(0, 10 - dc_crafted_today)
                        settlement_lines.append(
                            f"📜 **DCs** — {_dc_remaining}/10 remaining · resets in {_dch}h {_dcm:02d}m"
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        # Propagate
        settlement_lines.append(
            f"💡 **Propagate** — {_fmt_hms(user['last_propagate_time'], timedelta(hours=18))}"
        )

        embed.add_field(
            name="Settlement", value="\n".join(settlement_lines), inline=False
        )

        # ── Partners & Companions ─────────────────────────────────────────────
        pc_lines = []

        if player_level >= 10:
            try:
                from core.models import Partner
                from core.partners.data import PARTNER_DATA
                from core.partners.dispatch import (
                    BOSS_PARTY_DURATION_HOURS,
                    elapsed_hours,
                    get_cap_hours,
                )

                rows = await bot.database.partners.get_owned(user_id)
                all_partners = [
                    Partner.from_row(row, PARTNER_DATA[row["partner_id"]])
                    for row in rows
                    if row["partner_id"] in PARTNER_DATA
                ]

                active_dispatch = next(
                    (
                        partner
                        for partner in all_partners
                        if partner.is_dispatched
                        and partner.dispatch_task
                        and partner.dispatch_task != "boss_party"
                    ),
                    None,
                )
                boss_party = [
                    partner
                    for partner in all_partners
                    if partner.dispatch_task == "boss_party"
                    and (partner.is_dispatched or partner.dispatch_start_time)
                ]

                # Partner
                if active_dispatch:
                    elapsed = elapsed_hours(active_dispatch.dispatch_start_time)
                    cap = get_cap_hours(active_dispatch)
                    elapsed_h = min(int(cap), int(elapsed))
                    task_label = (active_dispatch.dispatch_task or "unknown").title()
                    if elapsed >= cap:
                        pc_lines.append(
                            f"📋 **Partner** — {int(cap)}/{int(cap)} hours of {task_label} completed (ready!)"
                        )
                    else:
                        pc_lines.append(
                            f"📋 **Partner** — {elapsed_h}/{int(cap)} hours of {task_label} completed"
                        )
                else:
                    pc_lines.append("📋 **Partner** — No partner dispatched")

                # Boss Raid
                if boss_party:
                    bp_elapsed = elapsed_hours(boss_party[0].dispatch_start_time)
                    bp_cap = int(BOSS_PARTY_DURATION_HOURS)
                    bp_done = min(bp_cap, int(bp_elapsed))
                    if bp_done >= bp_cap:
                        pc_lines.append(
                            f"🔱 **Boss Raid** — {bp_cap}/{bp_cap} hours completed (ready!)"
                        )
                    else:
                        pc_lines.append(
                            f"🔱 **Boss Raid** — {bp_done}/{bp_cap} hours completed"
                        )
            except Exception:
                pass

        # Companions
        if player_level >= 40:
            try:
                active_comps = await bot.database.companions.get_active(user_id)
                if not active_comps:
                    pc_lines.append("🐾 **Companions** — No companions deployed")
                else:
                    c_time_str = await bot.database.users.get_companion_collect_time(
                        user_id
                    )
                    if c_time_str:
                        c_diff = (
                            datetime.now() - datetime.fromisoformat(c_time_str)
                        ).total_seconds()
                        cycles = min(48, int(c_diff // 3600))
                        if cycles >= 48:
                            pc_lines.append(
                                "🐾 **Companions** — 48/48 adventures (ready to collect!)"
                            )
                        else:
                            pc_lines.append(
                                f"🐾 **Companions** — {cycles}/48 adventures completed"
                            )
                    else:
                        pc_lines.append("🐾 **Companions** — Ready to deploy")
            except Exception:
                pass

        if pc_lines:
            embed.add_field(
                name="Partners & Companions", value="\n".join(pc_lines), inline=False
            )

        # ── Gathering (contextual — only when gate is active) ─────────────────
        try:
            from core.skills.mechanics import SkillMechanics

            _skill_cfg = {
                "mining": ("⛏️", "Mining", "pickaxe_tier"),
                "fishing": ("🎣", "Fishing", "fishing_rod"),
                "woodcutting": ("🪓", "Woodcutting", "axe_type"),
            }
            gathering_lines: list[str] = []
            for sk, (emo, label, tool_col) in _skill_cfg.items():
                fam_end, mom = await bot.database.skills.get_familiarization_state(
                    user_id, server_id, sk
                )
                remaining = SkillMechanics.get_familiarization_remaining_seconds(
                    fam_end, mom
                )
                if remaining > 0:
                    skill_data = await bot.database.skills.get_data(
                        user_id, server_id, sk
                    )
                    if skill_data and skill_data[tool_col] >= 5:
                        continue
                    gh, gr = divmod(remaining // 60, 60)
                    gathering_lines.append(
                        f"{emo} **{label}** — Familiarizing: {gh}h {gr:02d}m"
                    )
                elif fam_end:
                    skill_data = await bot.database.skills.get_data(
                        user_id, server_id, sk
                    )
                    if skill_data and skill_data[tool_col] >= 5:
                        continue
                    gathering_lines.append(
                        f"{emo} **{label}** — ✅ Tool tier familiarized"
                    )

            if gathering_lines:
                embed.add_field(
                    name="Gathering", value="\n".join(gathering_lines), inline=False
                )
        except Exception:
            pass

        return embed
