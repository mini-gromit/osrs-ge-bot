"""
Notification batching queue with timing logic.

Collects NotificationDecision objects and determines when they're ready
for batched delivery based on configurable batching window.

Frontend-independent - does not know about Discord, embeds, or delivery.
"""
import logging
from typing import List, Dict
from datetime import datetime, timedelta
from collections import defaultdict
from .models import NotificationDecision
import config

logger = logging.getLogger(__name__)


class NotificationQueue:
    """
    In-memory notification batching queue with timing logic.

    Owns batching state and timing decisions. Frontends simply ask for
    ready notifications and the queue determines what to return based on:
    - Batching window (default: 20 seconds)
    - Maximum batch size (default: 5 notifications per user)
    - Priority override (critical priority bypasses batching)

    Batching Logic:
    - Notifications are collected with timestamps
    - Grouped by user_id
    - Ready when ANY of these conditions are met:
      1. Notification has critical priority → immediate delivery
      2. User accumulates max_batch_size notifications → immediate delivery
      3. First notification has been in queue >= batching_window → timed delivery
    - Automatically clears returned notifications

    Frontend-independent. Any frontend (Discord, CLI, SMS, etc.) can call
    get_ready_notifications() at any frequency - queue decides readiness.
    """

    def __init__(
        self,
        batching_window_seconds: int = None,
        max_batch_size: int = None
    ):
        """
        Initialize notification queue.

        Args:
            batching_window_seconds: Seconds to wait before batching is ready
                                     (default: from config.NOTIFICATION_BATCH_WINDOW)
            max_batch_size: Maximum notifications per user before immediate delivery
                           (default: from config.NOTIFICATION_MAX_BATCH_SIZE)
        """
        if batching_window_seconds is None:
            batching_window_seconds = config.NOTIFICATION_BATCH_WINDOW
        if max_batch_size is None:
            max_batch_size = config.NOTIFICATION_MAX_BATCH_SIZE

        self.batching_window = timedelta(seconds=batching_window_seconds)
        self.max_batch_size = max_batch_size

        # Store notifications with timestamps: user_id -> [(notification, timestamp), ...]
        self._notifications: Dict[int, List[tuple]] = defaultdict(list)

        # Track when first notification arrived for each user
        self._first_notification_time: Dict[int, datetime] = {}

    def enqueue(self, notification: NotificationDecision):
        """
        Add a single notification to the queue.

        Args:
            notification: NotificationDecision to queue for batching
        """
        user_id = notification.user_id
        now = datetime.now()

        # Track first notification time for this user
        if user_id not in self._first_notification_time:
            self._first_notification_time[user_id] = now

        # Store notification with timestamp
        self._notifications[user_id].append((notification, now))

    def enqueue_batch(self, notifications: List[NotificationDecision]):
        """
        Add multiple notifications to the queue.

        Args:
            notifications: List of NotificationDecisions to queue
        """
        for notification in notifications:
            self.enqueue(notification)

    def get_ready_notifications(self) -> Dict[int, List[NotificationDecision]]:
        """
        Get notifications ready for delivery.

        Determines readiness based on three conditions:
        1. Critical priority: Notification has priority='critical' → immediate
        2. Batch size limit: User has >= max_batch_size notifications → immediate
        3. Batching window: First notification >= batching_window seconds old → timed

        Any of these conditions triggers delivery for that user.

        Automatically clears returned notifications from queue.

        Returns:
            Dict mapping user_id to list of their ready notifications.
            Empty dict if no notifications are ready.
        """
        # Track queue size before processing
        queued = self.get_pending_count()

        now = datetime.now()
        ready_notifications: Dict[int, List[NotificationDecision]] = {}
        users_to_clear = []

        for user_id in list(self._notifications.keys()):
            user_notif_list = self._notifications[user_id]

            # Extract notifications (without timestamps)
            user_notifications = [notif for notif, _ in user_notif_list]

            # Condition 1: Check for critical priority
            has_critical = any(n.priority == 'critical' for n in user_notifications)

            # Condition 2: Check batch size limit
            exceeds_batch_size = len(user_notifications) >= self.max_batch_size

            # Condition 3: Check batching window
            first_time = self._first_notification_time.get(user_id)
            time_in_queue = now - first_time if first_time else timedelta(0)
            batching_complete = time_in_queue >= self.batching_window

            # Release if any condition is met
            if has_critical or exceeds_batch_size or batching_complete:
                ready_notifications[user_id] = user_notifications
                users_to_clear.append(user_id)

        # Clear notifications that were returned
        for user_id in users_to_clear:
            del self._notifications[user_id]
            del self._first_notification_time[user_id]

        # Production log: concise queue stats
        released = sum(len(notifs) for notifs in ready_notifications.values())
        pending = self.get_pending_count()

        if released > 0 or queued > 0:
            logger.info(
                f"[NOTIFY] Queue: "
                f"queued={queued}, "
                f"released={released}, "
                f"pending={pending}"
            )

        return ready_notifications

    def get_pending_count(self) -> int:
        """
        Get total number of pending notifications across all users.

        Returns:
            Number of notifications currently in queue
        """
        return sum(len(notifs) for notifs in self._notifications.values())

    def get_users_with_pending(self) -> int:
        """
        Get number of users with pending notifications.

        Returns:
            Number of unique users with notifications in queue
        """
        return len(self._notifications)
