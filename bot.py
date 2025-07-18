import json
import logging
import os
import platform
import sys
import aiosqlite
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
from dotenv import load_dotenv
from database import DatabaseManager
from discord import app_commands, Interaction
from discord.app_commands import CommandTree

if not os.path.isfile(f"{os.path.realpath(os.path.dirname(__file__))}/config.json"):
    sys.exit("'config.json' not found! Please add it and try again.")
else:
    with open(f"{os.path.realpath(os.path.dirname(__file__))}/config.json") as file:
        config = json.load(file)

"""	
Setup bot intents (events restrictions)
For more information about intents, please go to the following websites:
https://discordpy.readthedocs.io/en/latest/intents.html
https://discordpy.readthedocs.io/en/latest/intents.html#privileged-intents


Default Intents:
"""
intents = discord.Intents.default()
intents.bans = True
intents.dm_messages = True
intents.dm_reactions = True
intents.dm_typing = True
intents.emojis = True
intents.emojis_and_stickers = True
intents.guild_messages = True
intents.guild_reactions = True
intents.guild_scheduled_events = True
intents.guild_typing = True
intents.guilds = True
intents.integrations = True
intents.invites = True
intents.messages = True # `message_content` is required to get the content of the messages
intents.reactions = True
intents.typing = True
intents.voice_states = True
intents.webhooks = True

# Privileged Intents (Needs to be enabled on developer portal of Discord), please use them only if you need them:
intents.members = True
intents.message_content = True
intents.presences = True

"""
Uncomment this if you want to use prefix (normal) commands.
It is recommended to use slash commands and therefore not use prefix commands.

If you want to use prefix commands, make sure to also enable the intent below in the Discord developer portal.
"""
# intents.message_content = True
# intents.guilds = True

# Setup both of the loggers


class LoggingFormatter(logging.Formatter):
    # Colors
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    gray = "\x1b[38m"
    # Styles
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    COLORS = {
        logging.DEBUG: gray + bold,
        logging.INFO: blue + bold,
        logging.WARNING: yellow + bold,
        logging.ERROR: red,
        logging.CRITICAL: red + bold,
    }

    def format(self, record):
        log_color = self.COLORS[record.levelno]
        format = "(black){asctime}(reset) (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        format = format.replace("(black)", self.black + self.bold)
        format = format.replace("(reset)", self.reset)
        format = format.replace("(levelcolor)", log_color)
        format = format.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(format, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)


logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(LoggingFormatter())
# File handler
file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
file_handler_formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{"
)
file_handler.setFormatter(file_handler_formatter)

# Add the handlers
logger.addHandler(console_handler)
logger.addHandler(file_handler)

class CustomCommandTree(CommandTree):
    async def on_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            # Log and handle silently without propagating
            logger.info(f"Cooldown triggered for user {interaction.user.id} on command {interaction.command.name}, retry after {int(error.retry_after)} seconds")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        f"You are on cooldown. Try again in {int(error.retry_after)} seconds.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"You are on cooldown. Try again in {int(error.retry_after)} seconds.",
                        ephemeral=True
                    )
            except Exception as e:
                logger.error(f"Failed to send cooldown message: {type(e).__name__}: {e}")
        else:
            # Log other errors and let the bot's on_app_command_error handle them
            logger.error(f"Unhandled error in app command {interaction.command.name}: {type(error).__name__}: {error}")
            await super().on_error(interaction, error)

