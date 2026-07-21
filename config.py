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
DEFAULT_HOT_ITEMS_MAX_PROFIT = 999
DEFAULT_SUPER_HOT_MIN_PROFIT = 1000
DEFAULT_ALL_ALCHS_MIN_PROFIT = 600
DEFAULT_F2P_ALCHS_MIN_PROFIT = 600

# Super hot items filtering parameters
SUPER_HOT_MAX_ITEMS = 10
SUPER_HOT_MIN_LIMIT = 9
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

# Notification batching window (in seconds)
# Notifications are collected for this duration before being sent as a batch
NOTIFICATION_BATCH_WINDOW = 10  # 20 seconds

# Maximum batch size per user
# If a user accumulates this many notifications, release batch immediately
NOTIFICATION_MAX_BATCH_SIZE = 3  # notifications per user

# ============================================================================
# NOTIFICATION POLICY CONFIGURATION
# ============================================================================

# Severity scores for alchemy profit tiers (0-100 scale)
SEVERITY_SUPER_HOT = 80        # Profit >= 1000gp
SEVERITY_HOT_ITEMS = 60        # Profit >= 450gp
SEVERITY_ALL_ALCHS_HIGH = 60   # Profit >= 100gp
SEVERITY_ALL_ALCHS_LOW = 40    # Profit < 100gp

# Priority thresholds (based on severity score)
PRIORITY_CRITICAL_THRESHOLD = 90  # >= 90 = critical priority
PRIORITY_HIGH_THRESHOLD = 80      # >= 80 = high priority
PRIORITY_MEDIUM_THRESHOLD = 50    # >= 50 = medium priority
                                  # < 50 = low priority

# Default user notification preferences
DEFAULT_MIN_SEVERITY = 50         # Default minimum severity threshold
DEFAULT_COOLDOWN_MINUTES = 1     # Default cooldown between same-item notifications

PERSONAL_ALCH_MIN_LIMIT = 20
PERSONAL_ALCH_MIN_VOLUME = 50
PERSONAL_ALCH_MAX_ROI = 250
PERSONAL_ALCH_MAX_BUY_PRICE = None

# Duplicate suppression and cleanup
DUPLICATE_SUPPRESSION_MINUTES = 1  # Suppress duplicate events within this window
TRACKING_CLEANUP_HOURS = 1         # Clean old cooldown/duplicate tracking entries

# Validation limits for /notifications command
MAX_PROFIT_THRESHOLD = 100000      # Maximum allowed min_profit value (100k gp)
MIN_PROFIT_THRESHOLD = 1           # Minimum allowed min_profit value (1 gp)

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

# ============================================================================
# DEBUG FLAGS
# ============================================================================

# Enable detailed diagnostic logging for flipping alerts pipeline
# Shows item counts after each filter stage, statistics, and top filtered items
DEBUG_FLIPPING_FILTERS = False
