# Strategy Selector - Analyses market condition and picks the best strategy.
#
# FIX: Original returned HOLD for STRONGDOWNTREND which is fine, BUT it also
# returned HOLD when condition == UNKNOWN (not enough candles, or calc error).
# UNKNOWN is the most common condition early in the session when candle count
# is low — this silently skipped every stock for the first 30-40 minutes.
# Fix:
#   1. UNKNOWN  → default to VWAP_MOMENTUM (always try, let strategy decide)
#   2. STRONGDOWNTREND → still HOLD (correct, avoid shorting in paper mode)
#   3. Condition thresholds relaxed: trend_strength > 1.5 was too strict,
#      lowered to > 1.0 so STRONGUPTREND fires more often during normal moves.
#   4. select_strategy() now ALWAYS returns a (name, market_info) tuple —
#      never raises, never returns bare string.

import logging
import numpy as np
import pandas as pd
from config import settings

logger = logging.getLogger(__name__)


class StrategySelector:

    def analyze_market_condition(self, df: pd.DataFrame) -> dict:
        """Analyze current market condition. Returns safe defaults on any error."""
        fallback = {"condition": "UNKNOWN"}

        # Read from settings dynamically
        min_candles = getattr(settings, 'REGIME_MIN_CANDLES', 10)
        trend_thresh = getattr(settings, 'REGIME_TREND_STRENGTH_MIN', 0.8)
        vol_thresh = getattr(settings, 'REGIME_VOLATILITY_PCT_MIN', 2.0)
        oversold = getattr(settings, 'REGIME_RSI_OVERSOLD', 35)
        overbought = getattr(settings, 'REGIME_RSI_OVERBOUGHT', 65)

        if df.empty or len(df) < min_candles:
            return fallback

        try:
            close  = df["close"]
            high   = df["high"]
            low    = df["low"]
            volume = df["volume"]

            # Adjust lookback window based on available data size
            lookback = min(14, len(df) - 1)

            # Trend strength
            price_change   = close.diff().abs()
            volatility     = price_change.rolling(lookback).std() + 1e-9
            trend_strength = (price_change.rolling(lookback).mean() / volatility).iloc[-1]

            # Trend direction
            sma_fast = close.rolling(min(20, len(df))).mean()
            sma_slow = close.rolling(min(50, len(df))).mean()

            # Using basic SMA checks for trend to avoid NaN issues with limited data
            is_uptrend = close.iloc[-1] > sma_fast.iloc[-1] and (sma_fast.iloc[-1] > sma_slow.iloc[-1] or len(df) < 50)
            is_downtrend = close.iloc[-1] < sma_fast.iloc[-1] and (sma_fast.iloc[-1] < sma_slow.iloc[-1] or len(df) < 50)

            # ATR volatility %
            hl  = high - low
            hcp = (high - close.shift()).abs()
            lcp = (low  - close.shift()).abs()
            atr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(lookback).mean()
            vol_pct = atr.iloc[-1] / close.iloc[-1] * 100

            # RSI
            delta = close.diff()
            gain  = delta.where(delta > 0, 0).rolling(lookback).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(lookback).mean()
            rsi   = (100 - 100 / (1 + gain / (loss + 1e-9))).iloc[-1]

            # Volume ratio
            vol_ratio = volume.iloc[-1] / (volume.rolling(lookback).mean().iloc[-1] + 1e-9)

            if trend_strength > trend_thresh:
                if is_uptrend:
                    condition = "STRONG_UPTREND"
                elif is_downtrend:
                    condition = "STRONG_DOWNTREND"
                else:
                    condition = "TRENDING"
            elif vol_pct > vol_thresh:
                condition = "HIGH_VOLATILITY"
            elif rsi < oversold:
                condition = "OVERSOLD"
            elif rsi > overbought:
                condition = "OVERBOUGHT"
            elif abs(close.iloc[-1] - sma_fast.iloc[-1]) / (sma_fast.iloc[-1] + 1e-9) < 0.01:
                condition = "RANGING"
            else:
                # Priority 12 fix: ADX 14-period fallback to minimize UNKNOWN/NEUTRAL
                try:
                    import pandas_ta as ta
                    adx_df = ta.adx(high, low, close, length=14)
                    if adx_df is not None and not adx_df.empty:
                        adx_val = adx_df.iloc[-1, 0]
                        if pd.notna(adx_val):
                            if adx_val > 25:
                                condition = "TRENDING"
                            elif adx_val < 20:
                                condition = "RANGING"
                            else:
                                condition = "NEUTRAL"
                        else:
                            condition = "NEUTRAL"
                    else:
                        condition = "NEUTRAL"
                except Exception as e:
                    logger.debug(f"ADX fallback failed: {e}")
                    condition = "NEUTRAL"

            return {
                "condition":     condition,
                "trend_strength": trend_strength,
                "is_uptrend":    is_uptrend,
                "is_downtrend":  is_downtrend,
                "volatility_pct": vol_pct,
                "rsi":           rsi,
                "volume_ratio":  vol_ratio,
            }
        except Exception as e:
            logger.error(f"analyze_market_condition error: {e}")
            return fallback

    def select_strategy(self, symbol: str, df: pd.DataFrame) -> tuple:
        """
        Returns (strategy_name, market_info).
        FIX: UNKNOWN condition now defaults to VWAP_MOMENTUM instead of HOLD,
        so early-session stocks with few candles still get a trade attempt.
        STRONG_DOWNTREND still returns HOLD (correct — no long trades in downtrend).
        """
        if not settings.AUTO_STRATEGY_SELECTION:
            return settings.DEFAULT_STRATEGY, {"condition": "MANUAL"}

        market_info = self.analyze_market_condition(df)
        condition   = market_info.get("condition", "UNKNOWN")
        logger.info(f"{symbol} Market condition: {condition}")

        if condition == "STRONG_UPTREND":
            selected = np.random.choice(["VWAP_MOMENTUM", "EMA_CROSSOVER", "SUPERTREND"])

        elif condition == "STRONG_DOWNTREND":
            selected = "HOLD"   # no longs in downtrend

        elif condition in ("OVERSOLD", "RANGING"):
            selected = np.random.choice(["BOLLINGER_REVERSAL", "RSI_REVERSAL"])

        elif condition == "OVERBOUGHT":
            selected = np.random.choice(["BOLLINGER_REVERSAL", "RSI_REVERSAL"])

        elif condition == "HIGH_VOLATILITY":
            selected = np.random.choice(["ATR_BREAKOUT", "VOLUME_BREAKOUT"])

        elif condition == "TRENDING":
            selected = np.random.choice(["MACD_MOMENTUM", "VOLUME_BREAKOUT", "EMA_CROSSOVER"])

        else:
            # NEUTRAL or UNKNOWN — default to VWAP, let the strategy decide
            selected = "VWAP_MOMENTUM"

        logger.info(f"{symbol} Selected strategy: {selected}")
        return selected, market_info
