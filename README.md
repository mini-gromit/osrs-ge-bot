# OSRS GE Bot

A Python toolkit for monitoring the Old School RuneScape Grand Exchange and generating actionable trading alerts.

The project started as a Discord bot for High Alchemy opportunities but has evolved into a reusable market analysis engine capable of powering multiple frontends.

Current frontends include:
- Discord
- CLI

Future frontends include:
- RuneLite Plugin
- Web Dashboard
- Additional integrations

---

## Features

### High Alchemy Alerts
- Real-time profitable High Alchemy opportunities
- Members and F2P channels
- Crash risk detection
- Historical "Best Seen (15m)" opportunities
- Quality scoring and filtering

### Flipping Alerts
- Buy/sell recommendations
- GE tax-aware profit calculations
- ROI calculations
- Confidence scoring
- Liquidity filtering

### Historical Analysis
- Rolling market history
- Historical best buy prices
- Timestamp-based trend analysis
- Reusable history subsystem

### Discord Features
- Interactive `/setup` command
- Configurable alert channels
- Personal notification subscriptions via `/notifications`
- Rich embeds optimized for fast scanning

---

# Requirements

* Python 3.13.5+

---

# Installation

Clone the repository:

```bash
git clone <repository-url>
cd osrs-ge-bot
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Configuration

Create a `.env` file in the project root.

Example:

```text
DISCORD_APP_TOKEN=YOUR_DISCORD_BOT_TOKEN
```

Additional configuration options are available in `config.py`.

---

# Discord Bot Setup

## 1. Create a Discord Application

1. Visit the Discord Developer Portal.
2. Create a new application.
3. Create a Bot.
4. Copy the bot token into your `.env` file.

---

## 2. Enable Required Bot Permissions

The bot should be able to:

* View Channels
* Send Messages
* Embed Links
* Read Message History
* Use Slash Commands

---

## 3. Invite the Bot

Invite the bot to your server using the generated OAuth2 URL with the required permissions.

---

## 4. Start the Bot

```bash
python discord_bot.py
```

---

## 5. Configure Alert Channels

Run:

```
/setup
```

The interactive setup menu lets you configure channels for:

* High Alchemy Alerts
* F2P High Alchemy Alerts
* Best Seen (15m)
* Flipping Alerts
* Crash Risk Alerts

The bot stores channel configuration automatically.

---

## 6. Configure Personal Notifications

Run:

```
/notifications
```

Each user can independently configure:

* High Alchemy notifications
* Crash Risk notifications
* Minimum profit thresholds
* Severity/confidence preferences

Notification preferences are stored per user.

---

# Available Channels

Typical server layout:

```
#all-alchemy
#f2p-alchemy
#best-15min
#flipping
#crash-risk
```

You can name the channels however you'd like—the `/setup` command maps them to the appropriate alert type.

---

# Running Without Discord

The project also includes a standalone CLI.

```bash
python ge_tracker.py
```

This runs market analysis locally without Discord.

---

# Project Architecture

```
alerts/         Alert generation
api/            OSRS Wiki & external API clients
bot/            Discord bot
domain/         Business logic
engine/         Core market engine
events/         Shared event models
history/        Rolling market history subsystem
renderers/      Discord and CLI presentation
scheduler/      Background refresh jobs
```

Business logic lives in the `domain` layer.

Frontends (Discord, CLI, future RuneLite plugin, etc.) consume reusable `MarketEvent` objects.

---

# Roadmap

Planned improvements include:

* RuneLite plugin
* Additional notification frontends
* More advanced flipping analytics
* Historical market analytics
* Additional trading signals

---

## TODO

- Continue improving the flipping opportunity engine and ranking algorithms.
- Validate flipping recommendations over a longer period using live market data.
- Expand alerting frontends beyond Discord (RuneLite, CLI, etc.).
- Improve historical market analysis and additional trading strategies.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
