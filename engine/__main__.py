import logging
import time

from engine.calculator import OSRSAlchemyFlippingCalculator
from cli import main as cli
import config

# Configure logging
logging.basicConfig(
    format=config.LOG_FORMAT,
    datefmt=config.LOG_DATE_FORMAT,
    level=getattr(logging, config.LOG_LEVEL)
)

calculator = OSRSAlchemyFlippingCalculator()

print("=" * 70)
print("ENHANCED FLIPPING ANALYSIS WITH TREND ALERTS")
print("=" * 70)

cli.run_flipping_analysis(
    calculator,
    limit=15,
    min_margin=1000,
    min_volume=50,
    members_only=None,
    max_buy_price=20000000,
    max_margin_percent=15.0,
    exclude_high_risk=True,
    min_score=40,
    save_csv_file=True,
    fetch_history=True,
    use_averaged_prices=True,
    show_alerts=True,
    alert_min_margin=1000,
    alert_min_volume=20
)

time.sleep(2)

print("\n" + "=" * 70)
print("ENHANCED ALCHEMY ANALYSIS WITH CRASH DETECTION")
print("=" * 70)

cli.run_alchemy_analysis(
    calculator,
    min_profit=200,
    max_items=100,
    members_only=None,
    save_csv_file=True,
    max_buy_price=10000000,
    min_limit=None,
    min_volume=20,
    max_roi=None,
    show_non_alchemizable_sample=False,
    show_crash_alerts=True,
    alert_min_profit=100,
    alert_min_imbalance=2.0
)
