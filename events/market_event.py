from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict


@dataclass
class MarketEvent:
    """
    Base class for all market events.

    Contains reusable business/domain data only.
    No frontend or presentation logic.
    """
    event_type: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CrashRiskEvent(MarketEvent):
    """
    Market event for items with crash risk based on volume imbalance.
    """
    name: str
    item_id: int
    profit: int
    buy_price: int
    alch_value: int
    status: str
    high_volume: int
    low_volume: int
    volume_ratio: float
    alert_percent: float
    recommendation: str
    severity_score: int
    hourly_volume: int
    volume_spike: bool
    # Business context fields
    trade_limit: int
    roi_percent: float
    members: bool
    max_profit_per_limit: int
    # Explanation fields
    explanation: str
    impact_summary: str

    def __init__(
        self,
        name: str,
        item_id: int,
        profit: int,
        buy_price: int,
        alch_value: int,
        status: str,
        high_volume: int,
        low_volume: int,
        volume_ratio: float,
        alert_percent: float,
        recommendation: str,
        severity_score: int,
        hourly_volume: int,
        volume_spike: bool,
        trade_limit: int,
        roi_percent: float,
        members: bool,
        max_profit_per_limit: int,
        explanation: str,
        impact_summary: str,
    ):
        super().__init__(event_type="crash_risk")
        self.name = name
        self.item_id = item_id
        self.profit = profit
        self.buy_price = buy_price
        self.alch_value = alch_value
        self.status = status
        self.high_volume = high_volume
        self.low_volume = low_volume
        self.volume_ratio = volume_ratio
        self.alert_percent = alert_percent
        self.recommendation = recommendation
        self.severity_score = severity_score
        self.hourly_volume = hourly_volume
        self.volume_spike = volume_spike
        self.trade_limit = trade_limit
        self.roi_percent = roi_percent
        self.members = members
        self.max_profit_per_limit = max_profit_per_limit
        self.explanation = explanation
        self.impact_summary = impact_summary


@dataclass
class FlippingTrendEvent(MarketEvent):
    """
    Market event for flipping trend alerts.
    """
    name: str
    item_id: int
    buy_price: int
    sell_price: int
    margin: int
    status: str
    price_change_percent: float
    high_volume: int
    low_volume: int
    recommendation: str
    severity_score: int
    hourly_volume: int
    volume_spike: bool
    # Business context fields
    trade_limit: int
    members: bool
    margin_percent: float
    # Explanation fields
    explanation: str
    impact_summary: str

    def __init__(
        self,
        name: str,
        item_id: int,
        buy_price: int,
        sell_price: int,
        margin: int,
        status: str,
        price_change_percent: float,
        high_volume: int,
        low_volume: int,
        recommendation: str,
        severity_score: int,
        hourly_volume: int,
        volume_spike: bool,
        trade_limit: int,
        members: bool,
        margin_percent: float,
        explanation: str,
        impact_summary: str,
    ):
        super().__init__(event_type="flipping_trend")
        self.name = name
        self.item_id = item_id
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.margin = margin
        self.status = status
        self.price_change_percent = price_change_percent
        self.high_volume = high_volume
        self.low_volume = low_volume
        self.recommendation = recommendation
        self.severity_score = severity_score
        self.hourly_volume = hourly_volume
        self.volume_spike = volume_spike
        self.trade_limit = trade_limit
        self.members = members
        self.margin_percent = margin_percent
        self.explanation = explanation
        self.impact_summary = impact_summary