"""
SwingEngine: runs swing strategies on daily data and produces trade ideas,
then places paper trades via PaperTradingEngine (segment=SWING) and
sends Telegram alerts via NotificationService.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from math import floor

import pandas as pd
from dhanhq import dhanhq

from config import settings
from strategies.swing_strategy import SwingStrategy
from utils.paper_trading import PaperTradingEngine
from utils.notification_service import NotificationService


class SwingEngine:
    def __init__(
        self,
        dhan: dhanhq,
        trading_engine: PaperTradingEngine,
        symbols: List[str],
        notifier: Optional[NotificationService] = None,
    ):
        """
        Parameters
        ----------
        dhan : dhanhq
            Authenticated dhan client.
        trading_engine : PaperTradingEngine
            Shared paper trading engine instance (uses common cash ledger).
        symbols : list[str]
            Universe of symbols to scan for swing opportunities.
        notifier : NotificationService or None
            For sending pre-trade alerts (Telegram, later WhatsApp).
        """
        self.dhan = dhan
        self.engine = trading_engine
        self.symbols = symbols
        self.strategy = SwingStrategy()
        self.notifier = notifier
        from utils.dhan_helper import dhan_helper
        self.dhan_helper = dhan_helper

    def fetch_daily_ohlc(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch daily OHLCV data for swing analysis using Redis Lists warmed up previously."""
        import redis
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)

        try:
            closes = r.lrange(f"historical:daily:{symbol}:close", 0, -1)
            volumes = r.lrange(f"historical:daily:{symbol}:volume", 0, -1)

            if closes and volumes:
                highs = r.lrange(f"historical:daily:{symbol}:high", 0, -1)
                lows = r.lrange(f"historical:daily:{symbol}:low", 0, -1)

                # fallback to closes if high/low missing
                if not highs: highs = closes
                if not lows: lows = closes

                df = pd.DataFrame({
                    "close": pd.to_numeric(closes),
                    "volume": pd.to_numeric(volumes),
                    "high": pd.to_numeric(highs),
                    "low": pd.to_numeric(lows),
                })
                return df

            return pd.DataFrame()
        except Exception as e:
            print(f"[SWING] Error reading daily data for {symbol} from Redis: {e}")
            return None

    def _calculate_swing_quantity(self, entry: float, stop: float) -> int:
        """
        Risk-based position sizing using SWING_MAX_RISK_PER_TRADE_PCT
        and global MIN_POSITION_SIZE / MAX_POSITION_VALUE.
        """
        risk_capital = settings.INITIAL_CAPITAL * (
            settings.SWING_MAX_RISK_PER_TRADE_PCT / 100.0
        )
        risk_per_share = entry - stop
        if risk_per_share <= 0:
            return 0

        qty = floor(risk_capital / risk_per_share)
        if qty <= 0:
            return 0

        notional = qty * entry
        if notional < settings.MIN_POSITION_SIZE:
            return 0

        if notional > settings.MAX_POSITION_VALUE:
            qty_cap = floor(settings.MAX_POSITION_VALUE / entry)
            qty = max(qty_cap, 0)

        return qty

    def run_once(self):
        """
        Run a single swing scan for all configured symbols.

        Steps:
        - Fetch daily OHLCV.
        - Generate signal.
        - Compute qty based on risk.
        - Send Telegram alert with expected profit & risk.
        - Place paper BUY order via PaperTradingEngine with segment=SWING.
        """
        if not settings.SWING_ENABLED:
            print("[SWING] Disabled via settings.SWING_ENABLED = False")
            return

        print("[SWING] Running swing scan...")
        for symbol in self.symbols:
            df_daily = self.fetch_daily_ohlc(symbol)
            if df_daily is None or df_daily.empty:
                print(f"[SWING] {symbol}: no daily data")
                continue

            # In a full implementation, you'd fetch weekly data too.
            # We pass df_daily downsampled as a quick mock, but strategy handles df_weekly=None safely.
            df_weekly = df_daily.resample('W').last() if not df_daily.index.empty and isinstance(df_daily.index, pd.DatetimeIndex) else None

            from ml.regime_classifier import classifier
            # Here we need macro regime. We use NIFTY's regime.
            # For brevity in this fix, we'll assume it's set by main loop or default to NEUTRAL
            macro_regime = "NEUTRAL"
            if classifier.current_regime_info:
                # Map GMM label to macro string
                label = classifier.current_regime_info.get("label", "").upper()
                if "TREND" in label or "MOMENTUM" in label:
                    macro_regime = "TRENDING"

            signal = self.strategy.generate_signal(symbol, df_daily, current_position_qty=0, df_weekly=df_weekly, macro_regime=macro_regime)

            if not signal or signal.action == "HOLD":
                continue

            entry = df_daily["close"].iloc[-1]
            atr = self.strategy.atr(df_daily).iloc[-1]
            stop = entry - (atr * 2.5)
            target = entry + (atr * 5.0)

            qty = signal.quantity if signal.quantity else self._calculate_swing_quantity(entry, stop)
            if qty <= 0:
                print(f"[SWING] {symbol}: signal found but size=0 (risk too small/large)")
                continue

            # Compute risk & expected profit in ₹ and % of capital
            risk_value = (entry - stop) * qty
            risk_pct = (risk_value / settings.INITIAL_CAPITAL) * 100.0

            profit_value = (target - entry) * qty
            profit_pct = (profit_value / settings.INITIAL_CAPITAL) * 100.0

            print(
                "[SWING] Executing:",
                f"{settings.SEGMENT_SWING} {signal.action} {symbol}",
                f"qty={qty}",
                f"entry={entry:.2f}",
                f"sl={stop:.2f}",
                f"target={target:.2f}",
                f"timeframe=Daily",
                f"risk=₹{risk_value:,.2f} ({risk_pct:+.2f}%)",
                f"expP=₹{profit_value:,.2f} ({profit_pct:+.2f}%)",
            )
            print(f"[SWING] ACTION REQUIRED: MTF Pledge authorization needed for {symbol}.")

            # Send alert BEFORE placing order (per your requirement)
            if self.notifier is not None:
                try:
                    self.notifier.send_swing_trade_alert(
                        segment=settings.SEGMENT_SWING,
                        symbol=symbol,
                        side=signal.action,
                        qty=qty,
                        entry=entry,
                        stop_loss=stop,
                        target=target,
                        timeframe="Daily",
                        risk_value=risk_value,
                        risk_pct=risk_pct,
                        profit_value=profit_value,
                        profit_pct=profit_pct,
                    )
                except Exception as e:
                    print(f"[SWING] Notification error for {symbol}: {e}")

            # Place paper BUY as swing trade
            if signal.action == "BUY":
                trade = self.engine.buy(
                    symbol=symbol,
                    quantity=qty,
                    price=entry,
                    segment=settings.SEGMENT_SWING,
                    order_type="FOREVER", # Or OCO, to signify swing
                    stop_loss=stop,
                    take_profit=target,
                    product_type="MTF"
                )
                if trade is None:
                    print(f"[SWING] {symbol}: trade blocked by risk/margin engine")