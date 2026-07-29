"""
Bot health monitoring subsystem.

Provides operational visibility without spamming Discord.
"""
from .models import BotStatus, ServiceHealth, HealthState
from .manager import MonitoringManager
from .renderer import MonitoringRenderer
from .crash_handler import CrashHandler, run_with_crash_detection

__all__ = [
    'BotStatus',
    'ServiceHealth',
    'HealthState',
    'MonitoringManager',
    'MonitoringRenderer',
    'CrashHandler',
    'run_with_crash_detection',
]
