# core/settlement/views/town_hall.py
import discord
from discord import ButtonStyle, Interaction, ui

from core.images import SETTLEMENT_BUILDINGS
from core.settlement.mechanics import SettlementMechanics

from .base import SettlementBaseView


class TownHallView(SettlementBaseView):
    def __init__(self, bot, user_id, settlement, parent_view):
        super().__init__(bot, user_id)
        self.settlement = settlement
        self.parent = parent_view
        self.setup_ui()

    async def on_timeout(self):
        try:
            expired_embed = discord.Embed(
                title="Town Hall Session Expired",
                description="This Town Hall management session has timed out.\n\n"
                "Reopen your settlement dashboard to manage it again.",
                color=discord.Color.dark_grey(),
            )
            await self.parent.message.edit(embed=expired_embed, view=None)
        except:
            pass
        finally:
            self.stop()

    def build_embed(self):
        tier = self.settlement.town_hall_tier
        slots = self.settlement.building_slots

        next_slots = slots + 1

        desc = (
            f"**Level:** {tier}/7\n"
            f"**Building Slots:** {slots}\n"
            f"**Follower Cap Buff:** +{tier * 10}%\n"
        )

        embed = discord.Embed(
            title="🏛️ Town Hall", description=desc, color=discord.Color.dark_blue()
        )

        if tier < 7:
            costs = self._get_upgrade_cost(tier + 1)
            cost_str = (
                f"🪵 {costs['timber']:,} | 🪨 {costs['stone']:,} | 💰 {costs['gold']:,}"
            )

            if "specials" in costs:
                reqs = [f"{s['name']} x{s['qty']}" for s in costs["specials"]]
                cost_str += f"\n✨ **Requires:** {', '.join(reqs)}"

            embed.add_field(
                name="Upgrade Benefits",
                value=f"Slots: {slots} ➡️ **{next_slots}**",
                inline=False,
            )
            embed.add_field(name="Upgrade Cost", value=cost_str, inline=False)
        else:
            embed.add_field(
                name="Status", value="🌟 Maximum Tier Reached", inline=False
            )
        embed.set_thumbnail(url=SETTLEMENT_BUILDINGS["town_hall"])
        return embed

    def _get_upgrade_cost(self, target_tier):
        return SettlementMechanics.get_upgrade_cost("town_hall", target_tier - 1)

    def setup_ui(self):
        self.clear_items()

        btn_up = ui.Button(
            label="Upgrade Hall",
            style=ButtonStyle.success,
            emoji="⬆️",
            disabled=(self.settlement.town_hall_tier >= 7),
        )
        btn_up.callback = self.upgrade
        self.add_item(btn_up)

        btn_back = ui.Button(label="Back", style=ButtonStyle.secondary)
        btn_back.callback = self.go_back
        self.add_item(btn_back)

    async def upgrade(self, interaction: Interaction):
        target_tier = self.settlement.town_hall_tier + 1
        costs = self._get_upgrade_cost(target_tier)

        # 1. Check Resources
        if (
            self.settlement.timber < costs["timber"]
            or self.settlement.stone < costs["stone"]
        ):
            return await interaction.response.send_message(
                "Insufficient Timber or Stone!", ephemeral=True
            )

        gold = await self.bot.database.users.get_gold(self.user_id)
        if gold < costs["gold"]:
            return await interaction.response.send_message(
                "Insufficient Gold!", ephemeral=True
            )

        # 2. Check multiple special materials safely
        if "specials" in costs:
            # Validate ALL balances before deducting any to prevent partial consumption on failure
            for sp in costs["specials"]:
                async with self.bot.database.connection.execute(
                    f"SELECT {sp['key']} FROM users WHERE user_id = ?", (self.user_id,)
                ) as c:
                    owned = (await c.fetchone())[0]

                if owned < sp["qty"]:
                    return await interaction.response.send_message(
                        f"Need {sp['qty']}x {sp['name']}! (You have {owned})",
                        ephemeral=True,
                    )

            # If all checks pass, deduct them
            for sp in costs["specials"]:
                await self.bot.database.users.modify_currency(
                    self.user_id, sp["key"], -sp["qty"]
                )

        await interaction.response.defer()

        # 3. Consume Resources
        changes = {
            "timber": -costs["timber"],
            "stone": -costs["stone"],
        }
        await self.bot.database.settlement.commit_production(
            self.user_id, self.parent.server_id, changes
        )
        await self.bot.database.users.modify_gold(self.user_id, -costs["gold"])

        # 4. Update DB (Settlements Table)
        await self.bot.database.connection.execute(
            """UPDATE settlements 
               SET town_hall_tier = town_hall_tier + 1, 
                   building_slots = building_slots + 1 
               WHERE user_id = ? AND server_id = ?""",
            (self.user_id, self.parent.server_id),
        )
        await self.bot.database.connection.commit()

        # 5. Update Local State & Refresh
        self.settlement.town_hall_tier += 1
        self.settlement.building_slots += 1
        self.settlement.timber -= costs["timber"]
        self.settlement.stone -= costs["stone"]
        self.setup_ui()
        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def go_back(self, interaction: Interaction):
        self.parent.update_grid()
        await interaction.response.edit_message(
            embed=self.parent.build_embed(), view=self.parent
        )
        self.stop()
