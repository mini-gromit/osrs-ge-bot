import logging
from typing import List

from events import CrashRiskEvent
from domain import risk

logger = logging.getLogger(__name__)


# Quality filter defaults
# These ensure alerts are actionable and reduce noise from illiquid/low-value items

# Minimum hourly volume for actionable trading
# Rationale: Items with < 50/hr volume lack liquidity for reliable trading
# Tradeoff: May filter niche items, but those are rarely actionable anyway
DEFAULT_MIN_HOURLY_VOLUME = 50

# Minimum trade limit for meaningful profit potential
# Rationale: Very low limits (< 10) make total profit too small even with good margins
# Tradeoff: May miss high-value items with low limits, but most are collectibles
DEFAULT_MIN_TRADE_LIMIT = 10

# Minimum confidence score to filter noise
# Rationale: Confidence < 40 indicates poor data quality or conflicting signals
# Tradeoff: May miss early signals, but significantly reduces false positives
# Note: 40 filters out "very_low" confidence tier, keeps "low" and above
DEFAULT_MIN_CONFIDENCE = 40


def get_alchemy_crash_alerts(
    calculator,
    min_profit: int = 100,
    min_volume_imbalance: float = 2.0,
    min_limit: int = None,
    min_volume: int = None
) -> List[CrashRiskEvent]:
    """
    Get alchemy items with crash risk alerts.

    Generates CrashRiskEvent objects for all items meeting basic criteria.
    Filtering by confidence or severity belongs in the notification policy layer.

    Args:
        calculator: OSRSAlchemyFlippingCalculator instance
        min_profit: Minimum profit to consider alerting about
        min_volume_imbalance: Minimum volume ratio required for alert
        min_limit: Minimum trade limit filter
        min_volume: Minimum volume filter

    Returns:
        List of CrashRiskEvent objects with confidence metadata
    """
    alerts = []

    if not hasattr(calculator, "five_min_data") or not calculator.five_min_data:
        logger.warning("No 5-minute data available, fetching...")

        try:
            calculator.fetch_five_minute_data()

            if not calculator.five_min_data:
                logger.error(
                    "Still no 5-minute data after fetch - cannot generate alchemy alerts"
                )
                return []

            logger.info(
                f"Fetched 5-minute data for {len(calculator.five_min_data)} items"
            )

        except Exception as e:
            logger.error(f"Failed to fetch 5-minute data: {e}")
            return []

    logger.info(
        f"Looking for profitable items with profit ≥ {min_profit}gp..."
    )

    profitable_items = calculator.get_profitable_items(
        min_profit=min_profit,
        max_items=200,
        min_limit=min_limit,
        min_volume=min_volume
    )

    logger.info(
        f"Found {len(profitable_items)} profitable alchemy items to analyze"
    )

    for item in profitable_items:
        item_id = item["item_id"]

        try:
            crash_analysis = calculator.analyze_alchemy_crash_risk(item_id)

            if len(alerts) < 3:
                logger.debug(
                    f"{item['name']}: "
                    f"status={crash_analysis.get('status', 'unknown')}, "
                    f"volume_ratio={crash_analysis.get('volume_ratio', 0):.2f}"
                )

        except Exception as e:
            logger.warning(f"Error analyzing {item['name']}: {e}")
            continue

        if (
            crash_analysis.get("status") in ["crash_risk", "crashing"]
            and crash_analysis.get("volume_ratio", 0) >= min_volume_imbalance
        ):
            # Generate context explanations
            explanation = risk.generate_crash_explanation(
                status=crash_analysis["status"],
                volume_ratio=crash_analysis["volume_ratio"],
                volume_spike=crash_analysis.get("volume_spike", False),
                severity_score=crash_analysis.get("severity_score", 0)
            )

            impact_summary = risk.generate_crash_impact_summary(
                profit=item["profit"],
                roi_percent=item.get("roi_percent", 0),
                max_profit_per_limit=item.get("max_profit_per_limit", 0),
                trade_limit=item.get("limit", 0)
            )

            event = CrashRiskEvent(
                name=item["name"],
                item_id=item_id,
                profit=item["profit"],
                buy_price=item["buy_price"],
                alch_value=item["high_alch_value"],
                status=crash_analysis["status"],
                high_volume=crash_analysis["high_volume"],
                low_volume=crash_analysis["low_volume"],
                volume_ratio=crash_analysis["volume_ratio"],
                alert_percent=crash_analysis.get("alert_percent", 0),
                recommendation=crash_analysis.get(
                    "recommendation",
                    "unknown"
                ),
                severity_score=crash_analysis.get("severity_score", 0),
                hourly_volume=crash_analysis.get("hourly_volume", 0),
                volume_spike=crash_analysis.get("volume_spike", False),
                # Confidence and quality fields
                volume_confidence=crash_analysis.get("volume_confidence", "very_low"),
                confidence_score=crash_analysis.get("confidence_score", 10),
                total_volume=crash_analysis.get("total_volume", 0),
                price_decline_percent=crash_analysis.get("price_decline_percent", None),
                spike_magnitude=crash_analysis.get("spike_magnitude", 1.0),
                # Business context fields
                trade_limit=item.get("limit", 0),
                roi_percent=item.get("roi_percent", 0),
                members=item.get("members", False),
                max_profit_per_limit=item.get("max_profit_per_limit", 0),
                # Explanation fields
                explanation=explanation,
                impact_summary=impact_summary,
                # Historical trend metrics (optional)
                trend_15m=crash_analysis.get("trend_15m", None),
                trend_30m=crash_analysis.get("trend_30m", None),
                trend_60m=crash_analysis.get("trend_60m", None),
                consecutive_down_windows=crash_analysis.get("consecutive_down_windows", None),
                persistent_sell_pressure=crash_analysis.get("persistent_sell_pressure", None),
                largest_drawdown=crash_analysis.get("largest_drawdown", None)
            )

            # Apply quality filters to ensure actionable signals
            if event.hourly_volume < DEFAULT_MIN_HOURLY_VOLUME:
                # Skip: insufficient liquidity for reliable trading
                continue

            if event.trade_limit < DEFAULT_MIN_TRADE_LIMIT:
                # Skip: trade limit too low for meaningful profit
                continue

            if event.confidence_score < DEFAULT_MIN_CONFIDENCE:
                # Skip: poor signal quality (conflicting data or noise)
                continue

            alerts.append(event)

    logger.info(
        f"Generated {len(alerts)} crash alerts after quality filtering"
    )

    # Sort by ranking score (severity × confidence / 100)
    # This ranks high-quality signals (high severity + high confidence) above
    # noisy extreme ratios (high severity + low confidence)
    #
    # Ranking is calculated inline here, NOT stored in the event.
    # This keeps MarketEvents frontend-agnostic - different consumers can rank differently.
    #
    # Future ranking enhancements (TODO):
    # - Incorporate liquidity factor (hourly_volume / trade_limit ratio)
    # - Weight by persistence (when historical 5m windows become available)
    # - Boost items with confirmed price decline
    # - Consider profit potential (max_profit_per_limit)
    # - Apply user-specific preferences (members vs F2P, profit thresholds)
    #
    # When historical persistence data is available:
    # confidence_score will automatically increase for sustained pressure,
    # which naturally improves ranking without changing this formula.
    #
    # Example current behavior:
    #   Item A: severity=80, confidence=50 (sudden spike) → rank=40
    #   Item B: severity=60, confidence=90 (persistent) → rank=54
    #   → Item B ranks higher (better signal quality)
    alerts.sort(
        key=lambda x: (x.severity_score * x.confidence_score) // 100,
        reverse=True
    )

    return alerts