class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or(config["prefix"]),
            intents=intents,
            help_command=None,
            tree_cls=CustomCommandTree
        )
        """
        This creates custom bot variables so that we can access these variables in cogs more easily.

        For example, The config is available using the following code:
        - self.config # In this class
        - bot.config # In this file
        - self.bot.config # In cogs
        """
        self.logger = logger
        self.config = config
        self.database = None
        self.state_manager = StateManager(logger=self.logger)

    async def init_db(self) -> None:
        async with aiosqlite.connect(
            f"{os.path.realpath(os.path.dirname(__file__))}/database/database.db"
        ) as db:
            with open(
                f"{os.path.realpath(os.path.dirname(__file__))}/database/schema.sql"
            ) as file:
                await db.executescript(file.read())
            await db.commit()

    async def load_cogs(self) -> None:
        """
        The code in this function is executed whenever the bot will start.
        """
        for file in os.listdir(f"{os.path.realpath(os.path.dirname(__file__))}/cogs"):
            if file.endswith(".py"):
                extension = file[:-3]
                try:
                    await self.load_extension(f"cogs.{extension}")
                    self.logger.info(f"Loaded extension '{extension}'")
                except Exception as e:
                    exception = f"{type(e).__name__}: {e}"
                    self.logger.error(
                        f"Failed to load extension {extension}\n{exception}"
                    )

    @tasks.loop(minutes=1.0)
    async def status_task(self) -> None:
        """
        Setup the game status task of the bot.
        """
        # statuses = ["Idleology"]
        # await self.change_presence(activity=discord.Game(random.choice(statuses)))
        await self.change_presence(activity=discord.Game("Idleology"))

    @status_task.before_loop
    async def before_status_task(self) -> None:
        """
        Before starting the status changing task, we make sure the bot is ready
        """
        await self.wait_until_ready()

    async def setup_hook(self) -> None:
        """
        This will just be executed when the bot starts the first time.
        """
        self.logger.info(f"Logged in as {self.user.name}")
        self.logger.info(f"discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(
            f"Running on: {platform.system()} {platform.release()} ({os.name})"
        )
        self.logger.info("-------------------")
        await self.init_db()
        self.database = DatabaseManager(
            connection=await aiosqlite.connect(
                f"{os.path.realpath(os.path.dirname(__file__))}/database/database.db"
            )
        )
        await self.load_cogs()
        self.status_task.start()


    async def on_message(self, message: discord.Message) -> None:
        """
        The code in this event is executed every time someone sends a message, with or without the prefix

        :param message: The message that was sent.
        """
        if message.author == self.user or message.author.bot:
            return
        await self.process_commands(message)

    async def on_command_completion(self, context: Context) -> None:
        """
        The code in this event is executed every time a normal command has been *successfully* executed.

        :param context: The context of the command that has been executed.
        """
        full_command_name = context.command.qualified_name
        split = full_command_name.split(" ")
        executed_command = str(split[0])
        if context.guild is not None:
            self.logger.info(
                f"Executed {executed_command} command in {context.guild.name} (ID: {context.guild.id}) by {context.author} (ID: {context.author.id})"
            )
        else:
            self.logger.info(
                f"Executed {executed_command} command by {context.author} (ID: {context.author.id}) in DMs"
            )

    async def on_command_error(self, context: Context, error) -> None:
        """
        The code in this event is executed every time a normal valid command catches an error.

        :param context: The context of the normal command that failed executing.
        :param error: The error that has been faced.
        """
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(error.retry_after, 60)
            hours, minutes = divmod(minutes, 60)
            hours = hours % 24
            embed = discord.Embed(
                description=f"**Please slow down** - You can use this command again in {f'{round(hours)} hours' if round(hours) > 0 else ''} {f'{round(minutes)} minutes' if round(minutes) > 0 else ''} {f'{round(seconds)} seconds' if round(seconds) > 0 else ''}.",
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                description="You are not the owner of the bot!", color=0xE02B2B
            )
            await context.send(embed=embed)
            if context.guild:
                self.logger.warning(
                    f"{context.author} (ID: {context.author.id}) tried to execute an owner only command in the guild {context.guild.name} (ID: {context.guild.id}), but the user is not an owner of the bot."
                )
            else:
                self.logger.warning(
                    f"{context.author} (ID: {context.author.id}) tried to execute an owner only command in the bot's DMs, but the user is not an owner of the bot."
                )
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                description="You are missing the permission(s) `"
                + ", ".join(error.missing_permissions)
                + "` to execute this command!",
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                description="I am missing the permission(s) `"
                + ", ".join(error.missing_permissions)
                + "` to fully perform this command!",
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="Error!",
                # We need to capitalize because the command arguments have no capital letter in the code and they are the first word in the error message.
                description=str(error).capitalize(),
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        else:
            raise error

    async def on_app_command_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            retry_after = int(error.retry_after)
            # Check if the interaction is already responded to
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"You are on cooldown. Try again in {retry_after} seconds.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"You are on cooldown. Try again in {retry_after} seconds.",
                    ephemeral=True
                )
        else:
            # Log other errors for debugging but don't raise them to prevent duplicate logging
            self.logger.error(f"Error in app command: {type(error).__name__}: {error}")
            if interaction.response.is_done():
                await interaction.followup.send(
                    "An unexpected error occurred. Please try again later.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "An unexpected error occurred. Please try again later.",
                    ephemeral=True
                )

    async def check_user_registered(self, interaction: Interaction, existing_user) -> bool:
        """
        Check if a user is registered in the database. If not, send a registration prompt.
        :param interaction: The Discord interaction object.
        :return: True if the user is registered, False otherwise.
        """
        if not existing_user:
            await interaction.response.send_message(
                "Please /register with the 🏦 Adventurer's Guild first.",
                ephemeral=True
            )
            return False
        return True
    
    async def check_is_active(self, interaction: Interaction, user_id: str) -> bool:
        """
        Check if a user has an active operation.
        """
        if self.state_manager.is_active(user_id):
            await interaction.response.send_message(
                "Please finish all your other interactions first.",
                ephemeral=True)
            return False
        return True
    

    async def is_maintenance(self, interaction: Interaction, user_id: str) -> bool:
        """
        Check if a user has an active operation.
        """
        if user_id != str(866408616873820180):
            await interaction.response.send_message(
                "This command is under maintenance, please try again later.",
                ephemeral=True)
            return False
        return True


class StateManager:
    def __init__(self, logger):
        self.logger = logger
        self.active_operations = {}

    def set_active(self, user_id: str, operation: str):
        """Set a user's operation state."""
        self.logger.info(f'Set {user_id} as {operation}')
        self.active_operations[user_id] = operation

    def clear_active(self, user_id: str):
        """Clear a user's operation state."""
        self.logger.info(f'Attempt to clear {user_id}')
        if user_id in self.active_operations:
            self.logger.info(f'{user_id} found in active list, cleared')
            del self.active_operations[user_id]

    def is_active(self, user_id: str):
        """Check if a user is currently engaged in an operation."""
        return user_id in self.active_operations

    def clear_all(self):
        """Clear all active operations."""
        self.active_operations.clear()  # Clears the dictionary

load_dotenv()

bot = DiscordBot()
bot.run(os.getenv("TOKEN"))
