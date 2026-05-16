from strategies.base_strategy import BaseStrategy, Signal

class BollingerReversalStrategy(BaseStrategy):
    def generate_signal(self, symbol, df, current_position_qty, entry_price=None):
        if len(df) < 20:
            return Signal("HOLD", reason="Not enough data")
        close  = df["close"]
        sma    = close.rolling(20).mean()
        std    = close.rolling(20).std()
        upper  = sma + 2 * std
        lower  = sma - 2 * std
        price  = close.iloc[-1]
        rsi_v  = self.rsi(close).iloc[-1]
        atr_v  = self.atr(df).iloc[-1]
        qty    = self.position_size(price, atr_v)

        # Lower BB bandwidth requirement (e.g. min 0.02 to allow smaller compressions)
        bandwidth = (upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1]
        if bandwidth < 0.02:
            return Signal("HOLD", reason="BB bandwidth < 0.02 (too tight)")

        # Allow signals when price is within 1.5x ATR of the band
        near_lower = price <= lower.iloc[-1] + (atr_v * 1.5)
        near_upper = price >= upper.iloc[-1] - (atr_v * 1.5)

        if current_position_qty > 0:
            if price >= sma.iloc[-1]:
                return Signal("SELL", current_position_qty, "Price reverted to mean")
            return Signal("HOLD", reason="Long active")

        if current_position_qty < 0:
            if price <= sma.iloc[-1]:
                return Signal("COVER", abs(current_position_qty), "Price reverted to mean")
            return Signal("HOLD", reason="Short active")

        # Accept RSI in range 25-75 instead of 20-80 as the reversal zone
        if near_lower and rsi_v < 75 and qty > 0:
            return Signal("BUY", qty, f"Near lower BB | RSI {rsi_v:.1f}")
        if near_upper and rsi_v > 25 and qty > 0:
            return Signal("SHORT", qty, f"Near upper BB | RSI {rsi_v:.1f}")

        return Signal("HOLD", reason="No BB setup")
