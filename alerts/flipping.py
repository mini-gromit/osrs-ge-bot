import logging
from typing import List

from events import FlippingTrendEvent
from domain import risk, flipping

logger = logging.getLogger(__name__)


# Quality filter defaults
# These ensure flipping alerts are actionable and reduce noise from poor candidates

# Items to always exclude (manipulated or unsuitable for flipping)
EXCLUDED_ITEMS = [
    "Old school bond",  # Manipulated, poor liquidity
]

# Minimum hourly volume for reliable flipping
# Rationale: Low volume means you may not be able to buy/sell at observed prices
DEFAULT_MIN_HOURLY_VOLUME = 50

# Minimum trade limit for meaningful profit potential
# Rationale: Very low limits make total profit too small even with good margins
DEFAULT_MIN_TRADE_LIMIT = 10

# Minimum confidence score to filter noise (when available)
# Rationale: Low confidence indicates unreliable or conflicting signals
DEFAULT_MIN_CONFIDENCE = 40


def get_flipping_trend_alerts(
    calculator,
    min_margin: int = 1000,
    min_volume: int = 20,
    min_limit: int = None,
    min_hourly_volume: int = None
) -> List[FlippingTrendEvent]:
    """
    Get actionable flipping opportunities with realistic profit calculations.

    Calculates net profit after 2% GE tax and filters out poor candidates.

    Args:
        calculator: OSRSAlchemyFlippingCalculator instance
        min_margin: Minimum gross margin to consider
        min_volume: Minimum volume to consider (legacy parameter)
        min_limit: Minimum trade limit filter
        min_hourly_volume: Minimum hourly volume filter

    Returns:
        List of FlippingTrendEvent objects sorted by ranking score
    """
    alerts = []

    if not calculator.five_min_data:
        calculator.fetch_five_minute_data()

    flips = calculator.get_top_flips(
        limit=100,
        min_margin=min_margin,
        min_volume=min_volume,
        fetch_history=False
    )

    logger.info(f"Analyzing {len(flips)} potential flipping opportunities...")

    for flip in flips:
        item_id = flip["id"]
        item_name = flip["name"]

        # Quality filter: Exclude known problematic items
        if any(excluded.lower() in item_name.lower() for excluded in EXCLUDED_ITEMS):
            logger.debug(f"Excluded {item_name}: on exclusion list")
            continue

        # Calculate realistic profit after GE tax
        buy_price = flip["buy_price"]
        sell_price = flip["sell_price"]
        gross_margin, estimated_tax, net_profit = flipping.calculate_flip_profit(
            buy_price, sell_price
        )

        # Quality filter: Exclude negative or zero net profit
        if net_profit <= 0:
            logger.debug(f"Excluded {item_name}: net_profit={net_profit} (after tax)")
            continue

        trend_analysis = calculator.analyze_flipping_trend(item_id)

        if trend_analysis["status"] != "stable":
            # Get trade limit and hourly volume
            trade_limit = flip.get("limit", 0)
            hourly_volume = trend_analysis.get("hourly_volume", 0)

            # Quality filter: Minimum trade limit
            if trade_limit < (min_limit or DEFAULT_MIN_TRADE_LIMIT):
                logger.debug(f"Excluded {item_name}: trade_limit={trade_limit}")
                continue

            # Quality filter: Minimum hourly volume
            if hourly_volume < (min_hourly_volume or DEFAULT_MIN_HOURLY_VOLUME):
                logger.debug(f"Excluded {item_name}: hourly_volume={hourly_volume}")
                continue

            # Calculate max profit per limit with net profit
            max_profit_per_limit = net_profit * trade_limit if net_profit > 0 else 0

            # Generate context explanations
            explanation = risk.generate_flip_explanation(
                status=trend_analysis["status"],
                price_change_percent=trend_analysis["price_change_percent"],
                volume_spike=trend_analysis.get("volume_spike", False),
                severity_score=trend_analysis.get("severity_score", 0)
            )

            impact_summary = risk.generate_flip_impact_summary(
                margin=net_profit,  # Use net profit for impact
                margin_percent=flip.get("margin_percent", 0),
                max_profit_per_limit=max_profit_per_limit,
                trade_limit=trade_limit
            )

            event = FlippingTrendEvent(
                name=item_name,
                item_id=item_id,
                buy_price=buy_price,
                sell_price=sell_price,
                margin=gross_margin,  # Gross margin
                gross_margin=gross_margin,
                estimated_tax=estimated_tax,
                net_profit=net_profit,
                status=trend_analysis["status"],
                price_change_percent=trend_analysis["price_change_percent"],
                high_volume=trend_analysis["high_volume"],
                low_volume=trend_analysis["low_volume"],
                recommendation=trend_analysis["recommendation"],
                severity_score=trend_analysis.get("severity_score", 0),
                hourly_volume=hourly_volume,
                volume_spike=trend_analysis.get("volume_spike", False),
                # Business context fields
                trade_limit=trade_limit,
                members=flip.get("members", False),
                margin_percent=flip.get("margin_percent", 0),
                # Explanation fields
                explanation=explanation,
                impact_summary=impact_summary
            )

            alerts.append(event)

    logger.info(f"Generated {len(alerts)} flipping alerts after quality filtering")

    # Sort by ranking score: net_profit × liquidity
    # Confidence scoring not yet available for flipping, so we use liquidity only
    # Large margins on illiquid items rank lower than smaller margins on tradable items
    #
    # Ranking formula:
    # ranking = net_profit × (hourly_volume / 100)
    #
    # This naturally prioritizes:
    # - High net profit (after tax)
    # - High liquidity (volume)
    #
    # Future enhancements:
    # - Add confidence score when historical spread persistence is available
    # - Weight by trade_limit for profit potential
    alerts.sort(
        key=lambda x: x.net_profit * (x.hourly_volume / 100),
        reverse=True
    )

    return alerts