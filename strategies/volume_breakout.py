from strategies.base_strategy import BaseStrategy, Signal

class VolumeBreakoutStrategy(BaseStrategy):
    def generate_signal(self, symbol, df, current_position_qty, entry_price=None):
        if len(df) < 21:
            return Signal("HOLD", reason="Not enough data")
        close   = df["close"]
        volume  = df["volume"]
        high    = df["high"]
        low     = df["low"]
        price   = close.iloc[-1]
        vol_now = volume.iloc[-1]
        vol_avg = volume.rolling(20).mean().iloc[-1]
        res_level = high.iloc[-21:-1].max()
        sup_level = low.iloc[-21:-1].min()
        atr_v   = self.atr(df).iloc[-1]
        qty     = self.position_size(price, atr_v)
        vol_surge = vol_now > vol_avg * 1.5
        break_up   = price > res_level and vol_surge
        break_down = price < sup_level and vol_surge

        if current_position_qty > 0:
            if price < res_level * 0.98:
                return Signal("SELL", current_position_qty, "Breakout failed / pullback")
            return Signal("HOLD", reason="Long active")

        if current_position_qty < 0:
            if price > sup_level * 1.02:
                return Signal("COVER", abs(current_position_qty), "Breakdown failed / bounce")
            return Signal("HOLD", reason="Short active")

        if break_up and qty > 0:
            return Signal("BUY", qty, f"Volume breakout above {res_level:.2f}")
        if break_down and qty > 0:
            return Signal("SHORT", qty, f"Volume breakdown below {sup_level:.2f}")
        return Signal("HOLD", reason="No volume breakout")
