import statistics
from typing import Dict, List


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


def analyze_alchemy_crash_risk(item_id: int, five_min_data: Dict, volume_data: Dict) -> Dict:
    """
    Simplified alchemy crash detection - when low price volume >> high price volume.

    Args:
        item_id: Item ID to analyze
        five_min_data: 5-minute data dictionary
        volume_data: Hourly volume data dictionary

    Returns:
        Dictionary with simple crash analysis for alchemy items
    """
    result = {
        'status': 'stable',
        'high_volume': 0,
        'low_volume': 0,
        'hourly_volume': 0,
        'volume_ratio': 0,
        'volume_spike': False,
        'alert_percent': 0,
        'recommendation': 'safe'
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

        if hourly_vol > 0:
            hourly_avg_5min = hourly_vol / 12
            current_5min_total = high_vol + low_vol

            if current_5min_total > (hourly_avg_5min * 3):
                result['volume_spike'] = True

        if high_vol > 0:
            volume_ratio = low_vol / high_vol
            result['volume_ratio'] = round(volume_ratio, 1)
            result['alert_percent'] = round((volume_ratio - 1) * 100, 1)
        else:
            if low_vol > 0:
                result['volume_ratio'] = 999
                result['alert_percent'] = 999
            else:
                return result

        crash_score = 0

        if result['volume_ratio'] >= 5.0:
            crash_score += 30
        elif result['volume_ratio'] >= 3.0:
            crash_score += 20
        elif result['volume_ratio'] >= 2.0:
            crash_score += 10

        if result['volume_spike']:
            crash_score += 15

        if crash_score >= 35:
            result['status'] = 'crashing'
            result['recommendation'] = 'buy low'
        elif crash_score >= 20:
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
