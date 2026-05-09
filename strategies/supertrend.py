from strategies.base_strategy import BaseStrategy, Signal
import pandas as pd

class SupertrendStrategy(BaseStrategy):
    def _supertrend(self, df, period=10, multiplier=3.0):
        atr    = self.atr(df, period)
        hl2    = (df["high"] + df["low"]) / 2
        upper  = hl2 + multiplier * atr
        lower  = hl2 - multiplier * atr
        close  = df["close"]
        st     = pd.Series(index=df.index, dtype=float)
        trend  = pd.Series(1, index=df.index)
        for i in range(1, len(df)):
            if close.iloc[i] > upper.iloc[i - 1]:
                trend.iloc[i] = 1
            elif close.iloc[i] < lower.iloc[i - 1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i - 1]
        return trend

    def generate_signal(self, symbol, df, current_position_qty, entry_price=None):
        if len(df) < 15:
            return Signal("HOLD", reason="Not enough data")
        trend  = self._supertrend(df)
        t_now  = trend.iloc[-1]
        t_prev = trend.iloc[-2]
        price  = df["close"].iloc[-1]
        atr_v  = self.atr(df).iloc[-1]
        qty    = self.position_size(price, atr_v)
        flipped_bull = t_prev == -1 and t_now == 1
        flipped_bear = t_prev ==  1 and t_now == -1

        if current_position_qty > 0:
            if flipped_bear:
                return Signal("SELL", current_position_qty, "Supertrend flipped bearish")
            return Signal("HOLD", reason="Long active")

        if current_position_qty < 0:
            if flipped_bull:
                return Signal("COVER", abs(current_position_qty), "Supertrend flipped bullish")
            return Signal("HOLD", reason="Short active")

        if flipped_bull and qty > 0:
            return Signal("BUY", qty, "Supertrend bullish flip")
        if flipped_bear and qty > 0:
            return Signal("SHORT", qty, "Supertrend bearish flip")
        return Signal("HOLD", reason="No flip")
