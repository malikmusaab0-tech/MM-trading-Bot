from strategies.base_strategy import BaseStrategy, Signal

class RsiReversalStrategy(BaseStrategy):
    def generate_signal(self, symbol, df, current_position_qty, entry_price=None):
        if len(df) < 15:
            return Signal("HOLD", reason="Not enough data")
        close   = df["close"]
        rsi_now = self.rsi(close).iloc[-1]
        rsi_prv = self.rsi(close).iloc[-2]
        atr_v   = self.atr(df).iloc[-1]
        price   = close.iloc[-1]
        qty     = self.position_size(price, atr_v)

        # Widen oversold/overbought thresholds (35 and 65)
        bounce_up   = rsi_prv < 35 and rsi_now >= 35
        reject_down = rsi_prv > 65 and rsi_now <= 65

        if current_position_qty > 0:
            if rsi_now > 65:
                return Signal("SELL", current_position_qty, f"RSI overbought {rsi_now:.1f}")
            return Signal("HOLD", reason="Long active")

        if current_position_qty < 0:
            if rsi_now < 35:
                return Signal("COVER", abs(current_position_qty), f"RSI oversold {rsi_now:.1f}")
            return Signal("HOLD", reason="Short active")

        if bounce_up and qty > 0:
            return Signal("BUY", qty, f"RSI bounced from oversold {rsi_now:.1f}")
        if reject_down and qty > 0:
            return Signal("SHORT", qty, f"RSI rejected from overbought {rsi_now:.1f}")
        return Signal("HOLD", reason="No RSI extreme")
