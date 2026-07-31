"""
Flask API server for RuneLite plugin.

Provides lightweight endpoints for alchemy opportunities.
RuneLite plugin consumes this API - all business logic remains in Python.

Architecture:
- Background thread refreshes data on schedule
- API endpoints return cached results
- Plugin polls cached data (does not trigger refreshes)
"""

import logging
import time
import threading
from flask import Flask, jsonify
from engine import OSRSAlchemyFlippingCalculator
from scheduler import DataScheduler
import config

logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    datefmt=config.LOG_DATE_FORMAT
)

logger = logging.getLogger(__name__)

# Initialize calculator and scheduler
calculator = OSRSAlchemyFlippingCalculator()
scheduler = DataScheduler(calculator)

# Refresh configuration
REFRESH_INTERVAL = 60  # seconds between refreshes

# Cached data
cached_data = {
    'members': [],
    'f2p': [],
    'last_refresh_time': 0,
    'lock': threading.Lock()
}

app = Flask(__name__)


def refresh_cached_data():
    """
    Refresh market data and update cache.

    Called by background thread on schedule.
    Not triggered by API requests.
    """
    logger.info("Refreshing market data...")

    if not scheduler.refresh_all(force=True):
        logger.error("Failed to refresh market data")
        return

    # Get members opportunities (top 5, already ranked)
    members_events = calculator.get_profitable_alchemy_events(
        min_profit=config.DEFAULT_HOT_ITEMS_MIN_PROFIT,
        max_items=5,
        members_only=True
    )

    # Get F2P opportunities (top 5, already ranked)
    f2p_events = calculator.get_profitable_alchemy_events(
        min_profit=config.DEFAULT_F2P_ALCHS_MIN_PROFIT,
        max_items=5,
        members_only=False
    )

    # Convert events to API response format
    def event_to_dict(event):
        return {
            'item_id': event.item_id,
            'name': event.name,
            'profit': event.profit,
            'buy_price': event.buy_price
        }

    members_items = [event_to_dict(e) for e in members_events]
    f2p_items = [event_to_dict(e) for e in f2p_events]

    # Update cache
    with cached_data['lock']:
        cached_data['members'] = members_items
        cached_data['f2p'] = f2p_items
        cached_data['last_refresh_time'] = time.time()

    logger.info(f"Cache updated: {len(members_items)} members, {len(f2p_items)} F2P items")


def background_refresh_loop():
    """
    Background thread that refreshes data on schedule.

    Runs independently of API requests.
    Plugin polls do not trigger refreshes.
    """
    while True:
        try:
            refresh_cached_data()
        except Exception as e:
            logger.error(f"Error in background refresh: {e}", exc_info=True)

        # Sleep until next refresh
        time.sleep(REFRESH_INTERVAL)


@app.route('/alchemy', methods=['GET'])
def get_alchemy_opportunities():
    """
    Get top alchemy opportunities from cache.

    Returns cached data - does not trigger refresh.
    Background thread handles refresh scheduling.

    Response format:
    {
        "members": [...],  # Top 5 members items
        "f2p": [...],      # Top 5 F2P items
        "next_refresh": <seconds until backend refreshes>,
        "timestamp": <unix timestamp>
    }

    Each item contains:
    - item_id: int
    - name: str
    - profit: int (net profit in gp)
    - buy_price: int (current buy price)
    """
    try:
        current_time = time.time()

        # Read from cache
        with cached_data['lock']:
            members_items = cached_data['members']
            f2p_items = cached_data['f2p']
            last_refresh = cached_data['last_refresh_time']

        # Calculate seconds until next backend refresh
        elapsed = current_time - last_refresh
        next_refresh = max(0, int(REFRESH_INTERVAL - elapsed))

        response = {
            'members': members_items,
            'f2p': f2p_items,
            'next_refresh': next_refresh,
            'timestamp': int(current_time)
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in /alchemy endpoint: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    # Initial data fetch
    logger.info("Performing initial data refresh...")
    refresh_cached_data()

    # Start background refresh thread
    logger.info(f"Starting background refresh thread (interval: {REFRESH_INTERVAL}s)")
    refresh_thread = threading.Thread(target=background_refresh_loop, daemon=True)
    refresh_thread.start()

    # Start Flask server
    logger.info("Starting Flask API server on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
