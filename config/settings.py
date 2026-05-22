"""
PRIMA Pro Trading Bot - Configuration
Professional-grade settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATABASE_PATH = BASE_DIR / "data" / "trading.db"
LOG_FILE = BASE_DIR / "logs" / "trading.log"

# Notifications (Telegram / WhatsApp)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_ENABLED   = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
WHATSAPP_ENABLED   = False

# ---------------------------------------------------------------------------
# Segments (portfolio slices)
# ---------------------------------------------------------------------------
SEGMENT_INTRADAY = "INTRADAY"
SEGMENT_SWING    = "SWING"
SEGMENT_LONGTERM = "LONGTERM"

# DhanHQ API
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "dummy_client_id")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "dummy_access_token")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# PostgreSQL
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "trading_db")

# ---------------------------------------------------------------------------
# Trading Parameters
# ---------------------------------------------------------------------------
INITIAL_CAPITAL    = 100000   # Rs.1 Lakh starting capital
PAPER_TRADING_MODE = True

# Safe mode guardrail: If LIVE_TRADING_MODE is True, PAPER_TRADING_MODE MUST be False
LIVE_TRADING_MODE = os.getenv("LIVE_TRADING_MODE", "False").lower() in ("true", "1", "yes")
if LIVE_TRADING_MODE:
    PAPER_TRADING_MODE = False

MAX_DAILY_LOSS = int(os.getenv("MAX_DAILY_LOSS", 5000))

# Segment Capital Allocation (Percentages must sum to <= 1.0)
ALLOCATION_INTRADAY = 0.50
ALLOCATION_SWING    = 0.30
ALLOCATION_LONGTERM = 0.20

# Intraday Trading
# NOTE: INTRADAY_MARGIN_MULTIPLIER is kept ONLY for MAX_INTRADAY_EXPOSURE calc.
# Per-position sizing now uses POSITION_SIZE_CAPITAL_PCT x per-security leverage
# sourced from NSE VaR file / Kite API via MarginCache in risk_manager.py.
INTRADAY_MARGIN_MULTIPLIER = 5
MAX_INTRADAY_EXPOSURE = INITIAL_CAPITAL * INTRADAY_MARGIN_MULTIPLIER  # Rs.5L total cap
SQUARE_OFF_TIME = "15:15"

# ---------------------------------------------------------------------------
# Position Sizing  <-- DYNAMIC (replaces old static MAX_POSITION_VALUE)
# ---------------------------------------------------------------------------
# Fraction of *current available cash* to allocate per position (25%)
POSITION_SIZE_CAPITAL_PCT: float = 0.25

# Per-trade stop-risk as % of available capital (for risk-based sizing leg)
POSITION_SIZE_PCT: float = 5.0      # Risk allocation per asset

# Minimum notional value to bother placing an order
MIN_POSITION_SIZE: float = 500      # Minimum INR notional required to trade

# Max concurrent open positions
MAX_CONCURRENT_POSITIONS: int = 10

MAX_POSITION_VALUE: float = 25000   # Max INR notional per position

# ---------------------------------------------------------------------------
# Swing Trading
# ---------------------------------------------------------------------------
SWING_ENABLED              = True
SWING_TIMEFRAME            = "day"
SWING_MAX_POSITIONS        = 5
SWING_MAX_RISK_PER_TRADE_PCT = 1
SWING_MAX_TOTAL_RISK_PCT   = 5
SWING_NOTIFICATIONS_ENABLED = True

# ---------------------------------------------------------------------------
# Long-Term Investing Segment
# ---------------------------------------------------------------------------
LONGTERM_ENABLED        = True
LONGTERM_WATCHLIST      = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR",
]
LONGTERM_MAX_RISK_PER_TRADE_PCT    = 2.0
LONGTERM_REVIEW_TIME               = "21:00"
LONGTERM_MIN_MARGIN_OF_SAFETY_PCT  = 20.0
LONGTERM_OVERVALUED_THRESHOLD_PCT  = 10.0
LONGTERM_NOTIFICATIONS_ENABLED     = True

# ---------------------------------------------------------------------------
# Risk Management
# ---------------------------------------------------------------------------
STOP_LOSS_PCT                 = 1.5
STOP_LOSS_ATR_MULTIPLIER      = 1.5
TAKE_PROFIT_ATR_MULTIPLIER    = 2.0
TRAILING_STOP_ACTIVATION_PCT  = 1.0
TRAILING_STOP_DISTANCE_PCT    = 0.5

# ---------------------------------------------------------------------------
# Market Scanning
# ---------------------------------------------------------------------------
SCAN_INTERVAL_SECONDS = 60

SCAN_ENTIRE_MARKET   = False
MIN_STOCK_PRICE      = 10
MAX_STOCK_PRICE      = 50000
MIN_VOLUME           = 100000
MIN_LIQUIDITY_CRORE  = 1

# ---------------------------------------------------------------------------
# Regime Detection / Strategy Thresholds (PRI-10 / PRI-12)
# ---------------------------------------------------------------------------
REGIME_MIN_CANDLES         = 10   # Reduced from 20 to classify earlier in session
REGIME_TREND_STRENGTH_MIN  = 0.8  # Reduced from 1.0 to capture subtle emerging trends
REGIME_VOLATILITY_PCT_MIN  = 2.0  # Reduced from 3.0 to acknowledge volatile Nifty environments
REGIME_RSI_OVERSOLD        = 35   # Allow slight momentum buildup
REGIME_RSI_OVERBOUGHT      = 65

# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30
RSI_OVERBOUGHT = 70

MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9

ADX_PERIOD       = 14
ADX_STRONG_TREND = 25

STOCH_K          = 14
STOCH_D          = 3
STOCH_OVERSOLD   = 20
STOCH_OVERBOUGHT = 80

BB_PERIOD = 20
BB_STD    = 2.0

# ---------------------------------------------------------------------------
# Data Fetching
# ---------------------------------------------------------------------------
CANDLE_INTERVAL          = "5minute"
CANDLE_LOOKBACK_MINUTES  = 390
REFRESH_SECONDS          = 10

# ---------------------------------------------------------------------------
# Strategy Selection
# ---------------------------------------------------------------------------
AUTO_STRATEGY_SELECTION = True
DEFAULT_STRATEGY        = "VWAP_MOMENTUM"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = "INFO"

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
DASHBOARD_PORT             = 5000
DASHBOARD_REFRESH_INTERVAL = 2

# ---------------------------------------------------------------------------
# Pattern Recognition
# ---------------------------------------------------------------------------
ENABLE_PATTERN_RECOGNITION = True
PATTERN_LOOKBACK_CANDLES   = 50

# Default watchlist
DEFAULT_WATCHLIST = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT",
]

# Exchange
EXCHANGE     = "NSE"
PRODUCT_TYPE = "MIS"
ORDER_TYPE   = "MARKET"