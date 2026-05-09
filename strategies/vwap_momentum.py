from strategies.base_strategy import BaseStrategy, Signal
import pandas as pd

class VwapMomentumStrategy(BaseStrategy):
    def generate_signal(self, symbol, df, current_position_qty, entry_price=None):
        if len(df) < 20:
            return Signal("HOLD", reason="Not enough data")
        close = df["close"]; volume = df["volume"]
        vwap  = (close * volume).cumsum() / volume.cumsum()
        atr_v = self.atr(df).iloc[-1]
        rsi_v = self.rsi(close).iloc[-1]
        price = close.iloc[-1]
        vwap_v= vwap.iloc[-1]
        qty   = self.position_size(price, atr_v)

        # ── Manage existing LONG ───────────────────────────────────────
        if current_position_qty > 0:
            if price < vwap_v or rsi_v > 70:
                return Signal("SELL", current_position_qty, "VWAP momentum faded")
            return Signal("HOLD", reason="Holding long")

        # ── Manage existing SHORT ──────────────────────────────────────
        if current_position_qty < 0:
            if price > vwap_v or rsi_v < 30:
                return Signal("COVER", abs(current_position_qty), "Short momentum faded")
            return Signal("HOLD", reason="Holding short")

        # ── No position — check entries ────────────────────────────────
        if price > vwap_v + atr_v * 0.5 and rsi_v > 55 and qty > 0:
            return Signal("BUY", qty, f"Price above VWAP+ATR | RSI {rsi_v:.1f}")
        if price < vwap_v - atr_v * 0.5 and rsi_v < 45 and qty > 0:
            return Signal("SHORT", qty, f"Price below VWAP-ATR | RSI {rsi_v:.1f}")
        return Signal("HOLD", reason="No setup")
