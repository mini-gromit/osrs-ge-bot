"""
Frontend-independent notification decision models.

Represents the decision that a user should be notified about a MarketEvent.
Does not contain frontend-specific formatting or delivery details.
"""
from dataclasses import dataclass
from events import MarketEvent


@dataclass
class NotificationDecision:
    """
    Represents a decision to notify a user about a MarketEvent.

    Frontend-independent. Contains the business decision that a notification
    should be sent, without any frontend-specific formatting or delivery details.

    Frontends (Discord, CLI, SMS, etc.) consume this to render and deliver
    notifications in their own format.
    """
    user_id: int
    event: MarketEvent
    notification_type: str  # 'crash_risk', 'flipping_trend', etc.
    priority: str  # 'high', 'medium', 'low'

    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            'user_id': self.user_id,
            'event': self.event.to_dict(),
            'notification_type': self.notification_type,
            'priority': self.priority
        }
