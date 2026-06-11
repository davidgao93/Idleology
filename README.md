# Idleology

Idleology is a text-based idle RPG bot for Discord. Create your adventurer, engage in turn-based combat against monsters with modifiers and passives, manage a deep inventory with upgrades (forge, refine, temper, imbue, etc.), gather resources through skills, recruit and dispatch partners, build and manage a settlement with workers and development turns, and progress through extensive endgame systems like the Ascent (floor climbing), Codex (wave survival), Uber bosses, and the weekly Maw world boss.

The game features persistent player data, complex mechanics including essences, jewels, hematurgy blood passives, alchemy, quests, prestige cosmetics, and more — all accessible via slash commands and interactive views in Discord.

## Features

- **Combat**: Stamina-based encounters, weapon/armor/accessory/glove/boot/helmet passives, essences (including corrupted ones), ward system, crits, modifiers, and team support from companions and partners.
- **Progression**: Leveling, stat investment, ascension floors (up to 666), Codex tomes and runs, journey milestones.
- **Inventory & Economy**: Full gear management, upgrades (forge/refine/voidforge/temper/etc.), trading, gold, runes, keys, and resource gathering (mining/fishing/woodcutting).
- **Settlement**: Build structures, assign workers, development turns, Black Market deals, research, nursery for workers, and events.
- **Partners**: Gacha recruitment, skill training (combat & dispatch), timed dispatch tasks for rewards, affinity stories.
- **Endgame**: Apex hunting with soul stones, delve mining expeditions, maw world boss, prestige hall for cosmetics (titles, flairs, custom avatars, monuments), consume monster parts for permanent HP.
- **Other Systems**: Alchemy (potion transmutation & passives), quests (daily contracts + horizon paths), slayer tasks & emblems, events, minigames (casino), first-use tutorial.

The bot emphasizes long-term idle progression with active combat and management elements.

## Prerequisites

- Python 3.11.5 or newer
- A Discord account and server where you can add bots
- A Discord Bot token (create an application at https://discord.com/developers/applications)
- **Privileged Gateway Intents** enabled for your bot in the Discord Developer Portal:
  - Server Members Intent
  - Message Content Intent
  - Presence Intent

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Idleology.git
   cd Idleology
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the bot:
   - Create a `.env` file in the project root with your Discord bot token:
     ```
     TOKEN=your_bot_token_here
     ```
   - (Optional) Edit `config.json`:
     - `prefix`: Command prefix (default `&`)
     - `combat_logging`: Enable detailed combat logs (`true`/`false`)
     - Other guild/channel IDs as needed for your setup

4. Run the bot:
   ```bash
   python bot.py
   ```
   - On first run, the bot will automatically initialize the SQLite database (`database/database.db`) using `database/schema.sql` and apply any necessary migrations.
   - On Windows, you can also use `run_app.bat`.

## Usage

- Generate an invite link for your bot in the Discord Developer Portal (use the "bot" scope and grant necessary permissions like Send Messages, Embed Links, Use Slash Commands, etc.).
- Invite the bot to your Discord server.
- Use slash commands (recommended) or the configured prefix (e.g., `&combat`).
- Start by using `/register` (or the equivalent) to create your character and choose an appearance/ideology.
- Key starting commands include:
  - `/combat` — Fight monsters
  - `/inventory` or gear management commands — Manage equipment
  - `/settlement` — Build and manage your settlement
  - `/partners` — Recruit and manage partners
  - `/profile` — View your character
  - Many more systems via `/` commands (use Discord's command discovery)

The bot uses interactive Discord UI components (buttons, selects, modals) for most gameplay.

For a complete list of commands once the bot is running, check Discord's slash command menu or use any available help functionality.

## Architecture Overview

- **Cogs** (`cogs/`): Discord command handlers (thin layer).
- **Core** (`core/`): Game logic, models (Player, equipment, etc.), views (UI), mechanics (pure functions for combat, economy, etc.).
- **Database** (`database/`): SQLite with aiosqlite; all SQL lives in `database/repositories/`.
- **Assets** (`assets/`): Game data in CSV/JSON/TXT (monsters, items, exp tables, partners, etc.).
- **Bot entrypoint**: `bot.py` — Handles intents, DB init, cog loading, error handling, and StateManager for preventing concurrent activities.

See `AGENTS.md` and `CLAUDE.md` for detailed developer/architecture guidelines (primarily for contributors).

## Version

Current version: 0.91

## Contributing

Contributions are welcome! Please read `AGENTS.md` for coding standards, architecture rules (e.g., always extend `BaseView`, no raw SQL outside repositories, etc.), and guidelines before submitting pull requests.

## License

This project is provided as-is for personal/self-hosted use. Check the repository for any specific license terms.

## Disclaimer

- This is a self-hosted Discord bot. You are responsible for obtaining and securing your own bot token and complying with Discord's Terms of Service and Developer Policies.
- The bot uses privileged intents and requires proper configuration.
- Data is stored locally in SQLite; back up `database/database.db` as needed.

Enjoy your idle adventures in Idleology! ⚔️