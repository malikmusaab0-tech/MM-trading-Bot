from dataclasses import dataclass
from typing import Dict
from datetime import datetime
from config import settings
from data.database import get_session, Trade, Position, PortfolioSnapshot


@dataclass
class PortfolioState:
    cash: float
    positions: Dict[str, Position]
    equity: float


class PaperTradingEngine:
    def __init__(self):
        self.session = get_session()
        self.cash = settings.INITIAL_CAPITAL
        self._load_existing_state()

    def _load_existing_state(self):
        # Load latest snapshot if exists
        snapshot = (
            self.session.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.timestamp.desc())
            .first()
        )
        if snapshot:
            self.cash = snapshot.cash

    def _get_position(self, symbol: str) -> Position | None:
        return (
            self.session.query(Position)
            .filter(Position.symbol == symbol)
            .one_or_none()
        )

    def _ensure_position(self, symbol: str) -> Position:
        pos = self._get_position(symbol)
        if pos is None:
            pos = Position(symbol=symbol, quantity=0, avg_price=0.0)
            self.session.add(pos)
            self.session.commit()
        return pos

    def can_open_new_position(self, trade_value: float, open_positions_count: int) -> bool:
        if trade_value > settings.MAX_POSITION_VALUE:
            return False
        if open_positions_count >= settings.MAX_CONCURRENT_POSITIONS:
            return False
        if trade_value > self.cash:
            return False
        return True

    def buy(self, symbol: str, quantity: int, price: float):
        trade_value = quantity * price
        open_positions_count = (
            self.session.query(Position)
            .filter(Position.quantity != 0)
            .count()
        )
        if not self.can_open_new_position(trade_value, open_positions_count):
            return None

        pos = self._ensure_position(symbol)
        new_qty = pos.quantity + quantity
        if new_qty <= 0:
            return None

        pos.avg_price = ((pos.avg_price * pos.quantity) + trade_value) / new_qty
        pos.quantity = new_qty

        self.cash -= trade_value
        trade = Trade(symbol=symbol, side="BUY", quantity=quantity, price=price, paper=True)
        self.session.add(trade)
        self._snapshot()
        self.session.commit()
        return trade

    def sell(self, symbol: str, quantity: int, price: float):
        pos = self._get_position(symbol)
        if pos is None or pos.quantity <= 0:
            return None

        qty = min(quantity, pos.quantity)
        trade_value = qty * price

        pnl = (price - pos.avg_price) * qty
        pos.quantity -= qty
        if pos.quantity == 0:
            pos.avg_price = 0.0

        pos.realized_pnl += pnl
        self.cash += trade_value

        trade = Trade(symbol=symbol, side="SELL", quantity=qty, price=price, pnl=pnl, paper=True)
        self.session.add(trade)
        self._snapshot()
        self.session.commit()
        return trade

    def update_unrealized_pnls(self, ltp_map: Dict[str, float]):
        for pos in self.session.query(Position).filter(Position.quantity != 0):
            ltp = ltp_map.get(pos.symbol)
            if ltp is None:
                continue
            pos.unrealized_pnl = (ltp - pos.avg_price) * pos.quantity
        self.session.commit()

    def _snapshot(self):
        equity = self.cash
        for pos in self.session.query(Position).filter(Position.quantity != 0):
            equity += pos.avg_price * pos.quantity + pos.unrealized_pnl

        snap = PortfolioSnapshot(timestamp=datetime.utcnow(), equity=equity, cash=self.cash)
        self.session.add(snap)
