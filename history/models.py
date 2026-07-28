"""
Generic market snapshot and history models.

These models store raw observed market state without any business logic.
Consumers (crash detection, Best Seen, flipping) derive insights from these primitives.
"""

from typing import List, Optional
from datetime import datetime


class MarketSnapshot:
    """
    Single market observation for an item at a specific timestamp.

    Stores raw observed market state. No business logic.

    Price fields are always populated from current_prices.
    Volume fields are optional (populated from five_min_data when available).
    """
    def __init__(
        self,
        timestamp: float,
        avg_low: Optional[int],
        avg_high: Optional[int],
        buy_volume: Optional[int] = None,
        sell_volume: Optional[int] = None
    ):
        self.timestamp = timestamp
        self.avg_low = avg_low
        self.avg_high = avg_high
        self.buy_volume = buy_volume
        self.sell_volume = sell_volume


class MarketHistory:
    """
    Rolling chronological history of market snapshots for a single item.

    Maintains bounded list of observations with automatic expiration.
    """
    def __init__(self, max_snapshots: int = 20):
        """
        Initialize market history for an item.

        Args:
            max_snapshots: Maximum number of snapshots to retain (default 20 = ~20 minutes at 60s intervals)
        """
        self.snapshots: List[MarketSnapshot] = []
        self.max_snapshots = max_snapshots

    def add_snapshot(self, snapshot: MarketSnapshot):
        """
        Add a new snapshot and enforce max_snapshots limit.

        Args:
            snapshot: MarketSnapshot to add
        """
        self.snapshots.append(snapshot)

        # Keep only most recent max_snapshots
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots = self.snapshots[-self.max_snapshots:]

    def expire_old_snapshots(self, max_age_seconds: int):
        """
        Remove snapshots older than max_age.

        Args:
            max_age_seconds: Maximum age in seconds
        """
        if not self.snapshots:
            return

        cutoff_time = datetime.now().timestamp() - max_age_seconds

        self.snapshots = [
            s for s in self.snapshots
            if s.timestamp >= cutoff_time
        ]

    def get_recent_snapshots(self, lookback_minutes: int) -> List[MarketSnapshot]:
        """
        Get snapshots from the last N minutes (timestamp-based).

        Args:
            lookback_minutes: Number of minutes to look back

        Returns:
            List of snapshots within the time window (oldest first)
        """
        if lookback_minutes <= 0 or not self.snapshots:
            return []

        cutoff_time = datetime.now().timestamp() - (lookback_minutes * 60)

        return [
            s for s in self.snapshots
            if s.timestamp >= cutoff_time
        ]

    def get_latest_snapshot(self) -> Optional[MarketSnapshot]:
        """
        Get the most recent snapshot.

        Returns:
            Most recent MarketSnapshot, or None if no history
        """
        if not self.snapshots:
            return None
        return self.snapshots[-1]

    def has_history(self, min_snapshots: int = 1) -> bool:
        """
        Check if history exists with at least min_snapshots.

        Args:
            min_snapshots: Minimum required snapshots

        Returns:
            True if sufficient history exists
        """
        return len(self.snapshots) >= min_snapshots
