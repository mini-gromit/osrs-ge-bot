"""
Alert Policy Engine - Filters MarketEvents into NotificationDecision objects.

Responsibilities:
- Severity filtering (user min_severity threshold)
- Cooldown management (per-item, per-user)
- Duplicate suppression (same item/status within window)
- User preference matching

Frontend-independent. Produces reusable NotificationDecision objects.
"""
import logging
from typing import List, Dict, Set
from datetime import datetime, timedelta
from events import MarketEvent
from .models import NotificationDecision
from .preference_store import PreferenceStore
from events import ProfitableAlchemyEvent
import config

logger = logging.getLogger(__name__)


class AlertPolicy:
    """
    Alert Policy Engine - Determines which users should be notified about MarketEvents.

    Depends on PreferenceStore interface (not implementation) for flexibility.
    Tracks cooldowns and duplicates in memory (cleaned periodically).

    Frontend-independent - outputs NotificationDecision objects that any
    frontend can consume.
    """

    def __init__(self, preference_store: PreferenceStore):
        """
        Initialize AlertPolicy with a preference store.

        Args:
            preference_store: PreferenceStore implementation (JSON, DB, etc.)
        """
        self.preferences = preference_store
        self.cooldowns: Dict[tuple, datetime] = {}  # (user_id, notification_type, item_id) -> last_sent
        self.seen_recently: Dict[tuple, datetime] = {}  # (user_id, notification_type, item_id, status) -> last_seen
        self.rejection_log_counts: Dict[str, int] = {}  # notification_type -> count (for diagnostics)

    def should_notify_user(
        self,
        user_id: int,
        event: MarketEvent,
        notification_type: str
    ) -> bool:
        """
        Determine if a user should be notified about this event.

        Checks:
        1. User subscribed to this notification type
        2. Event severity >= user's minimum threshold
        3. Profit tier matching (for ProfitableAlchemyEvent)
        4. Not in cooldown period for this item
        5. Not a duplicate (same item/status recently seen)

        Args:
            user_id: User ID to check
            event: MarketEvent to evaluate
            notification_type: Type of notification

        Returns:
            True if user should be notified, False otherwise
        """
        # Helper for diagnostic logging (limit 10 per cycle)
        def _log_rejection(reason: str, details: dict = None):
            if notification_type not in ['all_alchs', 'f2p_alchs']:
                return
            if not isinstance(event, ProfitableAlchemyEvent):
                return

            count = self.rejection_log_counts.get(notification_type, 0)
            if count >= 100:
                return

            self.rejection_log_counts[notification_type] = count + 1

            log_parts = [
                f"[DIAG] Rejection #{count + 1}",
                f"type={notification_type}",
                f"user={user_id}",
                f"item={event.name}",
                f"profit={event.profit}",
                f"members={event.members}",
                f"reason={reason}"
            ]

            if details:
                for k, v in details.items():
                    log_parts.append(f"{k}={v}")

            logger.info(" | ".join(log_parts))

        # Check subscription
        if not self.preferences.is_subscribed(user_id, notification_type):
            _log_rejection("not_subscribed")
            return False

        # Severity filtering applies only to non-alchemy alerts.
        # Alchemy personal notifications are controlled by user profit threshold.
        if not isinstance(event, ProfitableAlchemyEvent):
            user_min_severity = self.preferences.get_min_severity(
                user_id,
                notification_type
            )

            if event.severity_score < user_min_severity:
                return False

        # Profit-based filtering for ProfitableAlchemyEvent
        if isinstance(event, ProfitableAlchemyEvent):
            # Personal notifications only support: all_alchs, f2p_alchs
            # Reject legacy tier types (super_hot, hot_items) for personal notifications
            if notification_type not in ['all_alchs', 'f2p_alchs']:
                logger.warning(
                    f"Personal notification type '{notification_type}' not supported "
                    f"for alchemy events. Use 'all_alchs' or 'f2p_alchs' instead."
                )
                _log_rejection("unsupported_type")
                return False

            # Get user-specific minimum profit threshold
            min_profit = self.preferences.get_user_min_profit(user_id, notification_type)
            if event.profit < min_profit:
                _log_rejection("profit_too_low", {"user_min_profit": min_profit})
                return False

            # Check F2P requirement for f2p_alchs
            if notification_type == 'f2p_alchs' and event.members:
                _log_rejection("members_item_for_f2p", {"user_min_profit": min_profit})
                return False  # User wants F2P only, but this is members item

        # Check cooldown (per-item, per-user, per-notification-type)
        cooldown_key = (user_id, notification_type, event.item_id)
        if cooldown_key in self.cooldowns:
            cooldown_minutes = self.preferences.get_cooldown_minutes(user_id)
            time_since = datetime.now() - self.cooldowns[cooldown_key]
            if time_since < timedelta(minutes=cooldown_minutes):
                remaining = cooldown_minutes - (time_since.total_seconds() / 60)
                _log_rejection("cooldown", {
                    "cooldown_minutes": cooldown_minutes,
                    "remaining_minutes": f"{remaining:.1f}"
                })
                return False

        # Check duplicate suppression (same item+status within window, per-user, per-notification-type)
        # Use 'profitable' as status for ProfitableAlchemyEvent, otherwise use event.status
        status = getattr(event, 'status', 'profitable')
        duplicate_key = (user_id, notification_type, event.item_id, status)
        if duplicate_key in self.seen_recently:
            time_since = datetime.now() - self.seen_recently[duplicate_key]
            if time_since < timedelta(minutes=config.DUPLICATE_SUPPRESSION_MINUTES):
                remaining = config.DUPLICATE_SUPPRESSION_MINUTES - (time_since.total_seconds() / 60)
                _log_rejection("duplicate", {
                    "suppression_window": config.DUPLICATE_SUPPRESSION_MINUTES,
                    "remaining_minutes": f"{remaining:.1f}"
                })
                return False

        return True

    def filter_events(
        self,
        events: List[MarketEvent],
        notification_type: str
    ) -> List[NotificationDecision]:
        """
        Filter MarketEvents into NotificationDecision objects.

        For each event:
        1. Check all subscribed users
        2. Apply policy rules (severity, cooldown, duplicates)
        3. Create NotificationDecision for qualifying users

        Args:
            events: List of MarketEvents to filter
            notification_type: Type of notification ('crash_risk', 'flipping_trend')

        Returns:
            List of NotificationDecision objects ready for frontend delivery
        """
        # Reset rejection log counter for this notification cycle
        self.rejection_log_counts[notification_type] = 0

        notifications = []

        # Get all subscribed users for this notification type
        subscribed_users = self.preferences.get_subscribed_users(notification_type)

        if not subscribed_users:
            return notifications

        for event in events:
            for user_id in subscribed_users:
                if self.should_notify_user(user_id, event, notification_type):
                    # Determine priority from severity score
                    if event.severity_score >= config.PRIORITY_CRITICAL_THRESHOLD:
                        priority = 'critical'
                    elif event.severity_score >= config.PRIORITY_HIGH_THRESHOLD:
                        priority = 'high'
                    elif event.severity_score >= config.PRIORITY_MEDIUM_THRESHOLD:
                        priority = 'medium'
                    else:
                        priority = 'low'

                    notification = NotificationDecision(
                        user_id=user_id,
                        event=event,
                        notification_type=notification_type,
                        priority=priority
                    )

                    notifications.append(notification)

                    # Update cooldown (scoped by user, notification type, and item)
                    cooldown_key = (user_id, notification_type, event.item_id)
                    self.cooldowns[cooldown_key] = datetime.now()

                    # Update duplicate tracking (scoped by user, notification type, item, and status)
                    status = getattr(event, 'status', 'profitable')
                    duplicate_key = (user_id, notification_type, event.item_id, status)
                    self.seen_recently[duplicate_key] = datetime.now()

        # Clean old tracking entries
        self._cleanup_old_tracking()

        # Production log: concise summary
        logger.info(
            f"[NOTIFY] {notification_type}: "
            f"subscribers={len(subscribed_users)}, "
            f"notifications={len(notifications)}"
        )

        return notifications

    def _cleanup_old_tracking(self):
        """
        Remove tracking entries older than 1 hour.

        Prevents unbounded memory growth from cooldown and duplicate tracking.
        Called after each filter_events() invocation.
        """
        cutoff = datetime.now() - timedelta(hours=config.TRACKING_CLEANUP_HOURS)

        # Clean cooldowns
        old_cooldown_count = len(self.cooldowns)
        self.cooldowns = {
            k: v for k, v in self.cooldowns.items()
            if v > cutoff
        }

        # Clean duplicate tracking
        old_seen_count = len(self.seen_recently)
        self.seen_recently = {
            k: v for k, v in self.seen_recently.items()
            if v > cutoff
        }

        cleaned_cooldowns = old_cooldown_count - len(self.cooldowns)
        cleaned_seen = old_seen_count - len(self.seen_recently)

        if cleaned_cooldowns > 0 or cleaned_seen > 0:
            logger.debug(
                f"Cleaned {cleaned_cooldowns} old cooldowns, "
                f"{cleaned_seen} old duplicate entries"
            )
