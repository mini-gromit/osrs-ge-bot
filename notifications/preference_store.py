"""
User preference storage abstraction for notification settings.

Defines PreferenceStore interface and provides JsonPreferenceStore implementation.
Allows future migration to SQLite/Postgres without changing AlertPolicy.
"""
import json
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Set, Optional
import config

logger = logging.getLogger(__name__)


class PreferenceStore(ABC):
    """
    Abstract interface for user notification preferences.

    AlertPolicy depends on this interface, not a specific implementation.
    Allows future migration to database storage without changing AlertPolicy.
    """

    @abstractmethod
    def is_subscribed(self, user_id: int, notification_type: str) -> bool:
        """Check if user is subscribed to notification type."""
        pass

    @abstractmethod
    def get_subscribed_users(self, notification_type: str) -> Set[int]:
        """Get all users subscribed to a notification type."""
        pass

    @abstractmethod
    def get_min_severity(self, user_id: int, notification_type: str) -> int:
        """Get user's minimum severity threshold (0-100)."""
        pass

    @abstractmethod
    def get_cooldown_minutes(self, user_id: int) -> int:
        """Get user's cooldown period in minutes."""
        pass

    @abstractmethod
    def set_min_severity(self, user_id: int, notification_type: str, severity: int):
        """Set user's minimum severity threshold."""
        pass

    @abstractmethod
    def set_cooldown(self, user_id: int, minutes: int):
        """Set user's cooldown period."""
        pass

    @abstractmethod
    def get_profit_tier_config(self, notification_type: str) -> Dict:
        """
        Get profit tier configuration for notification type.

        Returns dict with keys:
            - min_profit: Minimum profit required (int)
            - max_profit: Maximum profit allowed (int or None for unlimited)
            - f2p_only: Whether to filter to F2P items only (bool)

        Args:
            notification_type: Type of notification

        Returns:
            Tier configuration dict
        """
        pass

    @abstractmethod
    def get_user_min_profit(self, user_id: int, notification_type: str) -> int:
        """
        Get user's minimum profit threshold for alchemy notifications.

        Args:
            user_id: User ID
            notification_type: Type of notification ('all_alchs' or 'f2p_alchs')

        Returns:
            Minimum profit threshold in gp
        """
        pass

    @abstractmethod
    def set_user_min_profit(self, user_id: int, notification_type: str, min_profit: int):
        """
        Set user's minimum profit threshold for alchemy notifications.

        Args:
            user_id: User ID
            notification_type: Type of notification ('all_alchs' or 'f2p_alchs')
            min_profit: Minimum profit threshold in gp
        """
        pass


