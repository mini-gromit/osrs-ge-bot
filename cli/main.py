from typing import Dict, List
import pandas as pd


def display_alchemy_results(items: List[Dict], show_count: int = 20):
    """Display alchemy results in a formatted table"""
    if not items:
        print("No profitable alchemizable items found with the given criteria.")
        return

    print(f"\nTop {min(show_count, len(items))} High Alchemy Opportunities (Alchemizable Items Only):")
    print("-" * 140)
    print(f"{'Rank':<4} {'Item Name':<18} {'Buy Price':<10} {'Alch Value':<10} {'Profit':<8} {'ROI%':<5} {'Limit':<6} {'Max Profit':<10} {'Volume/hr':<10} {'Members'}")
    print("-" * 140)

    for i, item in enumerate(items[:show_count], 1):
        members_str = "Yes" if item['members'] else "No"
        volume_str = f"{item['recent_volume']:,}" if item['recent_volume'] > 0 else "N/A"
        print(f"{i:<4} {item['name'][:16]:<18} {item['buy_price']:<10,} "
              f"{item['high_alch_value']:<10,} {item['profit']:<8,} {item['roi_percent']:<5.1f} "
              f"{item['limit']:<6} {item['max_profit_per_limit']:<10,} {volume_str:<10} {members_str}")


