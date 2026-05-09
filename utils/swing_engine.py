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
from strategies.swing_trend_pullback import SwingTrendPullbackStrategy
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
        self.strategy = SwingTrendPullbackStrategy()
        self.notifier = notifier
        from utils.dhan_helper import dhan_helper
        self.dhan_helper = dhan_helper

    def fetch_daily_ohlc(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch daily OHLCV data for swing analysis using Dhan."""
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=180)  # ~6 months of history

        try:
            from utils.rate_limiter import retry_with_backoff
            sec_id = self.dhan_helper.get_security_id(symbol)
            if not sec_id:
                return pd.DataFrame()

            @retry_with_backoff(retries=3)
            def _fetch():
                return self.dhan.historical_daily_data(
                    symbol=sec_id,
                    exchange_segment='NSE_EQ',
                    instrument_type='EQUITY',
                    expiry_code=0,
                    from_date=from_dt.strftime('%Y-%m-%d'),
                    to_date=to_dt.strftime('%Y-%m-%d')
                )

            data = _fetch()

            if data and data.get('data'):
                df = pd.DataFrame(data['data'])
                # Need standardized column names
                df.rename(columns={
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'volume': 'volume',
                    'start_Time': 'timestamp'
                }, inplace=True)
                return df
            return pd.DataFrame()
        except Exception as e:
            print(f"[SWING] Error fetching daily data for {symbol}: {e}")
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
            df = self.fetch_daily_ohlc(symbol)
            if df is None or df.empty:
                print(f"[SWING] {symbol}: no data")
                continue

            signal = self.strategy.generate_signal(symbol, df)
            if not signal:
                continue

            entry = float(signal["entry"])
            stop = float(signal["stop_loss"])
            target = float(signal["target"])
            qty = self._calculate_swing_quantity(entry, stop)
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
                f"{signal['segment']} {signal['side']} {signal['symbol']}",
                f"qty={qty}",
                f"entry={entry:.2f}",
                f"sl={stop:.2f}",
                f"target={target:.2f}",
                f"timeframe={signal['timeframe']}",
                f"risk=₹{risk_value:,.2f} ({risk_pct:+.2f}%)",
                f"expP=₹{profit_value:,.2f} ({profit_pct:+.2f}%)",
            )

            # Send alert BEFORE placing order (per your requirement)
            if self.notifier is not None:
                try:
                    self.notifier.send_swing_trade_alert(
                        segment=settings.SEGMENT_SWING,
                        symbol=signal["symbol"],
                        side=signal["side"],
                        qty=qty,
                        entry=entry,
                        stop_loss=stop,
                        target=target,
                        timeframe=signal["timeframe"],
                        risk_value=risk_value,
                        risk_pct=risk_pct,
                        profit_value=profit_value,
                        profit_pct=profit_pct,
                    )
                except Exception as e:
                    print(f"[SWING] Notification error for {symbol}: {e}")

            # Place paper BUY as swing trade
            if signal["side"] == "BUY":
                trade = self.engine.buy(
                    symbol=signal["symbol"],
                    quantity=qty,
                    price=entry,
                    segment=settings.SEGMENT_SWING,
                    order_type="FOREVER", # Or OCO, to signify swing
                    stop_loss=stop,
                    take_profit=target
                )
                if trade is None:
                    print(f"[SWING] {symbol}: trade blocked by risk/margin engine")