from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional


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

    Includes historical trend metrics for sustained crash detection.
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
    # Confidence and quality fields
    volume_confidence: str
    confidence_score: int
    total_volume: int
    price_decline_percent: Optional[float]
    spike_magnitude: float
    # Historical trend metrics (Optional - require rolling history)
    trend_15m: Optional[float] = None  # 3 windows
    trend_30m: Optional[float] = None  # 6 windows
    trend_60m: Optional[float] = None  # 12 windows
    consecutive_down_windows: Optional[int] = None
    persistent_sell_pressure: Optional[bool] = None
    largest_drawdown: Optional[float] = None
    # Business context fields
    trade_limit: int = 0
    roi_percent: float = 0.0
    members: bool = False
    max_profit_per_limit: int = 0
    # Explanation fields
    explanation: str = ""
    impact_summary: str = ""

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
        volume_confidence: str,
        confidence_score: int,
        total_volume: int,
        price_decline_percent: Optional[float],
        spike_magnitude: float,
        trade_limit: int = 0,
        roi_percent: float = 0.0,
        members: bool = False,
        max_profit_per_limit: int = 0,
        explanation: str = "",
        impact_summary: str = "",
        # Historical trend metrics (optional)
        trend_15m: Optional[float] = None,
        trend_30m: Optional[float] = None,
        trend_60m: Optional[float] = None,
        consecutive_down_windows: Optional[int] = None,
        persistent_sell_pressure: Optional[bool] = None,
        largest_drawdown: Optional[float] = None,
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
        self.volume_confidence = volume_confidence
        self.confidence_score = confidence_score
        self.total_volume = total_volume
        self.price_decline_percent = price_decline_percent
        self.spike_magnitude = spike_magnitude
        self.trade_limit = trade_limit
        self.roi_percent = roi_percent
        self.members = members
        self.max_profit_per_limit = max_profit_per_limit
        self.explanation = explanation
        self.impact_summary = impact_summary
        # Historical trend metrics
        self.trend_15m = trend_15m
        self.trend_30m = trend_30m
        self.trend_60m = trend_60m
        self.consecutive_down_windows = consecutive_down_windows
        self.persistent_sell_pressure = persistent_sell_pressure
        self.largest_drawdown = largest_drawdown


@dataclass
class FlippingTrendEvent(MarketEvent):
    """
    Market event for flipping trend alerts with realistic profit calculations.

    Includes GE tax calculation (2% of sell price) to show actionable net profit.
    """
    name: str
    item_id: int
    buy_price: int
    sell_price: int
    margin: int  # Gross margin (sell_price - buy_price)
    gross_margin: int  # Same as margin, kept for compatibility
    estimated_tax: int  # floor(sell_price * 0.02)
    net_profit: int  # gross_margin - estimated_tax
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
        gross_margin: int,
        estimated_tax: int,
        net_profit: int,
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
        self.gross_margin = gross_margin
        self.estimated_tax = estimated_tax
        self.net_profit = net_profit
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


@dataclass
class ProfitableAlchemyEvent(MarketEvent):
    """
    Market event for profitable alchemy opportunities.

    Represents any profitable high-alchemy item. Tier differentiation
    (super_hot, hot_items, all_alchs, f2p_alchs) handled by AlertPolicy
    based on profit thresholds and member status.

    Generated by engine/calculator.py:get_profitable_alchemy_events()
    """
    name: str
    item_id: int
    profit: int           # Profit in gp (alch_value - buy_price - nature_rune_cost)
    buy_price: int        # Current buy price
    alch_value: int       # High alchemy value
    roi_percent: float    # Return on investment %
    trade_limit: int      # GE trade limit (4-hour period)
    hourly_volume: int    # Trading volume per hour
    members: bool         # True if members-only item
    severity_score: int   # 20-80 based on profit tier
    lowest_low: int       # Historical 5-min low (0 if not enriched)

    def __init__(self, name: str, item_id: int, profit: int, buy_price: int,
                 alch_value: int, roi_percent: float, trade_limit: int,
                 hourly_volume: int, members: bool, severity_score: int,
                 lowest_low: int):
        super().__init__(event_type="profitable_alchemy")
        self.name = name
        self.item_id = item_id
        self.profit = profit
        self.buy_price = buy_price
        self.alch_value = alch_value
        self.roi_percent = roi_percent
        self.trade_limit = trade_limit
        self.hourly_volume = hourly_volume
        self.members = members
        self.severity_score = severity_score
        self.lowest_low = lowest_low