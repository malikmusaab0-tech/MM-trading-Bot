from strategies.base_strategy import BaseStrategy, Signal

class EmaCrossoverStrategy(BaseStrategy):
    def generate_signal(self, symbol, df, current_position_qty, entry_price=None):
        if len(df) < 26:
            return Signal("HOLD", reason="Not enough data")
        close  = df["close"]
        fast   = self.ema(close, 9).iloc[-1]
        slow   = self.ema(close, 21).iloc[-1]
        fast_p = self.ema(close, 9).iloc[-2]
        slow_p = self.ema(close, 21).iloc[-2]
        atr_v  = self.atr(df).iloc[-1]
        price  = close.iloc[-1]
        qty    = self.position_size(price, atr_v)
        crossed_up   = fast_p <= slow_p and fast > slow
        crossed_down = fast_p >= slow_p and fast < slow

        if current_position_qty > 0:
            if crossed_down:
                return Signal("SELL", current_position_qty, "EMA bearish crossover")
            return Signal("HOLD", reason="Long active")

        if current_position_qty < 0:
            if crossed_up:
                return Signal("COVER", abs(current_position_qty), "EMA bullish crossover")
            return Signal("HOLD", reason="Short active")

        if crossed_up and qty > 0:
            return Signal("BUY", qty, f"EMA bullish crossover fast={fast:.2f} slow={slow:.2f}")
        if crossed_down and qty > 0:
            return Signal("SHORT", qty, f"EMA bearish crossover fast={fast:.2f} slow={slow:.2f}")
        return Signal("HOLD", reason="No crossover")
