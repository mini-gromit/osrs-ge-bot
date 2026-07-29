"""
Pure data models for bot health monitoring.

Contains only data structures with no Discord code or monitoring logic.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class HealthState(Enum):
    """Health state for a service or overall bot"""
    HEALTHY = "healthy"
    WARNING = "warning"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """
    Health status for a single service or subsystem.

    Attributes:
        name: Display name of the service
        state: Current health state
        last_success: Timestamp of last successful execution (None if never)
        last_error: Optional error message from last failure
    """
    name: str
    state: HealthState
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None

    def seconds_since_success(self) -> Optional[float]:
        """
        Calculate seconds since last successful execution.

        Returns:
            Seconds since last success, or None if never succeeded
        """
        if self.last_success is None:
            return None
        return (datetime.now() - self.last_success).total_seconds()


@dataclass
class BotStatus:
    """
    Complete bot status snapshot.

    Attributes:
        state: Overall bot health state
        version: Bot version string
        started_at: When the bot started
        scheduler: Health status of scheduler subsystem
        current_prices: Health status of current prices API
        five_minute_data: Health status of 5-minute data API
        history_store: Health status of history store
        discord: Health status of Discord connection
        alerts: Health status of alert pipeline
        items_tracked: Number of items currently tracked
        history_items: Number of items in history store
        memory_mb: Memory usage in megabytes
    """
    state: HealthState
    version: str
    started_at: datetime
    scheduler: ServiceHealth
    current_prices: ServiceHealth
    five_minute_data: ServiceHealth
    history_store: ServiceHealth
    discord: ServiceHealth
    alerts: ServiceHealth
    items_tracked: int = 0
    history_items: int = 0
    memory_mb: float = 0.0

    def uptime_seconds(self) -> float:
        """Calculate uptime in seconds"""
        return (datetime.now() - self.started_at).total_seconds()

    def uptime_formatted(self) -> str:
        """
        Format uptime as human-readable string.

        Returns:
            Uptime string like "2d 18h 42m" or "18h 42m" or "42m"
        """
        seconds = self.uptime_seconds()
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0 or days > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")

        return " ".join(parts)
