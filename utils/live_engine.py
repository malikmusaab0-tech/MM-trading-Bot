import logging
from datetime import datetime
import time
import threading
import socket

from dhanhq import dhanhq
from config import settings
from data.database import get_session, Trade, Position, PortfolioSnapshot
from utils.rate_limiter import retry_with_backoff

logger = logging.getLogger(__name__)

class DhanLiveEngine:
    def __init__(self, dhan: dhanhq):
        self.dhan = dhan
        self.cash = float(settings.INITIAL_CAPITAL)
        self.blocked = False
        self.max_loss = getattr(settings, 'MAX_DAILY_LOSS', 5000)
        self.heartbeat_timeout = 30
        self.last_heartbeat = time.time()
        self._start_heartbeat_monitor()

    def _start_heartbeat_monitor(self):
        def monitor():
            while True:
                try:
                    # Ping reliable external server to check internet
                    socket.create_connection(("1.1.1.1", 53), timeout=3)
                    self.last_heartbeat = time.time()
                    self.blocked = False
                except Exception:
                    pass

                if time.time() - self.last_heartbeat > self.heartbeat_timeout:
                    if not self.blocked:
                        logger.critical("[HEARTBEAT] Internet dropped for > 30s! Blocking orders and logging state.")
                        self.blocked = True
                        self._log_emergency_state()

                time.sleep(5)

        t = threading.Thread(target=monitor, daemon=True)
        t.start()

    def _log_emergency_state(self):
        """Logs last known state to prevent flying blind during network drops."""
        try:
            with get_session() as session:
                positions = session.query(Position).filter(Position.quantity != 0).all()
                for pos in positions:
                    logger.critical(f"Emergency Log - Symbol: {pos.symbol}, Qty: {pos.quantity}, AvgPrice: {pos.avg_price}")
        except Exception as e:
            logger.error(f"Failed to log emergency state: {e}")

    def _check_max_loss(self):
        val = self.get_portfolio_value()
        pnl = val - settings.INITIAL_CAPITAL
        if pnl <= -self.max_loss:
            logger.critical(f"[RISK] Max Daily Loss Reached: {pnl:.2f}. Blocking further orders.")
            self.blocked = True
            return False
        return True

    def _place_order(self, symbol, quantity, price, side, product_type, order_type="MARKET", stop_loss=None, take_profit=None):
        if self.blocked:
            logger.warning("[LIVE ENGINE] Engine is blocked (Max Loss or Network Drop). Cannot place order.")
            return None

        if not self._check_max_loss():
            return None

        from utils.dhan_helper import dhan_helper
        sec_id = dhan_helper.get_security_id(symbol)
        if not sec_id:
            logger.error(f"[LIVE ENGINE] Security ID not found for {symbol}")
            return None

        # Map Side
        txn_type = self.dhan.BUY if side in ["BUY", "COVER"] else self.dhan.SELL

        # Map Product Type
        prod_map = {
            "INTRADAY": self.dhan.INTRA,
            "MTF": self.dhan.MTF,
            "CNC": self.dhan.CNC
        }
        prod = prod_map.get(product_type, self.dhan.INTRA)

        # Map Order Type
        ord_map = {
            "MARKET": self.dhan.MARKET,
            "LIMIT": self.dhan.LIMIT,
            "BRACKET": self.dhan.BO,
            "FOREVER": self.dhan.MARKET # We simulate forever by placing standard or OCO logic if Dhan API supports it, but fallback to market/limit
        }
        dhan_ord_type = ord_map.get(order_type, self.dhan.MARKET)

        logger.info(f"[LIVE] Placing {side} order for {symbol} x{quantity} @ {price} | Prod: {product_type} | Type: {order_type}")

        try:
            # Note: Dhan API place_order signature:
            # security_id, exchange_segment, transaction_type, quantity, order_type, product_type, price
            # We omit BO details for simplicity in the wrapper unless explicitly building BO payload

            kwargs = {
                "security_id": str(sec_id),
                "exchange_segment": self.dhan.NSE,
                "transaction_type": txn_type,
                "quantity": int(quantity),
                "order_type": dhan_ord_type,
                "product_type": prod,
                "price": price if order_type != "MARKET" else 0
            }

            if order_type == "BRACKET" and stop_loss and take_profit:
                # Dhan API expects bo_profit_value and bo_stop_loss_Value as absolute point differences
                # For example, if entry is 100, SL is 95, TP is 110, then bo_profit_value=10, bo_stop_loss_Value=5
                if txn_type == self.dhan.BUY:
                    kwargs["bo_profit_value"] = abs(take_profit - price)
                    kwargs["bo_stop_loss_Value"] = abs(price - stop_loss)
                else:
                    kwargs["bo_profit_value"] = abs(price - take_profit)
                    kwargs["bo_stop_loss_Value"] = abs(stop_loss - price)

            response = self.dhan.place_order(**kwargs)
            logger.info(f"[LIVE] Order Response: {response}")

            if response and response.get('status') == 'success':
                return response
            else:
                logger.error(f"[LIVE] Order Failed: {response}")
                return None

        except Exception as e:
            logger.error(f"[LIVE] Exception placing order: {e}")
            return None

    # Implement PaperTradingEngine parity methods

    def buy(self, symbol, quantity, price, segment=None, order_type="REGULAR", stop_loss=None, take_profit=None, product_type=None):
        seg = segment or settings.SEGMENT_INTRADAY
        product_type = product_type or ("INTRADAY" if seg == settings.SEGMENT_INTRADAY else "MTF")
        res = self._place_order(symbol, quantity, price, "BUY", product_type, order_type, stop_loss, take_profit)

        if res:
            # Log to DB identically to PaperTradingEngine
            flagged_seg = f"{seg} [MTF PLEDGE REQ]" if product_type == "MTF" else seg
            with get_session() as session:
                pos = session.query(Position).filter(Position.symbol == symbol).one_or_none()
                if not pos:
                    pos = Position(symbol=symbol, quantity=0, avg_price=0.0, unrealized_pnl=0.0, realized_pnl=0.0, segment=seg)
                    session.add(pos)

                trade_value = quantity * price
                total_qty = pos.quantity + quantity
                pos.avg_price = ((pos.avg_price * pos.quantity) + trade_value) / total_qty
                pos.quantity = total_qty
                self.cash -= trade_value

                trade = Trade(
                    symbol=symbol, side="BUY", quantity=quantity, price=price, pnl=0.0, paper=False,
                    timestamp=datetime.utcnow(), segment=flagged_seg, order_type=order_type,
                    stop_loss=stop_loss, take_profit=take_profit, product_type=product_type,
                    is_mtf=(product_type == "MTF")
                )
                session.add(trade)
                session.add(PortfolioSnapshot(timestamp=datetime.utcnow(), equity=self.cash, cash=self.cash))
            return trade
        return None

    def sell(self, symbol, quantity, price, segment=None, order_type="REGULAR", product_type=None):
        seg = segment or settings.SEGMENT_INTRADAY
        product_type = product_type or ("INTRADAY" if seg == settings.SEGMENT_INTRADAY else "MTF")
        res = self._place_order(symbol, quantity, price, "SELL", product_type, order_type)

        if res:
            with get_session() as session:
                pos = session.query(Position).filter(Position.symbol == symbol).one_or_none()
                if pos:
                    pnl = (price - pos.avg_price) * quantity
                    pos.quantity -= quantity
                    pos.realized_pnl += pnl
                    self.cash += quantity * price

                    trade = Trade(
                        symbol=symbol, side="SELL", quantity=quantity, price=price, pnl=pnl, paper=False,
                        timestamp=datetime.utcnow(), exit_time=datetime.utcnow(), exit_price=price,
                        segment=seg, order_type=order_type, product_type=product_type,
                        is_mtf=(product_type == "MTF")
                    )
                    session.add(trade)
            return trade
        return None

    def short(self, symbol, quantity, price, segment=None, order_type="REGULAR", stop_loss=None, take_profit=None, product_type=None):
        seg = segment or settings.SEGMENT_INTRADAY
        product_type = product_type or ("INTRADAY" if seg == settings.SEGMENT_INTRADAY else "MTF")
        res = self._place_order(symbol, quantity, price, "SHORT", product_type, order_type, stop_loss, take_profit)
        if res:
             with get_session() as session:
                pos = session.query(Position).filter(Position.symbol == symbol).one_or_none()
                if not pos:
                    pos = Position(symbol=symbol, quantity=0, avg_price=0.0, unrealized_pnl=0.0, realized_pnl=0.0, segment=seg)
                    session.add(pos)

                trade_value = quantity * price
                existing_qty = abs(pos.quantity)
                total_qty = existing_qty + quantity
                pos.avg_price = ((pos.avg_price * existing_qty) + (price * quantity)) / total_qty
                pos.quantity -= quantity
                self.cash += trade_value

                trade = Trade(
                    symbol=symbol, side="SHORT", quantity=quantity, price=price, pnl=0.0, paper=False,
                    timestamp=datetime.utcnow(), segment=seg, order_type=order_type,
                    stop_loss=stop_loss, take_profit=take_profit, product_type=product_type,
                    is_mtf=(product_type == "MTF")
                )
                session.add(trade)
             return trade
        return None

    def cover(self, symbol, quantity, price, segment=None, order_type="REGULAR", product_type=None):
        seg = segment or settings.SEGMENT_INTRADAY
        product_type = product_type or ("INTRADAY" if seg == settings.SEGMENT_INTRADAY else "MTF")
        res = self._place_order(symbol, quantity, price, "COVER", product_type, order_type)
        if res:
            with get_session() as session:
                pos = session.query(Position).filter(Position.symbol == symbol).one_or_none()
                if pos:
                    pnl = (pos.avg_price - price) * quantity
                    pos.quantity += quantity
                    pos.realized_pnl += pnl
                    self.cash -= quantity * price
                    trade = Trade(
                        symbol=symbol, side="COVER", quantity=quantity, price=price, pnl=pnl, paper=False,
                        timestamp=datetime.utcnow(), exit_time=datetime.utcnow(), exit_price=price,
                        segment=seg, order_type=order_type, product_type=product_type,
                        is_mtf=(product_type == "MTF")
                    )
                    session.add(trade)
            return trade
        return None

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
        with get_session() as session:
            positions = session.query(Position).filter(Position.quantity != 0).all()
            unrealized = sum(float(p.unrealized_pnl or 0.0) for p in positions)
        return self.cash + unrealized

    def square_off_all(self, ltp_map: dict):
        with get_session() as session:
            positions = session.query(Position).filter(Position.quantity != 0).all()
            for pos in positions:
                ltp = ltp_map.get(pos.symbol)
                if ltp is None:
                    continue
                if pos.quantity > 0:
                    self.sell(pos.symbol, pos.quantity, ltp, segment=pos.segment)
                else:
                    self.cover(pos.symbol, abs(pos.quantity), ltp, segment=pos.segment)
                time.sleep(0.2)
