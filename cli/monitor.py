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
            # Refresh market data (logging now at DEBUG level)
            if not scheduler.refresh_all(force=True):
                print("[ERROR] Market refresh failed")
                time.sleep(interval_seconds)
                continue

            # Get market alerts
            crash_events = calculator.get_alchemy_alerts(
                min_profit=100,
                min_volume_imbalance=2.0
            )

            trend_events = calculator.get_flipping_alerts(
                min_margin=1000,
                min_volume=20
            )

            # Display concise dashboard
            CLIRenderer.display_market_dashboard(
                calculator,
                crash_events,
                trend_events
            )

            print(f"Next refresh in {interval_seconds} seconds...")
            print()

            time.sleep(interval_seconds)


        except KeyboardInterrupt:
            print("\nMonitor stopped.")
            break


        except Exception as e:
            logger.exception(
                f"Monitor failure: {e}"
            )
            time.sleep(interval_seconds)