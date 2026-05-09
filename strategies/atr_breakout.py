from strategies.base_strategy import BaseStrategy, Signal

class AtrBreakoutStrategy(BaseStrategy):
    def generate_signal(self, symbol, df, current_position_qty, entry_price=None):
        if len(df) < 12:
            return Signal("HOLD", reason="Not enough data")
        close  = df["close"]
        high   = df["high"]
        low    = df["low"]
        atr_v  = self.atr(df).iloc[-1]
        price  = close.iloc[-1]
        hi10   = high.iloc[-11:-1].max()
        lo10   = low.iloc[-11:-1].min()
        qty    = self.position_size(price, atr_v)
        break_up   = price > hi10 + atr_v * 0.2
        break_down = price < lo10 - atr_v * 0.2

        if current_position_qty > 0:
            if price < hi10 - atr_v:
                return Signal("SELL", current_position_qty, "ATR breakout pulled back")
            return Signal("HOLD", reason="Long active")

        if current_position_qty < 0:
            if price > lo10 + atr_v:
                return Signal("COVER", abs(current_position_qty), "ATR breakdown recovered")
            return Signal("HOLD", reason="Short active")

        if break_up and qty > 0:
            return Signal("BUY", qty, f"ATR breakout above 10-bar high {hi10:.2f}")
        if break_down and qty > 0:
            return Signal("SHORT", qty, f"ATR breakdown below 10-bar low {lo10:.2f}")
        return Signal("HOLD", reason="No ATR breakout")
