"""
Historical market data analysis for crash detection.

Analyzes rolling snapshots to detect sustained trends vs temporary spikes.
"""

import statistics
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta


class MarketSnapshot:
    """
    Single 5-minute market snapshot for an item.

    Stores price and volume data for a specific time window.
    """
    def __init__(
        self,
        timestamp: int,
        avg_low: Optional[int],
        avg_high: Optional[int],
        buy_volume: int,
        sell_volume: int
    ):
        self.timestamp = timestamp
        self.avg_low = avg_low
        self.avg_high = avg_high
        self.buy_volume = buy_volume
        self.sell_volume = sell_volume

    def sell_pressure_ratio(self) -> float:
        """Calculate sell/buy volume ratio for this snapshot."""
        if self.buy_volume <= 0:
            return 0.0
        return self.sell_volume / self.buy_volume

    def total_volume(self) -> int:
        """Total trading volume for this snapshot."""
        return self.buy_volume + self.sell_volume


class MarketHistory:
    """
    Rolling history of market snapshots for an item.

    Maintains approximately the last 12 snapshots (≈60 minutes at 5-min intervals).
    """
    def __init__(self, max_snapshots: int = 12):
        self.snapshots: List[MarketSnapshot] = []
        self.max_snapshots = max_snapshots

    def add_snapshot(self, snapshot: MarketSnapshot):
        """
        Add a new snapshot and expire old ones.

        Args:
            snapshot: MarketSnapshot to add
        """
        self.snapshots.append(snapshot)

        # Keep only most recent max_snapshots
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots = self.snapshots[-self.max_snapshots:]

    def expire_old_snapshots(self, max_age_seconds: int = 3900):
        """
        Remove snapshots older than max_age (default 65 minutes).

        Args:
            max_age_seconds: Maximum age in seconds (default 3900 = 65 minutes)
        """
        if not self.snapshots:
            return

        cutoff_time = datetime.now().timestamp() - max_age_seconds

        self.snapshots = [
            s for s in self.snapshots
            if s.timestamp >= cutoff_time
        ]

    def get_recent_windows(self, count: int) -> List[MarketSnapshot]:
        """
        Get most recent N snapshots.

        Args:
            count: Number of snapshots to retrieve

        Returns:
            List of most recent snapshots (oldest first)
        """
        if count <= 0 or not self.snapshots:
            return []

        return self.snapshots[-count:]

    def has_sufficient_history(self, min_windows: int = 3) -> bool:
        """
        Check if we have enough history for analysis.

        Args:
            min_windows: Minimum required snapshots

        Returns:
            True if sufficient history exists
        """
        return len(self.snapshots) >= min_windows


def calculate_price_trend(
    history: MarketHistory,
    windows: int
) -> Optional[float]:
    """
    Calculate price trend over the last N windows.

    Args:
        history: MarketHistory object
        windows: Number of windows to analyze (e.g., 3 for 15min, 6 for 30min)

    Returns:
        Percentage change from oldest to newest window, or None if insufficient data
    """
    snapshots = history.get_recent_windows(windows)

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


def calculate_consecutive_down_windows(history: MarketHistory) -> int:
    """
    Count consecutive windows where price declined.

    Args:
        history: MarketHistory object

    Returns:
        Number of consecutive declining windows (0 if no decline)
    """
    if len(history.snapshots) < 2:
        return 0

    consecutive_down = 0

    # Walk backwards from most recent
    for i in range(len(history.snapshots) - 1, 0, -1):
        curr_price = history.snapshots[i].avg_low
        prev_price = history.snapshots[i - 1].avg_low

        if curr_price is None or prev_price is None:
            break

        if curr_price < prev_price:
            consecutive_down += 1
        else:
            # Streak broken
            break

    return consecutive_down


