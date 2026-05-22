import logging
from math import floor
from typing import List
import pandas as pd
from dhanhq import dhanhq
import redis

from config import settings
from utils.paper_trading import PaperTradingEngine
from strategies.investing_momentum import InvestingMomentumStrategy
from utils.nifty_100_symbols import NIFTY_100_SYMBOLS

logger = logging.getLogger(__name__)

class InvestingEngine:
    def __init__(self, dhan: dhanhq, trading_engine: PaperTradingEngine):
        self.dhan = dhan
        self.engine = trading_engine
        self.strategy = InvestingMomentumStrategy()

    def fetch_historical_data(self, r: redis.Redis) -> dict:
        dfs = {}
        for symbol in NIFTY_100_SYMBOLS:
            closes = r.lrange(f"historical:daily:{symbol}:close", 0, -1)
            if closes and len(closes) > 120:  # Need ~6 months of data
                dfs[symbol] = pd.DataFrame({'close': pd.to_numeric(closes)})
        return dfs

    def run_manual_rebalance(self):
        """
        Public method to manually trigger the rebalance logic.
        """
        logger.info("[INVESTING] Manual rebalance triggered.")
        self._execute_rebalance()

    def run_monthly(self):
        """
        Executes the monthly investing strategy.
        Ranks Nifty 100 by momentum/volatility, and buys top 10 stocks
        as CNC (Delivery) orders.
        """
        logger.info("[INVESTING] Running monthly investing strategy...")
        self._execute_rebalance()

    def _execute_rebalance(self):
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
        dfs = self.fetch_historical_data(r)

        if not dfs:
            logger.warning("[INVESTING] No sufficient historical daily data found in Redis for momentum calculation.")
            return

        top_stocks = self.strategy.calculate_momentum_score(dfs)

        if not top_stocks:
            logger.info("[INVESTING] No stocks qualified for investing strategy.")
            return

        logger.info(f"[INVESTING] Top {len(top_stocks)} stocks selected.")

        # Calculate allocation per stock
        # removed investing_capital
        # Simple allocation: equal weight of 10% total capital per stock
        allocation_per_stock = self.engine.cash * 0.10

        for stock in top_stocks:
            symbol = stock['symbol']
            price = stock['price']
            score = stock['score']

            qty = floor(allocation_per_stock / price)

            if qty > 0:
                logger.info(f"[INVESTING] BUY {symbol} x{qty} @ Rs.{price:.2f} | Score: {score:.2f}")
                # Execute CNC Delivery order
                self.engine.buy(
                    symbol=symbol,
                    quantity=qty,
                    price=price,
                    segment=settings.SEGMENT_LONGTERM,
                    order_type="MARKET",
                    product_type="CNC" # Delivery
                )
            else:
                logger.info(f"[INVESTING] Skipping {symbol}, allocation too small to buy 1 share at Rs.{price:.2f}")

        logger.info("[INVESTING] Monthly investing strategy execution complete.")
