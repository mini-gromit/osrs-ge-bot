import logging
from typing import List

from events import CrashRiskEvent

logger = logging.getLogger(__name__)


def get_alchemy_crash_alerts(
    calculator,
    min_profit: int = 100,
    min_volume_imbalance: float = 2.0,
    min_limit: int = None,
    min_volume: int = None
) -> List[CrashRiskEvent]:
    """
    Get alchemy items with crash risk alerts.

    Args:
        calculator: OSRSAlchemyFlippingCalculator instance
        min_profit: Minimum profit to consider alerting about
        min_volume_imbalance: Minimum volume ratio required for alert
        min_limit: Minimum trade limit filter
        min_volume: Minimum volume filter

    Returns:
        List of CrashRiskEvent objects
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
                )
            )

            alerts.append(event)

            logger.info(
                f"Added alert for {item['name']}: "
                f"{crash_analysis['status']}"
            )

    logger.info(
        f"Generated {len(alerts)} alchemy crash alerts"
    )

    alerts.sort(
        key=lambda x: x.volume_ratio,
        reverse=True
    )

    return alerts