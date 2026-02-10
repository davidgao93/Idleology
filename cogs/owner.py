import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context
import sys
import importlib

class Owner(commands.Cog, name="owner"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.command(
        name="sync",
        description="Synchonizes the slash commands.",
    )
    @app_commands.describe(scope="The scope of the sync. Can be `global` or `guild`")
    @commands.is_owner()
    async def sync(self, context: Context, scope: str) -> None:
        """
        Synchonizes the slash commands.

        :param context: The command context.
        :param scope: The scope of the sync. Can be `global` or `guild`.
        """

        if scope == "global":
            await context.bot.tree.sync()
            embed = discord.Embed(
                description="Slash commands have been globally synchronized.",
                color=0xBEBEFE,
            )
            await context.send(embed=embed, ephemeral=True)
            return
        elif scope == "guild":
            context.bot.tree.copy_global_to(guild=context.guild)
            await context.bot.tree.sync(guild=context.guild)
            embed = discord.Embed(
                description="Slash commands have been synchronized in this guild.",
                color=0xBEBEFE,
            )
            await context.send(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description="The scope must be `global` or `guild`.", color=0xE02B2B
        )
        await context.send(embed=embed)

    @commands.command(
        name="unsync",
        description="Unsynchronizes the slash commands.",
    )
    @app_commands.describe(
        scope="The scope of the sync. Can be `global`, `current_guild` or `guild`"
    )
    @commands.is_owner()
    async def unsync(self, context: Context, scope: str) -> None:
        """
        Unsynchonizes the slash commands.

        :param context: The command context.
        :param scope: The scope of the sync. Can be `global`, `current_guild` or `guild`.
        """

        if scope == "global":
            context.bot.tree.clear_commands(guild=None)
            await context.bot.tree.sync()
            embed = discord.Embed(
                description="Slash commands have been globally unsynchronized.",
                color=0xBEBEFE,
            )
            await context.send(embed=embed, ephemeral=True)
            return
        elif scope == "guild":
            context.bot.tree.clear_commands(guild=context.guild)
            await context.bot.tree.sync(guild=context.guild)
            embed = discord.Embed(
                description="Slash commands have been unsynchronized in this guild.",
                color=0xBEBEFE,
            )
            await context.send(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description="The scope must be `global` or `guild`.", color=0xE02B2B
        )
        await context.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="load",
        description="Load a cog",
    )
    @app_commands.describe(cog="The name of the cog to load")
    @commands.is_owner()
    async def load(self, context: Context, cog: str) -> None:
        """
        The bot will load the given cog.

        :param context: The hybrid command context.
        :param cog: The name of the cog to load.
        """
        try:
            await self.bot.load_extension(f"cogs.{cog}")
        except Exception:
            embed = discord.Embed(
                description=f"Could not load the `{cog}` cog.", color=0xE02B2B
            )
            await context.send(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description=f"Successfully loaded the `{cog}` cog.", color=0xBEBEFE
        )
        await context.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="unload",
        description="Unloads a cog.",
    )
    @app_commands.describe(cog="The name of the cog to unload")
    @commands.is_owner()
    async def unload(self, context: Context, cog: str) -> None:
        """
        The bot will unload the given cog.

        :param context: The hybrid command context.
        :param cog: The name of the cog to unload.
        """
        try:
            await self.bot.unload_extension(f"cogs.{cog}")
        except Exception:
            embed = discord.Embed(
                description=f"Could not unload the `{cog}` cog.", color=0xE02B2B
            )
            await context.send(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description=f"Successfully unloaded the `{cog}` cog.", color=0xBEBEFE
        )
        await context.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="reload",
        description="Reloads a cog.",
    )
    @app_commands.describe(cog="The name of the cog to reload")
    @commands.is_owner()
    async def reload(self, context: Context, cog: str) -> None:
        """
        The bot will reload the given cog.

        :param context: The hybrid command context.
        :param cog: The name of the cog to reload.
        """
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
        except Exception:
            embed = discord.Embed(
                description=f"Could not reload the `{cog}` cog.", color=0xE02B2B
            )
            await context.send(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(
            description=f"Successfully reloaded the `{cog}` cog.", color=0xBEBEFE
        )
        await context.send(embed=embed, ephemeral=True)


    @commands.hybrid_command(
        name="clearall",
        description="Clear all active operations for users."
    )
    @commands.is_owner()
    async def clear_active_operations(self, context: Context) -> None:
        """Clears all active operations."""
        self.bot.state_manager.clear_all()
        await context.send("All active operations have been cleared.", ephemeral=True)



    @commands.hybrid_command(
        name="reload_system",
        description="Deep reloads Core logic, Database modules, and Cogs."
    )
    @commands.is_owner()
    async def reload_system(self, context: Context) -> None:
        """
        Deep reloads the bot's logic layers.
        """
        await context.defer()
        
        try:
            # 1. Save the existing DB connection
            # We don't want to close/re-open the SQL connection, just update the wrapper logic
            db_connection = self.bot.database.connection

            # 2. Unload all Cogs
            # This clears the old logic holding references to old Core modules
            current_extensions = list(self.bot.extensions.keys())
            for ext in current_extensions:
                await self.bot.unload_extension(ext)

            # 3. Nuke 'core' and 'database' from sys.modules
            # This forces Python to re-read these files from disk next time they are imported
            modules_to_reload = []
            for module_name in list(sys.modules.keys()):
                if module_name.startswith("core") or module_name.startswith("database"):
                    del sys.modules[module_name]
                    modules_to_reload.append(module_name)

            self.bot.logger.info(f"Purged {len(modules_to_reload)} modules from cache.")

            # 4. Re-Initialize Database Manager
            # We need to re-import the class to get the new methods
            import database
            importlib.reload(database)
            
            # Re-instantiate the manager with the EXISTING connection
            # This updates the .users, .equipment, etc. repositories with new code
            self.bot.database = database.DatabaseManager(connection=db_connection)
            self.bot.logger.info("DatabaseManager has been rebuilt.")

            # 5. Reload Cogs
            # When these load, they will import the 'fresh' core/database modules
            for ext in current_extensions:
                try:
                    await self.bot.load_extension(ext)
                except Exception as e:
                    self.bot.logger.error(f"Failed to reload {ext}: {e}")

            # 6. Clear all active operations
            self.bot.state_manager.clear_all()
            
            embed = discord.Embed(
                title="System Reloaded ♻️",
                description=f"**Core**: Refreshed\n**Database**: Refreshed\n**Cogs**: {len(current_extensions)} reloaded.",
                color=0x00FF00
            )
            await context.send(embed=embed)

        except Exception as e:
            self.bot.logger.error(f"Critical failure during system reload: {e}")
            embed = discord.Embed(
                title="Reload Failed 💥",
                description=f"```{e}```",
                color=0xE02B2B
            )
            await context.send(embed=embed)


    @commands.hybrid_command(
        name="debug",
        description="Check all active operations for users."
    )
    @commands.is_owner()
    async def debug_active_operations(self, context: Context) -> None:
        """Debug method."""
        is_active = self.bot.state_manager.active_operations
        await context.send(f"{is_active}", ephemeral=True)

async def setup(bot) -> None:
    await bot.add_cog(Owner(bot))
