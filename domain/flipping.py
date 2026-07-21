import statistics
import math
from typing import Dict, List, Tuple


def calculate_flip_profit(buy_price: int, sell_price: int) -> Tuple[int, int, int]:
    """
    Calculate realistic flip profit after Grand Exchange tax.

    The GE charges a 2% tax on the sell price when an item is sold.
    There is no tax when buying items.

    Args:
        buy_price: Price to buy at (instant buy, current low)
        sell_price: Price to sell at (instant sell, current high)

    Returns:
        Tuple of (gross_margin, estimated_tax, net_profit)
            - gross_margin: sell_price - buy_price
            - estimated_tax: floor(sell_price * 0.02)
            - net_profit: gross_margin - estimated_tax
    """
    if buy_price <= 0 or sell_price <= 0:
        return (0, 0, 0)

    gross_margin = sell_price - buy_price
    estimated_tax = math.floor(sell_price * 0.02)
    net_profit = gross_margin - estimated_tax

    return (gross_margin, estimated_tax, net_profit)


def calculate_capital_metrics(
    buy_price: int,
    net_profit: int,
    trade_limit: int,
    hourly_volume: int
) -> Dict[str, float]:
    """
    Calculate capital efficiency metrics for flipping opportunities.

    These metrics help evaluate the practicality and efficiency of flips
    independent of absolute profit amounts.

    Args:
        buy_price: Capital required per item
        net_profit: Net profit per item (after GE tax)
        trade_limit: GE trade limit (4-hour period)
        hourly_volume: Estimated hourly trading volume

    Returns:
        Dict containing:
            - required_capital: Buy price (capital per item)
            - profit_per_item: Net profit per flip
            - profit_per_million: How much profit per 1M gp invested
            - estimated_hourly_profit: Estimated profit per hour based on volume
    """
    if buy_price <= 0:
        return {
            'required_capital': 0,
            'profit_per_item': net_profit,
            'profit_per_million': 0.0,
            'estimated_hourly_profit': 0
        }

    # Profit per million invested (capital efficiency)
    profit_per_million = (net_profit / buy_price) * 1_000_000

    # Estimate hourly profit potential
    # Assumes you can flip at market volume rate, capped by trade limit per hour
    max_flips_per_hour = trade_limit / 4  # Trade limit is per 4 hours
    volume_constrained_flips = min(hourly_volume, max_flips_per_hour * 10)  # Conservative estimate
    estimated_hourly_profit = net_profit * volume_constrained_flips

    return {
        'required_capital': buy_price,
        'profit_per_item': net_profit,
        'profit_per_million': profit_per_million,
        'estimated_hourly_profit': int(estimated_hourly_profit)
    }


