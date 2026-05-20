from strategies.base_strategy import BaseStrategy, Signal
import pandas as pd

class VwapMomentumStrategy(BaseStrategy):
    def generate_signal(self, symbol, df, current_position_qty, entry_price=None, **kwargs):
        vwap_band_pct = kwargs.get("vwap_band_pct", 0.5)

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
        avg_volume = volume.rolling(20).mean().iloc[-1]

        up_band = vwap_v * (1 + (vwap_band_pct / 100))
        down_band = vwap_v * (1 - (vwap_band_pct / 100))

        if price > up_band and rsi_v < 30 and volume.iloc[-1] > avg_volume * 1.2 and qty > 0:
            return Signal("BUY", qty, f"Price > VWAP+{vwap_band_pct}% | RSI < 30 | Vol surge")

        if price < down_band and rsi_v > 70 and volume.iloc[-1] > avg_volume * 1.2 and qty > 0:
            return Signal("SHORT", qty, f"Price < VWAP-{vwap_band_pct}% | RSI > 70 | Vol surge")

        return Signal("HOLD", reason="No setup")
