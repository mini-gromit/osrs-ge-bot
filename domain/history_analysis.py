"""
Business logic for analyzing generic market history.

These functions consume the new history subsystem (history/) and provide
reusable analytical primitives for all features.

Design Principles:
- Work with history.MarketHistory and history.MarketSnapshot models
- Use timestamp-based queries (no assumptions about refresh intervals)
- Return raw results (no filtering/thresholds)
- Keep business logic separate from storage
- Handle missing volume data gracefully
"""

from typing import Optional, Dict, Tuple, List
from datetime import datetime
import statistics


def find_best_buy_price(
    item_history,  # history.MarketHistory from generic subsystem
    lookback_minutes: int = 15
) -> Optional[Dict]:
    """
    Find the lowest buy price observed in the last N minutes.

    Uses timestamp-based lookback - no assumptions about refresh intervals.

    Args:
        item_history: MarketHistory object from history subsystem
        lookback_minutes: Number of minutes to look back (default 15)

    Returns:
        Dict with best_price, minutes_ago, timestamp, or None if no data
    """
    if item_history is None:
        return None

    # Get snapshots from last N minutes (timestamp-based)
    snapshots = item_history.get_recent_snapshots(lookback_minutes)

    if not snapshots:
        return None

    # Find snapshot with lowest buy price
    best_snapshot = None
    best_price = None

    for snapshot in snapshots:
        if snapshot.avg_low is None:
            continue

        if best_price is None or snapshot.avg_low < best_price:
            best_price = snapshot.avg_low
            best_snapshot = snapshot

    if best_snapshot is None:
        return None

    # Calculate age of best price in minutes
    current_time = datetime.now().timestamp()
    age_seconds = current_time - best_snapshot.timestamp
    age_minutes = int(age_seconds / 60)

    return {
        'best_price': best_price,
        'minutes_ago': age_minutes,
        'timestamp': best_snapshot.timestamp
    }


# ============================================================================
# Crash Detection Analysis Functions
# ============================================================================
# These functions provide crash detection analytics using the new history
# subsystem. They handle missing volume data gracefully.
# ============================================================================

def calculate_price_trend_minutes(
    item_history,  # history.MarketHistory from generic subsystem
    lookback_minutes: int
) -> Optional[float]:
    """
    Calculate price trend over the last N minutes (timestamp-based).

    Args:
        item_history: MarketHistory object from history subsystem
        lookback_minutes: Number of minutes to analyze

    Returns:
        Percentage change from oldest to newest snapshot, or None if insufficient data
    """
    if item_history is None:
        return None

    snapshots = item_history.get_recent_snapshots(lookback_minutes)

    if len(snapshots) < 2:
        return None

    # Get prices from oldest and newest snapshots
    oldest_price = snapshots[0].avg_low
    newest_price = snapshots[-1].avg_low

    if oldest_price is None or newest_price is None or oldest_price <= 0:
        return None

    # Calculate percentage change
    change_percent = ((newest_price - oldest_price) / oldest_price) * 100

    return round(change_percent, 2)


def calculate_consecutive_down_windows(
    item_history  # history.MarketHistory from generic subsystem
) -> int:
    """
    Count consecutive windows where price declined.

    Args:
        item_history: MarketHistory object from history subsystem

    Returns:
        Number of consecutive declining windows (0 if no decline)
    """
    if item_history is None or len(item_history.snapshots) < 2:
        return 0

    consecutive_down = 0

    # Walk backwards from most recent
    for i in range(len(item_history.snapshots) - 1, 0, -1):
        curr_price = item_history.snapshots[i].avg_low
        prev_price = item_history.snapshots[i - 1].avg_low

        if curr_price is None or prev_price is None:
            break

        if curr_price < prev_price:
            consecutive_down += 1
        else:
            # Streak broken
            break

    return consecutive_down


