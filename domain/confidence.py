"""
Confidence scoring for market events.

Confidence represents how trustworthy a signal is, independent of event severity.
Higher confidence = more reliable signal, less noise.

Confidence is calculated from multiple independent signals, each weighted differently.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from domain.history import MarketHistory


# Confidence signal weights (must sum to 100)
# Updated weighting system with historical persistence
WEIGHT_HISTORICAL_SELL_PRESSURE = 40  # Replaces simple persistence
WEIGHT_PRICE_TREND_CONFIRMATION = 25  # Increased from 20
WEIGHT_VOLUME_QUALITY = 20  # Decreased from 40
WEIGHT_LIQUIDITY = 10  # New component
WEIGHT_DATA_COMPLETENESS = 5  # Decreased from 15

# Legacy weights (for backwards compatibility when history unavailable)
LEGACY_WEIGHT_VOLUME_QUALITY = 40
LEGACY_WEIGHT_SELL_PRESSURE_PERSISTENCE = 25
LEGACY_WEIGHT_PRICE_TREND_CONFIRMATION = 20
LEGACY_WEIGHT_DATA_COMPLETENESS = 15

# Volume quality thresholds (from domain/volume.py)
VOLUME_HIGH = 1000
VOLUME_MEDIUM = 200
VOLUME_LOW = 20

# Sell pressure persistence thresholds
PRESSURE_RATIO_EXTREME = 5.0  # Very high sell pressure
PRESSURE_RATIO_HIGH = 3.0
PRESSURE_RATIO_MODERATE = 2.0

# Price trend confirmation thresholds
PRICE_DECLINE_STRONG = -5.0  # -5% or more
PRICE_DECLINE_MODERATE = -2.0  # -2% to -5%


def calculate_volume_quality_score(
    total_volume: int,
    high_volume: int,
    low_volume: int
) -> int:
    """
    Calculate volume quality score (0-100).

    Higher score = more volume, both buy and sell sides active.

    Factors:
    - Absolute volume level
    - Both buy and sell volume present

    Args:
        total_volume: Total 5-minute volume (high + low)
        high_volume: Buy-side volume
        low_volume: Sell-side volume

    Returns:
        Score 0-100
    """
    score = 0

    # Base score from absolute volume
    if total_volume >= VOLUME_HIGH:
        score = 100
    elif total_volume >= VOLUME_MEDIUM:
        # Linear interpolation between VOLUME_MEDIUM (70) and VOLUME_HIGH (100)
        ratio = (total_volume - VOLUME_MEDIUM) / (VOLUME_HIGH - VOLUME_MEDIUM)
        score = int(70 + (ratio * 30))
    elif total_volume >= VOLUME_LOW:
        # Linear interpolation between VOLUME_LOW (40) and VOLUME_MEDIUM (70)
        ratio = (total_volume - VOLUME_LOW) / (VOLUME_MEDIUM - VOLUME_LOW)
        score = int(40 + (ratio * 30))
    else:
        # Very low volume
        ratio = min(total_volume / VOLUME_LOW, 1.0)
        score = int(10 + (ratio * 30))

    # Penalty if one side has no volume (unreliable ratio)
    if high_volume == 0 or low_volume == 0:
        score = max(10, score // 2)

    return min(100, max(0, score))


def calculate_sell_pressure_persistence_score(
    volume_ratio: float,
    volume_spike: bool,
    spike_magnitude: float
) -> int:
    """
    Calculate sell pressure persistence score (0-100).

    Higher score = sustained sell pressure, not just a spike.

    Current implementation uses available data:
    - Volume ratio magnitude
    - Whether it's a spike vs sustained

    Future enhancement (TODO):
    - Check multiple historical 5m windows
    - Decay score if pressure only appeared in one window

    Args:
        volume_ratio: Sell/buy volume ratio
        volume_spike: Whether current volume is spiking
        spike_magnitude: How much higher than normal (1.0 = normal)

    Returns:
        Score 0-100
    """
    score = 0

    # Base score from ratio magnitude
    if volume_ratio >= PRESSURE_RATIO_EXTREME:
        score = 90
    elif volume_ratio >= PRESSURE_RATIO_HIGH:
        score = 70
    elif volume_ratio >= PRESSURE_RATIO_MODERATE:
        score = 50
    else:
        # Scale linearly for ratios 1.0 - 2.0
        score = int(min(volume_ratio / PRESSURE_RATIO_MODERATE, 1.0) * 50)

    # Reduce confidence if it's a sudden spike (less persistent)
    if volume_spike and spike_magnitude > 5.0:
        # Very sudden spike - likely temporary
        score = int(score * 0.6)
    elif volume_spike and spike_magnitude > 3.0:
        # Moderate spike
        score = int(score * 0.8)

    # TODO: When historical sell pressure data becomes available:
    #
    # Analyze persistence across multiple 5-minute windows:
    #
    # Example 1 - Sustained pressure (HIGH confidence boost):
    #   15 min ago: Pressure 8.0x
    #   10 min ago: Pressure 10.0x
    #   5 min ago:  Pressure 12.0x
    #   Current:    Pressure 14.0x
    #   → Increasing trend = very persistent = +30% confidence boost
    #
    # Example 2 - Consistent pressure (MEDIUM confidence boost):
    #   15 min ago: Pressure 9.0x
    #   10 min ago: Pressure 9.5x
    #   5 min ago:  Pressure 9.2x
    #   Current:    Pressure 9.0x
    #   → Stable high pressure = persistent = +15% confidence boost
    #
    # Example 3 - Sudden spike (LOW confidence, already handled):
    #   15 min ago: Pressure 1.2x
    #   10 min ago: Pressure 1.5x
    #   5 min ago:  Pressure 1.8x
    #   Current:    Pressure 14.0x
    #   → Sudden jump = likely temporary = current penalty applies
    #
    # Implementation approach:
    # - Accept List[Dict] of historical 5m windows
    # - Calculate pressure ratio for each window
    # - Count windows with ratio >= PRESSURE_RATIO_HIGH
    # - If 3+ consecutive windows: boost by 20-30%
    # - If 2 consecutive windows: boost by 10-15%
    # - If only current window: apply existing spike penalty

    return min(100, max(0, score))


def calculate_historical_sell_pressure_score(
    market_history: Optional['MarketHistory'],
    current_ratio: float
) -> int:
    """
    Calculate historical sell pressure persistence score (0-100).

    Uses rolling history to distinguish sustained crashes from temporary spikes.

    Higher score = sell pressure has been elevated for multiple consecutive windows.

    Args:
        market_history: MarketHistory object with rolling snapshots (or None)
        current_ratio: Current sell/buy ratio

    Returns:
        Score 0-100
    """
    # Fallback: No history available, use current ratio only
    if market_history is None or not market_history.has_sufficient_history(min_windows=2):
        # Use simple ratio-based scoring
        if current_ratio >= PRESSURE_RATIO_EXTREME:
            return 70  # Reduced from full score since no persistence data
        elif current_ratio >= PRESSURE_RATIO_HIGH:
            return 50
        elif current_ratio >= PRESSURE_RATIO_MODERATE:
            return 30
        else:
            return 10

    # Import here to avoid circular dependency
    from domain.history import calculate_persistent_sell_pressure

    # Check for persistent sell pressure across history
    is_persistent, consecutive_windows, avg_ratio = calculate_persistent_sell_pressure(
        market_history,
        min_ratio=PRESSURE_RATIO_MODERATE,
        min_windows=3
    )

    score = 0

    # Base score from average historical ratio
    if avg_ratio >= PRESSURE_RATIO_EXTREME:
        score = 90
    elif avg_ratio >= PRESSURE_RATIO_HIGH:
        score = 70
    elif avg_ratio >= PRESSURE_RATIO_MODERATE:
        score = 50
    else:
        score = 30

    # Persistence bonus: More consecutive windows = higher confidence
    if consecutive_windows >= 6:
        # Very persistent (30+ minutes)
        score = min(100, score + 30)
    elif consecutive_windows >= 4:
        # Persistent (20+ minutes)
        score = min(100, score + 20)
    elif consecutive_windows >= 3:
        # Moderately persistent (15+ minutes)
        score = min(100, score + 10)
    elif consecutive_windows >= 2:
        # Slightly persistent (10+ minutes)
        score = min(100, score + 5)
    else:
        # Only current window - likely temporary spike
        score = max(10, score // 2)

    return min(100, max(0, score))


def calculate_price_trend_confirmation_score(
    volume_ratio: float,
    price_decline_percent: Optional[float]
) -> int:
    """
    Calculate price trend confirmation score (0-100).

    Higher score = price movement confirms the volume signal.

    Logic:
    - High sell pressure + price declining = confirms crash (high score)
    - High sell pressure + flat/rising price = conflicting signal (low score)
    - No price data available = neutral/medium score

    Args:
        volume_ratio: Sell/buy volume ratio
        price_decline_percent: Price change % (negative = decline, None = no data)

    Returns:
        Score 0-100
    """
    # No price history available
    if price_decline_percent is None:
        # Can't confirm or deny, return neutral-low score
        return 40

    # Price is declining - confirms sell pressure
    if price_decline_percent <= PRICE_DECLINE_STRONG:
        # Strong decline confirms high sell pressure
        return 100
    elif price_decline_percent <= PRICE_DECLINE_MODERATE:
        # Moderate decline
        return 80
    elif price_decline_percent < 0:
        # Small decline
        return 60

    # Price is flat or rising despite sell pressure
    # This is conflicting - reduces confidence
    if price_decline_percent == 0.0:
        # Flat price
        return 50
    elif price_decline_percent <= 2.0:
        # Slightly rising
        return 30
    else:
        # Strongly rising despite sell pressure - very conflicting
        return 10


def calculate_data_completeness_score(
    has_current_price: bool,
    has_five_min_history: bool,
    has_volume_data: bool,
    price_decline_percent: Optional[float]
) -> int:
    """
    Calculate data completeness score (0-100).

    Higher score = more data available to make decision.

    Missing data reduces confidence in the signal.

    Args:
        has_current_price: Whether current price data exists
        has_five_min_history: Whether 5-minute historical data exists
        has_volume_data: Whether volume data exists
        price_decline_percent: Price trend (None = no history)

    Returns:
        Score 0-100
    """
    score = 0

    # Each data source adds to completeness
    if has_current_price:
        score += 30

    if has_five_min_history and price_decline_percent is not None:
        score += 40  # Historical price data is most valuable
    elif has_five_min_history:
        score += 20  # Have 5m data but no price history

    if has_volume_data:
        score += 30

    return min(100, max(0, score))


def calculate_crash_confidence(
    volume_confidence: str,
    total_volume: int,
    high_volume: int,
    low_volume: int,
    volume_ratio: float,
    volume_spike: bool,
    spike_magnitude: float,
    price_decline_percent: Optional[float],
    has_current_price: bool = True,
    has_five_min_history: bool = True,
    has_volume_data: bool = True
) -> int:
    """
    Calculate overall confidence score for crash risk event.

    Combines multiple independent signals with weighted scoring.

    Signal breakdown:
    - Volume quality (40%): Absolute volume levels and data quality
    - Sell pressure persistence (25%): Is this sustained or temporary?
    - Price trend confirmation (20%): Does price confirm sell pressure?
    - Data completeness (15%): How much data do we have?

    Args:
        volume_confidence: Volume quality classification (high/medium/low/very_low)
        total_volume: Total 5-minute volume
        high_volume: Buy-side volume
        low_volume: Sell-side volume
        volume_ratio: Sell/buy ratio
        volume_spike: Whether volume is spiking
        spike_magnitude: Spike multiplier
        price_decline_percent: Price change % (None if no history)
        has_current_price: Whether current price exists
        has_five_min_history: Whether 5m data exists
        has_volume_data: Whether volume data exists

    Returns:
        Confidence score 0-100
    """
    # Calculate each signal component
    volume_quality = calculate_volume_quality_score(
        total_volume,
        high_volume,
        low_volume
    )

    persistence = calculate_sell_pressure_persistence_score(
        volume_ratio,
        volume_spike,
        spike_magnitude
    )

    price_confirmation = calculate_price_trend_confirmation_score(
        volume_ratio,
        price_decline_percent
    )

    data_completeness = calculate_data_completeness_score(
        has_current_price,
        has_five_min_history,
        has_volume_data,
        price_decline_percent
    )

    # Weighted combination
    confidence_score = (
        (volume_quality * WEIGHT_VOLUME_QUALITY) +
        (persistence * WEIGHT_SELL_PRESSURE_PERSISTENCE) +
        (price_confirmation * WEIGHT_PRICE_TREND_CONFIRMATION) +
        (data_completeness * WEIGHT_DATA_COMPLETENESS)
    ) / 100

    # Round to integer 0-100
    return int(min(100, max(0, confidence_score)))


def calculate_crash_confidence_with_history(
    market_history: Optional['MarketHistory'],
    volume_confidence: str,
    total_volume: int,
    high_volume: int,
    low_volume: int,
    volume_ratio: float,
    volume_spike: bool,
    spike_magnitude: float,
    price_decline_percent: Optional[float],
    current_hourly_volume: int = 0,
    has_current_price: bool = True,
    has_five_min_history: bool = True,
    has_volume_data: bool = True
) -> int:
    """
    Calculate overall confidence score with historical persistence analysis.

    Uses rolling history to detect sustained trends vs temporary spikes.

    New signal breakdown (when history available):
    - Historical sell pressure persistence (40%): Multiple windows of elevated pressure
    - Price trend confirmation (25%): Does price confirm sell pressure?
    - Volume quality (20%): Absolute volume levels
    - Liquidity (10%): Consistent volume and liquidity
    - Data completeness (5%): How much data do we have?

    Falls back to legacy scoring if history unavailable.

    Args:
        market_history: MarketHistory object with rolling snapshots (or None)
        volume_confidence: Volume quality classification (high/medium/low/very_low)
        total_volume: Total 5-minute volume
        high_volume: Buy-side volume
        low_volume: Sell-side volume
        volume_ratio: Sell/buy ratio
        volume_spike: Whether volume is spiking
        spike_magnitude: Spike multiplier
        price_decline_percent: Price change % (None if no history)
        current_hourly_volume: Current hourly trading volume
        has_current_price: Whether current price exists
        has_five_min_history: Whether 5m data exists
        has_volume_data: Whether volume data exists

    Returns:
        Confidence score 0-100
    """
    # Check if we have sufficient history for new scoring
    has_history = (
        market_history is not None
        and market_history.has_sufficient_history(min_windows=2)
    )

    if not has_history:
        # Fall back to legacy scoring
        return calculate_crash_confidence(
            volume_confidence,
            total_volume,
            high_volume,
            low_volume,
            volume_ratio,
            volume_spike,
            spike_magnitude,
            price_decline_percent,
            has_current_price,
            has_five_min_history,
            has_volume_data
        )

    # Import here to avoid circular dependency
    from domain.history import calculate_liquidity_score

    # Calculate each signal component with historical data
    volume_quality = calculate_volume_quality_score(
        total_volume,
        high_volume,
        low_volume
    )

    # Use historical persistence instead of simple persistence
    historical_pressure = calculate_historical_sell_pressure_score(
        market_history,
        volume_ratio
    )

    price_confirmation = calculate_price_trend_confirmation_score(
        volume_ratio,
        price_decline_percent
    )

    liquidity = calculate_liquidity_score(
        market_history,
        current_hourly_volume
    )

    data_completeness = calculate_data_completeness_score(
        has_current_price,
        has_five_min_history,
        has_volume_data,
        price_decline_percent
    )

    # Weighted combination with new weights
    confidence_score = (
        (historical_pressure * WEIGHT_HISTORICAL_SELL_PRESSURE) +
        (price_confirmation * WEIGHT_PRICE_TREND_CONFIRMATION) +
        (volume_quality * WEIGHT_VOLUME_QUALITY) +
        (liquidity * WEIGHT_LIQUIDITY) +
        (data_completeness * WEIGHT_DATA_COMPLETENESS)
    ) / 100

    # Round to integer 0-100
    return int(min(100, max(0, confidence_score)))
