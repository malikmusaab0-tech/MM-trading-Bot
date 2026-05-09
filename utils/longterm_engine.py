from math import floor
from typing import Dict, Optional, List

from config import settings
from data.database import get_session, Position, Fundamentals, LongTermIdea
from strategies.longterm_quality_value import LongTermQualityValueStrategy
from utils.paper_trading import PaperTradingEngine
from utils.notification_service import NotificationService


class LongTermEngine:
    def __init__(
        self,
        trading_engine: PaperTradingEngine,
        symbols: Optional[List[str]] = None,
        notifier: Optional[NotificationService] = None,
    ):
        self.engine = trading_engine
        self.symbols = symbols or settings.LONGTERM_WATCHLIST
        self.strategy = LongTermQualityValueStrategy()
        self.notifier = notifier

    # ------------------------------------------------------------------ #
    # Fundamentals loader: from DB 'fundamentals' table, not CSV
    # ------------------------------------------------------------------ #
    def _load_fundamentals(self) -> Dict[str, Dict[str, float]]:
        """
        Returns:
            { 'RELIANCE': { 'current_price': ..., 'fair_value': ... , ... }, ... }

        fair_value is taken from Fundamentals.fv_composite.
        """
        records: Dict[str, Dict[str, float]] = {}
        with get_session() as session:
            rows = (
                session.query(Fundamentals)
                .filter(Fundamentals.symbol.in_(self.symbols))
                .all()
            )
            for r in rows:
                if not r.current_price or not r.fv_composite:
                    continue
                sym = r.symbol.upper()
                records[sym] = {
                    "current_price": r.current_price,
                    "fair_value": r.fv_composite,
                    "pe": r.pe,
                    "pb": r.pb,
                    "roe": r.roe,
                    "debt_to_equity": r.debt_to_equity,
                }
        return records

    # ------------------------------------------------------------------ #
    # Position sizing
    # ------------------------------------------------------------------ #
    def _calculate_quantity(self, entry: float, fair_value: float) -> int:
        # Risk bucket for LT
        risk_capital = settings.INITIAL_CAPITAL * (
            settings.LONGTERM_MAX_RISK_PER_TRADE_PCT / 100.0
        )
        if entry <= 0:
            return 0

        # Simple: up to 5x that risk bucket as notional
        notional = risk_capital * 5
        qty = floor(notional / entry)

        if qty * entry < settings.MIN_POSITION_SIZE:
            return 0
        if qty * entry > settings.MAX_POSITION_VALUE:
            qty = floor(settings.MAX_POSITION_VALUE / entry)

        return max(qty, 0)

    def _get_position_qty(self, symbol: str) -> int:
        with get_session() as session:
            pos = (
                session.query(Position)
                .filter(Position.symbol == symbol)
                .one_or_none()
            )
            return pos.quantity if pos else 0

    # ------------------------------------------------------------------ #
    # Main review: create LongTermIdea rows, do NOT execute trades
    # ------------------------------------------------------------------ #
    def run_once(self):
        if not settings.LONGTERM_ENABLED:
            print("[LT] Disabled via settings.LONGTERM_ENABLED = False")
            return

        fundamentals = self._load_fundamentals()
        if not fundamentals:
            print("[LT] No fundamentals loaded.")
            return

        print("[LT] Running long-term review...")
        for symbol in self.symbols:
            sym = symbol.upper()
            if sym not in fundamentals:
                print(f"[LT] {sym}: no fundamentals row")
                continue

            f = fundamentals[sym]
            signal = self.strategy.generate_signal(sym, f)
            if not signal:
                continue

            action = signal["action"]
            fv = signal["fair_value"]
            mos = signal["margin_of_safety_pct"]
            reason = signal["reason"]
            timeframe = signal["timeframe"]
            price = float(f["current_price"])

            print(
                f"[LT] {sym}: {action} | FV={fv:.2f} MOS={mos:.1f}% | {reason}"
            )

            # HOLD is informational only
            if action == "HOLD":
                continue

            # ---------------------- BUY IDEA ---------------------------
            if action == "BUY":
                qty = self._calculate_quantity(entry=price, fair_value=fv)
                if qty <= 0:
                    print(f"[LT] {sym}: BUY idea but qty=0 (limits too tight)")
                    continue

                # For now, target = fair value; we can push higher for true multibaggers later
                target_price = fv
                upside_pct = (target_price - price) / price * 100.0
                multibagger_score = upside_pct  # simple ranking metric

                with get_session() as session:
                    idea = LongTermIdea(
                        symbol=sym,
                        action="BUY",
                        qty=qty,
                        entry_price=price,
                        target_price=target_price,
                        fair_value=fv,
                        margin_of_safety_pct=mos,
                        upside_pct=upside_pct,
                        multibagger_score=multibagger_score,
                        approved=False,
                        executed=False,
                        reason=reason,
                    )
                    session.add(idea)
                    session.flush()
                    idea_id = idea.id

                print(
                    f"[LT] Idea #{idea_id}: BUY {sym} x{qty} @ ₹{price:.2f}, "
                    f"target ₹{target_price:.2f} (upside {upside_pct:.1f}%)"
                )

                # Notify you, do not execute
                if self.notifier is not None:
                    try:
                        profit_value = (target_price - price) * qty
                        profit_pct = upside_pct
                        self.notifier.send_longterm_trade_alert(
                            symbol=sym,
                            action="BUY",
                            qty=qty,
                            entry=price,
                            fair_value=fv,
                            timeframe=timeframe,
                            margin_of_safety_pct=mos,
                            risk_value=0.0,
                            risk_pct=0.0,
                            profit_value=profit_value,
                            profit_pct=profit_pct,
                        )
                        self.notifier.send_text(
                            f"LT Idea #{idea_id}: BUY {sym} x{qty} @ ₹{price:.2f}, "
                            f"target ₹{target_price:.2f} (upside {upside_pct:.1f}%). "
                            f"Approve in dashboard/CLI to execute."
                        )
                    except Exception as e:
                        print(f"[LT] Notification error for {sym}: {e}")

            # ---------------------- SELL IDEA --------------------------
            elif action == "SELL":
                current_qty = self._get_position_qty(sym)
                if current_qty <= 0:
                    print(f"[LT] {sym}: SELL idea but no position to close")
                    continue

                with get_session() as session:
                    idea = LongTermIdea(
                        symbol=sym,
                        action="SELL",
                        qty=current_qty,
                        entry_price=price,
                        target_price=price,  # sell around current price
                        fair_value=fv,
                        margin_of_safety_pct=mos,
                        upside_pct=0.0,
                        multibagger_score=0.0,
                        approved=False,
                        executed=False,
                        reason=reason,
                    )
                    session.add(idea)
                    session.flush()
                    idea_id = idea.id

                print(
                    f"[LT] Idea #{idea_id}: SELL {sym} x{current_qty} "
                    f"@ around ₹{price:.2f}"
                )

                if self.notifier is not None:
                    try:
                        self.notifier.send_text(
                            f"LT Idea #{idea_id}: SELL {sym} x{current_qty} "
                            f"@ around ₹{price:.2f}. Approve to execute."
                        )
                    except Exception as e:
                        print(f"[LT] Notification error for {sym}: {e}")