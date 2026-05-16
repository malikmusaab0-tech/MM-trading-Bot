from strategies.base_strategy import BaseStrategy, Signal

class RsiReversalStrategy(BaseStrategy):
    def generate_signal(self, symbol, df, current_position_qty, entry_price=None, **kwargs):
        rsi_oversold = kwargs.get("rsi_oversold", 35)
        rsi_overbought = kwargs.get("rsi_overbought", 65)

        if len(df) < 15:
            return Signal("HOLD", reason="Not enough data")
        close   = df["close"]
        rsi_now = self.rsi(close).iloc[-1]
        rsi_prv = self.rsi(close).iloc[-2]
        atr_v   = self.atr(df).iloc[-1]
        price   = close.iloc[-1]
        qty     = self.position_size(price, atr_v)

        bounce_up   = rsi_prv < rsi_oversold and rsi_now >= rsi_oversold
        reject_down = rsi_prv > rsi_overbought and rsi_now <= rsi_overbought

        if current_position_qty > 0:
            if rsi_now > rsi_overbought:
                return Signal("SELL", current_position_qty, f"RSI overbought {rsi_now:.1f}")
            return Signal("HOLD", reason="Long active")

        if current_position_qty < 0:
            if rsi_now < rsi_oversold:
                return Signal("COVER", abs(current_position_qty), f"RSI oversold {rsi_now:.1f}")
            return Signal("HOLD", reason="Short active")

        if bounce_up and qty > 0:
            return Signal("BUY", qty, f"RSI bounced from oversold {rsi_now:.1f}")
        if reject_down and qty > 0:
            return Signal("SHORT", qty, f"RSI rejected from overbought {rsi_now:.1f}")
        return Signal("HOLD", reason="No RSI extreme")
