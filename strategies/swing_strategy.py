import pandas as pd
from strategies.base_strategy import BaseStrategy, Signal
import logging

logger = logging.getLogger(__name__)

class SwingStrategy(BaseStrategy):
    """
    Institutional Swing Engine (PRI-18)
    - Setup: Parse daily and weekly candle sets.
    - Gating Rule: Execute entries only if the Macro Nifty Index is TRENDING or NEUTRAL.
    - Entry Logic: Price crosses above 20 EMA, Daily RSI > 50 and rising over a 3-day window, Weekly RSI > 45.
    - Risk Profile: Trailing stop-loss 2.5x ATR, target 5.0x ATR.
    """

    def generate_signal(self, symbol, df_daily: pd.DataFrame, current_position_qty, df_weekly: pd.DataFrame = None, macro_regime: str = "NEUTRAL", entry_price=None, **kwargs):
        if len(df_daily) < 20 or (df_weekly is not None and len(df_weekly) < 14):
            return Signal("HOLD", reason="Not enough data")

        # Gating Rule
        if macro_regime not in ["TRENDING", "NEUTRAL"]:
            return Signal("HOLD", reason=f"Macro regime is {macro_regime}, skipping entry")

        close = df_daily["close"]
        price = close.iloc[-1]
        atr_v = self.atr(df_daily).iloc[-1]
        qty = self.position_size(price, atr_v)

        # Calculate indicators
        ema_20 = close.ewm(span=20, adjust=False).mean()
        rsi_daily = self.rsi(close)

        # Cross above 20 EMA
        crossed_above_ema = close.iloc[-2] <= ema_20.iloc[-2] and close.iloc[-1] > ema_20.iloc[-1]

        # Daily RSI > 50 and rising over 3-day window
        rsi_d_now = rsi_daily.iloc[-1]
        rsi_d_3_days_ago = rsi_daily.iloc[-4] if len(rsi_daily) >= 4 else rsi_daily.iloc[0]
        rsi_daily_rising = rsi_d_now > 50 and rsi_d_now > rsi_d_3_days_ago

        # Weekly RSI > 45
        weekly_rsi_ok = True
        if df_weekly is not None:
            rsi_weekly = self.rsi(df_weekly["close"])
            if rsi_weekly.iloc[-1] <= 45:
                weekly_rsi_ok = False

        if current_position_qty > 0:
            return Signal("HOLD", reason="Swing Long Active (Trailing stop handled by risk manager)")

        if current_position_qty < 0:
            return Signal("HOLD", reason="Swing Short Active (Trailing stop handled by risk manager)")

        if crossed_above_ema and rsi_daily_rising and weekly_rsi_ok and qty > 0:
            return Signal("BUY", qty, "Crossed 20 EMA with positive RSI momentum")

        return Signal("HOLD", reason="No Swing Setup")
