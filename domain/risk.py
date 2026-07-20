import statistics
from typing import Dict, List, Optional
from . import volume
from . import confidence


# Crash risk detection thresholds
VOLUME_RATIO_EXTREME = 5.0    # 5x+ sell pressure vs buy pressure
VOLUME_RATIO_HIGH = 3.0       # 3-5x sell pressure
VOLUME_RATIO_MODERATE = 2.0   # 2-3x sell pressure

# Crash risk scoring points
SCORE_EXTREME_IMBALANCE = 30
SCORE_HIGH_IMBALANCE = 20
SCORE_MODERATE_IMBALANCE = 10
SCORE_PRICE_DECLINE = 10

# Crash status thresholds
CRASH_THRESHOLD = 35  # "crashing" status
RISK_THRESHOLD = 20   # "crash_risk" status


def detect_pump_and_dump(history_prices: List[Dict], current_high: int, current_low: int) -> tuple:
    """
    Enhanced pump and dump detection with multiple criteria.

    Args:
        history_prices: List of historical price data
        current_high: Current high price
        current_low: Current low price

    Returns:
        Tuple of (is_suspicious, risk_level, reason)
    """
    if not history_prices or len(history_prices) < 10:
        return False, 0, "Insufficient data"

    try:
        recent_data = history_prices[-20:]

        highs = [entry.get('avgHighPrice', 0) for entry in recent_data if entry.get('avgHighPrice')]
        lows = [entry.get('avgLowPrice', 0) for entry in recent_data if entry.get('avgLowPrice')]
        volumes = [entry.get('highPriceVolume', 0) + entry.get('lowPriceVolume', 0)
                  for entry in recent_data
                  if entry.get('highPriceVolume') is not None and entry.get('lowPriceVolume') is not None]

        if len(highs) < 10 or len(lows) < 10:
            return False, 0, "Insufficient price data"

        avg_high = statistics.mean(highs)
        avg_low = statistics.mean(lows)
        median_high = statistics.median(highs)
        median_low = statistics.median(lows)

        high_std = statistics.stdev(highs) if len(highs) > 1 else 0
        low_std = statistics.stdev(lows) if len(lows) > 1 else 0

        risk_factors = []
        risk_score = 0

        high_spike_ratio = current_high / avg_high if avg_high > 0 else 1
        low_spike_ratio = current_low / avg_low if avg_low > 0 else 1

        if high_spike_ratio > 1.5:
            risk_score += 30
            risk_factors.append(f"High spike: {high_spike_ratio:.1f}x avg")
        elif high_spike_ratio > 1.3:
            risk_score += 15
            risk_factors.append(f"Moderate high spike: {high_spike_ratio:.1f}x avg")

        if low_spike_ratio > 1.2:
            risk_score += 25
            risk_factors.append(f"Low spike: {low_spike_ratio:.1f}x avg")

        if avg_high > 0:
            high_volatility = (high_std / avg_high) * 100
            if high_volatility > 20:
                risk_score += 20
                risk_factors.append(f"High volatility: {high_volatility:.1f}%")
            elif high_volatility > 15:
                risk_score += 10
                risk_factors.append(f"Moderate volatility: {high_volatility:.1f}%")

        high_median_deviation = abs(current_high - median_high) / median_high if median_high > 0 else 0
        if high_median_deviation > 0.5:
            risk_score += 15
            risk_factors.append(f"Median deviation: {high_median_deviation:.1%}")

        if volumes and len(volumes) >= 5:
            recent_volume = statistics.mean(volumes[-3:])
            older_volume = statistics.mean(volumes[:-3])

            if older_volume > 0:
                volume_change = recent_volume / older_volume
                if volume_change > 3.0:
                    risk_score += 20
                    risk_factors.append(f"Volume spike: {volume_change:.1f}x")
                elif volume_change < 0.3:
                    risk_score += 15
                    risk_factors.append(f"Volume drop: {volume_change:.1%}")

        if len(highs) >= 5:
            recent_highs = highs[-3:]
            if len(set(recent_highs)) > 1:
                max_recent = max(recent_highs)
                min_recent = min(recent_highs)
                if min_recent > 0:
                    recent_volatility = (max_recent - min_recent) / min_recent
                    if recent_volatility > 0.3:
                        risk_score += 15
                        risk_factors.append(f"Recent swing: {recent_volatility:.1%}")

        current_margin_percent = ((current_high - current_low) / current_low * 100) if current_low > 0 else 0
        if current_margin_percent > 25:
            risk_score += 25
            risk_factors.append(f"High margin: {current_margin_percent:.1f}%")
        elif current_margin_percent > 15:
            risk_score += 10
            risk_factors.append(f"Elevated margin: {current_margin_percent:.1f}%")

        if risk_score >= 30:
            return True, 3, "HIGH: " + "; ".join(risk_factors[:3])
        elif risk_score >= 20:
            return True, 2, "MEDIUM: " + "; ".join(risk_factors[:2])
        elif risk_score >= 10:
            return True, 1, "LOW: " + "; ".join(risk_factors[:2])
        else:
            return False, 0, "Clean"

    except Exception as e:
        return False, 0, f"Analysis error: {str(e)}"


