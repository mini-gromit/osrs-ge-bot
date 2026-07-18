"""
Notification Policy Layer - Filters MarketEvents into NotificationDecisions.

Provides:
- NotificationDecision: Frontend-independent notification decision model
- AlertPolicy: Policy engine for filtering MarketEvents
- PreferenceStore: Interface for user preference storage
- JsonPreferenceStore: JSON file-based preference storage
- NotificationQueue: Batching queue with timing logic
"""
from .models import NotificationDecision
from .policy import AlertPolicy
from .preference_store import PreferenceStore, JsonPreferenceStore
from .queue import NotificationQueue

__all__ = [
    'NotificationDecision',
    'AlertPolicy',
    'PreferenceStore',
    'JsonPreferenceStore',
    'NotificationQueue',
]