def calculate_persistent_sell_pressure(
    history: MarketHistory,
    min_ratio: float = 2.0,
    min_windows: int = 3
) -> Tuple[bool, int, float]:
    """
    Detect if sell pressure has been elevated for multiple consecutive windows.

    This distinguishes sustained crashes from temporary spikes.

    Args:
        history: MarketHistory object
        min_ratio: Minimum sell/buy ratio to consider "elevated"
        min_windows: Minimum consecutive windows required

    Returns:
        Tuple of (is_persistent, consecutive_windows, avg_ratio)
    """
    if len(history.snapshots) < min_windows:
        return (False, 0, 0.0)

    consecutive_elevated = 0
    ratios = []

    # Walk backwards from most recent
    for snapshot in reversed(history.snapshots):
        ratio = snapshot.sell_pressure_ratio()

        if ratio >= min_ratio:
            consecutive_elevated += 1
            ratios.append(ratio)
        else:
            # Streak broken
            break

    is_persistent = consecutive_elevated >= min_windows
    avg_ratio = statistics.mean(ratios) if ratios else 0.0

    return (is_persistent, consecutive_elevated, avg_ratio)


def calculate_largest_drawdown(history: MarketHistory) -> Optional[float]:
    """
    Calculate largest peak-to-trough price decline in history.

    Args:
        history: MarketHistory object

    Returns:
        Largest drawdown percentage, or None if insufficient data
    """
    if len(history.snapshots) < 2:
        return None

    prices = [s.avg_low for s in history.snapshots if s.avg_low is not None]

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


def calculate_volume_persistence(
    history: MarketHistory,
    spike_threshold: float = 5.0
) -> Tuple[int, float]:
    """
    Calculate how many consecutive windows had elevated volume.

    Args:
        history: MarketHistory object
        spike_threshold: Multiplier vs average volume to consider "elevated"

    Returns:
        Tuple of (consecutive_spike_windows, avg_spike_magnitude)
    """
    if len(history.snapshots) < 2:
        return (0, 1.0)

    # Calculate average historical volume
    volumes = [s.total_volume() for s in history.snapshots]
    avg_volume = statistics.mean(volumes) if volumes else 0

    if avg_volume <= 0:
        return (0, 1.0)

    consecutive_spikes = 0
    magnitudes = []

    # Walk backwards from most recent
    for snapshot in reversed(history.snapshots):
        total_vol = snapshot.total_volume()
        magnitude = total_vol / avg_volume if avg_volume > 0 else 1.0

        if magnitude >= spike_threshold:
            consecutive_spikes += 1
            magnitudes.append(magnitude)
        else:
            # Streak broken
            break

    avg_magnitude = statistics.mean(magnitudes) if magnitudes else 1.0

    return (consecutive_spikes, avg_magnitude)


def calculate_liquidity_score(
    history: MarketHistory,
    current_volume: int
) -> int:
    """
    Calculate liquidity score (0-100) based on volume consistency.

    Consistent volume = good liquidity = high score
    Declining volume = poor liquidity = low score

    Args:
        history: MarketHistory object
        current_volume: Current total volume

    Returns:
        Liquidity score (0-100)
    """
    if len(history.snapshots) < 2:
        # Insufficient history, use current volume only
        if current_volume >= 500:
            return 100
        elif current_volume >= 100:
            return 70
        elif current_volume >= 50:
            return 40
        else:
            return 10

    volumes = [s.total_volume() for s in history.snapshots]

    if not volumes or all(v == 0 for v in volumes):
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


# TODO: Future enhancements when more historical data becomes available:
#
# 1. Trend Acceleration Detection
#    - Calculate rate of change of price decline
#    - Detect if crash is accelerating vs stabilizing
#    - Example: -1% → -2% → -4% (accelerating) vs -3% → -3% → -3% (sustained)
#
# 2. Support/Resistance Levels
#    - Identify price levels where item historically bounced
#    - Warn when breaking through support levels
#    - Example: Item historically bounces at 100k, now at 95k
#
# 3. Recovery Pattern Detection
#    - Detect if price is starting to recover after crash
#    - Pattern: declining → flat → rising
#    - Adjust confidence based on recovery signals
#
# 4. Volume-Price Divergence
#    - Detect when price drops but volume is declining (weak signal)
#    - vs price drops with increasing volume (strong signal)
#    - Refine sell pressure persistence scoring
#
# 5. Correlation Analysis (Multi-Item)
#    - Detect market-wide crashes vs single-item crashes
#    - Example: All rune items crashing = game update
#    - Single item crashing = specific manipulation
#
# 6. Historical Baseline Comparison
#    - Compare current sell pressure to 24-hour / 7-day average
#    - Detect if this is unusual vs normal trading pattern
#    - Example: Item normally has 3x ratio, now 8x is significant