class JsonPreferenceStore(PreferenceStore):
    """
    JSON file-based preference storage implementation.

    Initial implementation using JSON files for persistence.
    Can be replaced with database implementation later without
    changing AlertPolicy code.
    """

    # Default preferences for personal notifications
    # Public channel tiers (super_hot, hot_items) are not included here
    DEFAULT_PREFERENCES = {
        'all_alchs': {
            'min_profit': config.DEFAULT_ALL_ALCHS_MIN_PROFIT
        },
        'f2p_alchs': {
            'min_profit': config.DEFAULT_F2P_ALCHS_MIN_PROFIT
        },
        'crash_risk': {
            'min_severity': config.DEFAULT_MIN_SEVERITY
        },
        'flipping_trend': {
            'min_severity': config.DEFAULT_MIN_SEVERITY
        }
    }

    # Legacy: Profit tier definitions for channel notifications only
    # Kept for backward compatibility with get_profit_tier_config()
    # Used by channel notification code, not personal notifications
    PROFIT_TIERS = {
        'super_hot': {
            'min_profit': config.DEFAULT_SUPER_HOT_MIN_PROFIT,
            'max_profit': None,
            'f2p_only': False
        },
        'hot_items': {
            'min_profit': config.DEFAULT_HOT_ITEMS_MIN_PROFIT,
            'max_profit': config.DEFAULT_HOT_ITEMS_MAX_PROFIT,
            'f2p_only': False
        },
        'all_alchs': {
            'min_profit': config.DEFAULT_ALL_ALCHS_MIN_PROFIT,
            'max_profit': None,
            'f2p_only': False
        },
        'f2p_alchs': {
            'min_profit': config.DEFAULT_F2P_ALCHS_MIN_PROFIT,
            'max_profit': None,
            'f2p_only': True
        }
    }

    def __init__(
        self,
        filename: str = 'user_preferences.json',
        subscription_manager=None
    ):
        """
        Initialize JSON preference store.

        Args:
            filename: Path to JSON file for storing preferences
            subscription_manager: Optional UserNotificationManager for subscriptions
        """
        self.filename = filename
        self.subscription_manager = subscription_manager
        self.preferences: Dict[int, Dict] = {}
        self.load_preferences()

    def load_preferences(self):
        """Load user preferences from JSON file with migration support."""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    raw_prefs = data.get('preferences', {})
                    self.preferences = {}

                    for uid, prefs in raw_prefs.items():
                        user_id = int(uid)
                        self.preferences[user_id] = self._migrate_user_preferences(prefs)

                logger.debug(f"Loaded preferences for {len(self.preferences)} users")
        except Exception as e:
            logger.error(f"Error loading preferences: {e}")
            self.preferences = {}

    def _migrate_user_preferences(self, prefs: Dict) -> Dict:
        """
        Migrate user preferences from flat format to grouped format.

        Old format: {"all_alchs_min_profit": 500, "crash_risk_min_severity": 60}
        New format: {"all_alchs": {"min_profit": 500}, "crash_risk": {"min_severity": 60}}

        Args:
            prefs: User preferences dict (may be old or new format)

        Returns:
            Preferences in new grouped format
        """
        migrated = {}

        # Preserve cooldown_minutes at top level (global setting)
        if 'cooldown_minutes' in prefs:
            migrated['cooldown_minutes'] = prefs['cooldown_minutes']

        # Check if already migrated (has grouped structure)
        has_grouped = any(
            isinstance(prefs.get(ntype), dict)
            for ntype in self.DEFAULT_PREFERENCES.keys()
        )

        if has_grouped:
            # Already in new format, copy grouped preferences
            for ntype in self.DEFAULT_PREFERENCES.keys():
                if ntype in prefs and isinstance(prefs[ntype], dict):
                    migrated[ntype] = prefs[ntype]
            return migrated

        # Migrate from flat format
        for ntype in self.DEFAULT_PREFERENCES.keys():
            group = {}

            # Migrate min_profit for alchemy notifications
            if ntype in ['all_alchs', 'f2p_alchs']:
                old_key = f'{ntype}_min_profit'
                if old_key in prefs:
                    group['min_profit'] = prefs[old_key]

            # Migrate min_severity for other notification types
            else:
                old_key = f'{ntype}_min_severity'
                if old_key in prefs:
                    group['min_severity'] = prefs[old_key]

            # Only add if we migrated something
            if group:
                migrated[ntype] = group

        return migrated

    def save_preferences(self):
        """Save user preferences to JSON file."""
        try:
            with open(self.filename, 'w') as f:
                json.dump({
                    'preferences': {
                        str(uid): prefs
                        for uid, prefs in self.preferences.items()
                    }
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")

    def is_subscribed(self, user_id: int, notification_type: str) -> bool:
        """
        Check if user is subscribed to notification type.

        Delegates to UserNotificationManager if available, otherwise returns True.
        """
        if self.subscription_manager:
            subscribed_users = self.subscription_manager.get_subscribers_for_type(
                notification_type
            )
            return user_id in subscribed_users
        return True

    def get_subscribed_users(self, notification_type: str) -> Set[int]:
        """
        Get all users subscribed to a notification type.

        Delegates to UserNotificationManager if available.
        """
        if self.subscription_manager:
            return self.subscription_manager.get_subscribers_for_type(
                notification_type
            )
        return set()

    def get_min_severity(self, user_id: int, notification_type: str) -> int:
        """
        Get user's minimum severity threshold.

        Uses grouped preference structure.

        Default: 50 (medium severity)
        Range: 0-100
        """
        user_prefs = self.preferences.get(user_id, {})
        ntype_prefs = user_prefs.get(notification_type, {})

        if 'min_severity' in ntype_prefs:
            return ntype_prefs['min_severity']

        # Return default from DEFAULT_PREFERENCES
        defaults = self.DEFAULT_PREFERENCES.get(notification_type, {})
        return defaults.get('min_severity', config.DEFAULT_MIN_SEVERITY)

    def get_cooldown_minutes(self, user_id: int) -> int:
        """
        Get user's cooldown period in minutes.

        Default: 15 minutes between notifications for same item
        """
        user_prefs = self.preferences.get(user_id, {})
        return user_prefs.get('cooldown_minutes', config.DEFAULT_COOLDOWN_MINUTES)

    def set_min_severity(self, user_id: int, notification_type: str, severity: int):
        """
        Set user's minimum severity threshold.

        Uses grouped preference structure.

        Args:
            user_id: User ID
            notification_type: Type of notification
            severity: Minimum severity (0-100)
        """
        self.preferences.setdefault(user_id, {})
        self.preferences[user_id].setdefault(notification_type, {})
        self.preferences[user_id][notification_type]['min_severity'] = severity
        self.save_preferences()

    def set_cooldown(self, user_id: int, minutes: int):
        """
        Set user's cooldown period.

        Args:
            user_id: User ID
            minutes: Cooldown period in minutes
        """
        self.preferences.setdefault(user_id, {})
        self.preferences[user_id]['cooldown_minutes'] = minutes
        self.save_preferences()

    def get_user_min_profit(self, user_id: int, notification_type: str) -> int:
        """
        Get user's minimum profit threshold for alchemy notifications.

        For personal notifications only. Uses grouped preference structure.
        Returns user-specific threshold if set, otherwise returns default.

        Args:
            user_id: User ID
            notification_type: Type of notification ('all_alchs' or 'f2p_alchs')

        Returns:
            Minimum profit threshold in gp
        """
        user_prefs = self.preferences.get(user_id, {})
        ntype_prefs = user_prefs.get(notification_type, {})

        if 'min_profit' in ntype_prefs:
            return ntype_prefs['min_profit']

        # Return default from DEFAULT_PREFERENCES
        defaults = self.DEFAULT_PREFERENCES.get(notification_type, {})
        return defaults.get('min_profit', config.DEFAULT_ALL_ALCHS_MIN_PROFIT)

    def set_user_min_profit(self, user_id: int, notification_type: str, min_profit: int):
        """
        Set user's minimum profit threshold for alchemy notifications.

        For personal notifications only. Uses grouped preference structure.
        Allows users to customize their profit thresholds independently.

        Args:
            user_id: User ID
            notification_type: Type of notification ('all_alchs' or 'f2p_alchs')
            min_profit: Minimum profit threshold in gp
        """
        self.preferences.setdefault(user_id, {})
        self.preferences[user_id].setdefault(notification_type, {})
        self.preferences[user_id][notification_type]['min_profit'] = min_profit
        self.save_preferences()

    def get_profit_tier_config(self, notification_type: str) -> Dict:
        """
        Get profit tier configuration for notification type.

        Returns configuration dict with profit thresholds and F2P filtering
        for the given notification type. Used by AlertPolicy to filter
        ProfitableAlchemyEvent objects by tier.

        Args:
            notification_type: Type of notification

        Returns:
            Dict with min_profit, max_profit, f2p_only keys
        """
        return self.PROFIT_TIERS.get(notification_type, {
            'min_profit': 0,
            'max_profit': None,
            'f2p_only': False
        })
