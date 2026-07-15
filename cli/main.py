from typing import Dict, List
import pandas as pd
import logging

from renderers import CLIRenderer
from engine import OSRSAlchemyFlippingCalculator
from scheduler import DataScheduler
from cli.monitor import run_market_monitor_loop 

logger = logging.getLogger(__name__)


def save_to_csv(items: List[Dict], filename: str = "osrs_analysis.csv"):
    """Save results to CSV file"""
    if not items:
        print("No data to save.")
        return

    try:
        df = pd.DataFrame(items)
        df.to_csv(filename, index=False)
        print(f"Results saved to {filename}")
    except Exception as e:
        print(f"Error saving to CSV: {e}")
        print("Data structure might be incompatible with CSV format.")


def run_alchemy_analysis(calculator, min_profit: int = 0, max_items: int = 100,
                        members_only: bool = None, save_csv_file: bool = False,
                        max_buy_price: int = None, min_limit: int = None,
                        min_volume: int = None, max_roi: float = None,
                        show_non_alchemizable_sample: bool = False,
                        show_crash_alerts: bool = False,
                        alert_min_profit: int = 100,
                        alert_min_imbalance: float = 2.0):
    """
    Run complete alchemy profit analysis with optional crash detection

    Args:
        calculator: OSRSAlchemyFlippingCalculator instance
        min_profit: Minimum profit per cast
        max_items: Maximum number of items to analyze
        members_only: Filter by members items (True/False/None for all)
        save_csv_file: Whether to save results to CSV
        max_buy_price: Maximum buy price for items (None for no limit)
        min_limit: Minimum buying limit (None for no limit)
        min_volume: Minimum hourly trading volume (None for no limit)
        max_roi: Maximum ROI percentage (None for no limit)
        show_non_alchemizable_sample: Show sample of filtered non-alchemizable items
        show_crash_alerts: Whether to show crash risk alerts
        alert_min_profit: Minimum profit for crash alerts
        alert_min_imbalance: Minimum volume imbalance ratio for alerts
    """
    analysis_title = "OSRS High Alchemy Profit Analysis with Alchemizable Filter"
    if show_crash_alerts:
        analysis_title += " + Crash Detection"

    print(f"Starting {analysis_title}...")
    print("=" * 70)

    if not calculator.fetch_item_mapping():
        print("Failed to fetch item mapping. Exiting.")
        return

    if not calculator.fetch_current_prices():
        print("Failed to fetch current prices. Exiting.")
        return

    if not calculator.fetch_volume_data():
        print("Failed to fetch volume data. Continuing without volume filtering.")

    if show_crash_alerts:
        print("Fetching 5-minute data for crash risk analysis...")
        if not calculator.fetch_five_minute_data():
            print("Warning: Failed to fetch 5-minute data, crash alerts will be limited")

    if show_non_alchemizable_sample:
        print("\nSample of items filtered out as non-alchemizable:")
        print("-" * 80)
        non_alch_sample = calculator.get_non_alchemizable_sample()
        for item in non_alch_sample:
            reason = "No alch value" if item['highalch'] <= 0 else "No trade limit" if item['limit'] <= 0 else "Name/examine filter"
            print(f"{item['name'][:25]:<25} | Alch: {item['highalch']:<6} | Limit: {item['limit']:<4} | Reason: {reason}")
        print("-" * 80)

    print(f"\nFilters applied:")
    print(f"Minimum profit: {min_profit:,} gp")
    if max_buy_price is not None:
        print(f"Maximum buy price: {max_buy_price:,} gp")
    if min_limit is not None:
        print(f"Minimum buying limit: {min_limit}")
    if min_volume is not None:
        print(f"Minimum hourly volume: {min_volume:,}")
    if max_roi is not None:
        print(f"Maximum ROI: {max_roi}%")
    if members_only is not None:
        print(f"Membership: {'Members only' if members_only else 'F2P only'}")
    if show_crash_alerts:
        print(f"Crash alerts: Enabled (min profit: {alert_min_profit:,}gp, min imbalance: {alert_min_imbalance}x)")

    profitable_items = calculator.get_profitable_items(
        min_profit=min_profit,
        max_items=max_items,
        members_only=members_only,
        max_buy_price=max_buy_price,
        min_limit=min_limit,
        min_volume=min_volume,
        max_roi=max_roi
    )

    CLIRenderer.display_alchemy_results(profitable_items)

    if show_crash_alerts and profitable_items:
        crash_alerts = calculator.get_alchemy_alerts(
            min_profit=alert_min_profit,
            min_volume_imbalance=alert_min_imbalance
        )
        profitable_item_ids = {item['item_id'] for item in profitable_items}
        CLIRenderer.display_alchemy_crash_alerts(crash_alerts, profitable_item_ids)

    if save_csv_file:
        save_to_csv(profitable_items, "alchemy_profits.csv")

    if profitable_items:
        crash_alerts = None
        if show_crash_alerts:
            crash_alerts = calculator.get_alchemy_alerts(alert_min_profit, alert_min_imbalance)
        CLIRenderer.display_alchemy_summary(profitable_items, calculator.nature_rune_cost, crash_alerts)