def analyze_alchemy_crash_risk(
    item_id: int,
    five_min_data: Dict,
    volume_data: Dict,
    current_prices: Dict,
    market_history_data: Dict = None
) -> Dict:
    """
    Alchemy crash detection based on volume imbalance and price decline.

    Detects when sell pressure significantly exceeds buy pressure, indicating
    a potential price crash where alchemy items can be bought below normal value.

    Enhanced with rolling historical analysis to distinguish sustained crashes
    from temporary spikes.

    Args:
        item_id: Item ID to analyze
        five_min_data: 5-minute data dictionary (avgHighPrice, avgLowPrice, volumes)
        volume_data: Hourly volume data dictionary
        current_prices: Current price data dictionary (high, low prices)
        market_history_data: Optional Dict[int, MarketHistory] for historical analysis

    Returns:
        Dictionary with crash analysis including confidence and trend metrics
    """
    result = {
        'status': 'stable',
        'high_volume': 0,
        'low_volume': 0,
        'hourly_volume': 0,
        'volume_ratio': 0,
        'volume_spike': False,
        'severity_score': 0,
        'alert_percent': 0,
        'recommendation': 'safe',
        # Confidence fields
        'volume_confidence': 'very_low',
        'confidence_score': 10,
        'total_volume': 0,
        'price_decline_percent': None,
        'spike_magnitude': 1.0,
        # Historical trend metrics (None if history unavailable)
        'trend_15m': None,
        'trend_30m': None,
        'trend_60m': None,
        'consecutive_down_windows': None,
        'persistent_sell_pressure': None,
        'largest_drawdown': None
    }

    try:
        five_min_info = five_min_data.get(item_id)
        if not five_min_info:
            return result

        high_vol = five_min_info.get('high_volume', 0)
        low_vol = five_min_info.get('low_volume', 0)
        hourly_vol = volume_data.get(item_id, 0)

        result['high_volume'] = high_vol
        result['low_volume'] = low_vol
        result['hourly_volume'] = hourly_vol

        # Calculate total volume and confidence
        total_vol = high_vol + low_vol
        result['total_volume'] = total_vol
        result['volume_confidence'] = volume.calculate_volume_confidence(total_vol)

        # Calculate volume spike using shared module
        spike_analysis = volume.calculate_volume_spike(total_vol, hourly_vol)
        result['volume_spike'] = spike_analysis['is_spike']
        result['spike_magnitude'] = spike_analysis['magnitude']

        # Calculate volume ratio (sell pressure / buy pressure)
        if high_vol > 0:
            volume_ratio = low_vol / high_vol
            result['volume_ratio'] = round(volume_ratio, 1)
            result['alert_percent'] = round((volume_ratio - 1) * 100, 1)
        else:
            # Insufficient data - no buy volume
            if low_vol > 0:
                # Don't use 999 - mark as insufficient data
                result['volume_ratio'] = 0
                result['alert_percent'] = 0
                result['volume_confidence'] = 'very_low'
                return result
            else:
                # No volume at all
                return result

        # Calculate price decline percentage
        # Note: current_prices uses string keys
        # Note: five_min_data uses 'avg_low' key (set in engine/calculator.py:131)
        current_price_info = current_prices.get(str(item_id), {})
        current_low = current_price_info.get('low', 0)
        five_min_low = five_min_info.get('avg_low', None)

        if five_min_low is None:
            # No historical data available
            result['price_decline_percent'] = None
        elif current_low > 0 and five_min_low > 0:
            # Calculate percentage change
            price_decline = ((current_low - five_min_low) / five_min_low) * 100
            result['price_decline_percent'] = round(price_decline, 2)
        else:
            # History exists but prices are invalid
            result['price_decline_percent'] = None

        # Calculate base crash score using constants
        crash_score = 0

        if result['volume_ratio'] >= VOLUME_RATIO_EXTREME:
            crash_score += SCORE_EXTREME_IMBALANCE
        elif result['volume_ratio'] >= VOLUME_RATIO_HIGH:
            crash_score += SCORE_HIGH_IMBALANCE
        elif result['volume_ratio'] >= VOLUME_RATIO_MODERATE:
            crash_score += SCORE_MODERATE_IMBALANCE

        # Add spike score from shared calculation
        crash_score += spike_analysis['score']

        # Boost score if price is actually declining
        if result['price_decline_percent'] is not None and result['price_decline_percent'] < -2.0:
            crash_score += SCORE_PRICE_DECLINE

        # Severity is independent of confidence
        result['severity_score'] = crash_score

        # Get market history for this item if available
        market_history = None
        if market_history_data and item_id in market_history_data:
            market_history = market_history_data[item_id]

        # Calculate historical trend metrics if history available
        if market_history and market_history.has_sufficient_history(min_windows=2):
            from domain import history

            # Calculate price trends over different time windows
            result['trend_15m'] = history.calculate_price_trend(market_history, windows=3)
            result['trend_30m'] = history.calculate_price_trend(market_history, windows=6)
            result['trend_60m'] = history.calculate_price_trend(market_history, windows=12)

            # Calculate persistence metrics
            result['consecutive_down_windows'] = history.calculate_consecutive_down_windows(market_history)

            is_persistent, consecutive_windows, avg_ratio = history.calculate_persistent_sell_pressure(
                market_history,
                min_ratio=2.0,
                min_windows=3
            )
            result['persistent_sell_pressure'] = is_persistent

            result['largest_drawdown'] = history.calculate_largest_drawdown(market_history)

        # Calculate confidence score using multi-signal framework
        # Use historical scoring if available, otherwise legacy scoring
        result['confidence_score'] = confidence.calculate_crash_confidence_with_history(
            market_history=market_history,
            volume_confidence=result['volume_confidence'],
            total_volume=total_vol,
            high_volume=high_vol,
            low_volume=low_vol,
            volume_ratio=result['volume_ratio'],
            volume_spike=result['volume_spike'],
            spike_magnitude=result['spike_magnitude'],
            price_decline_percent=result['price_decline_percent'],
            current_hourly_volume=hourly_vol,
            has_current_price=bool(current_price_info.get('low')),
            has_five_min_history=bool(five_min_info),
            has_volume_data=bool(hourly_vol)
        )

        # Assign status based on severity
        if crash_score >= CRASH_THRESHOLD:
            result['status'] = 'crashing'
            result['recommendation'] = 'buy low'
        elif crash_score >= RISK_THRESHOLD:
            result['status'] = 'crash_risk'
            result['recommendation'] = 'consider buying'
        else:
            result['status'] = 'stable'
            result['recommendation'] = 'stable'

    except Exception:
        result['status'] = 'error'

    return result


