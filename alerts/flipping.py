import logging
import statistics
from typing import List, Dict, Any
from collections import defaultdict

from events import FlippingTrendEvent
from domain import risk, flipping, confidence
import config

logger = logging.getLogger(__name__)


# Quality filter defaults
# These ensure flipping alerts are actionable and reduce noise from poor candidates

# Items to always exclude (manipulated or unsuitable for flipping)
EXCLUDED_ITEMS = [
    "Old school bond",  # Manipulated, poor liquidity
]

# Quality thresholds for ranking penalties
# These influence ranking but don't eliminate opportunities
# Items below these thresholds rank lower but remain visible

# Hourly volume threshold for ranking penalty
# Items below this receive reduced ranking score
DEFAULT_HOURLY_VOLUME_THRESHOLD = 50

# Trade limit threshold for ranking penalty
# Items below this receive reduced ranking score
DEFAULT_TRADE_LIMIT_THRESHOLD = 10

# Minimum confidence score threshold (not currently used for filtering)
# Low confidence indicates unreliable or conflicting signals
DEFAULT_MIN_CONFIDENCE = 40


# Opportunity Score Weights
# Used to rank flipping opportunities by quality, not just absolute profit
# These weights determine how different factors contribute to the final ranking
#
# Philosophy:
# - Net profit is the primary driver (50%)
# - Liquidity ensures you can execute (25%)
# - Capital efficiency rewards better ROI (15%)
# - Scalability considers trade limits (8%)
# - Trend provides small context bonus (2%)
#
# Total: 100%
WEIGHT_NET_PROFIT = 50
WEIGHT_LIQUIDITY = 25
WEIGHT_CAPITAL_EFFICIENCY = 15
WEIGHT_SCALABILITY = 8
WEIGHT_TREND_BONUS = 2

# Trend multipliers for opportunity score
# Trends provide context but don't dominate ranking
TREND_MULTIPLIER_STRONG = 1.10    # surge/crash (10% bonus)
TREND_MULTIPLIER_MODERATE = 1.05  # surge_risk/crash_risk (5% bonus)
TREND_MULTIPLIER_STABLE = 1.00    # stable (no bonus)


def _format_stat_summary(values: List[float], label: str) -> str:
    """Format min/median/max statistics for a metric."""
    if not values:
        return f"{label}: N/A"

    return (
        f"{label}: "
        f"min={min(values):.0f}, "
        f"median={statistics.median(values):.0f}, "
        f"max={max(values):.0f}"
    )


