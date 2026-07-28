"""
Generic rolling market history storage service.

Provides "dumb" storage primitives. No business logic.
Consumers derive insights by querying stored snapshots.
"""

import logging
from typing import Dict, Optional, Iterator, Tuple
from datetime import datetime

from history.models import MarketSnapshot, MarketHistory

logger = logging.getLogger(__name__)


class HistoryStore:
    """
    Central registry for rolling market history across all items.

    Responsibilities:
    - Store snapshots
    - Expire old snapshots
    - Provide generic query primitives

    Non-responsibilities (belong in domain/alerts):
    - Calculate best buy prices
    - Compute crash scores
    - Determine profitability
    - Apply business filters
    """

    def __init__(self, max_snapshots: int = 20, max_age_seconds: int = 3900):
        """
        Initialize history store.

        Args:
            max_snapshots: Maximum snapshots per item (default 20 = ~20 minutes)
            max_age_seconds: Maximum snapshot age (default 3900 = 65 minutes)
        """
        self._histories: Dict[int, MarketHistory] = {}
        self.max_snapshots = max_snapshots
        self.max_age_seconds = max_age_seconds

    def add_snapshot(self, item_id: int, snapshot: MarketSnapshot):
        """
        Add a single snapshot for an item.

        Args:
            item_id: Item ID
            snapshot: MarketSnapshot to add
        """
        if item_id not in self._histories:
            self._histories[item_id] = MarketHistory(max_snapshots=self.max_snapshots)

        self._histories[item_id].add_snapshot(snapshot)

    def add_snapshots_batch(self, snapshots: Dict[int, MarketSnapshot]):
        """
        Add multiple snapshots in a single batch.

        This is the primary collection method called by the scheduler.

        Args:
            snapshots: Dict mapping item_id -> MarketSnapshot
        """
        for item_id, snapshot in snapshots.items():
            self.add_snapshot(item_id, snapshot)

        logger.info(f"Added {len(snapshots)} snapshots to history store")

    def expire_old_snapshots(self):
        """
        Remove snapshots older than max_age_seconds across all items.

        Should be called after each batch collection.
        """
        for history in self._histories.values():
            history.expire_old_snapshots(self.max_age_seconds)

    def get_history(self, item_id: int) -> Optional[MarketHistory]:
        """
        Get full MarketHistory for an item.

        Args:
            item_id: Item ID

        Returns:
            MarketHistory object, or None if no history exists
        """
        return self._histories.get(item_id)

    def get_recent_snapshots(self, item_id: int, lookback_minutes: int) -> list:
        """
        Get snapshots for an item from the last N minutes.

        Args:
            item_id: Item ID
            lookback_minutes: Number of minutes to look back

        Returns:
            List of MarketSnapshot objects (oldest first), or empty list if no history
        """
        history = self.get_history(item_id)
        if history is None:
            return []

        return history.get_recent_snapshots(lookback_minutes)

    def get_latest_snapshot(self, item_id: int) -> Optional[MarketSnapshot]:
        """
        Get the most recent snapshot for an item.

        Args:
            item_id: Item ID

        Returns:
            Most recent MarketSnapshot, or None if no history
        """
        history = self.get_history(item_id)
        if history is None:
            return None

        return history.get_latest_snapshot()

    def has_history(self, item_id: int, min_snapshots: int = 1) -> bool:
        """
        Check if an item has history with at least min_snapshots.

        Args:
            item_id: Item ID
            min_snapshots: Minimum required snapshots

        Returns:
            True if sufficient history exists
        """
        history = self.get_history(item_id)
        if history is None:
            return False

        return history.has_history(min_snapshots)

    def iter_history(self) -> Iterator[Tuple[int, MarketHistory]]:
        """
        Iterate over all items with history.

        Yields:
            Tuples of (item_id, MarketHistory)
        """
        return iter(self._histories.items())

    def get_item_count(self) -> int:
        """
        Get the total number of items with history.

        Returns:
            Count of items
        """
        return len(self._histories)
