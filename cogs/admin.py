import asyncio
import collections
import os

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from core.combat.economy.victory import apply_victory_rewards
from core.combat.mobgen.gen_mob import generate_encounter
from core.items.factory import load_player
from core.models import Monster
from database.backup import create_backup, list_backups

_MAX_COUNT = 200
_BACKUP_RETENTION_COUNT = 28


class Admin(commands.Cog, name="admin"):
    def __init__(self, bot) -> None:
        self.bot = bot

    def _is_admin(self, user_id: str) -> bool:
        admin_ids = [str(x) for x in self.bot.config.get("admin_user_ids", [])]
        return user_id in admin_ids

    @app_commands.command(
        name="sim_combat",
        description="[Admin] Simulate N combat victories and apply all rewards silently.",
    )
    @app_commands.describe(count="Number of combats to simulate (1–200, default 50)")
    async def sim_combat(self, interaction: Interaction, count: int = 50) -> None:
        user_id = str(interaction.user.id)
        server_id = str(interaction.guild_id)

        if not self._is_admin(user_id):
            return await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )

        count = max(1, min(count, _MAX_COUNT))

        # One API call — required by Discord's 3-second interaction window.
        await interaction.response.defer(ephemeral=True)

        # Fix 8: block if the target user already has an interactive session open.
        # Running apply_victory_rewards 200× while combat is active causes
        # application-level lost-update races on the same DB rows.
        if self.bot.state_manager.is_active(user_id):
            return await interaction.followup.send(
                "Cannot simulate while you have an active session. Close it first.",
                ephemeral=True,
            )

        user_row = await self.bot.database.users.get(user_id, server_id)
        if not user_row:
            return await interaction.followup.send("No character found.")

        player = await load_player(user_id, user_row, self.bot.database)

        slayer_tree_data = await self.bot.database.slayer.get_tree(user_id, server_id)
        player.slayer_tree_nodes = slayer_tree_data["nodes_owned"]
        task_species = getattr(player, "active_task_species", None)

        level_start = player.level
        asc_start = player.ascension

        # Aggregators
        total_gold = 0
        total_xp = 0
        item_slots: collections.Counter = collections.Counter()
        special_drops: collections.Counter = collections.Counter()
        body_parts = 0
        eggs: collections.Counter = collections.Counter()
        companions_gained = 0
        dust_total = 0

        for _ in range(count):
            monster = await generate_encounter(
                player,
                Monster(
                    name="",
                    level=0,
                    hp=0,
                    max_hp=0,
                    xp=0,
                    attack=0,
                    defence=0,
                    modifiers=[],
                    image="",
                    flavor="",
                ),
                is_treasure=False,
                task_species=task_species,
                slayer_tree_nodes=player.slayer_tree_nodes,
            )

            reward_data = await apply_victory_rewards(
                self.bot,
                user_id,
                server_id,
                player,
                monster,
                message=None,
                combat_logger=None,
            )

            total_gold += reward_data.get("gold", 0)
            total_xp += reward_data.get("xp", 0)

            # Gear drops — use the rolls dict so we get the slot even when inventory was full.
            rolls = reward_data.get("rolls", {})
            if rolls.get("gear_hit") and reward_data.get("items"):
                slot = rolls.get("item_slot", "unknown")
                item_slots[slot] += 1

            for drop in reward_data.get("special", []):
                special_drops[drop] += 1

            if reward_data.get("body_part"):
                body_parts += 1

            if reward_data.get("egg"):
                eggs[reward_data["egg"]] += 1

            if reward_data.get("consolation_dust"):
                dust_total += reward_data["consolation_dust"]

            for msg in reward_data.get("msgs", []):
                if "joined your roster" in msg:
                    companions_gained += 1

        # Fix 6: one write after the loop instead of N writes inside it.
        # apply_victory_rewards already persists gold; this persists level/asc/exp/hp.
        await self.bot.database.users.update_from_player_object(player)

        # --- Build summary embed (single Discord API call) ---
        levels_gained = player.level - level_start
        asc_gained = player.ascension - asc_start

        embed = discord.Embed(
            title=f"Combat Simulation — {count} Fight{'s' if count != 1 else ''}",
            color=discord.Color.gold(),
        )

        core_lines = [
            f"**Gold:** {total_gold:,}",
            f"**XP:** {total_xp:,}",
        ]
        if levels_gained:
            core_lines.append(f"**Level-ups:** {levels_gained} → now Level {player.level}")
        if asc_gained:
            core_lines.append(f"**Ascensions:** {asc_gained} → Ascension {player.ascension}")
        embed.add_field(name="Core Rewards", value="\n".join(core_lines), inline=False)

        # Gear drops
        items_total = sum(item_slots.values())
        if items_total:
            slot_lines = [f"{n}x {s.capitalize()}" for s, n in item_slots.most_common()]
            embed.add_field(
                name=f"Gear Drops ({items_total})",
                value="\n".join(slot_lines),
                inline=True,
            )
        else:
            embed.add_field(name="Gear Drops", value="None", inline=True)

        # Special drops — cap display at 15 unique entries to avoid embed overflow
        if special_drops:
            top = special_drops.most_common(15)
            lines = [f"{n}x {k}" for k, n in top]
            if len(special_drops) > 15:
                lines.append(f"*(+{len(special_drops) - 15} more types)*")
            embed.add_field(name="Special Drops", value="\n".join(lines), inline=True)
        else:
            embed.add_field(name="Special Drops", value="None", inline=True)

        # Misc
        misc_lines = []
        if body_parts:
            misc_lines.append(f"**{body_parts}** body part(s)")
        for tier, n in eggs.most_common():
            misc_lines.append(f"**{n}** {tier} egg(s)")
        if companions_gained:
            misc_lines.append(f"**{companions_gained}** companion(s) tamed")
        if dust_total:
            misc_lines.append(f"**{dust_total:,}** cosmic dust")
        if misc_lines:
            embed.add_field(name="Misc", value="\n".join(misc_lines), inline=False)

        embed.set_footer(
            text=f"Level {player.level} | Ascension {player.ascension} | All rewards applied to DB"
        )

        # One API call — the result.
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="db_backup",
        description="[Admin] Create an on-demand database backup for rollback safety.",
    )
    async def db_backup(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        if not self._is_admin(user_id):
            return await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)
        root = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))
        db_path = f"{root}/database/database.db"
        backup_dir = f"{root}/database/backups"
        path = await asyncio.to_thread(
            create_backup, db_path, backup_dir, _BACKUP_RETENTION_COUNT
        )
        size_mb = os.path.getsize(path) / (1024 * 1024)
        total = len(list_backups(backup_dir))
        await interaction.followup.send(
            f"Backup created: `{os.path.basename(path)}` ({size_mb:.1f} MB). "
            f"{total} backup(s) retained (cap {_BACKUP_RETENTION_COUNT}).",
            ephemeral=True,
        )

    @app_commands.command(
        name="db_backups",
        description="[Admin] List available database backups.",
    )
    async def db_backups(self, interaction: Interaction) -> None:
        user_id = str(interaction.user.id)
        if not self._is_admin(user_id):
            return await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )

        root = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))
        backup_dir = f"{root}/database/backups"
        backups = list_backups(backup_dir)
        if not backups:
            return await interaction.response.send_message(
                "No backups found yet.", ephemeral=True
            )

        lines = []
        for name in backups[-15:]:
            size_mb = os.path.getsize(os.path.join(backup_dir, name)) / (1024 * 1024)
            lines.append(f"`{name}` — {size_mb:.1f} MB")
        embed = discord.Embed(
            title="Database Backups",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"{len(backups)} total backup(s) on disk")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(Admin(bot))
