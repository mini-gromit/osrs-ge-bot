# OSRS GE Bot

Tool for tracking OSRS Grand Exchange flipping and high alchemy opportunities.
Discord was the original goal, but I will be expanding the alerting tools as I go.

## Status

WIP — currently being refactored from monolithic scripts into a cleaner
module structure.

## Requirements

- Python 3.13.5

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root and add your Discord bot token:
   ```
   DISCORD_APP_TOKEN=INSERT-TOKEN-HERE
   ```

3. Invite the bot to your Discord server.

4. Run the bot:
   ```bash
   python osrs-alchemy.py
   ```

5. In your Discord channel, run:
   ```
   !setup #alch-alerts #flipping-alerts
   ```
   This wires up alchemy and flipping alerts to those channels.

## Usage

Run the standalone analysis CLI (no Discord needed):
```bash
python ge-tracker.py
```

## More info

TODO
