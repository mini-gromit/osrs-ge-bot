"""
Historical market data infrastructure.

Single source of historical market information for the entire application.
Owns retrieval and normalization of historical price and volume data.

Public Interface:
    - HistoryClient class - Primary interface for historical data
        .get_price_history()
        .get_volume_history()
        .get_snapshot_at()

All historical responses are normalized to consistent internal models
regardless of underlying API source.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class HistoricalDataPoint:
    """
    Normalized historical market data point.

    Represents a single point in time for an item's price and volume data.
    All historical data from any source is converted to this format.

    Fields:
        timestamp: Unix timestamp (seconds since epoch)
        high_price: Average high (sell) price, or None if unavailable
        low_price: Average low (buy) price, or None if unavailable
        high_volume: Volume traded at high price, or None if unavailable
        low_volume: Volume traded at low price, or None if unavailable

    Note:
        - Recent data typically has all fields populated
        - Historical data may have None for volume fields
        - Prices are in GP (gold pieces)
        - Volumes are trade counts
    """
    timestamp: int
    high_price: Optional[int] = None
    low_price: Optional[int] = None
    high_volume: Optional[int] = None
    low_volume: Optional[int] = None


class HistoryClient:
    """
    Client for accessing historical market data.

    Provides clean, normalized interface to historical price and volume data.
    Hides all API source details and data format differences.

    Usage:
        from api import history
        from api.client import OSRSAPIClient

        client = OSRSAPIClient()
        history_client = history.HistoryClient(client)

        # Get price history
        prices = history_client.get_price_history(item_id=2, days=30)

        # Get volume history
        volumes = history_client.get_volume_history(item_id=2, days=90)

        # Get historical snapshot
        snapshot = history_client.get_snapshot_at(timestamp=1672330200)
    """

    def __init__(self, api_client):
        """
        Initialize history client with API client.

        Args:
            api_client: OSRSAPIClient instance for HTTP communication
        """
        self.client = api_client

    def get_price_history(
        self,
        item_id: int,
        days: int = 90
    ) -> List[HistoricalDataPoint]:
        """
        Get historical price data for an item.

        Returns normalized historical data points with prices and volumes
        (when available). Automatically selects best data source and time
        resolution based on requested period.

        Args:
            item_id: Item ID to fetch history for
            days: Number of days of historical data (default: 90)

        Returns:
            List of HistoricalDataPoint objects, ordered chronologically.

        Example:
            prices = history_client.get_price_history(item_id=2, days=30)
            for point in prices:
                print(f"At {point.timestamp}:")
                print(f"  High: {point.high_price} GP")
                print(f"  Low: {point.low_price} GP")
                print(f"  Volume: {point.high_volume} / {point.low_volume}")

        Note:
            - Recent data (≤365 days) includes volume information
            - Historical data (>365 days) may lack volume for early periods
            - Data availability starts from 2015, volume from March 2021
        """
        raw_data = _fetch_hybrid_history(
            self.client,
            item_id,
            days,
            include_volumes=True
        )
        return _normalize_historical_data(raw_data)

    def get_volume_history(
        self,
        item_id: int,
        days: int = 90
    ) -> List[HistoricalDataPoint]:
        """
        Get historical trading volume data for an item.

        Returns normalized data points with focus on volume information.
        Automatically limits time range to ensure volume data availability.

        Args:
            item_id: Item ID to fetch history for
            days: Number of days of volume history (default: 90, max: 365)

        Returns:
            List of HistoricalDataPoint objects with volume data.

        Example:
            volumes = history_client.get_volume_history(item_id=2, days=30)
            total_high_volume = sum(p.high_volume or 0 for p in volumes)
            print(f"Total sell volume: {total_high_volume}")

        Note:
            - Volume data most reliable for recent periods (≤365 days)
            - Requests beyond 365 days automatically limited
            - Historical volume available from March 2021 onwards
        """
        # Limit to 365 days to ensure volume availability
        limited_days = min(days, 365)
        raw_data = _fetch_hybrid_history(
            self.client,
            item_id,
            limited_days,
            include_volumes=True
        )
        return _normalize_historical_data(raw_data)

    def get_snapshot_at(
        self,
        timestamp: int,
        resolution: str = "1h"
    ) -> Optional[Dict[str, HistoricalDataPoint]]:
        """
        Get market snapshot at a specific historical timestamp.

        Retrieves the complete market state (all items) at a given point in
        time. Returns normalized data for all available items.

        Args:
            timestamp: Unix timestamp (seconds since epoch)
            resolution: Data resolution - '5m' or '1h' (default: '1h')

        Returns:
            Dictionary mapping item IDs (as strings) to HistoricalDataPoint,
            or None if snapshot unavailable.

        Example:
            import time
            one_hour_ago = int(time.time()) - 3600
            snapshot = history_client.get_snapshot_at(one_hour_ago)

            if snapshot:
                for item_id, point in snapshot.items():
                    print(f"Item {item_id}: {point.high_price} GP")

        Use Cases:
            - Compare current market to past state
            - Backtest trading strategies
            - Analyze market behavior at specific events
            - Reconstruct historical market conditions
        """
        raw_snapshot = self.client.fetch_timestamp_snapshot(timestamp, resolution)
        if not raw_snapshot:
            return None

        # Normalize snapshot data
        normalized = {}
        for item_id, data in raw_snapshot.items():
            normalized[item_id] = HistoricalDataPoint(
                timestamp=timestamp,
                high_price=data.get('avgHighPrice'),
                low_price=data.get('avgLowPrice'),
                high_volume=data.get('highPriceVolume'),
                low_volume=data.get('lowPriceVolume')
            )
        return normalized


# ============================================================================
# Normalization Functions
# ============================================================================

def _normalize_historical_data(raw_data: List[Dict]) -> List[HistoricalDataPoint]:
    """
    Normalize raw API response to consistent HistoricalDataPoint format.

    Handles multiple input formats from different API sources and converts
    them all to the standardized HistoricalDataPoint model.

    Supported input formats:
    1. Real-Time API (timeseries):
       {'timestamp': int, 'avgHighPrice': int, 'avgLowPrice': int,
        'highPriceVolume': int, 'lowPriceVolume': int}

    2. Exchange API:
       {'id': str, 'price': int, 'volume': int|None, 'timestamp': int}

    Args:
        raw_data: List of raw data dictionaries from any API source

    Returns:
        List of normalized HistoricalDataPoint objects
    """
    if not raw_data:
        return []

    # Detect format based on first entry
    first_entry = raw_data[0]

    if 'avgHighPrice' in first_entry:
        # Real-Time API format (timeseries)
        return _normalize_timeseries_data(raw_data)
    elif 'price' in first_entry:
        # Exchange API format
        return _normalize_exchange_data(raw_data)
    else:
        # Unknown format - return empty
        return []


def _normalize_timeseries_data(data: List[Dict]) -> List[HistoricalDataPoint]:
    """
    Normalize Real-Time API (timeseries) format to HistoricalDataPoint.

    Input format:
        {
            'timestamp': 1672330200,
            'avgHighPrice': 162,
            'avgLowPrice': 155,
            'highPriceVolume': 204403,
            'lowPriceVolume': 11966
        }

    Args:
        data: List of timeseries data dictionaries

    Returns:
        List of HistoricalDataPoint objects
    """
    normalized = []
    for entry in data:
        point = HistoricalDataPoint(
            timestamp=entry.get('timestamp'),
            high_price=entry.get('avgHighPrice'),
            low_price=entry.get('avgLowPrice'),
            high_volume=entry.get('highPriceVolume'),
            low_volume=entry.get('lowPriceVolume')
        )
        normalized.append(point)
    return normalized


def _normalize_exchange_data(data: List[Dict]) -> List[HistoricalDataPoint]:
    """
    Normalize Exchange API format to HistoricalDataPoint.

    Input format:
        {
            'id': '2',
            'price': 260,
            'volume': 29319905,  # May be None
            'timestamp': 1784150188000  # Milliseconds!
        }

    Args:
        data: List of exchange data dictionaries

    Returns:
        List of HistoricalDataPoint objects

    Note:
        Exchange API timestamps are in milliseconds, converted to seconds
    """
    normalized = []
    for entry in data:
        # Exchange API provides single 'price' (midpoint)
        # We don't have separate high/low, so use same value for both
        price = entry.get('price')
        volume = entry.get('volume')

        # Exchange API uses millisecond timestamps - convert to seconds
        timestamp_ms = entry.get('timestamp', 0)
        timestamp = int(timestamp_ms / 1000) if timestamp_ms else 0

        point = HistoricalDataPoint(
            timestamp=timestamp,
            high_price=price,
            low_price=price,  # Exchange API doesn't separate high/low
            high_volume=volume,  # Exchange API doesn't separate high/low volumes
            low_volume=volume
        )
        normalized.append(point)
    return normalized


# ============================================================================
# Internal Implementation
# ============================================================================

def _fetch_hybrid_history(
    client,
    item_id: int,
    days: int,
    include_volumes: bool
) -> List[Dict]:
    """
    Internal: Fetch historical data using optimal data source.

    Intelligently selects between available data sources based on:
    - Requested time period
    - Volume data requirements
    - Data source limitations

    Strategy:
    - Recent data with volumes: Use high-frequency API (timeseries)
    - Medium-term without volumes: Use exchange API (last 90 days)
    - Long-term without volumes: Use exchange API (all history)

    Args:
        client: OSRSAPIClient instance
        item_id: Item ID to fetch
        days: Number of days requested
        include_volumes: Whether volume data is required

    Returns:
        List of raw data dictionaries (format varies by source)
    """
    if days <= 365 and include_volumes:
        # Use timeseries API - provides volume data with optimal resolution
        timestep = _select_timestep(days)
        return client.fetch_timeseries(item_id, timestep)
    elif days <= 90:
        # Use exchange API - last 90 days without volume requirement
        return client.fetch_exchange_history(item_id, endpoint="last90d")
    else:
        # Use exchange API - complete history (may lack volumes for old data)
        return client.fetch_exchange_history(item_id, endpoint="all")


def _select_timestep(days: int) -> str:
    """
    Internal: Select optimal time resolution for requested period.

    Maps requested days to the finest resolution that fits within
    API data point limits (365 points maximum).

    Args:
        days: Number of days of history requested

    Returns:
        Time resolution: '5m', '1h', '6h', or '24h'

    Resolution Coverage:
        '5m':  Up to 1.3 days  (365 × 5 minutes)
        '1h':  Up to 15 days   (365 hours)
        '6h':  Up to 91 days   (365 × 6 hours)
        '24h': Up to 365 days  (365 days)
    """
    if days <= 1:
        return "5m"
    elif days <= 15:
        return "1h"
    elif days <= 91:
        return "6h"
    else:
        return "24h"


# ============================================================================
# Backward Compatibility (Legacy Function-Based API)
# ============================================================================

def get_price_history(
    client,
    item_id: int,
    days: int = 90
) -> List[HistoricalDataPoint]:
    """
    Legacy function-based API. Use HistoryClient class instead.

    Maintained for backward compatibility.
    New code should use: HistoryClient(client).get_price_history(...)
    """
    history_client = HistoryClient(client)
    return history_client.get_price_history(item_id, days)


def get_volume_history(
    client,
    item_id: int,
    days: int = 90
) -> List[HistoricalDataPoint]:
    """
    Legacy function-based API. Use HistoryClient class instead.

    Maintained for backward compatibility.
    New code should use: HistoryClient(client).get_volume_history(...)
    """
    history_client = HistoryClient(client)
    return history_client.get_volume_history(item_id, days)


def get_snapshot_at(
    client,
    timestamp: int,
    resolution: str = "1h"
) -> Optional[Dict[str, HistoricalDataPoint]]:
    """
    Legacy function-based API. Use HistoryClient class instead.

    Maintained for backward compatibility.
    New code should use: HistoryClient(client).get_snapshot_at(...)
    """
    history_client = HistoryClient(client)
    return history_client.get_snapshot_at(timestamp, resolution)