def analyze_flipping_trend(item_id: int, current_prices: Dict, five_min_data: Dict,
                          volume_data: Dict) -> Dict:
    """
    Simplified flipping trend analysis for Discord alerts.

    Args:
        item_id: Item ID to analyze
        current_prices: Current price data dictionary
        five_min_data: 5-minute data dictionary
        volume_data: Hourly volume data dictionary

    Returns:
        Dictionary with simple trend analysis
    """
    result = {
        'status': 'stable',
        'high_volume': 0,
        'low_volume': 0,
        'hourly_volume': 0,
        'volume_spike': False,
        'severity_score': 0,
        'price_change_percent': 0,
        'recommendation': 'safe'
    }

    try:
        current_price = current_prices.get(str(item_id))
        five_min_info = five_min_data.get(item_id)
        hourly_vol = volume_data.get(item_id, 0)

        if not current_price or not five_min_info:
            return result

        result['high_volume'] = five_min_info.get('high_volume', 0)
        result['low_volume'] = five_min_info.get('low_volume', 0)
        result['hourly_volume'] = hourly_vol

        if hourly_vol > 0:
            hourly_avg_5min = hourly_vol / 12
            current_5min_total = result['high_volume'] + result['low_volume']
            if current_5min_total > (hourly_avg_5min * 3):
                result['volume_spike'] = True

        current_high = current_price.get('high')
        five_min_high = five_min_info.get('high')

        if current_high and five_min_high and five_min_high > 0:
            price_change = ((current_high - five_min_high) / five_min_high) * 100
            result['price_change_percent'] = round(price_change, 1)

            high_vol = result['high_volume']
            low_vol = result['low_volume']
            volume_imbalance = False

            if high_vol > 0:
                volume_ratio = low_vol / high_vol
                volume_imbalance = volume_ratio > 2.0
            elif low_vol > 10:
                volume_imbalance = True

            crash_score = 0
            surge_score = 0

            if price_change <= -5.0:
                crash_score += 30
            elif price_change <= -2.0:
                crash_score += 15
            elif price_change >= 5.0:
                surge_score += 30
            elif price_change >= 2.0:
                surge_score += 15

            if volume_imbalance:
                crash_score += 15
            if result['volume_spike'] and price_change < -1:
                crash_score += 20
            if result['volume_spike'] and price_change > 1:
                surge_score += 10

            result['severity_score'] = max(crash_score, surge_score)

            if crash_score >= 35:
                result['status'] = 'crashing'
                result['recommendation'] = 'avoid'
            elif crash_score >= 20:
                result['status'] = 'crash_risk'
                result['recommendation'] = 'caution'
            elif surge_score >= 35:
                result['status'] = 'surging'
                result['recommendation'] = 'opportunity'
            elif surge_score >= 15:
                result['status'] = 'surge_risk'
                result['recommendation'] = 'caution'
            else:
                result['status'] = 'stable'
                result['recommendation'] = 'safe'

    except Exception:
        result['status'] = 'error'

    return result