def _log_filter_diagnostics(diagnostics: Dict[str, Any], final_count: int) -> None:
    """
    Log comprehensive diagnostic information about the filtering pipeline.

    Shows:
    - Item counts after each stage
    - Statistics for filtered items
    - Top 10 items removed by each filter with reasons
    """
    logger.info("=" * 80)
    logger.info("FLIPPING ALERTS FILTER DIAGNOSTICS")
    logger.info("=" * 80)

    # Stage-by-stage item counts
    logger.info("\n--- PIPELINE STAGE COUNTS ---")

    raw_count = diagnostics['stage_counts']['raw_candidates']
    logger.info(f"Raw candidates:                {raw_count:>4}")

    # Calculate cumulative counts after hard filters
    exclusion_filtered = len(diagnostics['filtered_items']['exclusion_list'])
    after_exclusion = raw_count - exclusion_filtered
    logger.info(f"After exclusion filter:        {after_exclusion:>4}")

    ge_tax_filtered = len(diagnostics['filtered_items']['ge_tax_filter'])
    after_ge_tax = after_exclusion - ge_tax_filtered
    logger.info(f"After GE tax filter:           {after_ge_tax:>4}")

    logger.info(f"Opportunities created:         {after_ge_tax:>4}")

    # Show ranking penalties (not eliminations)
    limit_penalized = len(diagnostics['filtered_items'].get('trade_limit_penalty', []))
    volume_penalized = len(diagnostics['filtered_items'].get('hourly_volume_penalty', []))
    logger.info(f"  Low trade limit (penalty):   {limit_penalized:>4}")
    logger.info(f"  Low volume (penalty):        {volume_penalized:>4}")

    logger.info(f"Final ranked alerts:           {final_count:>4}")

    # Statistics for filtered items
    logger.info("\n--- FILTERED ITEM STATISTICS ---")

    stats = diagnostics['filter_stats']

    # GE Tax filter stats (hard filter)
    if stats.get('net_profit_filtered'):
        logger.info("\nGE Tax Filter (net_profit <= 0) [ELIMINATED]:")
        logger.info(f"  {_format_stat_summary(stats['net_profit_filtered'], 'Net Profit (gp)')}")
        logger.info(f"  {_format_stat_summary(stats['gross_margin_filtered'], 'Gross Margin (gp)')}")
        logger.info(f"  {_format_stat_summary(stats['ge_tax_filtered'], 'GE Tax (gp)')}")

    # Trade Limit penalty stats (ranking penalty, not eliminated)
    if stats.get('trade_limit_penalized'):
        logger.info("\nTrade Limit Penalty (ranked lower, not eliminated):")
        logger.info(f"  {_format_stat_summary(stats['trade_limit_penalized'], 'Trade Limit')}")
        logger.info(f"  {_format_stat_summary(stats['net_profit_trade_limit_penalized'], 'Net Profit (gp)')}")
        logger.info(f"  {_format_stat_summary(stats['margin_percent_trade_limit_penalized'], 'Margin (%)')}")

    # Hourly Volume penalty stats (ranking penalty, not eliminated)
    if stats.get('hourly_volume_penalized'):
        logger.info("\nHourly Volume Penalty (ranked lower, not eliminated):")
        logger.info(f"  {_format_stat_summary(stats['hourly_volume_penalized'], 'Hourly Volume')}")
        logger.info(f"  {_format_stat_summary(stats['net_profit_volume_penalized'], 'Net Profit (gp)')}")
        logger.info(f"  {_format_stat_summary(stats['margin_percent_volume_penalized'], 'Margin (%)')}")

    # Top 10 items removed by each filter
    logger.info("\n--- TOP 10 FILTERED ITEMS BY STAGE ---")

    filtered = diagnostics['filtered_items']

    if filtered['exclusion_list']:
        logger.info("\nRemoved (Exclusion List):")
        for name, reason in filtered['exclusion_list'][:10]:
            logger.info(f"  {name}: {reason}")

    if filtered.get('ge_tax_filter'):
        logger.info("\nEliminated (GE Tax - net profit <= 0):")
        for name, reason in filtered['ge_tax_filter'][:10]:
            logger.info(f"  {name}: {reason}")

    if filtered.get('trade_limit_penalty'):
        logger.info("\nPenalized (Low Trade Limit - ranked lower):")
        for name, reason in filtered['trade_limit_penalty'][:10]:
            logger.info(f"  {name}: {reason}")

    if filtered.get('hourly_volume_penalty'):
        logger.info("\nPenalized (Low Hourly Volume - ranked lower):")
        for name, reason in filtered['hourly_volume_penalty'][:10]:
            logger.info(f"  {name}: {reason}")

    logger.info("\n" + "=" * 80)
    logger.info("END DIAGNOSTICS")
    logger.info("=" * 80 + "\n")