def analyze_spread_stability(
    current_buy: int,
    current_sell: int,
    historical_data: List[Dict]
) -> Dict[str, any]:
    """
    Analyze spread behavior over time using historical price data.

    Determines whether the spread is stable, improving, shrinking, or volatile.
    This helps identify sustainable flipping opportunities vs temporary arbitrage.

    Args:
        current_buy: Current buy price
        current_sell: Current sell price
        historical_data: List of historical 5-minute data points with high/low prices

    Returns:
        Dict containing:
            - spread_status: 'stable', 'improving', 'shrinking', 'volatile', 'unknown'
            - spread_volatility: Coefficient of variation (%) of historical spreads
            - mean_spread: Average historical spread
            - current_spread: Current spread amount
            - spread_percentile: Where current spread ranks (0-100)
    """
    if not historical_data or len(historical_data) < 5:
        return {
            'spread_status': 'unknown',
            'spread_volatility': 0.0,
            'mean_spread': 0,
            'current_spread': current_sell - current_buy,
            'spread_percentile': 50.0
        }

    # Extract historical spreads
    spreads = []
    for data_point in historical_data:
        high = data_point.get('avgHighPrice') or data_point.get('highPriceVolume', 0)
        low = data_point.get('avgLowPrice') or data_point.get('lowPriceVolume', 0)
        if high > 0 and low > 0:
            spreads.append(high - low)

    if len(spreads) < 5:
        return {
            'spread_status': 'unknown',
            'spread_volatility': 0.0,
            'mean_spread': 0,
            'current_spread': current_sell - current_buy,
            'spread_percentile': 50.0
        }

    current_spread = current_sell - current_buy
    mean_spread = statistics.mean(spreads)

    # Calculate spread volatility (coefficient of variation)
    if mean_spread > 0:
        spread_volatility = (statistics.stdev(spreads) / mean_spread) * 100
    else:
        spread_volatility = 0.0

    # Determine spread percentile (where does current spread rank?)
    spread_percentile = (sum(1 for s in spreads if s <= current_spread) / len(spreads)) * 100

    # Analyze recent trend (last 10 data points vs earlier)
    if len(spreads) >= 10:
        recent_spreads = spreads[-10:]
        earlier_spreads = spreads[:-10]

        recent_mean = statistics.mean(recent_spreads)
        earlier_mean = statistics.mean(earlier_spreads)

        spread_change = ((recent_mean - earlier_mean) / earlier_mean) * 100 if earlier_mean > 0 else 0

        # Classify spread status
        if spread_volatility > 30:
            spread_status = 'volatile'
        elif abs(spread_change) < 5:
            spread_status = 'stable'
        elif spread_change > 5:
            spread_status = 'improving'
        else:
            spread_status = 'shrinking'
    else:
        # Not enough data for trend analysis
        if spread_volatility > 30:
            spread_status = 'volatile'
        else:
            spread_status = 'stable'

    return {
        'spread_status': spread_status,
        'spread_volatility': spread_volatility,
        'mean_spread': int(mean_spread),
        'current_spread': current_spread,
        'spread_percentile': spread_percentile
    }


