import json
import os
import logging
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ChannelConfig:
    """Discord channel configuration"""
    super_hot_items: int
    hot_items: int
    welcome_channel: Optional[int] = None
    all_alchs: Optional[int] = None
    f2p_alchs: Optional[int] = None
    crash_risk_alerts: Optional[int] = None
    flipping_trend_alerts: Optional[int] = None

    super_hot_message_id: Optional[int] = None
    hot_items_message_id: Optional[int] = None
    all_alchs_message_id: Optional[int] = None
    f2p_alchs_message_id: Optional[int] = None
    opt_in_message_id: Optional[int] = None
    crash_risk_message_id: Optional[int] = None
    flipping_trend_message_id: Optional[int] = None


@dataclass
class ProfitThresholds:
    """Profit threshold configuration"""
    hot_items_min_profit: int = 450
    super_hot_min_profit: int = 1000
    all_alchs_min_profit: int = 1
    f2p_alchs_min_profit: int = 1


class ConfigManager:
    """Manages bot configuration persistence"""

    def __init__(self, config_file: str = 'channel_config.json'):
        self.config_file = config_file
        self.channel_config: Optional[ChannelConfig] = None
        self.profit_thresholds = ProfitThresholds()

    def load_config(self) -> Optional[ChannelConfig]:
        """Load channel configuration from file"""
        if not os.path.exists(self.config_file):
            return None

        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)

            self.channel_config = ChannelConfig(
                super_hot_items=data.get('super_hot_items'),
                hot_items=data.get('hot_items'),
                welcome_channel=data.get('welcome_channel'),
                all_alchs=data.get('all_alchs'),
                f2p_alchs=data.get('f2p_alchs'),
                crash_risk_alerts=data.get('crash_risk_alerts'),
                flipping_trend_alerts=data.get('flipping_trend_alerts'),
                super_hot_message_id=data.get('super_hot_message_id'),
                hot_items_message_id=data.get('hot_items_message_id'),
                all_alchs_message_id=data.get('all_alchs_message_id'),
                f2p_alchs_message_id=data.get('f2p_alchs_message_id'),
                opt_in_message_id=data.get('opt_in_message_id'),
                crash_risk_message_id=data.get('crash_risk_message_id'),
                flipping_trend_message_id=data.get('flipping_trend_message_id')
            )

            self.profit_thresholds = ProfitThresholds(
                hot_items_min_profit=data.get('hot_items_min_profit', 450),
                super_hot_min_profit=data.get('super_hot_min_profit', 1000),
                all_alchs_min_profit=data.get('all_alchs_min_profit', 1),
                f2p_alchs_min_profit=data.get('f2p_alchs_min_profit', 1)
            )

            return self.channel_config

        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return None

    def save_config(self, channel_config: ChannelConfig) -> bool:
        """Save channel configuration to file"""
        try:
            self.channel_config = channel_config

            data = asdict(channel_config)
            data.update(asdict(self.profit_thresholds))

            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def update_message_id(self, category: str, message_id: int) -> bool:
        """Update a message ID in the configuration"""
        if not self.channel_config:
            return False

        try:
            if category == 'super_hot':
                self.channel_config.super_hot_message_id = message_id
            elif category == 'hot_items':
                self.channel_config.hot_items_message_id = message_id
            elif category == 'all_alchs':
                self.channel_config.all_alchs_message_id = message_id
            elif category == 'f2p_alchs':
                self.channel_config.f2p_alchs_message_id = message_id
            elif category == 'crash_risk':
                self.channel_config.crash_risk_message_id = message_id
            elif category == 'flipping_trend':
                self.channel_config.flipping_trend_message_id = message_id
            else:
                return False

            return self.save_config(self.channel_config)

        except Exception as e:
            logger.error(f"Error updating message ID: {e}")
            return False
