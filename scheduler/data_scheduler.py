"""
Data refresh scheduler for market data.

Coordinates refresh intervals for different data sources without coupling
timing logic to business logic.
"""
import time
import logging
from typing import Optional
from engine import OSRSAlchemyFlippingCalculator
import config

logger = logging.getLogger(__name__)


class DataScheduler:
    """
    Manages refresh timing for different market data sources.

    Wraps the calculator and tracks when each data source was last fetched.
    Only calls fetch methods when data is stale based on configured intervals.
    """

    def __init__(self, calculator: OSRSAlchemyFlippingCalculator):
        """
        Initialize scheduler with a calculator instance.

        Args:
            calculator: The calculator to coordinate refreshes for
        """
        self.calculator = calculator

        # Track last fetch timestamps
        self._last_fetch_times = {
            'item_mapping': 0,
            'current_prices': 0,
            'volume_data': 0,
            'five_minute_data': 0,
            'timeseries': 0,
        }

        # Refresh intervals from config (in seconds)
        self._intervals = {
            'item_mapping': config.REFRESH_INTERVAL_ITEM_MAPPING,
            'current_prices': config.REFRESH_INTERVAL_CURRENT_PRICES,
            'volume_data': config.REFRESH_INTERVAL_VOLUME_DATA,
            'five_minute_data': config.REFRESH_INTERVAL_FIVE_MINUTE_DATA,
            'timeseries': config.REFRESH_INTERVAL_TIMESERIES,
        }

    def _is_stale(self, source: str) -> bool:
        """
        Check if a data source needs refreshing.

        Args:
            source: Name of the data source

        Returns:
            True if data is stale and should be refreshed
        """
        current_time = time.time()
        last_fetch = self._last_fetch_times[source]
        interval = self._intervals[source]

        return (current_time - last_fetch) >= interval

    def refresh_item_mapping(self, force: bool = False) -> bool:
        """
        Refresh item mapping if stale.

        Args:
            force: If True, refresh regardless of staleness

        Returns:
            True if data was fetched, False if skipped or failed
        """
        if not force and not self._is_stale('item_mapping'):
            return False

        logger.debug("Refreshing item mapping...")
        success = self.calculator.fetch_item_mapping()

        if success:
            self._last_fetch_times['item_mapping'] = time.time()
            logger.info("Item mapping refreshed successfully")
        else:
            logger.warning("Failed to refresh item mapping")

        return success

    def refresh_current_prices(self, force: bool = False) -> bool:
        """
        Refresh current prices if stale.

        Args:
            force: If True, refresh regardless of staleness

        Returns:
            True if data was fetched, False if skipped or failed
        """
        if not force and not self._is_stale('current_prices'):
            return False

        logger.debug("Refreshing current prices...")
        success = self.calculator.fetch_current_prices()

        if success:
            self._last_fetch_times['current_prices'] = time.time()
            logger.debug("Current prices refreshed successfully")
        else:
            logger.warning("Failed to refresh current prices")

        return success

    def refresh_volume_data(self, force: bool = False) -> bool:
        """
        Refresh volume data if stale.

        Args:
            force: If True, refresh regardless of staleness

        Returns:
            True if data was fetched, False if skipped or failed
        """
        if not force and not self._is_stale('volume_data'):
            return False

        logger.debug("Refreshing volume data...")
        success = self.calculator.fetch_volume_data()

        if success:
            self._last_fetch_times['volume_data'] = time.time()
            logger.debug("Volume data refreshed successfully")
        else:
            logger.warning("Failed to refresh volume data")

        return success

    def refresh_five_minute_data(self, force: bool = False) -> bool:
        """
        Refresh 5-minute price data if stale.

        Args:
            force: If True, refresh regardless of staleness

        Returns:
            True if data was fetched, False if skipped or failed
        """
        if not force and not self._is_stale('five_minute_data'):
            return False

        logger.debug("Refreshing 5-minute data...")
        success = self.calculator.fetch_five_minute_data()

        if success:
            self._last_fetch_times['five_minute_data'] = time.time()
            logger.debug("5-minute data refreshed successfully")
        else:
            logger.warning("Failed to refresh 5-minute data")

        return success

    def refresh_all(self, force: bool = False) -> bool:
        """
        Refresh all data sources based on their staleness.

        Args:
            force: If True, refresh all sources regardless of staleness

        Returns:
            True if all critical refreshes succeeded, False otherwise
        """
        logger.info("Refreshing market data...")

        # Item mapping is critical - must succeed
        if not self.refresh_item_mapping(force):
            if self._last_fetch_times['item_mapping'] == 0:
                logger.error("Item mapping never loaded")
                return False

        # Current prices are critical - must succeed
        if not self.refresh_current_prices(force):
            if self._last_fetch_times['current_prices'] == 0:
                logger.error("Current prices never loaded")
                return False

        # Volume and 5-minute data are optional but helpful
        self.refresh_volume_data(force)
        self.refresh_five_minute_data(force)

        return True

    def get_last_refresh_time(self, source: str) -> float:
        """
        Get the timestamp when a data source was last refreshed.

        Args:
            source: Name of the data source

        Returns:
            Unix timestamp of last refresh, or 0 if never refreshed
        """
        return self._last_fetch_times.get(source, 0)