def calculate_persistent_sell_pressure(
    item_history,  # history.MarketHistory from generic subsystem
    min_ratio: float = 2.0,
    min_windows: int = 3
) -> Tuple[bool, int, float]:
    """
    Detect if sell pressure has been elevated for multiple consecutive windows.

    Handles missing volume data gracefully - returns (False, 0, 0.0) if volumes unavailable.

    Args:
        item_history: MarketHistory object from history subsystem
        min_ratio: Minimum sell/buy ratio to consider "elevated"
        min_windows: Minimum consecutive windows required

    Returns:
        Tuple of (is_persistent, consecutive_windows, avg_ratio)
    """
    if item_history is None or len(item_history.snapshots) < min_windows:
        return (False, 0, 0.0)

    consecutive_elevated = 0
    ratios = []

    # Walk backwards from most recent
    for snapshot in reversed(item_history.snapshots):
        # Handle missing volume data
        if snapshot.buy_volume is None or snapshot.sell_volume is None:
            # No volume data - can't calculate ratio
            break

        if snapshot.buy_volume <= 0:
            ratio = 0.0
        else:
            ratio = snapshot.sell_volume / snapshot.buy_volume

        if ratio >= min_ratio:
            consecutive_elevated += 1
            ratios.append(ratio)
        else:
            # Streak broken
            break

    is_persistent = consecutive_elevated >= min_windows
    avg_ratio = statistics.mean(ratios) if ratios else 0.0

    return (is_persistent, consecutive_elevated, avg_ratio)


def calculate_largest_drawdown(
    item_history  # history.MarketHistory from generic subsystem
) -> Optional[float]:
    """
    Calculate largest peak-to-trough price decline in history.

    Args:
        item_history: MarketHistory object from history subsystem

    Returns:
        Largest drawdown percentage, or None if insufficient data
    """
    if item_history is None or len(item_history.snapshots) < 2:
        return None

    prices = [s.avg_low for s in item_history.snapshots if s.avg_low is not None]

    if len(prices) < 2:
        return None

    max_drawdown = 0.0
    peak_price = prices[0]

    for price in prices:
        # Update peak if higher
        if price > peak_price:
            peak_price = price

        # Calculate drawdown from peak
        if peak_price > 0:
            drawdown = ((price - peak_price) / peak_price) * 100
            max_drawdown = min(max_drawdown, drawdown)

    return round(max_drawdown, 2)


def calculate_liquidity_score(
    item_history,  # history.MarketHistory from generic subsystem
    current_volume: int
) -> int:
    """
    Calculate liquidity score (0-100) based on volume consistency.

    Consistent volume = good liquidity = high score
    Declining volume = poor liquidity = low score

    Handles missing volume data gracefully.

    Args:
        item_history: MarketHistory object from history subsystem
        current_volume: Current total volume

    Returns:
        Liquidity score (0-100)
    """
    if item_history is None or len(item_history.snapshots) < 2:
        # Insufficient history, use current volume only
        if current_volume >= 500:
            return 100
        elif current_volume >= 100:
            return 70
        elif current_volume >= 50:
            return 40
        else:
            return 10

    # Calculate total volumes from snapshots (handle missing volumes)
    volumes = []
    for s in item_history.snapshots:
        if s.buy_volume is not None and s.sell_volume is not None:
            volumes.append(s.buy_volume + s.sell_volume)

    if not volumes or all(v == 0 for v in volumes):
        # No volume data available - use current volume fallback
        if current_volume >= 500:
            return 100
        elif current_volume >= 100:
            return 70
        elif current_volume >= 50:
            return 40
        else:
            return 10

    avg_volume = statistics.mean(volumes)
    vol_stdev = statistics.stdev(volumes) if len(volumes) >= 2 else 0

    # Check if volume is declining
    recent_avg = statistics.mean(volumes[-3:]) if len(volumes) >= 3 else volumes[-1]
    older_avg = statistics.mean(volumes[:3]) if len(volumes) >= 3 else volumes[0]

    declining = recent_avg < older_avg * 0.8  # 20% decline

    # Calculate coefficient of variation
    cv = (vol_stdev / avg_volume * 100) if avg_volume > 0 else 100

    # Base score on volume level
    if avg_volume >= 500:
        base_score = 100
    elif avg_volume >= 200:
        base_score = 85
    elif avg_volume >= 100:
        base_score = 70
    elif avg_volume >= 50:
        base_score = 50
    else:
        base_score = 30

    # Penalty for high volatility
    if cv > 50:
        base_score -= 20
    elif cv > 30:
        base_score -= 10

    # Penalty for declining liquidity
    if declining:
        base_score -= 15

    return max(0, min(100, base_score))
