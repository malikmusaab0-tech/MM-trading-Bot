import logging
from math import floor
from typing import List
import pandas as pd
from dhanhq import dhanhq
import redis

from config import settings
from utils.paper_trading import PaperTradingEngine
from strategies.long_term_investing import LongTermInvestingStrategy
from utils.nifty_100_symbols import NIFTY_100_SYMBOLS

logger = logging.getLogger(__name__)

class InvestingEngine:
    def __init__(self, dhan: dhanhq, trading_engine: PaperTradingEngine):
        self.dhan = dhan
        self.engine = trading_engine
        self.strategy = LongTermInvestingStrategy()

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

        allocations = self.strategy.rank_and_allocate(dfs, top_n=30)

        if not allocations:
            logger.info("[INVESTING] No stocks qualified for investing strategy.")
            return

        logger.info(f"[INVESTING] {len(allocations)} stocks selected for allocation.")

        investing_capital = self.engine.cash * getattr(settings, 'ALLOCATION_LONGTERM', 0.20)

        for symbol, weight in allocations.items():
            price = dfs[symbol]["close"].iloc[-1]
            allocation_value = investing_capital * weight
            qty = floor(allocation_value / price)

            if qty > 0:
                logger.info(f"[INVESTING] BUY {symbol} x{qty} @ Rs.{price:.2f} | Weight: {weight*100:.2f}%")
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
