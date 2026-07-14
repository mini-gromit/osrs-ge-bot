from typing import List

from events import FlippingTrendEvent


def get_flipping_trend_alerts(
    calculator,
    min_margin: int = 1000,
    min_volume: int = 20
) -> List[FlippingTrendEvent]:
    """
    Get flipping items with trend alerts.

    Args:
        calculator: OSRSAlchemyFlippingCalculator instance
        min_margin: Minimum margin to consider
        min_volume: Minimum volume to consider

    Returns:
        List of FlippingTrendEvent objects
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

    for flip in flips:
        item_id = flip["id"]

        trend_analysis = calculator.analyze_flipping_trend(item_id)

        if trend_analysis["status"] != "stable":
            event = FlippingTrendEvent(
                name=flip["name"],
                item_id=item_id,
                buy_price=flip["buy_price"],
                sell_price=flip["sell_price"],
                margin=flip["margin"],
                status=trend_analysis["status"],
                price_change_percent=trend_analysis["price_change_percent"],
                high_volume=trend_analysis["high_volume"],
                low_volume=trend_analysis["low_volume"],
                recommendation=trend_analysis["recommendation"]
            )

            alerts.append(event)

    alerts.sort(
        key=lambda x: abs(x.price_change_percent),
        reverse=True
    )

    return alerts