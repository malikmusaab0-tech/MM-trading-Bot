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
        near_lower = price <= lower.iloc[-1] * 1.005
        near_upper = price >= upper.iloc[-1] * 0.995

        if current_position_qty > 0:
            if price >= sma.iloc[-1]:
                return Signal("SELL", current_position_qty, "Price reverted to mean")
            return Signal("HOLD", reason="Long active")

        if current_position_qty < 0:
            if price <= sma.iloc[-1]:
                return Signal("COVER", abs(current_position_qty), "Price reverted to mean")
            return Signal("HOLD", reason="Short active")

        if near_lower and rsi_v < 35 and qty > 0:
            return Signal("BUY", qty, f"Near lower BB | RSI {rsi_v:.1f}")
        if near_upper and rsi_v > 65 and qty > 0:
            return Signal("SHORT", qty, f"Near upper BB | RSI {rsi_v:.1f}")
        return Signal("HOLD", reason="No BB setup")
