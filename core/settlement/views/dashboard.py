# core/settlement/views/dashboard.py
import asyncio
from datetime import datetime

import discord
from discord import ButtonStyle, Interaction, SelectOption, ui

from core.companions.mechanics import CompanionMechanics
from core.images import SETTLEMENT_BUILDINGS
from core.settlement.constants import BUILDING_INFO, RESOURCE_DISPLAY_NAMES
from core.settlement.mechanics import SettlementMechanics
from core.settlement.views.black_market import BlackMarketView
from core.settlement.views.construction import BuildConstructionView
from core.settlement.views.detail import BuildingDetailView
from core.settlement.views.town_hall import TownHallView

from .base import SettlementBaseView


class SettlementDashboardView(SettlementBaseView):
    def __init__(self, bot, user_id, server_id, settlement, follower_count: int):
        super().__init__(bot, user_id)
        self.server_id = server_id
        self.settlement = settlement
        self.follower_count = follower_count
        self.update_grid()

    RESOURCE_DISPLAY_NAMES = RESOURCE_DISPLAY_NAMES  # from constants

    def _format_changes(self, changes: dict) -> str:
        positive_items = []
        for key, value in changes.items():
            if value <= 0:
                continue
            name = self.RESOURCE_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            emoji = ""
            if key == "timber":
                emoji = "🪵 "
            elif key == "stone":
                emoji = "🪨 "
            elif key == "gold":
                emoji = "💰 "
            positive_items.append(f"{emoji}{name}: +{value:,}")

        if not positive_items:
            return "No resources produced (no workers, generators, or raw materials)."

        return "\n".join(positive_items)

    async def on_timeout(self):
        self.bot.state_manager.clear_active(self.user_id)
        try:
            expired_embed = discord.Embed(
                title="Settlement Session Expired",
                description="This settlement management session has timed out.\n\n"
                "Run the command again to reopen the dashboard.",
                color=discord.Color.dark_grey(),
            )
            await self.message.edit(embed=expired_embed, view=None)
        except:
            pass

    def build_embed(self) -> discord.Embed:
        workers_used = sum(b.workers_assigned for b in self.settlement.buildings)

        embed = discord.Embed(title="Town Hall", color=discord.Color.dark_green())
        embed.description = (
            f"**Tier {self.settlement.town_hall_tier}** Settlement\n"
            f"👥 **Workforce:** {workers_used}/{self.follower_count}\n"
            f"🪵 **Timber:** {self.settlement.timber:,}\n"
            f"🪨 **Stone:** {self.settlement.stone:,}"
        )
        embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["town_hall"])

        if self.settlement.buildings:
            lines = []
            for b in self.settlement.buildings:
                status = "🟢" if b.workers_assigned > 0 else "🔴"
                if b.name == "Black Market":
                    status = "⚫"
                lines.append(f"• **{b.name}** (T{b.tier}) {status}")
            embed.add_field(name="Buildings", value="\n".join(lines), inline=False)
        else:
            embed.add_field(
                name="Buildings", value="No buildings constructed yet.", inline=False
            )

        return embed

    def update_grid(self):
        self.clear_items()

        built_map = {b.slot_index: b for b in self.settlement.buildings}

        # Row 0 — Select dropdown
        options = []
        for i in range(self.settlement.building_slots):
            if i in built_map:
                b = built_map[i]
                status = "🟢" if b.workers_assigned > 0 else "🔴"
                if b.name == "Black Market":
                    status = "⚫"
                options.append(
                    SelectOption(
                        label=f"{b.name} (T{b.tier})",
                        value=f"built_{i}",
                        description=f"Workers: {b.workers_assigned} | Status: {status}",
                        emoji=status,
                    )
                )
            else:
                options.append(
                    SelectOption(
                        label=f"Slot {i+1} — Empty",
                        value=f"empty_{i}",
                        description="Click to construct a new building",
                        emoji="🔨",
                    )
                )

        if options:
            select = ui.Select(
                placeholder="Select a building to manage...",
                options=options,
                row=0,
            )

            async def _on_select(interaction: Interaction, s=select):
                value = s.values[0]
                if value.startswith("built_"):
                    slot = int(value.split("_")[1])
                    await self.open_building(interaction, built_map[slot])
                else:
                    slot = int(value.split("_")[1])
                    await self.open_build_menu(interaction, slot)

            select.callback = _on_select
            self.add_item(select)

        # Row 1 — Controls
        th_btn = ui.Button(
            label=f"Town Hall (T{self.settlement.town_hall_tier})",
            style=ButtonStyle.primary,
            row=1,
            emoji="🏛️",
        )
        th_btn.callback = self.open_town_hall
        self.add_item(th_btn)

        collect_btn = ui.Button(
            label="Collect", style=ButtonStyle.success, row=1, emoji="🚜"
        )
        collect_btn.callback = self.collect_resources
        self.add_item(collect_btn)

        guide_btn = ui.Button(
            label="Guide", style=ButtonStyle.secondary, row=1, emoji="📖"
        )
        guide_btn.callback = self.show_guide
        self.add_item(guide_btn)

        close_btn = ui.Button(label="Close", style=ButtonStyle.danger, row=1)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

    async def show_guide(self, interaction: Interaction):
        embed = discord.Embed(title="📖 Building Guide", color=discord.Color.blue())
        for btype, info in BUILDING_INFO.items():  # from constants
            embed.add_field(
                name=btype.replace("_", " ").title(),
                value=info,
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def open_town_hall(self, interaction: Interaction):
        view = TownHallView(self.bot, self.user_id, self.settlement, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_build_menu(self, interaction: Interaction, slot_index: int):
        uber_prog = await self.bot.database.uber.get_uber_progress(
            self.user_id, self.server_id
        )
        view = BuildConstructionView(
            self.bot, self.user_id, slot_index, self, uber_prog
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def open_building(self, interaction: Interaction, building):
        if building.building_type == "black_market":
            view = BlackMarketView(self.bot, self.user_id, self, building)
        else:
            view = BuildingDetailView(self.bot, self.user_id, building, self)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def collect_resources(self, interaction: Interaction):
        await interaction.response.defer()

        uid, sid = self.user_id, self.server_id

        # 1. Fetch inventory for limiting logic
        mining = await self.bot.database.skills.get_data(uid, sid, "mining")
        wood = await self.bot.database.skills.get_data(uid, sid, "woodcutting")
        fish = await self.bot.database.skills.get_data(uid, sid, "fishing")

        raw_inv = {
            "iron": mining[3],
            "coal": mining[4],
            "gold": mining[5],
            "platinum": mining[6],
            "idea": mining[7],
            "oak_logs": wood[3],
            "willow_logs": wood[4],
            "mahogany_logs": wood[5],
            "magic_logs": wood[6],
            "idea_logs": wood[7],
            "desiccated_bones": fish[3],
            "regular_bones": fish[4],
            "sturdy_bones": fish[5],
            "reinforced_bones": fish[6],
            "titanium_bones": fish[7],
        }

        # 2. Calculate time elapsed
        now = datetime.now()
        last = datetime.fromisoformat(self.settlement.last_collection_time)
        hours = (now - last).total_seconds() / 3600

        if hours < 0.1:  # Minimum 6 minutes
            return await interaction.followup.send(
                "Your workers haven't generated anything yet.", ephemeral=True
            )

        # 3. Calculate changes
        total_changes: dict[str, int] = {}
        for b in self.settlement.buildings:
            changes = SettlementMechanics.calculate_production(
                b.building_type, b.tier, b.workers_assigned, hours, raw_inv
            )
            for k, v in changes.items():
                total_changes[k] = total_changes.get(k, 0) + v
                if k in raw_inv:
                    raw_inv[k] += v

        print("DEBUG total_changes AFTER MERGE:", total_changes)

        # Make a copy specifically for display (so you can filter it safely)
        display_changes = dict(total_changes)

        cookie_xp = 0
        if "companion_cookie" in total_changes:
            cookies = total_changes.pop("companion_cookie")
            cookie_xp = cookies

            if "companion_cookie" in display_changes:
                display_changes["Companion XP"] = display_changes.pop(
                    "companion_cookie"
                )

        # Pop market gold before committing to skill tables (it belongs in users.gold)
        market_gold = 0
        if "market_gold" in total_changes:
            market_gold = total_changes.pop("market_gold")
            display_changes["Market Gold"] = display_changes.pop(
                "market_gold", market_gold
            )

        # 4. Commit to DB with the full changes
        await self.bot.database.settlement.commit_production(uid, sid, total_changes)
        if market_gold > 0:
            await self.bot.database.users.modify_gold(uid, market_gold)
        await self.bot.database.settlement.update_collection_timer(uid, sid)

        # Commit companion XP
        xp_msg = ""
        if cookie_xp > 0:
            active_rows = await self.bot.database.companions.get_active(self.user_id)
            if active_rows:
                xp_per_pet = cookie_xp // len(active_rows)
                for row in active_rows:
                    comp_id, cur_lvl, cur_exp = row[0], row[5], row[6]

                    # Add XP
                    cur_exp += xp_per_pet
                    # Level logic
                    while cur_lvl < 100:
                        req = CompanionMechanics.calculate_next_level_xp(cur_lvl)
                        if cur_exp >= req:
                            cur_exp -= req
                            cur_lvl += 1
                        else:
                            break
                    await self.bot.database.companions.update_stats(
                        comp_id, cur_lvl, cur_exp
                    )

                xp_msg = f"\n🐾 **Companion Ranch:** Distributed {cookie_xp:,} XP among active pets."

        # 5. Update local settlement state
        self.settlement.timber += display_changes.get("timber", 0)
        self.settlement.stone += display_changes.get("stone", 0)
        self.settlement.last_collection_time = now.isoformat()

        # 6. Build updated embed
        embed = self.build_embed()

        # 7. Use display_changes for the Last Collection field
        formatted_changes = self._format_changes(display_changes) + xp_msg
        embed.add_field(
            name="Last Collection",
            value=(
                f"⏱️ Time since last collection: {hours:.2f} hours\n\n"
                f"📦 Yield:\n{formatted_changes}"
            ),
            inline=False,
        )

        # 8. Content message depending on whether anything positive was produced
        has_positive = any(v > 0 for v in display_changes.values())
        if has_positive:
            content = "✅ **Collection Complete**"
        else:
            content = "ℹ️ Collection complete, but no resources were produced."

        await interaction.edit_original_response(embed=embed, view=self)
        await asyncio.sleep(1.0)

    async def close_view(self, interaction: Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.bot.state_manager.clear_active(self.user_id)
        self.stop()
