from typing import List, Dict
from datetime import datetime
from events import CrashRiskEvent, FlippingTrendEvent


class CLIRenderer:
    """
    CLI-specific presentation logic.

    Handles table formatting, alert displays, and summary output.
    Consumes business/domain data and produces formatted CLI output.
    """

    @staticmethod
    def display_market_dashboard(calculator, crash_events: List[CrashRiskEvent], trend_events: List[FlippingTrendEvent]):
        """
        Display concise operator-facing market dashboard.

        Shows refresh summary and top opportunities in a compact format.
        Designed for terminal monitoring without verbose logging noise.

        Args:
            calculator: OSRSAlchemyFlippingCalculator instance with loaded data
            crash_events: List of crash risk alerts
            trend_events: List of market trend alerts
        """
        # Clear screen for clean dashboard view (optional)
        print("\n" * 2)
        print("=" * 70)
        print("OSRS Market Engine")
        print("=" * 70)
        print()

        # Refresh summary
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        items_scanned = len(calculator.item_mapping)

        # Count profitable items (quick check with minimal filtering)
        profitable_count = 0
        if calculator.current_prices and calculator.item_mapping:
            profitable_items = calculator.get_profitable_items(
                min_profit=100,
                max_items=500
            )
            profitable_count = len(profitable_items)

        alert_count = len(crash_events) + len(trend_events)

        # Check enrichment status
        enriched_count = 0
        if calculator.five_min_data:
            enriched_count = sum(
                1 for item_data in calculator.five_min_data.values()
                if item_data.get('lowest_low') is not None
            )
        enrichment_status = f"{enriched_count}/{len(calculator.five_min_data)}" if calculator.five_min_data else "0/0"

        print(f"Refresh: {timestamp}")
        print(f"Scanned: {items_scanned:,} items | Profitable: {profitable_count} | Alerts: {alert_count}")
        print(f"Enrichment: {enrichment_status} items enriched with historical data")
        print()

        # Top opportunities - combine crash and trend events
        all_opportunities = []

        # Add crash alerts as opportunities
        for event in crash_events[:10]:
            status_text = event.status.replace('_', ' ')
            all_opportunities.append({
                'name': event.name,
                'profit': event.profit,
                'roi': event.roi_percent,
                'status': status_text,
                'type': 'alchemy'
            })

        # Add trend alerts as opportunities
        for event in trend_events[:10]:
            status_text = event.status.replace('_', ' ')
            all_opportunities.append({
                'name': event.name,
                'profit': event.margin,
                'roi': event.margin_percent,
                'status': status_text,
                'type': 'flip'
            })

        if all_opportunities:
            print("Top Opportunities:")
            print("-" * 70)
            for opp in all_opportunities[:3]:
                # Format as one-liner
                type_tag = "[ALCH]" if opp['type'] == 'alchemy' else "[FLIP]"
                print(f"{opp['name']:<25} {type_tag:<7} +{opp['profit']:>5,.0f} gp  {opp['roi']:>5.0f}% ROI  {opp['status']}")
        else:
            print("No significant market opportunities detected.")
            print("Market conditions appear stable.")

        print()
        print("=" * 70)

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def display_alchemy_crash_alerts(crash_alerts: List[CrashRiskEvent], profitable_item_ids: set):
        """Display crash risk alerts"""
        print("\n" + "=" * 70)
        print("CRASH RISK ALERTS")
        print("=" * 70)

        relevant_alerts = [alert for alert in crash_alerts
                        if alert.item_id in profitable_item_ids]
        other_alerts = [alert for alert in crash_alerts
                    if alert.item_id not in profitable_item_ids]

        if relevant_alerts:
            print(f"\n🚨 CRASH RISK FOR YOUR ITEMS ({len(relevant_alerts)} items):")
            print("-" * 110)
            print(f"{'Item':<26} | {'Profit':<8} | {'ROI':<5} | {'Status':<12} | {'Vol Ratio':<10} | {'Conf':<6} | {'Hourly Vol':<11} | {'Sev':<9} | {'Rec'}")
            print("-" * 110)

            for alert in relevant_alerts:
                status_emoji = '🔴' if alert.status == 'crashing' else '🟡'
                rec_emoji = '🔥' if alert.recommendation == 'buy low' else '⚠️'

                # Volume spike with magnitude
                if alert.volume_spike and alert.spike_magnitude > 1.0:
                    vol_spike_emoji = f'📈{alert.spike_magnitude:.1f}x'
                else:
                    vol_spike_emoji = ''

                # Confidence emoji
                confidence_emoji = {
                    'high': '🟢',
                    'medium': '🟡',
                    'low': '🟠',
                    'very_low': '🔴'
                }.get(alert.volume_confidence, '⚪')

                member_tag = "[M]" if alert.members else "[F2P]"

                print(f"{status_emoji} {alert.name[:20]:<20} {member_tag:<5} | "
                    f"{alert.profit:>7,.0f} | "
                    f"{alert.roi_percent:>5.0f}% | "
                    f"{alert.status:<12} | "
                    f"{alert.volume_ratio:>8.1f}x | "
                    f"{alert.confidence_score:<3}{confidence_emoji:<3} | "
                    f"{alert.hourly_volume:>9,}{vol_spike_emoji:<2} | "
                    f"{alert.severity_score:>7}/100 | "
                    f"{rec_emoji} {alert.recommendation.upper()}")
        else:
            print("\n✅ No crash risks detected for your profitable alchemy items")
            print("All your items show healthy volume balance")

        if other_alerts:
            print(f"\n📊 OTHER CRASH RISKS ({len(other_alerts[:5])} of {len(other_alerts)}):")
            print("-" * 100)

            for alert in other_alerts[:5]:
                status_emoji = '🔴' if alert.status == 'crashing' else '🟡'

                # Volume spike with magnitude
                if alert.volume_spike and alert.spike_magnitude > 1.0:
                    vol_spike_emoji = f'📈{alert.spike_magnitude:.1f}x'
                else:
                    vol_spike_emoji = ''

                # Confidence emoji
                confidence_emoji = {
                    'high': '🟢',
                    'medium': '🟡',
                    'low': '🟠',
                    'very_low': '🔴'
                }.get(alert.volume_confidence, '⚪')

                member_tag = "[M]" if alert.members else "[F2P]"
                print(f"{status_emoji} {alert.name[:25]:<25} {member_tag:<5} | "
                    f"Profit: {alert.profit:>6,.0f} | "
                    f"ROI: {alert.roi_percent:>4.0f}% | "
                    f"Vol Ratio: {alert.volume_ratio:>5.1f}x | "
                    f"Conf: {alert.confidence_score}{confidence_emoji} | "
                    f"Hourly Vol: {alert.hourly_volume:>7,}{vol_spike_emoji:<2} | "
                    f"Severity: {alert.severity_score:>2}/100")

    @staticmethod
    def display_flipping_trend_alerts(flipping_alerts: List[FlippingTrendEvent], flip_item_ids: set):
        """Display flipping trend alerts"""
        print("\n" + "=" * 70)
        print("MARKET TREND & CRASH ALERTS")
        print("=" * 70)

        relevant_alerts = [alert for alert in flipping_alerts
                        if alert.item_id in flip_item_ids]

        if relevant_alerts:
            print(f"\n🚨 ACTIVE ALERTS ({len(relevant_alerts)} items):")
            print("-" * 110)

            for alert in relevant_alerts:
                status_emoji = {
                    'crashing': '🔴',
                    'crash_risk': '🟡',
                    'surging': '🟢',
                    'surge_risk': '🟠'
                }.get(alert.status, '⚪')

                recommendation_emoji = {
                    'avoid': '❌',
                    'caution': '⚠️',
                    'opportunity': '💰',
                    'safe': '✅'
                }.get(alert.recommendation, '❓')

                vol_spike_emoji = '📈' if alert.volume_spike else ''
                member_tag = "[M]" if alert.members else "[F2P]"

                print(f"{status_emoji} {alert.name[:25]:<25} {member_tag:<5} | "
                    f"Status: {alert.status:<12} | "
                    f"Margin: {alert.margin:>6,.0f} ({alert.margin_percent:>4.1f}%) | "
                    f"Price Δ: {alert.price_change_percent:>6.1f}% | "
                    f"Hourly: {alert.hourly_volume:>6,}{vol_spike_emoji:<2} | "
                    f"Sev: {alert.severity_score:>2}/100 | "
                    f"{recommendation_emoji} {alert.recommendation.upper()}")
        else:
            print("\n✅ No significant alerts for your current flipping opportunities")
            print("All items appear stable based on recent 5-minute data")

        other_alerts = [alert for alert in flipping_alerts
                    if alert.item_id not in flip_item_ids]

        if other_alerts:
            print(f"\n📊 OTHER MARKET MOVEMENTS ({len(other_alerts[:10])} of {len(other_alerts)}):")
            print("-" * 100)

            for alert in other_alerts[:10]:
                status_emoji = {
                    'crashing': '🔴',
                    'crash_risk': '🟡',
                    'surging': '🟢',
                    'surge_risk': '🟠'
                }.get(alert.status, '⚪')

                vol_spike_emoji = '📈' if alert.volume_spike else ''
                member_tag = "[M]" if alert.members else "[F2P]"

                print(f"{status_emoji} {alert.name[:25]:<25} {member_tag:<5} | "
                    f"Status: {alert.status:<12} | "
                    f"Margin: {alert.margin:>6,.0f} ({alert.margin_percent:>4.1f}%) | "
                    f"Price Δ: {alert.price_change_percent:>6.1f}% | "
                    f"Hourly: {alert.hourly_volume:>6,}{vol_spike_emoji:<2} | "
                    f"Sev: {alert.severity_score:>2}/100")

    @staticmethod
    def display_alchemy_summary(profitable_items: List[Dict], nature_rune_cost: int,
                               crash_alerts: List[CrashRiskEvent] = None):
        """Display summary statistics for alchemy analysis"""
        if not profitable_items:
            return

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
        print(f"Nature rune cost used: {nature_rune_cost} gp")

        if crash_alerts:
            profitable_item_ids = {item['item_id'] for item in profitable_items}
            relevant_alerts = [alert for alert in crash_alerts
                            if alert.item_id in profitable_item_ids]

            alert_counts = {}
            for alert in relevant_alerts:
                status = alert.status
                alert_counts[status] = alert_counts.get(status, 0) + 1

            print(f"\nCrash Alert Summary for Your Items:")
            if alert_counts:
                for status, count in alert_counts.items():
                    emoji = '🔴' if status == 'crashing' else '🟡'
                    print(f"  {emoji} {status.replace('_', ' ').title()}: {count}")
            else:
                print(f"  ✅ All items stable (no crash risks detected)")

    @staticmethod
    def display_flipping_summary(flips: List[Dict], flipping_alerts: List[FlippingTrendEvent] = None):
        """Display summary statistics for flipping analysis"""
        if not flips:
            return

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

        if flipping_alerts:
            flip_item_ids = {flip['id'] for flip in flips}
            relevant_alerts = [alert for alert in flipping_alerts
                            if alert.item_id in flip_item_ids]

            alert_counts = {}
            for alert in relevant_alerts:
                status = alert.status
                alert_counts[status] = alert_counts.get(status, 0) + 1

            print(f"\nAlert Summary for Your Items:")
            if alert_counts:
                for status, count in alert_counts.items():
                    emoji = {'crashing': '🔴', 'crash_risk': '🟡',
                            'surging': '🟢', 'surge_risk': '🟠'}.get(status, '⚪')
                    print(f"  {emoji} {status.replace('_', ' ').title()}: {count}")
            else:
                print(f"  ✅ All items stable (no alerts)")
