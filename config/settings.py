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

# Kite API
KITE_API_KEY = os.getenv("KITE_API_KEY", "2kcgzxe407fpuvif")
KITE_API_SECRET = os.getenv("KITE_API_SECRET", "15n1n3w5k3y70pvxayy7148q3dziawtc")

# Trading Parameters
INITIAL_CAPITAL = 100000  # ₹1 Lakh
PAPER_TRADING_MODE = True

# Intraday Trading
INTRADAY_MARGIN_MULTIPLIER = 5  # MIS margin (5x for stocks)
MAX_INTRADAY_EXPOSURE = INITIAL_CAPITAL * INTRADAY_MARGIN_MULTIPLIER  # ₹5L exposure
SQUARE_OFF_TIME = "15:15"  # Auto square-off time

# Position Sizing
MAX_POSITION_VALUE = 25000  # Max ₹25K per position
MAX_CONCURRENT_POSITIONS = 10  # Max 10 positions
MIN_POSITION_SIZE = 1000  # Min ₹1K per position
POSITION_SIZE_PCT = 0.02  # 2% risk per trade

# Risk Management
STOP_LOSS_PCT = 1.5  # 1.5% stop loss
TAKE_PROFIT_ATR_MULTIPLIER = 2.0  # 2x ATR for TP
STOP_LOSS_ATR_MULTIPLIER = 1.0  # 1x ATR for SL
TRAILING_STOP_ACTIVATION_PCT = 1.0  # Activate trailing at 1% profit
TRAILING_STOP_DISTANCE_PCT = 0.5  # Trail 0.5% behind

# Market Scanning
SCAN_ENTIRE_MARKET = True  # Scan all NSE stocks vs watchlist
MIN_STOCK_PRICE = 10  # Ignore penny stocks
MAX_STOCK_PRICE = 50000  # No upper limit practically
MIN_VOLUME = 100000  # Minimum 1L volume
MIN_LIQUIDITY_CRORE = 1  # Minimum ₹1 Cr turnover

# Indicators
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

ADX_PERIOD = 14
ADX_STRONG_TREND = 25

STOCH_K = 14
STOCH_D = 3
STOCH_OVERSOLD = 20
STOCH_OVERBOUGHT = 80

BB_PERIOD = 20
BB_STD = 2.0

# Data Fetching
CANDLE_INTERVAL = "5minute"  # 5-minute candles
CANDLE_LOOKBACK_MINUTES = 390  # 1 trading day (6.5 hours)
REFRESH_SECONDS = 10  # Scan every 10 seconds

# Strategy Selection
AUTO_STRATEGY_SELECTION = True  # Auto-select best strategy per stock
DEFAULT_STRATEGY = "VWAP_MOMENTUM"  # Fallback strategy

# Logging
LOG_LEVEL = "INFO"

# Dashboard
DASHBOARD_PORT = 5000
DASHBOARD_REFRESH_INTERVAL = 2  # seconds

# Pattern Recognition
ENABLE_PATTERN_RECOGNITION = True
PATTERN_LOOKBACK_CANDLES = 50

# Default watchlist (if not scanning entire market)
DEFAULT_WATCHLIST = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT"
]

# Exchange
EXCHANGE = "NSE"
PRODUCT_TYPE = "MIS"  # Intraday
ORDER_TYPE = "MARKET"  # Market orders
