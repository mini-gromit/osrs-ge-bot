import time
import logging

from engine import OSRSAlchemyFlippingCalculator
from scheduler import DataScheduler
from renderers import CLIRenderer

logger = logging.getLogger(__name__)


def run_market_monitor_loop(interval_seconds: int = 300):
    """
    Continuously monitor OSRS market events.

    Refreshes market data and displays alerts periodically.
    """

    calculator = OSRSAlchemyFlippingCalculator()
    scheduler = DataScheduler(calculator)

    print("Starting OSRS Market Monitor")
    print(f"Refresh interval: {interval_seconds}s")
    print()

    while True:
        try:
            print("=" * 70)
            print("Refreshing market data...")
            print("=" * 70)

            if not scheduler.refresh_all(force=True):
                print("[ERROR] Market refresh failed")
                time.sleep(interval_seconds)
                continue


            crash_events = calculator.get_alchemy_alerts(
                min_profit=100,
                min_volume_imbalance=2.0
            )

            trend_events = calculator.get_flipping_alerts(
                min_margin=1000,
                min_volume=20
            )


            if crash_events:
                print("\nCRASH ALERTS")
                CLIRenderer.display_alchemy_crash_alerts(
                    crash_events,
                    set()
                )


            if trend_events:
                print("\nTREND ALERTS")
                CLIRenderer.display_flipping_trend_alerts(
                    trend_events,
                    set()
                )


            print(
                f"\nSleeping {interval_seconds} seconds..."
            )

            time.sleep(interval_seconds)


        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break


        except Exception as e:
            logger.exception(
                f"Monitor failure: {e}"
            )
            time.sleep(interval_seconds)