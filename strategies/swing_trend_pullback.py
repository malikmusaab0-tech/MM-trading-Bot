"""
Swing strategy: daily trend-following with pullback entries.

Idea (long side):
- Trade only in clear uptrends (close > 50-day EMA).
- Look for pullbacks towards 20-day EMA.
- Stop-loss below recent swing low, target at 2R by default.

Short side is symmetric (can disable initially if you want only long).
"""

from dataclasses import dataclass
from typing import Optional, Dict

import pandas as pd
from config import settings


@dataclass
class SwingSignal:
    segment: str
    symbol: str
    side: str          # "BUY" / "SELL" (for shorts)
    entry: float
    stop_loss: float
    target: float
    timeframe: str     # e.g. "2-4 weeks"


class SwingTrendPullbackStrategy:
    def __init__(
        self,
        ema_trend_period: int = 50,
        ema_pullback_period: int = 20,
        risk_reward: float = 2.0,
    ):
        self.ema_trend_period = ema_trend_period
        self.ema_pullback_period = ema_pullback_period
        self.risk_reward = risk_reward

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_trend"] = df["close"].ewm(
            span=self.ema_trend_period, adjust=False
        ).mean()
        df["ema_pullback"] = df["close"].ewm(
            span=self.ema_pullback_period, adjust=False
        ).mean()
        return df

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[Dict]:
        """
        Parameters
        ----------
        symbol : str
            NSE symbol (e.g., "RELIANCE").
        df : DataFrame
            Daily OHLCV data with columns: open, high, low, close, volume.
            Index should be datetime or have a 'date' like index.

        Returns
        -------
        dict or None
            High-level swing trade idea, or None if no trade.
        """
        if df is None or len(df) < max(self.ema_trend_period, self.ema_pullback_period) + 5:
            return None

        df = self._compute_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(last["close"])
        ema_trend = float(last["ema_trend"])
        ema_pullback = float(last["ema_pullback"])

        # Simple long-side logic:
        # - Uptrend: price above trend EMA
        # - Pullback: price near or slightly below pullback EMA, but trend intact
        in_uptrend = close > ema_trend
        pulled_back = close <= ema_pullback * 1.01  # within +1% of pullback EMA

        if in_uptrend and pulled_back:
            # Use recent swing low (last N bars) as stop
            lookback = df.tail(10)
            swing_low = float(lookback["low"].min())
            entry = close
            stop = swing_low
            if stop >= entry:
                return None  # invalid R

            risk_per_share = entry - stop
            target = entry + self.risk_reward * risk_per_share

            return {
                "segment": settings.SEGMENT_SWING,
                "symbol": symbol,
                "side": "BUY",
                "entry": entry,
                "stop_loss": stop,
                "target": target,
                "timeframe": "2-4 weeks",
            }

        # For now, skip short-side swing logic; add later if needed.
        return None