from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from config import settings

@dataclass
class Signal:
    action: str  # BUY | SELL | SHORT | COVER | HOLD
    quantity: int = 0
    reason: str = ""

class BaseStrategy:
    def __init__(self, capital: float):
        self.capital = capital

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        hl  = df["high"] - df["low"]
        hcp = (df["high"] - df["close"].shift()).abs()
        lcp = (df["low"]  - df["close"].shift()).abs()
        tr  = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        up    = delta.where(delta > 0, 0.0)
        down  = -delta.where(delta < 0, 0.0)
        rs    = up.rolling(period).mean() / (down.rolling(period).mean() + 1e-9)
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def ema(series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    def position_size(self, price: float, atr: float) -> int:
        risk_capital   = self.capital * 0.01
        per_share_risk = max(atr, price * 0.005)
        qty     = int(risk_capital / per_share_risk)
        if qty < 1:
            return 0
        max_qty = int(settings.MAX_POSITION_VALUE / price)
        return min(qty, max_qty)

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        current_position_qty: int,   # >0 long, <0 short, 0 flat
        entry_price: float | None = None,
    ) -> Signal:
        raise NotImplementedError