def run_flipping_analysis(calculator, limit: int = 10, min_margin: int = 200,
                        min_volume: int = 20, max_buy_price: int = None,
                        members_only: bool = None, save_csv_file: bool = False,
                        fetch_history: bool = True, max_margin_percent: float = 20.0,
                        exclude_high_risk: bool = True, min_score: int = 30,
                        use_averaged_prices: bool = True, show_alerts: bool = True,
                        alert_min_margin: int = 1000, alert_min_volume: int = 20):
    """
    Enhanced flipping analysis with optional price averaging and integrated alerts

    Args:
        calculator: OSRSAlchemyFlippingCalculator instance
        show_alerts: Whether to show crash/trend alerts for flipping items
        alert_min_margin: Minimum margin for flipping alerts
        alert_min_volume: Minimum volume for flipping alerts
    """
    print("Starting Enhanced OSRS Flipping Analysis with Price Averaging and Alerts...")
    print("=" * 70)

    if not calculator.item_mapping:
        if not calculator.fetch_item_mapping():
            print("Failed to fetch item mapping. Exiting.")
            return

    if not calculator.current_prices:
        if not calculator.fetch_current_prices():
            print("Failed to fetch current prices. Exiting.")
            return

    if not calculator.volume_data:
        if not calculator.fetch_volume_data():
            print("Failed to fetch volume data. Exiting.")
            return

    if use_averaged_prices:
        calculator.use_flipping_averages = True
        print("Fetching averaged prices for more stable flipping analysis...")
        if not calculator.fetch_flipping_average_prices():
            print("Warning: Failed to fetch averaged prices, falling back to realtime prices")
            calculator.use_flipping_averages = False
    else:
        calculator.use_flipping_averages = False

    if show_alerts:
        print("Fetching 5-minute data for trend and crash analysis...")
        if not calculator.fetch_five_minute_data():
            print("Warning: Failed to fetch 5-minute data, alerts will be limited")

    print(f"\nPrice source: {'Averaged (more stable)' if calculator.use_flipping_averages else 'Realtime'}")
    print(f"Alert system: {'Enabled' if show_alerts else 'Disabled'}")
    print(f"\nEnhanced Filters applied:")
    print(f"Minimum margin: {min_margin:,} gp")
    print(f"Minimum volume: {min_volume:,}")
    print(f"Maximum margin percentage: {max_margin_percent}%")
    print(f"Minimum score: {min_score}/100")
    print(f"Exclude high risk: {'Yes' if exclude_high_risk else 'No'}")
    if max_buy_price is not None:
        print(f"Maximum buy price: {max_buy_price:,} gp")
    if members_only is not None:
        print(f"Membership: {'Members only' if members_only else 'F2P only'}")

    flips = calculator.get_top_flips(
        limit=limit * 2,
        min_margin=min_margin,
        min_volume=min_volume,
        max_buy_price=max_buy_price,
        fetch_history=fetch_history,
        max_margin_percent=max_margin_percent,
        exclude_high_risk=exclude_high_risk,
        min_score=min_score
    )

    if members_only is not None:
        flips = [flip for flip in flips if flip['members'] == members_only]

    flips = flips[:limit]

    CLIRenderer.display_flip_results(flips)

    if show_alerts and flips:
        flipping_alerts = calculator.get_flipping_alerts(
            min_margin=alert_min_margin,
            min_volume=alert_min_volume
        )
        flip_item_ids = {flip['id'] for flip in flips}
        CLIRenderer.display_flipping_trend_alerts(flipping_alerts, flip_item_ids)

    if save_csv_file:
        save_to_csv(flips, "enhanced_flipping_opportunities.csv")

    if flips:
        flipping_alerts = None
        if show_alerts:
            flipping_alerts = calculator.get_flipping_alerts(alert_min_margin, alert_min_volume)
        CLIRenderer.display_flipping_summary(flips, flipping_alerts)