def generate_crash_explanation(
    status: str,
    volume_ratio: float,
    volume_spike: bool,
    severity_score: int
) -> str:
    """
    Generate plain-English explanation of crash risk situation.

    Args:
        status: Current status ('crash_risk' or 'crashing')
        volume_ratio: Ratio of sell volume to buy volume
        volume_spike: Whether there's unusual volume activity
        severity_score: Risk severity (0-100)

    Returns:
        Business-focused explanation string
    """
    if status == 'crashing':
        base = f"Heavy sell pressure detected: {volume_ratio:.1f}x more players selling than buying."
    elif status == 'crash_risk':
        base = f"Elevated sell pressure: {volume_ratio:.1f}x more players selling than buying."
    else:
        return "Market conditions stable"

    if volume_spike:
        base += " Unusual volume activity detected."

    if severity_score >= 35:
        base += " Price likely declining rapidly."
    elif severity_score >= 20:
        base += " Price may be declining."

    return base


def generate_crash_impact_summary(
    profit: int,
    roi_percent: float,
    max_profit_per_limit: int,
    trade_limit: int
) -> str:
    """
    Generate summary of profit opportunity impact.

    Args:
        profit: Profit per item
        roi_percent: Return on investment percentage
        max_profit_per_limit: Maximum profit if buying full limit
        trade_limit: How many can be bought

    Returns:
        Business-focused impact summary
    """
    parts = []

    # Profit per item
    parts.append(f"{profit:,} gp profit per alch")

    # Max profit potential
    if max_profit_per_limit > 0:
        parts.append(f"{max_profit_per_limit:,} gp max (limit: {trade_limit})")

    # ROI
    if roi_percent >= 50:
        parts.append(f"{roi_percent:.0f}% ROI (excellent)")
    elif roi_percent >= 30:
        parts.append(f"{roi_percent:.0f}% ROI (good)")
    elif roi_percent >= 15:
        parts.append(f"{roi_percent:.0f}% ROI (moderate)")
    else:
        parts.append(f"{roi_percent:.0f}% ROI")

    return " • ".join(parts)


