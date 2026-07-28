"""
Generic market history subsystem.

Provides reusable rolling history storage and query primitives.

Public API:
    - MarketSnapshot: Single market observation
    - MarketHistory: Rolling history for one item
    - HistoryStore: Central registry for all items

Design Principles:
    - Store raw observations only
    - No business logic
    - Timestamp-based queries
    - Optional volume data
    - Reusable across all consumers
"""

from history.models import MarketSnapshot, MarketHistory
from history.store import HistoryStore

__all__ = [
    'MarketSnapshot',
    'MarketHistory',
    'HistoryStore'
]