def run_market_monitor():
    """
    Standalone CLI workflow for market monitoring.

    Creates calculator and scheduler, refreshes data, retrieves MarketEvents,
    and displays alerts through CLI renderer.

    This is a standalone frontend that consumes the MarketEvent pipeline
    without requiring Discord.
    """
    print("=" * 70)
    print("OSRS Market Monitor - Standalone CLI")
    print("=" * 70)
    print()

    # Create calculator instance
    logger.info("Initializing market calculator...")
    calculator = OSRSAlchemyFlippingCalculator()

    # Create scheduler instance
    logger.info("Initializing data scheduler...")
    scheduler = DataScheduler(calculator)

    # Refresh all market data
    print("Refreshing market data...")
    print()

    if not scheduler.refresh_all(force=True):
        print("[ERROR] Failed to refresh critical market data")
        return

    # Provide feedback on what was loaded
    if calculator.item_mapping:
        print(f"[OK] Item mapping loaded ({len(calculator.item_mapping)} items)")

    if calculator.current_prices:
        print(f"[OK] Current prices loaded ({len(calculator.current_prices)} items)")

    if calculator.volume_data:
        print(f"[OK] Volume data loaded ({len(calculator.volume_data)} items)")

    if calculator.five_min_data:
        print(f"[OK] 5-minute data loaded ({len(calculator.five_min_data)} items)")

    print()
    print("Analyzing market alerts...")
    print()

    # Retrieve crash risk alerts
    crash_events = calculator.get_alchemy_alerts(
        min_profit=100,
        min_volume_imbalance=2.0
    )

    # Retrieve flipping trend alerts
    trend_events = calculator.get_flipping_alerts(
        min_margin=1000,
        min_volume=20
    )

    # Display results
    if crash_events or trend_events:
        if crash_events:
            print("=" * 70)
            print("CRASH RISK ALERTS")
            print("=" * 70)
            print()
            print(f"Found {len(crash_events)} items with crash risk signals")
            print()

            # Display crash alerts (pass empty set to show all)
            CLIRenderer.display_alchemy_crash_alerts(crash_events, set())
            print()

        if trend_events:
            print("=" * 70)
            print("MARKET TREND ALERTS")
            print("=" * 70)
            print()
            print(f"Found {len(trend_events)} items with significant market movements")
            print()

            # Display trend alerts (pass empty set to show all)
            CLIRenderer.display_flipping_trend_alerts(trend_events, set())
            print()
    else:
        print("=" * 70)
        print("No active market alerts detected")
        print("=" * 70)
        print()
        print("Market conditions appear stable.")
        print("No significant crash risks or trend movements found.")
        print()

    print("=" * 70)
    print("Market analysis complete")
    print("=" * 70)


if __name__ == "__main__":
    """
    Entry point for standalone CLI monitor execution.

    Run with: python -m cli.main
    """
    run_market_monitor_loop(
        interval_seconds=15 # Set to 15 seconds for testing; adjust as needed for production
    )
