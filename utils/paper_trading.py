from datetime import datetime
from config import settings
from data.database import get_session, Trade, Position, PortfolioSnapshot


class PaperTradingEngine:
    """
    Paper trading engine with MIS intraday margin support.
    - cash = actual capital (e.g. Rs 1,00,000)
    - MIS limit = cash x INTRADAY_MARGIN_MULTIPLIER
    - dhan: optional dhanhq instance for live LTP in dashboard.
    """

    def __init__(self, dhan=None):
        self.dhan = dhan
        self.cash = float(settings.INITIAL_CAPITAL)
        self._load_existing_state()

    def _load_existing_state(self):
        with get_session() as session:
            snap = (
                session.query(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.desc())
                .first()
            )
            if snap:
                self.cash = float(snap.cash)

    def _get_pos(self, session, symbol):
        # Single position row per symbol for now (shared across segments)
        return session.query(Position).filter(Position.symbol == symbol).one_or_none()

    def _total_exposure(self, session):
        rows = session.query(Position).filter(Position.quantity != 0).all()
        return sum(abs(p.quantity) * p.avg_price for p in rows)

    def _can_open(self, trade_value, session):
        open_count = session.query(Position).filter(Position.quantity != 0).count()
        if open_count >= settings.MAX_CONCURRENT_POSITIONS:
            print(
                f"[RISK] Block: open={open_count} >= "
                f"MAX={settings.MAX_CONCURRENT_POSITIONS}"
            )
            return False
        if trade_value > settings.MAX_POSITION_VALUE:
            print(
                f"[RISK] Block: trade_value {trade_value:,.0f} > "
                f"MAX_POSITION_VALUE {settings.MAX_POSITION_VALUE:,.0f}"
            )
            return False
        mis_limit = self.cash * settings.INTRADAY_MARGIN_MULTIPLIER
        exposure_after = self._total_exposure(session) + trade_value
        if exposure_after > mis_limit:
            print(
                f"[RISK] Block: exposure {exposure_after:,.0f} > "
                f"MIS limit {mis_limit:,.0f}"
            )
            return False
        return True

    # ------------------------------------------------------------------ #
    # NOTE: segment is optional; defaults to INTRADAY if not provided.
    # Swing/long-term will pass SEGMENT_SWING / SEGMENT_LONGTERM explicitly.
    # ------------------------------------------------------------------ #

    def buy(self, symbol, quantity, price, segment=None, order_type="REGULAR", stop_loss=None, take_profit=None):
        seg = segment or settings.SEGMENT_INTRADAY
        trade_value = quantity * price
        with get_session() as session:
            if not self._can_open(trade_value, session):
                return None
            pos = self._get_pos(session, symbol)
            if pos is None:
                pos = Position(
                    symbol=symbol,
                    quantity=0,
                    avg_price=0.0,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0,
                    segment=seg,
                )
                session.add(pos)
                session.flush()
            # If an existing position exists, keep its segment (we don't try to
            # hold intraday + swing in the same symbol simultaneously).
            if pos.segment is None:
                pos.segment = seg

            if pos.quantity < 0:
                print(f"[SKIP] {symbol} already SHORT — cannot BUY")
                return None
            total_qty = pos.quantity + quantity
            pos.avg_price = ((pos.avg_price * pos.quantity) + trade_value) / total_qty
            pos.quantity = total_qty
            self.cash -= trade_value
            trade = Trade(
                symbol=symbol,
                side="BUY",
                quantity=quantity,
                price=price,
                pnl=0.0,
                paper=True,
                timestamp=datetime.utcnow(),
                segment=seg,
                order_type=order_type,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            session.add(trade)
            session.add(
                PortfolioSnapshot(
                    timestamp=datetime.utcnow(),
                    equity=self.cash,
                    cash=self.cash,
                )
            )
            print(
                f"[ENGINE] BUY {symbol} x{quantity} @ {price:.2f} | "
                f"seg={seg} | cash={self.cash:,.2f}"
            )
            return trade

    def sell(self, symbol, quantity, price, segment=None, order_type="REGULAR"):
        seg = segment or settings.SEGMENT_INTRADAY
        with get_session() as session:
            pos = self._get_pos(session, symbol)
            if pos is None or pos.quantity <= 0:
                return None
            qty = min(quantity, pos.quantity)
            pnl = (price - pos.avg_price) * qty
            pos.quantity -= qty
            if pos.quantity == 0:
                pos.avg_price = 0.0
            pos.realized_pnl = (pos.realized_pnl or 0.0) + pnl
            self.cash += qty * price
            trade = Trade(
                symbol=symbol,
                side="SELL",
                quantity=qty,
                price=price,
                pnl=pnl,
                paper=True,
                timestamp=datetime.utcnow(),
                segment=seg,
                order_type=order_type,
            )
            session.add(trade)
            session.add(
                PortfolioSnapshot(
                    timestamp=datetime.utcnow(),
                    equity=self.cash,
                    cash=self.cash,
                )
            )
            print(
                f"[ENGINE] SELL {symbol} x{qty} @ {price:.2f} | "
                f"seg={seg} | P&L={pnl:+.2f} | cash={self.cash:,.2f}"
            )
            return trade

    def short(self, symbol, quantity, price, segment=None, order_type="REGULAR", stop_loss=None, take_profit=None):
        seg = segment or settings.SEGMENT_INTRADAY
        trade_value = quantity * price
        with get_session() as session:
            if not self._can_open(trade_value, session):
                return None
            pos = self._get_pos(session, symbol)
            if pos is None:
                pos = Position(
                    symbol=symbol,
                    quantity=0,
                    avg_price=0.0,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0,
                    segment=seg,
                )
                session.add(pos)
                session.flush()
            if pos.segment is None:
                pos.segment = seg

            if pos.quantity > 0:
                print(f"[SKIP] {symbol} already LONG — cannot SHORT")
                return None
            existing_qty = abs(pos.quantity)
            total_qty = existing_qty + quantity
            pos.avg_price = (
                (pos.avg_price * existing_qty) + (price * quantity)
            ) / total_qty
            pos.quantity -= quantity
            self.cash += trade_value
            trade = Trade(
                symbol=symbol,
                side="SHORT",
                quantity=quantity,
                price=price,
                pnl=0.0,
                paper=True,
                timestamp=datetime.utcnow(),
                segment=seg,
                order_type=order_type,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            session.add(trade)
            session.add(
                PortfolioSnapshot(
                    timestamp=datetime.utcnow(),
                    equity=self.cash,
                    cash=self.cash,
                )
            )
            print(
                f"[ENGINE] SHORT {symbol} x{quantity} @ {price:.2f} | "
                f"seg={seg} | cash={self.cash:,.2f}"
            )
            return trade

    def cover(self, symbol, quantity, price, segment=None, order_type="REGULAR"):
        seg = segment or settings.SEGMENT_INTRADAY
        with get_session() as session:
            pos = self._get_pos(session, symbol)
            if pos is None or pos.quantity >= 0:
                return None
            qty = min(quantity, abs(pos.quantity))
            pnl = (pos.avg_price - price) * qty
            pos.quantity += qty
            if pos.quantity == 0:
                pos.avg_price = 0.0
            pos.realized_pnl = (pos.realized_pnl or 0.0) + pnl
            self.cash -= qty * price
            trade = Trade(
                symbol=symbol,
                side="COVER",
                quantity=qty,
                price=price,
                pnl=pnl,
                paper=True,
                timestamp=datetime.utcnow(),
                segment=seg,
                order_type=order_type,
            )
            session.add(trade)
            session.add(
                PortfolioSnapshot(
                    timestamp=datetime.utcnow(),
                    equity=self.cash,
                    cash=self.cash,
                )
            )
            print(
                f"[ENGINE] COVER {symbol} x{qty} @ {price:.2f} | "
                f"seg={seg} | P&L={pnl:+.2f} | cash={self.cash:,.2f}"
            )
            return trade

    def update_unrealized_pnls(self, ltp_map: dict):
        with get_session() as session:
            for pos in session.query(Position).filter(Position.quantity != 0):
                ltp = ltp_map.get(pos.symbol)
                if ltp is None:
                    continue
                if pos.quantity > 0:
                    pos.unrealized_pnl = (ltp - pos.avg_price) * pos.quantity
                else:
                    pos.unrealized_pnl = (pos.avg_price - ltp) * abs(pos.quantity)

    def get_portfolio_value(self) -> float:
        """Returns total portfolio value: cash + unrealized P&L of all open positions."""
        with get_session() as session:
            positions = session.query(Position).filter(Position.quantity != 0).all()
            unrealized = sum(float(p.unrealized_pnl or 0.0) for p in positions)
        return self.cash + unrealized

    def square_off_all(self, ltp_map: dict):
        """Emergency square-off: closes all open positions at given LTPs."""
        with get_session() as session:
            positions = session.query(Position).filter(Position.quantity != 0).all()
            for pos in positions:
                ltp = ltp_map.get(pos.symbol)
                if ltp is None:
                    print(f"[SQUAREOFF] No LTP for {pos.symbol}, skipping.")
                    continue
                if pos.quantity > 0:
                    self.sell(pos.symbol, pos.quantity, ltp, segment=pos.segment)
                else:
                    self.cover(pos.symbol, abs(pos.quantity), ltp, segment=pos.segment)