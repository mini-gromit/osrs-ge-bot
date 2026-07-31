# OSRS Alchemy RuneLite Plugin

RuneLite plugin that displays profitable high alchemy opportunities.

## Architecture

This plugin follows a clean separation of concerns:

- **Python Backend**: All business logic (calculations, rankings, filtering)
- **RuneLite Plugin**: Display only (no calculations or business logic)

## Features

- Members and F2P tabs
- Top 5 items per category
- RuneLite item sprites
- Click to copy buy price
- Refresh timer countdown
- Auto-refresh from backend

## Installation

### Backend Setup

1. Start the Python API server:
```bash
cd /path/to/osrs-ge-bot
python api_server.py
```

The server will run on `http://localhost:5000`

### Plugin Installation

#### Option 1: Development Mode

1. Clone this repository
2. Open RuneLite in development mode
3. Add this plugin to your RuneLite development plugins
4. Build and run

#### Option 2: JAR Installation

1. Build the plugin:
```bash
cd runelite-plugin
./gradlew build
```

2. Copy the JAR to your RuneLite plugins folder:
```bash
cp build/libs/runelite-plugin-1.0.0.jar ~/.runelite/plugins/
```

3. Restart RuneLite

## Configuration

Access plugin settings in RuneLite's configuration panel:

- **Backend URL**: URL of the Python API (default: `http://localhost:5000`)
- **Auto Refresh**: Automatically refresh data (default: enabled)
- **Refresh Interval**: How often to refresh in seconds (default: 60)
- **Default Tab**: Which tab to show on startup (Members/F2P)

## Usage

1. Click the Alchemy icon in the RuneLite sidebar
2. Select Members or F2P tab
3. View top 5 alchemy opportunities
4. Click any item to copy its buy price to clipboard

The buy price is copied without commas for easy pasting into the Grand Exchange.

## API Endpoint

The plugin consumes the `/alchemy` endpoint:

```json
{
  "members": [
    {
      "item_id": 1234,
      "name": "Dragon platelegs",
      "profit": 1002,
      "buy_price": 160998
    }
  ],
  "f2p": [...],
  "next_refresh": 42,
  "timestamp": 1234567890
}
```

## Icon

Place a `alchemy_icon.png` file (16x16 or 32x32) in `src/main/resources/` for the sidebar icon.

A simple icon can be created using:
- Gold/yellow color scheme
- Alch symbol or coins
- Transparent background

## Development

### Building

```bash
./gradlew build
```

### Testing

```bash
./gradlew test
```

### Code Style

Follows standard RuneLite plugin conventions:
- Lombok for boilerplate reduction
- Slf4j for logging
- Google style guide for Java
- Inject dependencies via Guice

## File Structure

```
runelite-plugin/
├── build.gradle                 # Build configuration
├── runelite-plugin.properties   # Plugin metadata
├── src/main/
│   ├── java/com/osrsalchemy/
│   │   ├── AlchemyPlugin.java          # Main plugin class
│   │   ├── AlchemyPluginConfig.java    # Configuration
│   │   ├── AlchemyPanel.java           # UI panel
│   │   ├── AlchemyHttpClient.java      # Network layer
│   │   └── AlchemyOpportunity.java     # Data model
│   └── resources/
│       └── alchemy_icon.png            # Plugin icon
└── README.md
```

## Non-Goals (Phase 1)

This initial version intentionally does NOT include:

- Flipping
- Crash alerts
- Historical charts
- Notifications
- Overlays
- Any automation
- GE integration
- Bank integration

These may be added in future phases.

## Support

For issues or questions:
1. Check that the Python backend is running
2. Verify the backend URL in plugin settings
3. Check RuneLite logs for errors
4. Ensure you have the latest version

## License

[Insert License Here]
