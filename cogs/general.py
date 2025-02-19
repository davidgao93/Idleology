import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context
from datetime import datetime, timedelta

class General(commands.Cog, name="general"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.context_menu_user = app_commands.ContextMenu(
            name="Grab ID", callback=self.grab_id
        )
        self.bot.tree.add_command(self.context_menu_user)
        self.context_menu_message = app_commands.ContextMenu(
            name="Remove spoilers", callback=self.remove_spoilers
        )
        self.bot.tree.add_command(self.context_menu_message)

    # Message context menu command
    async def remove_spoilers(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """
        Removes the spoilers from the message. This command requires the MESSAGE_CONTENT intent to work properly.

        :param interaction: The application command interaction.
        :param message: The message that is being interacted with.
        """
        spoiler_attachment = None
        for attachment in message.attachments:
            if attachment.is_spoiler():
                spoiler_attachment = attachment
                break
        embed = discord.Embed(
            title="Message without spoilers",
            description=message.content.replace("||", ""),
            color=0xBEBEFE,
        )
        if spoiler_attachment is not None:
            embed.set_image(url=attachment.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # User context menu command
    async def grab_id(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """
        Grabs the ID of the user.

        :param interaction: The application command interaction.
        :param user: The user that is being interacted with.
        """
        embed = discord.Embed(
            description=f"The ID of {user.mention} is `{user.id}`.",
            color=0xBEBEFE,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="help", description="List Idleology's commands"
    )
    async def help(self, context: commands.Context) -> None:
        # Brief description of Idleology
        game_description = (
            "Welcome to **Idleology**! 💡 This is a Discord idle RPG where you journey through "
            "Tabularasa.\n\n"
            "Once you're /registered, use any of the commands below. May the best ideology win."
        )

        #prefix = self.bot.config["prefix"]
        prefix = "/"
        embed = discord.Embed(
            title="Help",
            description=game_description,
            color=0xBEBEFE
        )

        # Adding commands from all cogs
        for i in self.bot.cogs:
            if i == "owner" and not (await self.bot.is_owner(context.author)):
                continue
            cog = self.bot.get_cog(i.lower())
            print(f'Checking cog {cog}')
            if cog is None:
                self.bot.logger.warning(f"Cog '{i}' not found or not properly initialized.")
                continue
            commands = cog.get_commands()
            data = []
            for command in commands:
                description = command.description.partition("\n")[0]
                data.append(f"{prefix}{command.name} - {description}")
            help_text = "\n".join(data)
            embed.add_field(
                name=i.capitalize(), value=f"```{help_text}```", inline=False
            )
        await context.send(embed=embed)

    @commands.hybrid_command(name="getstarted", description="Get information and tips for playing Idleology.")
    async def info(self, context: Context) -> None:
        """Sends an information embed with gameplay and command instructions."""
        
        embed = discord.Embed(
            title="Welcome to Idleology!",
            description="Here's a quick guide to help you get started and enjoy your journey in Tabularasa.",
            color=0x00FF00
        )
        
        embed.add_field(
            name="How to Play Idleology",
            value=(
                "Idleology is an idle RPG where you can register with the adventurer's guild, engage in combat, "
                "level up and spread your ideology to progress through the world of Tabularasa. "
                "Use the commands below to get started!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Getting Started",
            value=(
                "**1. Register Your Character:**"
                "Use `/register <character_name>` to register with the 🏦 Adventurer's Guild and start your journey!\n"
                "**2. View Your Stats:**"
                "Check your character's stats using `/stats` to track your progress.\n"
                "**3. Choose Your Ideology:**"
                "Join or create an ideology that best fits your adventure. Use `/ideology` to see the leaderboard.\n"
                "**4. Engage in Combat:**"
                "Fight enemies using `/combat` to gain experience and level up!\n"
                "**5. And much more!**\n"
                "Use `/help` for the full list of commands!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Gaining Experience and Leveling Up",
            value=(
                "In combat, you can earn experience points (XP). "
                "To level up, keep battling enemies.\n\n"
                "Here are some points to remember:\n"
                "- Engage in combat every 10 minutes using the `/combat` command.\n"
                "- ⚔️ to attack, 🩹 to heal (if you have potions, buy with /shop),"
                " ⏩ to auto-batle (stops at <10% hp), 🏃 to run\n"
                "- Leveling up increases your stats!"
                "- The tavern is a great place to rest and make some quick cash!"
                "- You also heal over time if you're down on your luck."
                "- Check your skills with the /skills command!"
            ),
            inline=False
        )

        embed.add_field(
            name="Forging and refining items",
            value=(
                "When you win your combats, you have a chance of dropping loot."
                "Loot drops in the form of weapons.\n\n"
                "Here are some points to remember:\n"
                "- Weapons can be forged with skilling materials.\n"
                "- Weapons can be refined with gold.\n"
                "- Weapons can gain powerful passives via forging."
                "- Weapons can gain more stats with refining."
                "- Check your equipment with the /inventory command!"
            ),
            inline=False
        )

        embed.set_footer(text="It's all in the mind.")
        
        await context.send(embed=embed)


    @commands.hybrid_command(name="cooldowns", description="Check your current cooldowns (cd) for various commands.")
    async def cooldowns(self, context: Context) -> None:
        """Check the cooldowns of /rest, /checkin, and /propagate commands."""
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        # Get user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's Guild. Please /register first.")
            return

        # Check cooldown for /rest
        last_rest_time = existing_user[13]  # Assuming last_rest_time is at index 13

        cooldown_duration = timedelta(hours=2)
        rest_remaining = None
        if last_rest_time:
            last_rest_time_dt = datetime.fromisoformat(last_rest_time)
            time_since_rest = datetime.now() - last_rest_time_dt
            if time_since_rest < cooldown_duration:
                remaining_time = cooldown_duration - time_since_rest
                rest_remaining = remaining_time
        else:
            # If last_rest_time is None, the user can immediately rest
            rest_remaining = timedelta(0)

        # Check cooldown for /checkin
        last_checkin_time = existing_user[18]  # Assuming last_checkin_time is at index 14
        checkin_remaining = None
        checkin_duration = timedelta(hours=18)
        if last_checkin_time:
            last_checkin_time_dt = datetime.fromisoformat(last_checkin_time)
            time_since_checkin = datetime.now() - last_checkin_time_dt
            if time_since_checkin < checkin_duration:
                remaining_time = checkin_duration - time_since_checkin
                checkin_remaining = remaining_time
        else:
            checkin_remaining = timedelta(0)  # First check-in

        # Check cooldown for /propagate
        last_propagate_time = existing_user[14]  # Index for last_propagate_time (update if necessary)
        propagate_remaining = None
        propagate_duration = timedelta(hours=18)

        if last_propagate_time:
            last_propagate_time_dt = datetime.fromisoformat(last_propagate_time)
            time_since_propagate = datetime.now() - last_propagate_time_dt
            if time_since_propagate < propagate_duration:
                remaining_time = propagate_duration - time_since_propagate
                propagate_remaining = remaining_time
        else:
            propagate_remaining = timedelta(0)  # First propagate

        # Creating the embed
        embed = discord.Embed(
            title="Timers",
            color=0x00FF00
        )

        # Building the embed fields
        if rest_remaining:
            embed.add_field(name="/rest 🛏️", value=f"**{rest_remaining.seconds // 3600} hours "
                                                        f"{(rest_remaining.seconds // 60) % 60} minutes** remaining. (400 gp bypass)")
        else:
            embed.add_field(name="/rest 🛏️", value="Available now!", inline=False)

        if checkin_remaining:
            embed.add_field(name="/checkin 🛖", value=f"**{checkin_remaining.seconds // 3600} hours "
                                                            f"{(checkin_remaining.seconds // 60) % 60} minutes** remaining.")
        else:
            embed.add_field(name="/checkin 🛖", value="Available now!", inline=False)

        if propagate_remaining:
            embed.add_field(name="/propagate 💡", value=f"**{propagate_remaining.seconds // 3600} hours "
                                                            f"{(propagate_remaining.seconds // 60) % 60} minutes** remaining.")
        else:
            embed.add_field(name="/propagate 💡", value="Available now!", inline=False)

        # Send the embed message
        await context.send(embed=embed)


    @commands.hybrid_command(name="ids", description="Fetch your user ID and all item IDs.")
    async def ids(self, context: commands.Context) -> None:
        """Fetch and display the user's ID along with IDs of their items."""
        user_id = str(context.author.id)
        server_id = str(context.guild.id)

        # Fetch user data
        existing_user = await self.bot.database.fetch_user(user_id, server_id)
        if not existing_user:
            await context.send("You are not registered with the 🏦 Adventurer's Guild. Please /register first.")
            return

        # Fetch user item data
        user_items = await self.bot.database.fetch_user_items(user_id)

        # Construct the embed to show information
        embed = discord.Embed(
            title="User ID and Item IDs",
            color=0xBEBEFE
        )
        embed.add_field(name="User ID", value=user_id, inline=False)

        if user_items:
            items_description = "\n".join([f"**ID:** {item[0]} - **Name:** {item[1]}" for item in user_items])
            embed.add_field(name="Your Items", value=items_description, inline=False)
        else:
            embed.add_field(name="Your Items", value="You have no items in your inventory.", inline=False)

        await context.send(embed=embed)

async def setup(bot) -> None:
    await bot.add_cog(General(bot))