def get_flipping_trend_alerts(
    calculator,
    min_margin: int = 1000,
    min_volume: int = 20,
    min_limit: int = None,
    min_hourly_volume: int = None,
    max_alerts: int = 15
) -> List[FlippingTrendEvent]:
    """
    Get actionable flipping opportunities with realistic profit calculations.

    Calculates net profit after 2% GE tax. Uses ranking-based quality assessment
    instead of hard filters to maximize opportunity visibility.

    Hard filters (eliminate opportunities):
    - Exclusion list (manipulated items like Old School Bond)
    - Net profit <= 0 (after GE tax)

    Ranking penalties (lower rank, not eliminated):
    - Low trade limit (< 10): Reduced scalability score
    - Low hourly volume (< 50): Reduced liquidity score
    - Low confidence: Informational only

    Trend metadata included:
    - status: stable, surge_risk, surging, crash_risk, crashing
    - price_change_percent: 5-minute price movement
    - volume_spike: unusual trading activity
    - severity_score: trend strength (0-100)

    Ranking prioritizes:
    1. Net profit (50% - primary driver)
    2. Liquidity (25% - hourly volume)
    3. Capital efficiency (15% - profit per million)
    4. Scalability (8% - trade limit)
    5. Trend (2% - small bonus, not dominant)

    Args:
        calculator: OSRSAlchemyFlippingCalculator instance
        min_margin: Minimum gross margin to consider
        min_volume: Minimum volume to consider (legacy parameter)
        min_limit: Threshold for trade limit penalty (not elimination)
        min_hourly_volume: Threshold for volume penalty (not elimination)
        max_alerts: Maximum number of alerts to return (default: 15)

    Returns:
        List of FlippingTrendEvent objects sorted by opportunity score
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

    # Initialize diagnostic tracking if enabled
    if config.DEBUG_FLIPPING_FILTERS:
        diagnostics = {
            'stage_counts': {'raw_candidates': len(flips)},
            'filtered_items': defaultdict(list),  # {filter_name: [(item_name, reason_details)]}
            'filter_stats': defaultdict(list)  # {metric_name: [values]}
        }

    for flip in flips:
        item_id = flip["id"]
        item_name = flip["name"]

        # Quality filter: Exclude known problematic items
        if any(excluded.lower() in item_name.lower() for excluded in EXCLUDED_ITEMS):
            if config.DEBUG_FLIPPING_FILTERS:
                matched = [e for e in EXCLUDED_ITEMS if e.lower() in item_name.lower()][0]
                diagnostics['filtered_items']['exclusion_list'].append(
                    (item_name, f"matched '{matched}'")
                )
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
            if config.DEBUG_FLIPPING_FILTERS:
                diagnostics['filtered_items']['ge_tax_filter'].append(
                    (item_name, f"net_profit={net_profit} gp (gross={gross_margin}, tax={estimated_tax})")
                )
                diagnostics['filter_stats']['net_profit_filtered'].append(net_profit)
                diagnostics['filter_stats']['gross_margin_filtered'].append(gross_margin)
                diagnostics['filter_stats']['ge_tax_filtered'].append(estimated_tax)
            logger.debug(f"Excluded {item_name}: net_profit={net_profit} (after tax)")
            continue

        # Analyze trend - this provides context metadata, not a filtering criterion
        trend_analysis = calculator.analyze_flipping_trend(item_id)

        # Get trade limit and hourly volume
        trade_limit = flip.get("limit", 0)
        hourly_volume = trend_analysis.get("hourly_volume", 0)

        # Track items with low trade limits (for diagnostics)
        if config.DEBUG_FLIPPING_FILTERS:
            limit_threshold = min_limit or DEFAULT_TRADE_LIMIT_THRESHOLD
            if trade_limit < limit_threshold:
                diagnostics['filtered_items']['trade_limit_penalty'].append(
                    (item_name, f"limit={trade_limit} (threshold={limit_threshold}, ranked lower)")
                )
                diagnostics['filter_stats']['trade_limit_penalized'].append(trade_limit)
                diagnostics['filter_stats']['net_profit_trade_limit_penalized'].append(net_profit)
                diagnostics['filter_stats']['margin_percent_trade_limit_penalized'].append(
                    flip.get("margin_percent", 0)
                )

        # Track items with low hourly volume (for diagnostics)
        if config.DEBUG_FLIPPING_FILTERS:
            volume_threshold = min_hourly_volume or DEFAULT_HOURLY_VOLUME_THRESHOLD
            if hourly_volume < volume_threshold:
                diagnostics['filtered_items']['hourly_volume_penalty'].append(
                    (item_name, f"{hourly_volume}/hr (threshold={volume_threshold}, ranked lower)")
                )
                diagnostics['filter_stats']['hourly_volume_penalized'].append(hourly_volume)
                diagnostics['filter_stats']['net_profit_volume_penalized'].append(net_profit)
                diagnostics['filter_stats']['margin_percent_volume_penalized'].append(
                    flip.get("margin_percent", 0)
                )

        # Calculate capital efficiency metrics
        capital_metrics = flipping.calculate_capital_metrics(
            buy_price=buy_price,
            net_profit=net_profit,
            trade_limit=trade_limit,
            hourly_volume=hourly_volume
        )

        # Analyze spread stability from historical data if available
        historical_five_min = calculator.five_min_data.get(item_id, {}) if calculator.five_min_data else {}
        historical_timeseries = historical_five_min.get('data', []) if isinstance(historical_five_min, dict) else []

        spread_analysis = flipping.analyze_spread_stability(
            current_buy=buy_price,
            current_sell=sell_price,
            historical_data=historical_timeseries
        )

        # Calculate confidence score
        data_completeness = 100 if historical_timeseries else 50
        flip_confidence = confidence.calculate_flipping_confidence(
            hourly_volume=hourly_volume,
            spread_status=spread_analysis['spread_status'],
            spread_volatility=spread_analysis['spread_volatility'],
            data_completeness=data_completeness,
            volume_consistency=50.0  # TODO: Calculate from historical volume data
        )

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
            # Capital efficiency metrics
            required_capital=capital_metrics['required_capital'],
            profit_per_million=capital_metrics['profit_per_million'],
            estimated_hourly_profit=capital_metrics['estimated_hourly_profit'],
            # Spread intelligence
            spread_status=spread_analysis['spread_status'],
            spread_volatility=spread_analysis['spread_volatility'],
            # Confidence
            confidence_score=flip_confidence,
            # Explanation fields
            explanation=explanation,
            impact_summary=impact_summary
        )

        alerts.append(event)

    logger.info(f"Generated {len(alerts)} flipping alerts after quality filtering")

    # Log diagnostic information if enabled
    if config.DEBUG_FLIPPING_FILTERS:
        _log_filter_diagnostics(diagnostics, len(alerts))

    # Sort by opportunity score
    # Opportunity quality prioritizes realistic, executable opportunities
    # Uses weighted scoring across multiple independent factors
    #
    # Opportunity Score Formula:
    # score = (
    #     (net_profit_score × WEIGHT_NET_PROFIT) +
    #     (liquidity_score × WEIGHT_LIQUIDITY) +
    #     (capital_efficiency_score × WEIGHT_CAPITAL_EFFICIENCY) +
    #     (scalability_score × WEIGHT_SCALABILITY)
    # ) × trend_multiplier
    #
    # Component scores (normalized 0-100):
    # - net_profit_score: Absolute profit potential
    # - liquidity_score: Can you actually trade at these prices?
    # - capital_efficiency_score: Profit per million gp invested
    # - scalability_score: Trade limit allows volume execution
    # - trend_multiplier: Small bonus for active trends
    #
    # This approach:
    # - Balances absolute profit with capital efficiency
    # - Requires realistic liquidity for execution
    # - Rewards scalable opportunities
    # - Trend provides context, not dominance
    def calculate_opportunity_score(event: FlippingTrendEvent) -> float:
        """
        Calculate opportunity quality score for ranking.

        Returns a composite score balancing profit, liquidity, capital efficiency,
        and scalability. Higher score = better opportunity.
        """
        # Net profit score (0-100): Normalize based on profit tiers
        if event.net_profit >= 100000:
            net_profit_score = 100
        elif event.net_profit >= 50000:
            net_profit_score = 80 + (event.net_profit - 50000) / 50000 * 20
        elif event.net_profit >= 25000:
            net_profit_score = 60 + (event.net_profit - 25000) / 25000 * 20
        elif event.net_profit >= 10000:
            net_profit_score = 40 + (event.net_profit - 10000) / 15000 * 20
        elif event.net_profit >= 5000:
            net_profit_score = 20 + (event.net_profit - 5000) / 5000 * 20
        else:
            net_profit_score = max(0, event.net_profit / 5000 * 20)

        # Liquidity score (0-100): Based on hourly volume
        if event.hourly_volume >= 500:
            liquidity_score = 100
        elif event.hourly_volume >= 200:
            liquidity_score = 80 + (event.hourly_volume - 200) / 300 * 20
        elif event.hourly_volume >= 100:
            liquidity_score = 60 + (event.hourly_volume - 100) / 100 * 20
        elif event.hourly_volume >= 50:
            liquidity_score = 40 + (event.hourly_volume - 50) / 50 * 20
        elif event.hourly_volume >= 20:
            # Low volume: 20-49/hr = 20-40 score
            liquidity_score = 20 + (event.hourly_volume - 20) / 30 * 20
        elif event.hourly_volume >= 5:
            # Very low volume: 5-19/hr = 5-20 score (severe penalty)
            liquidity_score = 5 + (event.hourly_volume - 5) / 15 * 15
        else:
            # Near-zero volume: < 5/hr = 1 score (nearly eliminates from ranking)
            liquidity_score = max(1, event.hourly_volume)

        # Capital efficiency score (0-100): Profit per million invested
        if event.profit_per_million >= 200000:
            capital_efficiency_score = 100
        elif event.profit_per_million >= 100000:
            capital_efficiency_score = 80 + (event.profit_per_million - 100000) / 100000 * 20
        elif event.profit_per_million >= 50000:
            capital_efficiency_score = 60 + (event.profit_per_million - 50000) / 50000 * 20
        elif event.profit_per_million >= 20000:
            capital_efficiency_score = 40 + (event.profit_per_million - 20000) / 30000 * 20
        else:
            capital_efficiency_score = max(0, event.profit_per_million / 20000 * 40)

        # Scalability score (0-100): Trade limit allows volume
        if event.trade_limit >= 100:
            scalability_score = 100
        elif event.trade_limit >= 50:
            scalability_score = 80 + (event.trade_limit - 50) / 50 * 20
        elif event.trade_limit >= 25:
            scalability_score = 60 + (event.trade_limit - 25) / 25 * 20
        elif event.trade_limit >= 10:
            scalability_score = 40 + (event.trade_limit - 10) / 15 * 20
        elif event.trade_limit >= 5:
            scalability_score = 20 + (event.trade_limit - 5) / 5 * 20
        elif event.trade_limit >= 1:
            # Very low limits: 1-4 items = 5-15 score (severe penalty)
            scalability_score = 5 + (event.trade_limit - 1) / 4 * 10
        else:
            # 0 trade limit: score of 1 (nearly eliminates from ranking)
            scalability_score = 1

        # Weighted composite score
        composite_score = (
            (net_profit_score * WEIGHT_NET_PROFIT) +
            (liquidity_score * WEIGHT_LIQUIDITY) +
            (capital_efficiency_score * WEIGHT_CAPITAL_EFFICIENCY) +
            (scalability_score * WEIGHT_SCALABILITY)
        ) / 100

        # Quality gate penalties: severe multiplicative penalties for critical deficiencies
        # These prevent unrealistic opportunities from ranking too high
        quality_multiplier = 1.0

        # Severe penalty for zero/near-zero trade limit (can't execute at scale)
        if event.trade_limit == 0:
            quality_multiplier *= 0.15  # 85% penalty
        elif event.trade_limit < 5:
            quality_multiplier *= 0.50  # 50% penalty

        # Severe penalty for zero/near-zero volume (can't execute at market prices)
        if event.hourly_volume < 5:
            quality_multiplier *= 0.15  # 85% penalty
        elif event.hourly_volume < 20:
            quality_multiplier *= 0.50  # 50% penalty

        # Compounding penalty: both low limit AND low volume = even worse
        if event.trade_limit < 5 and event.hourly_volume < 20:
            quality_multiplier *= 0.30  # Additional 70% penalty for double deficiency

        composite_score *= quality_multiplier

        # Trend multiplier: small bonus for active trends
        if event.status in ("surging", "crashing"):
            trend_multiplier = TREND_MULTIPLIER_STRONG
        elif event.status in ("surge_risk", "crash_risk"):
            trend_multiplier = TREND_MULTIPLIER_MODERATE
        else:  # "stable"
            trend_multiplier = TREND_MULTIPLIER_STABLE

        # Apply trend bonus (2% of total weight)
        final_score = composite_score * trend_multiplier

        return final_score

    alerts.sort(key=calculate_opportunity_score, reverse=True)

    # Return top N alerts (default: 15)
    return alerts[:max_alerts]