def calculate_flip_score(current_high_price: int, current_low_price: int,
                        volume: int, margin: int, limit: int, history_prices: List[Dict],
                        detect_pump_and_dump_func, base_score=0) -> tuple:
    """
    Balanced granular flip score calculation.

    Args:
        current_high_price: Current high price
        current_low_price: Current low price
        volume: Trading volume
        margin: Profit margin
        limit: Trade limit
        history_prices: Historical price data
        detect_pump_and_dump_func: Function to detect pump and dump
        base_score: Base score to start from

    Returns:
        Tuple of (score, summary, risk_info)
    """
    score = base_score
    factors = [f"Base: {base_score}"]

    buy_price_with_tax = int(current_low_price * 1.01)
    sell_price_after_tax = int(current_high_price * 0.99)
    actual_margin = sell_price_after_tax - buy_price_with_tax
    actual_margin_percent = (actual_margin / buy_price_with_tax * 100) if buy_price_with_tax > 0 else 0

    scoring_margin = actual_margin
    scoring_margin_percent = actual_margin_percent

    is_suspicious, risk_level, risk_reason = detect_pump_and_dump_func(
        history_prices, current_high_price, current_low_price
    )

    if is_suspicious:
        if risk_level >= 3:
            score -= 50
            factors.append(f"🚨 HIGH RISK: {risk_reason}")
        elif risk_level >= 2:
            score -= 25
            factors.append(f"⚠️ MEDIUM RISK: {risk_reason}")
        else:
            score -= 10
            factors.append(f"⚡ LOW RISK: {risk_reason}")

    if scoring_margin >= 50000:
        margin_score = min(20, 18 + (scoring_margin - 50000) / 50000)
    elif scoring_margin >= 25000:
        margin_score = 16 + (scoring_margin - 25000) / 12500
    elif scoring_margin >= 15000:
        margin_score = 14 + (scoring_margin - 15000) / 5000
    elif scoring_margin >= 10000:
        margin_score = 12 + (scoring_margin - 10000) / 2500
    elif scoring_margin >= 5000:
        margin_score = 9 + (scoring_margin - 5000) / 1667
    elif scoring_margin >= 2500:
        margin_score = 6 + (scoring_margin - 2500) / 833
    elif scoring_margin >= 1000:
        margin_score = 3 + (scoring_margin - 1000) / 500
    elif scoring_margin >= 500:
        margin_score = 1 + (scoring_margin - 500) / 250
    else:
        margin_score = max(0, scoring_margin / 500)

    margin_score = round(margin_score, 1)
    score += margin_score
    factors.append(f"Margin: {margin_score}/20")

    if volume >= 500:
        volume_score = min(20, 18 + (volume - 500) / 250)
    elif volume >= 400:
        volume_score = 16 + (volume - 300) / 150
    elif volume >= 300:
        volume_score = 14 + (volume - 60) / 30
    elif volume >= 200:
        volume_score = 12 + (volume - 150) / 75
    elif volume >= 100:
        volume_score = 9 + (volume - 100) / 50
    elif volume >= 50:
        volume_score = 7 + (volume - 50) / 25
    elif volume >= 30:
        volume_score = 5 + (volume - 30) / 15
    elif volume >= 15:
        volume_score = 3 + (volume - 15) / 7.5
    elif volume >= 10:
        volume_score = 1 + (volume - 10) / 7.5
    else:
        volume_score = volume / 10

    volume_score = round(volume_score, 1)
    score += volume_score
    factors.append(f"Volume: {volume_score}/20")

    capped_margin_percent = min(25, scoring_margin_percent)

    if capped_margin_percent >= 8:
        roi_score = 13 + (capped_margin_percent - 8) / 8.5
    elif capped_margin_percent >= 5:
        roi_score = 11 + (capped_margin_percent - 5) / 1.5
    elif capped_margin_percent >= 3:
        roi_score = 8 + (capped_margin_percent - 3) / 0.67
    elif capped_margin_percent >= 2:
        roi_score = 6 + (capped_margin_percent - 2) / 0.5
    elif capped_margin_percent >= 1:
        roi_score = 4 + (capped_margin_percent - 1) / 0.5
    elif capped_margin_percent >= 0.5:
        roi_score = 2 + (capped_margin_percent - 0.5) / 0.25
    else:
        roi_score = capped_margin_percent * 4

    roi_score = round(roi_score, 1)
    score += roi_score
    factors.append(f"ROI: {roi_score}/15 ({scoring_margin_percent:.1f}%)")

    stability_score = 8
    trend_info = "No trend data"

    if history_prices and len(history_prices) >= 8:
        try:
            recent_data = history_prices[-15:]
            highs = [entry.get('avgHighPrice', 0) for entry in recent_data if entry.get('avgHighPrice')]
            lows = [entry.get('avgLowPrice', 0) for entry in recent_data if entry.get('avgLowPrice')]

            if len(highs) >= 8 and len(lows) >= 8:
                avg_high = statistics.mean(highs)
                avg_low = statistics.mean(lows)

                if avg_high > 0 and avg_low > 0:
                    high_cv = (statistics.stdev(highs) / avg_high) * 100
                    low_cv = (statistics.stdev(lows) / avg_low) * 100
                    avg_cv = (high_cv + low_cv) / 2

                    if avg_cv < 2:
                        stability_score = 25
                        trend_info = "🟢 Extremely Stable"
                    elif avg_cv < 4:
                        stability_score = 22 + (4 - avg_cv) * 1.5
                        trend_info = "🟢 Very Stable"
                    elif avg_cv < 7:
                        stability_score = 18 + (7 - avg_cv) * 1.33
                        trend_info = "🟢 Stable"
                    elif avg_cv < 12:
                        stability_score = 14 + (12 - avg_cv) * 0.8
                        trend_info = "🟡 Mostly Stable"
                    elif avg_cv < 20:
                        stability_score = 10 + (20 - avg_cv) * 0.5
                        trend_info = "🟡 Moderate"
                    elif avg_cv < 30:
                        stability_score = 6 + (30 - avg_cv) * 0.4
                        trend_info = "🟠 Volatile"
                    else:
                        stability_score = max(3, 6 - (avg_cv - 30) * 0.1)
                        trend_info = "🔴 Very Volatile"

                if avg_high > 0 and avg_low > 0:
                    high_deviation = abs(current_high_price - avg_high) / avg_high
                    low_deviation = abs(current_low_price - avg_low) / avg_low
                    avg_deviation = (high_deviation + low_deviation) / 2

                    if avg_deviation < 0.05:
                        score += 4
                        trend_info += " | Perfect avg"
                    elif avg_deviation < 0.1:
                        score += 3
                        trend_info += " | Near avg"
                    elif avg_deviation < 0.15:
                        score += 2
                        trend_info += " | Close to avg"
                    elif avg_deviation < 0.25:
                        score += 1
                        trend_info += " | Reasonable avg"
                    elif avg_deviation > 0.5:
                        score -= 2
                        trend_info += " | Far from avg"
                    elif avg_deviation > 0.35:
                        score -= 1
                        trend_info += " | Off avg"

        except Exception:
            pass

    stability_score = round(stability_score, 1)
    score += stability_score
    factors.append(f"Stability: {stability_score}/25")

    if limit <= 0:
        limit_score = 2
    else:
        daily_profit_potential = scoring_margin * limit

        if daily_profit_potential >= 2000000:
            limit_score = 13 + min(2, (daily_profit_potential - 2000000) / 2000000)
        elif daily_profit_potential >= 1000000:
            limit_score = 11 + (daily_profit_potential - 1000000) / 500000
        elif daily_profit_potential >= 500000:
            limit_score = 9 + (daily_profit_potential - 500000) / 250000
        elif daily_profit_potential >= 250000:
            limit_score = 7 + (daily_profit_potential - 250000) / 125000
        elif daily_profit_potential >= 100000:
            limit_score = 5 + (daily_profit_potential - 100000) / 75000
        elif daily_profit_potential >= 50000:
            limit_score = 3 + (daily_profit_potential - 50000) / 25000
        else:
            limit_score = 2 + daily_profit_potential / 25000

    limit_score = round(limit_score, 1)
    score += limit_score
    factors.append(f"Limit: {limit_score}/15")

    if volume > 0 and scoring_margin > 0:
        turnover_ratio = volume / max(1, current_low_price / 1000)

        if turnover_ratio > 30:
            liquidity_score = 5
        elif turnover_ratio > 20:
            liquidity_score = 4.5 + (turnover_ratio - 20) / 20
        elif turnover_ratio > 15:
            liquidity_score = 4 + (turnover_ratio - 15) / 10
        elif turnover_ratio > 10:
            liquidity_score = 3.5 + (turnover_ratio - 10) / 10
        elif turnover_ratio > 5:
            liquidity_score = 2.5 + (turnover_ratio - 5) / 5
        elif turnover_ratio > 2:
            liquidity_score = 1.5 + (turnover_ratio - 2) / 3
        elif turnover_ratio > 1:
            liquidity_score = 1 + (turnover_ratio - 1) / 1
        else:
            liquidity_score = 0.5 + turnover_ratio / 2
    else:
        liquidity_score = 0.5

    liquidity_score = round(liquidity_score, 1)
    score += liquidity_score
    factors.append(f"Liquidity: {liquidity_score}/5")

    score = max(0, min(100, round(score, 1)))

    risk_indicator = ""
    if is_suspicious:
        if risk_level >= 3:
            risk_indicator = "🚨 HIGH RISK"
        elif risk_level >= 2:
            risk_indicator = "⚠️ MEDIUM RISK"
        else:
            risk_indicator = "⚡ LOW RISK"
    else:
        risk_indicator = "✅ Clean"

    summary = f"{trend_info} | {risk_indicator} | Score: {score}/100"

    return score, summary, (is_suspicious, risk_level, risk_reason)