def display_flip_results(flips: List[Dict], show_count: int = 20):
    """Enhanced display with risk indicators"""
    if not flips:
        print("No profitable flipping opportunities found with the given criteria.")
        return

    print(f"\nTop {min(show_count, len(flips))} Flipping Opportunities:")
    print("-" * 150)
    print(f"{'Rank':<4} {'Item Name':<25} {'Buy Price':<12} {'Sell Price':<12} {'Margin':<9} {'Margin%':<7} {'Volume':<8} {'Score':<5} {'Risk':<12} {'Members'}")
    print("-" * 150)

    for i, flip in enumerate(flips[:show_count], 1):
        members_str = "Yes" if flip['members'] else "No"

        risk_level = flip.get('risk_level', 0)
        if risk_level >= 3:
            risk_indicator = "🚨 HIGH"
        elif risk_level >= 2:
            risk_indicator = "⚠️ MEDIUM"
        elif risk_level >= 1:
            risk_indicator = "⚡ LOW"
        else:
            risk_indicator = "✅ Clean"

        print(f"{i:<4} {flip['name'][:23]:<25} {flip['buy_price']:<12,} "
              f"{flip['sell_price']:<12,} {flip['margin']:<9,} {flip['margin_percent']:<7.1f} "
              f"{flip['volume']:<8,} {flip['score']:<5.0f} {risk_indicator:<12} {members_str}")

    print(f"\nDetailed Risk Analysis for Top {min(5, len(flips))} Items:")
    print("-" * 80)
    for i, flip in enumerate(flips[:min(5, len(flips))], 1):
        risk_info = flip.get('risk_info', 'No analysis')
        print(f"{i}. {flip['name']}: {risk_info}")


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

    display_alchemy_results(profitable_items)

    if show_crash_alerts and profitable_items:
        print("\n" + "=" * 70)
        print("ALCHEMY CRASH RISK ALERTS")
        print("=" * 70)

        crash_alerts = calculator.get_alchemy_alerts(
            min_profit=alert_min_profit,
            min_volume_imbalance=alert_min_imbalance
        )

        profitable_item_ids = {item['item_id'] for item in profitable_items}

        relevant_alerts = [alert for alert in crash_alerts
                        if alert['item_id'] in profitable_item_ids]
        other_alerts = [alert for alert in crash_alerts
                    if alert['item_id'] not in profitable_item_ids]

        if relevant_alerts:
            print(f"\n🚨 CRASH RISK FOR YOUR ITEMS ({len(relevant_alerts)} items):")
            print("-" * 70)
            print(f"{'Item':<25} | {'Profit':<8} | {'Status':<12} | {'Vol Ratio':<10} | {'Alert %':<8} | {'Rec'}")
            print("-" * 70)

            for alert in relevant_alerts:
                status_emoji = '🔴' if alert['status'] == 'crashing' else '🟡'
                rec_emoji = '🔥' if alert['recommendation'] == 'buy low' else '⚠️'

                print(f"{status_emoji} {alert['name'][:23]:<23} | "
                    f"{alert['profit']:>7,.0f} | "
                    f"{alert['status']:<12} | "
                    f"{alert['volume_ratio']:>8.1f}x | "
                    f"{alert['alert_percent']:>6.1f}% | "
                    f"{rec_emoji} {alert['recommendation'].upper()}")
        else:
            print("\n✅ No crash risks detected for your profitable alchemy items")
            print("All your items show healthy volume balance")

        if other_alerts:
            print(f"\n📊 OTHER ALCHEMY CRASH RISKS ({len(other_alerts[:5])} of {len(other_alerts)}):")
            print("-" * 70)

            for alert in other_alerts[:5]:
                status_emoji = '🔴' if alert['status'] == 'crashing' else '🟡'
                print(f"{status_emoji} {alert['name'][:30]:<30} | "
                    f"Profit: {alert['profit']:>6,.0f} | "
                    f"Vol Ratio: {alert['volume_ratio']:>5.1f}x | "
                    f"Status: {alert['status']}")

    if save_csv_file:
        save_to_csv(profitable_items, "alchemy_profits.csv")

    if profitable_items:
        total_profitable = len(profitable_items)
        avg_profit = sum(item['profit'] for item in profitable_items) / total_profitable
        max_profit = profitable_items[0]['profit'] if profitable_items else 0
        avg_volume = sum(item['recent_volume'] for item in profitable_items) / total_profitable
        avg_roi = sum(item['roi_percent'] for item in profitable_items) / total_profitable

        print(f"\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total profitable alchemizable items found: {total_profitable}")
        print(f"Average profit per cast: {avg_profit:,.1f} gp")
        print(f"Maximum profit per cast: {max_profit:,} gp")
        print(f"Average ROI: {avg_roi:.1f}%")
        print(f"Average hourly volume: {avg_volume:,.0f}")
        print(f"Nature rune cost used: {calculator.nature_rune_cost} gp")

        if show_crash_alerts:
            crash_alerts = calculator.get_alchemy_alerts(alert_min_profit, alert_min_imbalance)
            profitable_item_ids = {item['item_id'] for item in profitable_items}
            relevant_alerts = [alert for alert in crash_alerts
                            if alert['item_id'] in profitable_item_ids]

            alert_counts = {}
            for alert in relevant_alerts:
                status = alert['status']
                alert_counts[status] = alert_counts.get(status, 0) + 1

            print(f"\nCrash Alert Summary for Your Items:")
            if alert_counts:
                for status, count in alert_counts.items():
                    emoji = '🔴' if status == 'crashing' else '🟡'
                    print(f"  {emoji} {status.replace('_', ' ').title()}: {count}")
            else:
                print(f"  ✅ All items stable (no crash risks detected)")


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

    display_flip_results(flips)

    if show_alerts and flips:
        print("\n" + "=" * 70)
        print("MARKET TREND & CRASH ALERTS")
        print("=" * 70)

        flipping_alerts = calculator.get_flipping_alerts(
            min_margin=alert_min_margin,
            min_volume=alert_min_volume
        )

        flip_item_ids = {flip['id'] for flip in flips}
        relevant_alerts = [alert for alert in flipping_alerts
                        if alert['item_id'] in flip_item_ids]

        if relevant_alerts:
            print(f"\n🚨 ACTIVE ALERTS ({len(relevant_alerts)} items):")
            print("-" * 70)

            for alert in relevant_alerts:
                status_emoji = {
                    'crashing': '🔴',
                    'crash_risk': '🟡',
                    'surging': '🟢',
                    'surge_risk': '🟠'
                }.get(alert['status'], '⚪')

                recommendation_emoji = {
                    'avoid': '❌',
                    'caution': '⚠️',
                    'opportunity': '💰',
                    'safe': '✅'
                }.get(alert['recommendation'], '❓')

                print(f"{status_emoji} {alert['name'][:30]:<30} | "
                    f"Status: {alert['status']:<12} | "
                    f"Price Δ: {alert['price_change_percent']:>6.1f}% | "
                    f"Vol: {alert['high_volume']:>4}/{alert['low_volume']:<4} | "
                    f"{recommendation_emoji} {alert['recommendation'].upper()}")
        else:
            print("\n✅ No significant alerts for your current flipping opportunities")
            print("All items appear stable based on recent 5-minute data")

        other_alerts = [alert for alert in flipping_alerts
                    if alert['item_id'] not in flip_item_ids]

        if other_alerts:
            print(f"\n📊 OTHER MARKET MOVEMENTS ({len(other_alerts[:10])} of {len(other_alerts)}):")
            print("-" * 70)

            for alert in other_alerts[:10]:
                status_emoji = {
                    'crashing': '🔴',
                    'crash_risk': '🟡',
                    'surging': '🟢',
                    'surge_risk': '🟠'
                }.get(alert['status'], '⚪')

                print(f"{status_emoji} {alert['name'][:30]:<30} | "
                    f"Status: {alert['status']:<12} | "
                    f"Price Δ: {alert['price_change_percent']:>6.1f}% | "
                    f"Margin: {alert['margin']:>8,.0f}gp")

    if save_csv_file:
        save_to_csv(flips, "enhanced_flipping_opportunities.csv")

    if flips:
        total_flips = len(flips)
        avg_margin = sum(flip['margin'] for flip in flips) / total_flips
        avg_margin_percent = sum(flip['margin_percent'] for flip in flips) / total_flips
        avg_volume = sum(flip['volume'] for flip in flips) / total_flips
        avg_score = sum(flip['score'] for flip in flips) / total_flips

        high_risk = len([f for f in flips if f.get('risk_level', 0) >= 3])
        medium_risk = len([f for f in flips if f.get('risk_level', 0) == 2])
        low_risk = len([f for f in flips if f.get('risk_level', 0) == 1])
        clean = len([f for f in flips if f.get('risk_level', 0) == 0])

        print(f"\n" + "=" * 70)
        print("ENHANCED SUMMARY")
        print("=" * 70)
        print(f"Total flipping opportunities found: {total_flips}")
        print(f"Average margin: {avg_margin:,.0f} gp ({avg_margin_percent:.1f}%)")
        print(f"Average volume: {avg_volume:,.0f}")
        print(f"Average flip score: {avg_score:.1f}/100")
        print(f"\nRisk Distribution:")
        print(f"  🚨 High Risk: {high_risk}")
        print(f"  ⚠️ Medium Risk: {medium_risk}")
        print(f"  ⚡ Low Risk: {low_risk}")
        print(f"  ✅ Clean: {clean}")

        if show_alerts:
            flipping_alerts = calculator.get_flipping_alerts(alert_min_margin, alert_min_volume)
            flip_item_ids = {flip['id'] for flip in flips}
            relevant_alerts = [alert for alert in flipping_alerts
                            if alert['item_id'] in flip_item_ids]

            alert_counts = {}
            for alert in relevant_alerts:
                status = alert['status']
                alert_counts[status] = alert_counts.get(status, 0) + 1

            print(f"\nAlert Summary for Your Items:")
            if alert_counts:
                for status, count in alert_counts.items():
                    emoji = {'crashing': '🔴', 'crash_risk': '🟡',
                            'surging': '🟢', 'surge_risk': '🟠'}.get(status, '⚪')
                    print(f"  {emoji} {status.replace('_', ' ').title()}: {count}")
            else:
                print(f"  ✅ All items stable (no alerts)")
