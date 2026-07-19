"""
Shared volume analysis utilities.

Provides reusable volume spike detection and confidence calculations
used across crash risk and flipping trend analysis.
"""

# Volume spike detection thresholds
SPIKE_THRESHOLD_MODERATE = 3.0   # 3x normal volume
SPIKE_THRESHOLD_LARGE = 5.0      # 5x normal volume
SPIKE_THRESHOLD_EXTREME = 10.0   # 10x normal volume

# Volume confidence thresholds (absolute volume)
VOLUME_CONFIDENCE_HIGH = 1000    # High-confidence volume
VOLUME_CONFIDENCE_MEDIUM = 100   # Medium-confidence volume
VOLUME_CONFIDENCE_LOW = 10       # Low-confidence volume

# Spike scoring points
SPIKE_SCORE_EXTREME = 25
SPIKE_SCORE_LARGE = 15
SPIKE_SCORE_MODERATE = 10


def calculate_volume_spike(
    current_5min_volume: int,
    hourly_volume: int,
    spike_threshold: float = SPIKE_THRESHOLD_MODERATE
) -> dict:
    """Calculate volume spike metrics.

    Analyzes whether current 5-minute volume represents an unusual spike
    compared to the hourly baseline.

    Args:
        current_5min_volume: Total volume in the last 5 minutes
        hourly_volume: Total volume over the last hour
        spike_threshold: Minimum magnitude to consider a spike (default: 3.0x)

    Returns:
        Dictionary containing:
            - is_spike (bool): Whether volume exceeds spike threshold
            - magnitude (float): Current volume / normal 5-min average (1.0 = normal)
            - score (int): Spike severity score (0-25)
            - confidence (str): Data quality level ("high", "medium", "low")
    """
    # Calculate expected 5-minute volume from hourly baseline
    # (hourly volume / 12 five-minute periods)
    hourly_avg_5min = hourly_volume / 12 if hourly_volume > 0 else 0

    # Calculate spike magnitude
    if hourly_avg_5min > 0:
        magnitude = current_5min_volume / hourly_avg_5min
    else:
        # No baseline data - can't determine if spike
        magnitude = 1.0

    is_spike = magnitude > spike_threshold

    # Calculate score based on magnitude
    if magnitude > SPIKE_THRESHOLD_EXTREME:
        score = SPIKE_SCORE_EXTREME
    elif magnitude > SPIKE_THRESHOLD_LARGE:
        score = SPIKE_SCORE_LARGE
    elif magnitude > SPIKE_THRESHOLD_MODERATE:
        score = SPIKE_SCORE_MODERATE
    else:
        score = 0

    # Confidence based on absolute hourly volume
    if hourly_volume >= VOLUME_CONFIDENCE_HIGH:
        confidence = "high"
    elif hourly_volume >= VOLUME_CONFIDENCE_MEDIUM:
        confidence = "medium"
    elif hourly_volume >= VOLUME_CONFIDENCE_LOW:
        confidence = "low"
    else:
        confidence = "very_low"

    return {
        "is_spike": is_spike,
        "magnitude": magnitude,
        "score": score,
        "confidence": confidence
    }


def calculate_volume_confidence(total_volume: int) -> str:
    """Calculate confidence level based on absolute volume magnitude.

    Higher volume provides more reliable market signals.
    Low-volume items may show extreme ratios from small trades.

    Args:
        total_volume: Total trading volume (buy + sell combined)

    Returns:
        Confidence level: "high", "medium", "low", or "very_low"
    """
    if total_volume >= VOLUME_CONFIDENCE_HIGH:
        return "high"
    elif total_volume >= VOLUME_CONFIDENCE_MEDIUM:
        return "medium"
    elif total_volume >= VOLUME_CONFIDENCE_LOW:
        return "low"
    else:
        return "very_low"


def calculate_confidence_multiplier(confidence: str) -> float:
    """Get severity score multiplier based on confidence level.

    Reduces severity scores for low-confidence signals to prevent
    false positives from low-volume market noise.

    Args:
        confidence: Confidence level ("high", "medium", "low", "very_low")

    Returns:
        Multiplier to apply to base severity score (0.1 to 1.0)
    """
    multipliers = {
        "high": 1.0,      # Full severity for high-volume signals
        "medium": 0.7,    # Moderate reduction
        "low": 0.4,       # Significant reduction
        "very_low": 0.1   # Heavy reduction for noise
    }
    return multipliers.get(confidence, 1.0)
