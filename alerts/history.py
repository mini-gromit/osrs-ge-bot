import logging
from typing import List, Optional
from datetime import datetime

from events import HistoricalAlchemyOpportunityEvent
from domain import history_analysis
import config

logger = logging.getLogger(__name__)

# Debug flag for detailed logging
DEBUG_FILTERING = False


# Quality filter defaults - same as alchemy alerts for consistency
DEFAULT_MIN_HOURLY_VOLUME = 50
DEFAULT_MIN_TRADE_LIMIT = 10


def get_historical_alchemy_alerts(
    calculator,
    min_profit: int = 100,
    min_limit: int = None,
    min_volume: int = None,
    lookback_windows: int = 15  # 15 windows = 15 minutes at 60-second intervals
) -> List[HistoricalAlchemyOpportunityEvent]:
    """
    Get best alchemy opportunities seen during the last 15 minutes.

    This differs from instant alchemy alerts by using the lowest buy price
    observed in recent history rather than just the current snapshot.

    Now uses the generic history subsystem which tracks ~4,400 items from
    current_prices (instead of ~1,700 from five_min_data). This provides
    much broader coverage of the market.

    Args:
        calculator: OSRSAlchemyFlippingCalculator instance
        min_profit: Minimum profit threshold (using historical best price)
        min_limit: Minimum trade limit filter
        min_volume: Minimum volume filter
        lookback_windows: Deprecated (now uses timestamp-based 15-minute lookback)

    Returns:
        List of HistoricalAlchemyOpportunityEvent objects
    """
    events = []

    # Check if we have rolling history data
    if not hasattr(calculator, "history_store") or calculator.history_store.get_item_count() == 0:
        logger.warning("No rolling history available - cannot generate historical alerts")
        return []

    # Get all profitable items using current prices
    # We'll recalculate profit using historical best prices
    logger.info("Analyzing rolling history for best buy opportunities...")

    profitable_items = calculator.get_profitable_items(
        min_profit=1,  # Get all items, we'll filter by historical profit later
        max_items=500,
        min_limit=min_limit,
        min_volume=min_volume
    )

    logger.info(f"Found {len(profitable_items)} items to analyze for historical opportunities")

    # Track filtering reasons
    filter_stats = {
        'no_history': 0,
        'no_best_window': 0,
        'low_profit': 0,
        'low_volume': 0,
        'low_limit': 0,
        'passed': 0
    }

    for item in profitable_items:
        item_id = item["item_id"]

        # Check if we have rolling history for this item
        if not calculator.history_store.has_history(item_id):
            filter_stats['no_history'] += 1
            if DEBUG_FILTERING:
                logger.debug(f"  {item['name']}: NO HISTORY")
            continue

        item_history = calculator.history_store.get_history(item_id)

        # Calculate best buy price from rolling history (timestamp-based, last 15 min)
        best_buy_result = history_analysis.find_best_buy_price(
            item_history,
            lookback_minutes=15  # Use timestamp-based lookup instead of window count
        )

        if best_buy_result is None:
            # No historical data available for this item
            filter_stats['no_best_window'] += 1
            if DEBUG_FILTERING:
                logger.debug(f"  {item['name']}: NO BEST PRICE (snapshots={len(item_history.snapshots)})")
            continue

        best_buy_price = best_buy_result['best_price']
        window_age_minutes = best_buy_result['minutes_ago']
        best_buy_timestamp = best_buy_result['timestamp']

        # Calculate profit using the historical best buy price
        high_alch_value = item['high_alch_value']
        nature_rune_cost = calculator.nature_rune_cost
        best_profit = high_alch_value - best_buy_price - nature_rune_cost

        # Filter by minimum profit threshold
        if best_profit < min_profit:
            filter_stats['low_profit'] += 1
            if DEBUG_FILTERING:
                logger.debug(f"  {item['name']}: LOW PROFIT ({best_profit} < {min_profit})")
            continue

        # Create event
        event = HistoricalAlchemyOpportunityEvent(
            name=item['name'],
            item_id=item_id,
            best_buy_price=best_buy_price,
            best_buy_timestamp=int(best_buy_timestamp),
            current_buy_price=item['buy_price'],
            high_alch_value=high_alch_value,
            best_profit=best_profit,
            trade_limit=item.get('limit', 0),
            hourly_volume=item.get('recent_volume', 0),
            minutes_since_seen=window_age_minutes,
            is_f2p=not item.get('members', False)
        )

        # Apply quality filters
        if event.hourly_volume < DEFAULT_MIN_HOURLY_VOLUME:
            filter_stats['low_volume'] += 1
            if DEBUG_FILTERING:
                logger.debug(f"  {item['name']}: LOW VOLUME ({event.hourly_volume} < {DEFAULT_MIN_HOURLY_VOLUME})")
            continue

        if event.trade_limit < DEFAULT_MIN_TRADE_LIMIT:
            filter_stats['low_limit'] += 1
            if DEBUG_FILTERING:
                logger.debug(f"  {item['name']}: LOW LIMIT ({event.trade_limit} < {DEFAULT_MIN_TRADE_LIMIT})")
            continue

        filter_stats['passed'] += 1
        events.append(event)

    # Log filtering statistics
    logger.info(f"Generated {len(events)} historical alchemy opportunity events")
    logger.info(f"Filtering breakdown: no_history={filter_stats['no_history']}, "
                f"no_best_window={filter_stats['no_best_window']}, "
                f"low_profit={filter_stats['low_profit']}, "
                f"low_volume={filter_stats['low_volume']}, "
                f"low_limit={filter_stats['low_limit']}, "
                f"passed={filter_stats['passed']}")

    # Sort by best historical profit (descending)
    # Use tie breakers: hourly volume, then trade limit
    events.sort(
        key=lambda x: (x.best_profit, x.hourly_volume, x.trade_limit),
        reverse=True
    )

    return events


def get_top_historical_opportunities(
    calculator,
    min_profit: int = 100
) -> dict:
    """
    Get top 3 Members and top 3 F2P historical alchemy opportunities.

    Returns both lists in a single dict for easy consumption by renderers.

    Args:
        calculator: OSRSAlchemyFlippingCalculator instance
        min_profit: Minimum profit threshold

    Returns:
        Dict with 'members' and 'f2p' keys containing top 3 events each
    """
    all_events = get_historical_alchemy_alerts(
        calculator=calculator,
        min_profit=min_profit
    )

    # Split into Members and F2P
    members_events = [e for e in all_events if not e.is_f2p]
    f2p_events = [e for e in all_events if e.is_f2p]

    # Return top 3 of each
    return {
        'members': members_events[:5],
        'f2p': f2p_events[:5]
    }
