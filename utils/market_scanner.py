# Market Scanner - Scans entire NSE market for trading opportunities
# Filters stocks based on volume, liquidity, price action, and technical indicators
#
# FIX: scan_for_opportunities() was calling kite.quote(symbol) one-by-one
# for every stock in the liquid list (up to 952 calls per cycle).
# This exhausted Zerodha rate limits before main.py could call batch_ltp(),
# causing "Too many requests" and zero orders placed.
# Fix: replaced per-symbol kite.quote() with a single batched kite.quote()
# call (500 symbols per chunk), then all signal scoring is done from that
# cached dict — zero individual API calls inside the loop.

import logging
import time
from typing import List, Dict

import pandas as pd
from kiteconnect import KiteConnect

from config import settings

logger = logging.getLogger(__name__)


class MarketScanner:
    """Scans NSE market for trading opportunities"""

    def __init__(self, kite: KiteConnect):
        self.kite        = kite
        self.instruments = []
        self._load_instruments()

    def _load_instruments(self):
        try:
            all_instruments  = self.kite.instruments("NSE")
            self.instruments = [
                inst for inst in all_instruments
                if inst["instrument_type"] == "EQ" and inst["segment"] == "NSE"
            ]
            logger.info(f"Loaded {len(self.instruments)} NSE equity instruments")
        except Exception as e:
            logger.error(f"Failed to load instruments: {e}")
            self.instruments = []

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _batch_quote(self, symbols: list) -> dict:
        """
        Fetch kite.quote() for a list of NSE symbols in chunks of 500.
        Returns {'NSE:SYM': data_dict} merged from all chunks.
        Adds a small sleep between chunks to avoid rate limiting.
        """
        result     = {}
        chunk_size = 500
        keys       = [f"NSE:{s}" for s in symbols]
        for i in range(0, len(keys), chunk_size):
            chunk = keys[i: i + chunk_size]
            try:
                data = self.kite.quote(chunk)
                result.update(data)
            except Exception as e:
                logger.warning(f"_batch_quote error chunk {i}: {e}")
            if i + chunk_size < len(keys):
                time.sleep(0.4)   # respect ~3 req/s Zerodha limit between chunks
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Liquid stocks filter
    # ─────────────────────────────────────────────────────────────────────────
    def get_liquid_stocks(self) -> List[str]:
        """
        Get liquid NSE stocks using a single batched quote call per 500 symbols.
        FIX: was calling kite.quote() per-batch already here (ok), but
        scan_for_opportunities() then called kite.quote() again per-symbol
        on the resulting list — that second layer is what we eliminated.
        """
        try:
            symbols    = [f"NSE:{inst['tradingsymbol']}" for inst in self.instruments]
            liquid     = []
            chunk_size = 500

            for i in range(0, len(symbols), chunk_size):
                chunk = symbols[i: i + chunk_size]
                try:
                    quotes = self.kite.quote(chunk)
                    for key, data in quotes.items():
                        trading_symbol = key.replace("NSE:", "")
                        ltp    = data.get("last_price", 0)
                        volume = data.get("volume", 0)
                        if (settings.MIN_STOCK_PRICE <= ltp <= settings.MAX_STOCK_PRICE
                                and volume >= settings.MIN_VOLUME):
                            turnover_cr = ltp * volume / 10_000_000
                            if turnover_cr >= settings.MIN_LIQUIDITY_CRORE:
                                liquid.append(trading_symbol)
                except Exception as e:
                    logger.warning(f"get_liquid_stocks error chunk {i}: {e}")
                if i + chunk_size < len(symbols):
                    time.sleep(0.4)

            logger.info(f"Found {len(liquid)} liquid stocks")
            return liquid

        except Exception as e:
            logger.error(f"Error in get_liquid_stocks: {e}")
            return settings.DEFAULT_WATCHLIST

    # ─────────────────────────────────────────────────────────────────────────
    # Main scan — FULLY BATCHED, zero per-symbol API calls
    # ─────────────────────────────────────────────────────────────────────────
    def scan_for_opportunities(self, stocks: List[str] = None) -> List[Dict]:
        """
        Scan stocks for trading opportunities.

        FIX: old code called kite.quote(f"NSE:{symbol}") inside a for-loop
        over all liquid stocks — up to 952 individual API calls per cycle.
        New code fetches ALL quotes in one _batch_quote() call (chunked at 500),
        then scores signals purely from the resulting dict. No API calls inside
        the scoring loop.
        """
        if stocks is None:
            stocks = self.get_liquid_stocks() if settings.SCAN_ENTIRE_MARKET                      else settings.DEFAULT_WATCHLIST

        if not stocks:
            return []

        # ── Single batched quote fetch for all candidate stocks ───────────
        logger.info(f"Fetching quotes for {len(stocks)} stocks (batched)...")
        quote_cache = self._batch_quote(stocks)

        if not quote_cache:
            logger.warning("quote_cache empty — no opportunities this cycle")
            return []

        # ── Score signals from cache — ZERO API calls here ───────────────
        opportunities = []
        for symbol in stocks:
            try:
                key  = f"NSE:{symbol}"
                data = quote_cache.get(key)
                if not data:
                    continue

                ohlc       = data.get("ohlc", {})
                ltp        = data.get("last_price", 0)
                volume     = data.get("volume", 0)
                avg_volume = data.get("average_price", 0) * volume if volume else 0

                signals       = []
                signal_strength = 0

                # Volume surge
                if avg_volume > 0 and volume > avg_volume * 1.5:
                    signals.append("VOLUME_SURGE")
                    signal_strength += 1

                # Near day low (potential bounce)
                day_low = ohlc.get("low", ltp)
                if ltp and day_low and ltp <= day_low * 1.02:
                    signals.append("NEAR_DAY_LOW")
                    signal_strength += 1

                # Near day high (potential breakout)
                day_high = ohlc.get("high", ltp)
                if ltp and day_high and ltp >= day_high * 0.98:
                    signals.append("NEAR_DAY_HIGH")
                    signal_strength += 1

                # Strong intraday move (>2%)
                day_open = ohlc.get("open", 0)
                if day_open:
                    change_pct = (ltp - day_open) / day_open * 100
                    if abs(change_pct) >= 2:
                        signals.append(
                            f"STRONG_MOVE+{change_pct:.1f}"
                            if change_pct > 0
                            else f"STRONG_MOVE{change_pct:.1f}"
                        )
                        signal_strength += 2
                else:
                    change_pct = 0

                if signal_strength >= 2:
                    opportunities.append({
                        "symbol":          symbol,
                        "ltp":             ltp,
                        "volume":          volume,
                        "signals":         signals,
                        "signal_strength": signal_strength,
                        "change_pct":      change_pct,
                    })

            except Exception as e:
                logger.debug(f"Error scoring {symbol}: {e}")
                continue

        opportunities.sort(key=lambda x: x["signal_strength"], reverse=True)
        logger.info(f"Found {len(opportunities)} trading opportunities")
        return opportunities[:50]

    # ─────────────────────────────────────────────────────────────────────────
    # Detailed scan (candle-based) — unchanged
    # ─────────────────────────────────────────────────────────────────────────
    def get_detailed_scan(self, symbol: str, df: pd.DataFrame) -> Dict:
        """Detailed technical analysis on a stock using OHLCV dataframe"""
        if df.empty or len(df) < 30:
            return {}
        try:
            close = df["close"]
            high  = df["high"]
            low   = df["low"]

            # RSI
            delta = close.diff()
            gain  = delta.where(delta > 0, 0).rolling(window=settings.RSI_PERIOD).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(window=settings.RSI_PERIOD).mean()
            rs    = gain / (loss + 1e-9)
            rsi   = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]

            # MACD
            ema_fast   = close.ewm(span=settings.MACD_FAST).mean()
            ema_slow   = close.ewm(span=settings.MACD_SLOW).mean()
            macd_line  = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=settings.MACD_SIGNAL).mean()
            macd_hist  = macd_line - signal_line

            # ATR
            tr  = pd.concat([
                high - low,
                (high - close.shift()).abs(),
                (low  - close.shift()).abs(),
            ], axis=1).max(axis=1)
            atr = tr.rolling(settings.ADX_PERIOD).mean()

            # Stochastic
            low_min  = low.rolling(settings.STOCH_K).min()
            high_max = high.rolling(settings.STOCH_K).max()
            stoch_k  = 100 * (close - low_min) / (high_max - low_min + 1e-9)
            stoch_d  = stoch_k.rolling(settings.STOCH_D).mean()

            # Support / Resistance
            recent_high   = high.tail(20).max()
            recent_low    = low.tail(20).min()
            current_price = close.iloc[-1]

            return {
                "symbol":       symbol,
                "price":        current_price,
                "rsi":          current_rsi,
                "rsi_signal":   ("OVERSOLD"  if current_rsi < settings.RSI_OVERSOLD
                                 else "OVERBOUGHT" if current_rsi > settings.RSI_OVERBOUGHT
                                 else "NEUTRAL"),
                "macd":         macd_line.iloc[-1],
                "macd_signal":  signal_line.iloc[-1],
                "macd_histogram": macd_hist.iloc[-1],
                "macd_crossover": ("BULLISH" if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] < 0
                                   else "BEARISH" if macd_hist.iloc[-1] < 0 and macd_hist.iloc[-2] > 0
                                   else "NONE"),
                "stoch_k":      stoch_k.iloc[-1],
                "stoch_d":      stoch_d.iloc[-1],
                "stoch_signal": ("OVERSOLD"  if stoch_k.iloc[-1] < settings.STOCH_OVERSOLD
                                 else "OVERBOUGHT" if stoch_k.iloc[-1] > settings.STOCH_OVERBOUGHT
                                 else "NEUTRAL"),
                "atr":          atr.iloc[-1],
                "support":      recent_low,
                "resistance":   recent_high,
                "trend":        ("BULLISH" if current_price > close.rolling(20).mean().iloc[-1]
                                 else "BEARISH"),
            }
        except Exception as e:
            logger.error(f"Error in detailed scan for {symbol}: {e}")
            return {}
