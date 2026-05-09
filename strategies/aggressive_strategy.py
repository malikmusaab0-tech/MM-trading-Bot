"""
AGGRESSIVE VWAP Strategy - Trades More Frequently
Use this for testing to see trades happening
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from config import settings


@dataclass
class Signal:
    action: str         # "BUY", "SELL", "HOLD"
    quantity: int = 0
    reason: str = ""


class AggressiveVwapStrategy:
    """More aggressive VWAP strategy that trades more often"""
    
    def __init__(self, capital: float):
        self.capital = capital
        print("⚡ AGGRESSIVE VWAP STRATEGY LOADED (trades more frequently)")

    @staticmethod
    def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # VWAP
        tp = (df["high"] + df["low"] + df["close"]) / 3.0
        vwap = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
        df["vwap"] = vwap

        # Bollinger (20)
        window = 20
        ma = df["close"].rolling(window=window).mean()
        std = df["close"].rolling(window=window).std()
        df["bb_mid"] = ma
        df["bb_upper"] = ma + 2 * std
        df["bb_lower"] = ma - 2 * std

        # RSI (14)
        delta = df["close"].diff()
        up = np.where(delta > 0, delta, 0.0)
        down = np.where(delta < 0, -delta, 0.0)
        roll_up = pd.Series(up).rolling(14).mean()
        roll_down = pd.Series(down).rolling(14).mean()
        rs = roll_up / (roll_down + 1e-9)
        df["rsi"] = 100.0 - (100.0 / (1.0 + rs))

        # ATR (14)
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14).mean()

        # Volume average
        df["vol_ma"] = df["volume"].rolling(20).mean()

        return df

    def _position_size(self, price: float, atr: float) -> int:
        # Risk ~1% of capital per trade
        risk_capital = self.capital * 0.01
        per_share_risk = max(atr, price * 0.005)
        qty = int(risk_capital / per_share_risk)
        if qty <= 0:
            return 1  # At least 1 share
        max_qty = int(settings.MAX_POSITION_VALUE / price)
        return min(qty, max(1, max_qty))

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        current_position_qty: int,
        entry_price: float | None,
    ) -> Signal:
        if df.empty or len(df) < 25:  # Reduced from 30
            return Signal(action="HOLD", reason="not_enough_data")

        df = self._compute_indicators(df)
        row = df.iloc[-1]

        price = row["close"]
        vwap = row["vwap"]
        bb_lower = row["bb_lower"]
        bb_upper = row["bb_upper"]
        bb_mid = row["bb_mid"]
        rsi = row["rsi"]
        atr = row["atr"]
        vol = row["volume"]
        vol_ma = row["vol_ma"]

        if np.isnan([vwap, bb_lower, bb_upper, rsi, atr, vol_ma]).any():
            return Signal(action="HOLD", reason="indicators_not_ready")

        # AGGRESSIVE ENTRY - More conditions will trigger
        if current_position_qty == 0:
            # RELAXED CONDITIONS - easier to enter
            
            # Option 1: Price > VWAP and RSI oversold (RELAXED from 20-40 to 20-50)
            if price > vwap and 20 <= rsi <= 50:
                qty = self._position_size(price, atr)
                if qty > 0:
                    return Signal(
                        action="BUY",
                        quantity=qty,
                        reason=f"AGGRESSIVE: Price>{vwap:.2f}, RSI={rsi:.1f}",
                    )
            
            # Option 2: Price near lower BB (RELAXED from 1% to 5%)
            if price <= bb_lower * 1.05:  # Within 5% of lower BB
                qty = self._position_size(price, atr)
                if qty > 0:
                    return Signal(
                        action="BUY",
                        quantity=qty,
                        reason=f"AGGRESSIVE: Near BB lower={bb_lower:.2f}",
                    )
            
            # Option 3: Simple volume surge (RELAXED from 1.5x to 1.2x)
            if vol > vol_ma * 1.2:  # Just 20% above average
                qty = self._position_size(price, atr)
                if qty > 0:
                    return Signal(
                        action="BUY",
                        quantity=qty,
                        reason=f"AGGRESSIVE: Volume surge {vol/vol_ma:.1f}x",
                    )
            
            # Option 4: Price pullback to VWAP (NEW - will trigger often)
            if 0.98 <= (price / vwap) <= 1.02:  # Price within 2% of VWAP
                qty = self._position_size(price, atr)
                if qty > 0:
                    return Signal(
                        action="BUY",
                        quantity=qty,
                        reason=f"AGGRESSIVE: Price at VWAP={vwap:.2f}",
                    )
            
            return Signal(action="HOLD", reason=f"Waiting: P={price:.2f}, VWAP={vwap:.2f}, RSI={rsi:.1f}")

        # Exit logic (same as before)
        if entry_price is None:
            return Signal(action="HOLD", reason="no_entry_price")

        tp_price = entry_price + settings.TAKE_PROFIT_ATR_MULTIPLIER * atr
        sl_price = entry_price - settings.STOP_LOSS_ATR_MULTIPLIER * atr

        if price >= tp_price:
            return Signal(action="SELL", quantity=current_position_qty, reason="take_profit")
        if price <= sl_price:
            return Signal(action="SELL", quantity=current_position_qty, reason="stop_loss")
        if price < vwap * 0.98:  # 2% below VWAP
            return Signal(action="SELL", quantity=current_position_qty, reason="lost_trend")

        return Signal(action="HOLD", reason="holding_trend")