def generate_flip_explanation(
    status: str,
    price_change_percent: float,
    volume_spike: bool,
    severity_score: int
) -> str:
    """
    Generate plain-English explanation of flipping trend situation.

    Args:
        status: Current status ('crashing', 'crash_risk', 'surging', 'surge_risk')
        price_change_percent: Price change percentage
        volume_spike: Whether there's unusual volume activity
        severity_score: Severity score (0-100)

    Returns:
        Business-focused explanation string
    """
    if status == 'crashing':
        base = f"Price crashing: down {abs(price_change_percent):.1f}% in last 5 minutes."
    elif status == 'crash_risk':
        base = f"Price declining: down {abs(price_change_percent):.1f}% in last 5 minutes."
    elif status == 'surging':
        base = f"Price surging: up {price_change_percent:.1f}% in last 5 minutes."
    elif status == 'surge_risk':
        base = f"Price rising: up {price_change_percent:.1f}% in last 5 minutes."
    else:
        return "Price stable"

    if volume_spike:
        base += " Unusual trading activity detected."

    if status in ['crashing', 'crash_risk']:
        if severity_score >= 35:
            base += " Avoid buying - high crash risk."
        elif severity_score >= 20:
            base += " Exercise caution."
    elif status in ['surging', 'surge_risk']:
        if severity_score >= 35:
            base += " Strong upward momentum."
        elif severity_score >= 15:
            base += " Potential opportunity."

    return base


def generate_flip_impact_summary(
    margin: int,
    margin_percent: float,
    max_profit_per_limit: int,
    trade_limit: int
) -> str:
    """
    Generate summary of flipping opportunity impact.

    Args:
        margin: Margin per flip
        margin_percent: Margin as percentage
        max_profit_per_limit: Maximum profit if flipping full limit
        trade_limit: How many can be flipped

    Returns:
        Business-focused impact summary
    """
    parts = []

    # Margin per flip
    parts.append(f"{margin:,} gp margin per flip")

    # Margin percentage
    if margin_percent >= 10:
        parts.append(f"{margin_percent:.1f}% margin (excellent)")
    elif margin_percent >= 5:
        parts.append(f"{margin_percent:.1f}% margin (good)")
    else:
        parts.append(f"{margin_percent:.1f}% margin")

    # Max profit potential
    if max_profit_per_limit > 0:
        parts.append(f"{max_profit_per_limit:,} gp max (limit: {trade_limit})")

    return " • ".join(parts)
