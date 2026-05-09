from strategies.base_strategy import BaseStrategy, Signal

class MacdMomentumStrategy(BaseStrategy):
    def generate_signal(self, symbol, df, current_position_qty, entry_price=None):
        if len(df) < 26:
            return Signal("HOLD", reason="Not enough data")
        close    = df["close"]
        macd     = self.ema(close, 12) - self.ema(close, 26)
        signal   = self.ema(macd, 9)
        hist     = macd - signal
        h_now    = hist.iloc[-1]
        h_prev   = hist.iloc[-2]
        atr_v    = self.atr(df).iloc[-1]
        price    = close.iloc[-1]
        qty      = self.position_size(price, atr_v)
        bull_cross = h_prev <= 0 < h_now
        bear_cross = h_prev >= 0 > h_now

        if current_position_qty > 0:
            if bear_cross or h_now < 0:
                return Signal("SELL", current_position_qty, "MACD histogram turned negative")
            return Signal("HOLD", reason="Long active")

        if current_position_qty < 0:
            if bull_cross or h_now > 0:
                return Signal("COVER", abs(current_position_qty), "MACD histogram turned positive")
            return Signal("HOLD", reason="Short active")

        if bull_cross and h_now > 0 and qty > 0:
            return Signal("BUY", qty, f"MACD bullish cross hist={h_now:.2f}")
        if bear_cross and h_now < 0 and qty > 0:
            return Signal("SHORT", qty, f"MACD bearish cross hist={h_now:.2f}")
        return Signal("HOLD", reason="No MACD cross")
