"""
Centralized configuration for OSRS Alchemy/Flipping Tool.

All thresholds, magic numbers, and keyword lists should be defined here.
"""

# ============================================================================
# ALCHEMY CONFIGURATION
# ============================================================================

# Cost of nature rune for high alchemy calculations
NATURE_RUNE_COST = 125

# Keywords that indicate an item cannot be alchemized
NON_ALCHEMIZABLE_KEYWORDS = [
    'noted', '(noted)', 'bank note', 'certificate',
    'clue', 'casket', 'scroll', 'pet', 'spirit',
    'teleport', 'tab', 'tablet', 'crystal seed',
    'broken', 'damaged', 'degraded', 'uncharged',
    'contract', 'bloodied', 'severance', 'sensory'
]

# ============================================================================
# FLIPPING CONFIGURATION
# ============================================================================

# Number of historical periods to use for price averaging
FLIPPING_HISTORY_PERIODS = 300  # 120 * 6h = 30 days

# Whether to use averaged prices for flipping by default
USE_FLIPPING_AVERAGES = True

# ============================================================================
# DISCORD BOT CONFIGURATION
# ============================================================================

# Default profit thresholds for Discord alerts (in gp)
DEFAULT_HOT_ITEMS_MIN_PROFIT = 450
DEFAULT_SUPER_HOT_MIN_PROFIT = 1000
DEFAULT_ALL_ALCHS_MIN_PROFIT = 1
DEFAULT_F2P_ALCHS_MIN_PROFIT = 1

# Super hot items filtering parameters
SUPER_HOT_MAX_ITEMS = 20
SUPER_HOT_MIN_LIMIT = 7
SUPER_HOT_MIN_VOLUME = 20
SUPER_HOT_MAX_ROI = 225

# Historical enrichment threshold
# Items with profit >= this value will have historical data enriched during refresh
ENRICHMENT_MIN_PROFIT = 100  # Covers all display tiers

# Bot monitoring interval (in minutes)
MONITORING_INTERVAL_MINUTES = 2

# Bot monitoring interval (in seconds)
MONITORING_INTERVAL_SECONDS = 10

# Alert persistence (in minutes)
ALERT_PERSISTENCE_MINUTES = 2

# ============================================================================
# DATA REFRESH INTERVALS (in seconds)
# ============================================================================

# How often to refresh different data sources
REFRESH_INTERVAL_ITEM_MAPPING = 3600      # 1 hour - rarely changes
REFRESH_INTERVAL_CURRENT_PRICES = 2       # Always refresh - real-time prices
REFRESH_INTERVAL_VOLUME_DATA = 2          # Always refresh - hourly volume updates
REFRESH_INTERVAL_FIVE_MINUTE_DATA = 60     # Always refresh - short-term trends
REFRESH_INTERVAL_TIMESERIES = 300         # 5 minutes - historical data

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Logging format
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Default log level
LOG_LEVEL = 'INFO'
