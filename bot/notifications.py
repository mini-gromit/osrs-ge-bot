import json
import os
from datetime import datetime
from typing import Dict, Set


class UserNotificationManager:
    """Manages user notification subscriptions"""

    def __init__(self, filename='user_notifications.json'):
        self.filename = filename
        self.user_subscriptions: Dict[int, Set[str]] = {}
        self.load_subscriptions()

    def load_subscriptions(self):
        """Load user subscriptions from file"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    data = json.load(f)

                if 'user_subscriptions' in data:
                    for uid_str, sub_list in data['user_subscriptions'].items():
                        self.user_subscriptions[int(uid_str)] = set(sub_list)

                print(f"Loaded subscriptions for {len(self.user_subscriptions)} users")

        except Exception as e:
            print(f"Error loading subscriptions: {e}")
            self.user_subscriptions = {}

    def save_subscriptions(self):
        """Save user subscriptions to file"""
        try:
            serializable = {
                str(uid): list(subs)
                for uid, subs in self.user_subscriptions.items()
            }

            with open(self.filename, 'w') as f:
                json.dump({
                    'user_subscriptions': serializable,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)

        except Exception as e:
            print(f"Error saving subscriptions: {e}")

    def subscribe_user(self, user_id: int, notification_type: str) -> bool:
        """
        Subscribe a user to a notification type.

        Args:
            user_id: Discord user ID
            notification_type: Type of notification to subscribe to

        Returns:
            True if subscription was added, False if already subscribed
        """
        self.user_subscriptions.setdefault(user_id, set())

        if notification_type not in self.user_subscriptions[user_id]:
            self.user_subscriptions[user_id].add(notification_type)
            self.save_subscriptions()
            return True

        return False

    def unsubscribe_user(self, user_id: int, notification_type: str = None) -> bool:
        """
        Unsubscribe a user from a notification type.

        Args:
            user_id: Discord user ID
            notification_type: Type to unsubscribe from (None = all)

        Returns:
            True if unsubscription was successful
        """
        if user_id not in self.user_subscriptions:
            return False

        if notification_type is None:
            del self.user_subscriptions[user_id]
            self.save_subscriptions()
            return True

        if notification_type in self.user_subscriptions[user_id]:
            self.user_subscriptions[user_id].remove(notification_type)

            if not self.user_subscriptions[user_id]:
                del self.user_subscriptions[user_id]

            self.save_subscriptions()
            return True

        return False

    def get_subscribers_for_type(self, notification_type: str) -> Set[int]:
        """
        Get all subscribers for a notification type.

        Args:
            notification_type: Type of notification

        Returns:
            Set of user IDs subscribed to this type
        """
        return {
            uid for uid, subs in self.user_subscriptions.items()
            if notification_type in subs
        }
