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
        if df.empty or len(df) < 20:
            return fallback
        try:
            close  = df["close"]
            high   = df["high"]
            low    = df["low"]
            volume = df["volume"]

            # Trend strength
            price_change   = close.diff().abs()
            volatility     = price_change.rolling(14).std() + 1e-9
            trend_strength = (price_change.rolling(14).mean() / volatility).iloc[-1]

            # Trend direction
            sma20      = close.rolling(20).mean()
            sma50      = close.rolling(min(50, len(df))).mean()
            is_uptrend = close.iloc[-1] > sma20.iloc[-1] and sma20.iloc[-1] > sma50.iloc[-1]
            is_downtrend = close.iloc[-1] < sma20.iloc[-1] and sma20.iloc[-1] < sma50.iloc[-1]

            # ATR volatility %
            hl  = high - low
            hcp = (high - close.shift()).abs()
            lcp = (low  - close.shift()).abs()
            atr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1).rolling(14).mean()
            vol_pct = atr.iloc[-1] / close.iloc[-1] * 100

            # RSI
            delta = close.diff()
            gain  = delta.where(delta > 0, 0).rolling(14).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi   = (100 - 100 / (1 + gain / (loss + 1e-9))).iloc[-1]

            # Volume ratio
            vol_ratio = volume.iloc[-1] / (volume.rolling(20).mean().iloc[-1] + 1e-9)

            # FIX: lowered threshold 1.5 → 1.0 so normal trending days are caught
            if trend_strength > 1.0:
                if is_uptrend:
                    condition = "STRONG_UPTREND"
                elif is_downtrend:
                    condition = "STRONG_DOWNTREND"
                else:
                    condition = "TRENDING"
            elif vol_pct > 3:
                condition = "HIGH_VOLATILITY"
            elif rsi < 35:
                condition = "OVERSOLD"
            elif rsi > 65:
                condition = "OVERBOUGHT"
            elif abs(close.iloc[-1] - sma20.iloc[-1]) / (sma20.iloc[-1] + 1e-9) < 0.01:
                condition = "RANGING"
            else:
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
