"""
Monitoring manager for tracking bot and service health.

Responsible for tracking service health, timestamps, and determining
overall bot health status.
"""
import psutil
import os
import logging
from datetime import datetime
from typing import Optional, Dict
from .models import BotStatus, ServiceHealth, HealthState

logger = logging.getLogger(__name__)


class MonitoringManager:
    """
    Manages bot health monitoring and status tracking.

    Tracks health of all subsystems and determines overall bot status.
    Provides methods for subsystems to report success/failure.
    """

    # Health timeout thresholds (in seconds)
    TIMEOUT_SCHEDULER = 180  # 3 minutes
    TIMEOUT_CURRENT_PRICES = 180  # 3 minutes
    TIMEOUT_FIVE_MINUTE = 300  # 5 minutes
    TIMEOUT_HISTORY = 600  # 10 minutes
    TIMEOUT_DISCORD = 60  # 1 minute
    TIMEOUT_ALERTS = 180  # 3 minutes

    def __init__(self, version: str = "v1.0.1"):
        """
        Initialize monitoring manager.

        Args:
            version: Bot version string
        """
        self.version = version
        self.started_at = datetime.now()
        self.previous_crash = False  # Set to True if bot crashed previously

        # Service health tracking
        self._services: Dict[str, ServiceHealth] = {
            'scheduler': ServiceHealth('Scheduler', HealthState.UNKNOWN),
            'current_prices': ServiceHealth('Current Prices', HealthState.UNKNOWN),
            'five_minute_data': ServiceHealth('5 Minute Data', HealthState.UNKNOWN),
            'history_store': ServiceHealth('History Store', HealthState.UNKNOWN),
            'discord': ServiceHealth('Discord', HealthState.UNKNOWN),
            'alerts': ServiceHealth('Alerts', HealthState.UNKNOWN),
        }

        # Previous state for change detection
        self._previous_states: Dict[str, HealthState] = {
            name: HealthState.UNKNOWN for name in self._services
        }

        # Metrics
        self.items_tracked = 0
        self.history_items = 0

    def mark_scheduler_success(self):
        """Mark scheduler subsystem as healthy"""
        self._mark_success('scheduler')

    def mark_current_prices_success(self):
        """Mark current prices API as healthy"""
        self._mark_success('current_prices')

    def mark_five_minute_success(self):
        """Mark 5-minute data API as healthy"""
        self._mark_success('five_minute_data')

    def mark_history_success(self):
        """Mark history store as healthy"""
        self._mark_success('history_store')

    def mark_discord_success(self):
        """Mark Discord connection as healthy"""
        self._mark_success('discord')

    def mark_alerts_success(self):
        """Mark alerts pipeline as healthy"""
        self._mark_success('alerts')

    def mark_scheduler_failure(self, error: str = None):
        """Mark scheduler subsystem as failed"""
        self._mark_failure('scheduler', error)

    def mark_current_prices_failure(self, error: str = None):
        """Mark current prices API as failed"""
        self._mark_failure('current_prices', error)

    def mark_five_minute_failure(self, error: str = None):
        """Mark 5-minute data API as failed"""
        self._mark_failure('five_minute_data', error)

    def mark_history_failure(self, error: str = None):
        """Mark history store as failed"""
        self._mark_failure('history_store', error)

    def mark_discord_failure(self, error: str = None):
        """Mark Discord connection as failed"""
        self._mark_failure('discord', error)

    def mark_alerts_failure(self, error: str = None):
        """Mark alerts pipeline as failed"""
        self._mark_failure('alerts', error)

    def _mark_success(self, service_name: str):
        """
        Mark a service as successful.

        Args:
            service_name: Name of the service
        """
        service = self._services[service_name]
        service.last_success = datetime.now()
        service.last_error = None
        self._update_service_health(service_name)

    def _mark_failure(self, service_name: str, error: Optional[str]):
        """
        Mark a service as failed.

        Args:
            service_name: Name of the service
            error: Optional error message
        """
        service = self._services[service_name]
        service.last_error = error or "Unknown error"
        self._update_service_health(service_name)

    def _update_service_health(self, service_name: str):
        """
        Update health state for a service based on timeout thresholds.

        Args:
            service_name: Name of the service
        """
        service = self._services[service_name]

        # Get timeout threshold for this service
        timeout_map = {
            'scheduler': self.TIMEOUT_SCHEDULER,
            'current_prices': self.TIMEOUT_CURRENT_PRICES,
            'five_minute_data': self.TIMEOUT_FIVE_MINUTE,
            'history_store': self.TIMEOUT_HISTORY,
            'discord': self.TIMEOUT_DISCORD,
            'alerts': self.TIMEOUT_ALERTS,
        }
        timeout_threshold = timeout_map.get(service_name, 300)

        # Determine health state
        if service.last_success is None:
            # Never succeeded
            service.state = HealthState.UNKNOWN
        else:
            seconds_since = service.seconds_since_success()

            if seconds_since < timeout_threshold:
                service.state = HealthState.HEALTHY
            elif seconds_since < timeout_threshold * 1.5:
                service.state = HealthState.WARNING
            else:
                service.state = HealthState.UNHEALTHY

    def update_metrics(self, items_tracked: int = None, history_items: int = None):
        """
        Update bot metrics.

        Args:
            items_tracked: Number of items currently tracked
            history_items: Number of items in history store
        """
        if items_tracked is not None:
            self.items_tracked = items_tracked
        if history_items is not None:
            self.history_items = history_items

    def get_memory_usage(self) -> float:
        """
        Get current memory usage in megabytes.

        Returns:
            Memory usage in MB
        """
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0

    def determine_overall_health(self) -> HealthState:
        """
        Determine overall bot health based on service states.

        Returns:
            Overall health state
        """
        # Update all service health states
        for service_name in self._services:
            self._update_service_health(service_name)

        # Critical services: scheduler, current_prices, discord
        critical_services = ['scheduler', 'current_prices', 'discord']

        # If any critical service is unhealthy, bot is unhealthy
        for service_name in critical_services:
            if self._services[service_name].state == HealthState.UNHEALTHY:
                return HealthState.UNHEALTHY

        # If any critical service has warning, bot has warning
        for service_name in critical_services:
            if self._services[service_name].state == HealthState.WARNING:
                return HealthState.WARNING

        # If all critical services are healthy or unknown, bot is healthy
        return HealthState.HEALTHY

    def get_status(self) -> BotStatus:
        """
        Get complete bot status snapshot.

        Returns:
            BotStatus object with current state
        """
        # Update all service health states
        for service_name in self._services:
            self._update_service_health(service_name)

        overall_health = self.determine_overall_health()

        return BotStatus(
            state=overall_health,
            version=self.version,
            started_at=self.started_at,
            scheduler=self._services['scheduler'],
            current_prices=self._services['current_prices'],
            five_minute_data=self._services['five_minute_data'],
            history_store=self._services['history_store'],
            discord=self._services['discord'],
            alerts=self._services['alerts'],
            items_tracked=self.items_tracked,
            history_items=self.history_items,
            memory_mb=self.get_memory_usage()
        )

    def get_state_changes(self) -> Dict[str, tuple[HealthState, HealthState]]:
        """
        Detect state changes since last check.

        Returns:
            Dict mapping service names to (old_state, new_state) tuples
            Only includes services that changed state.
        """
        changes = {}

        for service_name, service in self._services.items():
            old_state = self._previous_states[service_name]
            new_state = service.state

            if old_state != new_state:
                changes[service_name] = (old_state, new_state)
                self._previous_states[service_name] = new_state

        return changes

    def has_state_changed(self) -> bool:
        """
        Check if any service state has changed.

        Returns:
            True if any service changed state
        """
        return len(self.get_state_changes()) > 0
