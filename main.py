# PRIMA PRO - Professional Trading Bot (Long + Short Edition)
import time
import json
import os
from datetime import datetime, timedelta
import logging

import pandas as pd
from dhanhq import dhanhq

from config import settings
from data.database import init_db, get_session, Position
from utils.auth import get_dhan_client, load_access_token
from utils.paper_trading import PaperTradingEngine
from utils.market_scanner import MarketScanner
from utils.strategy_selector import StrategySelector
from utils.risk_manager import RiskManager
from utils.pattern_recognizer import PatternRecognizer
from utils.swing_engine import SwingEngine
from utils.notification_service import NotificationService
from utils.longterm_engine import LongTermEngine

from strategies.vwap_momentum import VwapMomentumStrategy
from strategies.ema_crossover import EmaCrossoverStrategy
from strategies.supertrend import SupertrendStrategy
from strategies.bollinger_reversal import BollingerReversalStrategy
from strategies.rsi_reversal import RsiReversalStrategy
from strategies.macd_momentum import MacdMomentumStrategy
from strategies.volume_breakout import VolumeBreakoutStrategy
from strategies.atr_breakout import AtrBreakoutStrategy
from strategies.base_strategy import Signal


# ── Logging (Windows CP1252 safe) ─────────────────────────────────────────────
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            msg = msg.encode("ascii", errors="replace").decode("ascii")
            self.stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


logging.basicConfig(
    filename=settings.LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
console = SafeStreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)
logger = logging.getLogger(__name__)


SCAN_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "scan_state.json"
)


def write_scan_state(state: dict):
    try:
        import pandas as pd
        # Add next_rebalance_due if not present
        if "next_rebalance_due" not in state:
            now = datetime.now()
            last_bday = pd.date_range(start=now.replace(day=1), periods=1, freq='BME')
            next_due = pd.to_datetime(last_bday[0]).strftime("%Y-%m-%d 15:00:00")
            state["next_rebalance_due"] = next_due

        with open(SCAN_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.debug(f"scan_state write failed: {e}")


def fetch_candles(
    dhan: dhanhq, symbol: str, interval: str = None
) -> pd.DataFrame:
    import redis
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)

    # We refactored to use Redis lists directly
    closes = r.lrange(f"historical:5min:{symbol}:close", 0, -1)
    volumes = r.lrange(f"historical:5min:{symbol}:volume", 0, -1)

    if closes and volumes:
        # Since we just have close and volume right now to satisfy simple models, we use those.
        # But strategies also use open/high/low in ATR.
        # We didn't warm high/low/open. Let's return just close/vol and emulate ATR using close diffs if needed,
        # or we should probably update warm_data to include high/low for correct ATR.
        # Assuming we update warm_data to also store high/low in a minute... Let's read them.
        highs = r.lrange(f"historical:5min:{symbol}:high", 0, -1)
        lows = r.lrange(f"historical:5min:{symbol}:low", 0, -1)

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


def get_strategy(name: str, capital: float):
    mapping = {
        "VWAP_MOMENTUM": VwapMomentumStrategy,
        "EMA_CROSSOVER": EmaCrossoverStrategy,
        "SUPERTREND": SupertrendStrategy,
        "BOLLINGER_REVERSAL": BollingerReversalStrategy,
        "RSI_REVERSAL": RsiReversalStrategy,
        "MACD_MOMENTUM": MacdMomentumStrategy,
        "VOLUME_BREAKOUT": VolumeBreakoutStrategy,
        "ATR_BREAKOUT": AtrBreakoutStrategy,
    }
    return mapping.get(name, VwapMomentumStrategy)(capital=capital)


def get_atr(df: pd.DataFrame, current_price: float) -> float:
    if len(df) >= 14:
        hl = df["high"] - df["low"]
        hcp = (df["high"] - df["close"].shift()).abs()
        lcp = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([hl, hcp, lcp], axis=1).max(axis=1)
        return tr.rolling(14).mean().iloc[-1]
    return current_price * 0.02


def main():
    import argparse
    parser = argparse.ArgumentParser(description="PRIMA PRO Trading Bot")
    parser.add_argument("--rebalance", action="store_true", help="Run manual investing rebalance and exit.")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("PRIMA PRO - LONG + SHORT EDITION")
    logger.info("=" * 60)

    # Run pre-flight system checks
    from utils.system_check import preflight_check
    preflight_check()

    access_token = load_access_token()
    if not access_token:
        logger.error("No Dhan access_token.")
        # return # We will just use the dummy one or settings

    dhan = get_dhan_client(access_token)

    # Initialize Engine (Paper vs Live)
    if settings.LIVE_TRADING_MODE:
        from utils.live_engine import DhanLiveEngine
        engine = DhanLiveEngine(dhan=dhan)
    else:
        engine = PaperTradingEngine()

    from utils.investing_engine import InvestingEngine
    investing_engine = InvestingEngine(
        dhan=dhan,
        trading_engine=engine
    )

    if args.rebalance:
        if settings.LIVE_TRADING_MODE:
            print("\033[91m" + "WARNING: You are about to execute a MANUAL REBALANCE in LIVE TRADING MODE." + "\033[0m")
            confirm = input("Are you sure you want to proceed? (yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                print("Manual rebalance aborted.")
                return

        # Warm data into Redis if we're going to rebalance just to be safe
        import redis
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
        from utils.data_warming import warm_data
        warm_data(dhan, r)

        investing_engine.run_manual_rebalance()

        # Update dashboard state
        state = {}
        if os.path.exists(SCAN_STATE_FILE):
            try:
                with open(SCAN_STATE_FILE, "r") as f:
                    state = json.load(f)
            except: pass
        state["next_rebalance_due"] = "Manual execution completed."
        write_scan_state(state)

        logger.info("Manual rebalance complete. Exiting.")
        return

    # Warm data into Redis
    import redis
    r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)
    from utils.data_warming import warm_data
    warm_data(dhan, r)

    # Start WebSocket listener in a separate thread
    import threading
    from utils.websocket_listener import start_websocket
    ws_thread = threading.Thread(target=start_websocket, daemon=True)
    ws_thread.start()

    init_db()

    from utils.risk_manager import set_dhan_client as set_margin_dhan
    set_margin_dhan(dhan)

    if settings.LIVE_TRADING_MODE:
        print("\033[91m" + "==================================================" + "\033[0m")
        print("\033[91m" + "CRITICAL WARNING: LIVE TRADING MODE IS ENABLED!" + "\033[0m")
        print("\033[91m" + "REAL MONEY WILL BE USED FOR ORDER EXECUTION." + "\033[0m")
        print("\033[91m" + "==================================================" + "\033[0m")

    scanner = MarketScanner(dhan)
    selector = StrategySelector()
    risk_manager = RiskManager()
    pattern_rec = PatternRecognizer()

    notifier = NotificationService()

    # Startup ping
    try:
        notifier.send_text(
            f"PRIMA Pro started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as e:
        logger.info(f"[NOTIFY] Startup notification failed: {e}")

    # SwingEngine: daily swing ideas + paper trades (segment=SWING) + alerts
    swing_engine = SwingEngine(
        dhan=dhan,
        trading_engine=engine,
        symbols=settings.DEFAULT_WATCHLIST,
        notifier=notifier,
    )
    last_swing_run_date = None

    last_investing_run_month = None

    logger.info(f"Paper Mode : {settings.PAPER_TRADING_MODE}")
    logger.info(f"Capital    : Rs.{settings.INITIAL_CAPITAL:,.2f}")
    logger.info(f"Max Pos    : {settings.MAX_CONCURRENT_POSITIONS}")
    # ── CHANGED: show dynamic sizing config instead of removed MAX_POSITION_VALUE
    logger.info(f"Pos Cap    : {settings.POSITION_SIZE_CAPITAL_PCT * 100:.0f}% of cash x per-symbol leverage (dynamic)")
    logger.info("=" * 60)

    bot_running = True
    has_squared_off_intraday = False

    while bot_running:
        try:
            now = datetime.now()
            market_open = datetime.strptime("09:15", "%H:%M").time()
            market_close = datetime.strptime("15:30", "%H:%M").time()
            square_off_time = datetime.strptime(settings.SQUARE_OFF_TIME, "%H:%M").time()

            # Reset square off flag each day
            if now.time() < market_open:
                has_squared_off_intraday = False

            # ── Intraday Hard Square-Off (15:15) ──────────
            if not has_squared_off_intraday and now.time() >= square_off_time:
                logger.warning(f"Initiating hard square-off for all INTRADAY positions at {square_off_time}.")
                import redis
                r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)

                with get_session() as session:
                    intraday_positions = (
                        session.query(Position)
                        .filter(Position.quantity != 0)
                        .filter(Position.segment == settings.SEGMENT_INTRADAY)
                        .all()
                    )

                    ltp_map = {}
                    for p in intraday_positions:
                        raw_data = r.hgetall(f"live_state:{p.symbol}")
                        if raw_data and raw_data.get("ltp"):
                            ltp_map[p.symbol] = float(raw_data["ltp"])

                    if ltp_map:
                        engine.square_off_all(ltp_map)

                has_squared_off_intraday = True

            # ── Daily Swing scan hook (around 15:20, once per day) ──────────
            if settings.SWING_ENABLED and last_swing_run_date != now.date():
                swing_run_time = datetime.strptime("15:20", "%H:%M").time()
                if now.time() >= swing_run_time:
                    try:
                        swing_engine.run_once()
                        logger.info("[SWING] Daily swing scan completed.")
                    except NotImplementedError as e:
                        logger.info(f"[SWING] Data source not wired yet: {e}")
                    except Exception as e:
                        logger.exception(f"[SWING] Error in swing scan: {e}")
                    finally:
                        last_swing_run_date = now.date()

            # ── Investing review hook (monthly) ────────────
            # Trigger on the last trading day of the month within the final 30 minutes (e.g. 15:00)
            if settings.LONGTERM_ENABLED and last_investing_run_month != now.month:
                import pandas as pd
                # Get the last business day of the current month
                last_bday = pd.date_range(start=now.replace(day=1), periods=1, freq='BME')
                # Check if today is the last business day (approximate last trading day)
                is_last_trading_day = now.date() == pd.to_datetime(last_bday[0]).date()

                # Check if it's the final 30 minutes of the session (15:00 to 15:30)
                final_window_start = datetime.strptime("15:00", "%H:%M").time()

                if is_last_trading_day and now.time() >= final_window_start:
                    try:
                        investing_engine.run_monthly()
                        logger.info("[INVESTING] Monthly investing review completed.")
                    except Exception as e:
                        logger.exception(f"[INVESTING] Error in investing review: {e}")
                    finally:
                        last_investing_run_month = now.month

            # ── Market hours check for INTRADAY ─────────────────────────────
            if not (market_open <= now.time() <= market_close):
                logger.info("Outside market hours. Waiting 60s...")
                write_scan_state(
                    {
                        "scanning": False,
                        "stocks": [],
                        "liquidcount": 0,
                        "oppcount": 0,
                        "lastscan": "Outside market hours",
                    }
                )
                time.sleep(60)
                continue

            write_scan_state(
                {
                    "scanning": True,
                    "stocks": [],
                    "liquidcount": 0,
                    "oppcount": 0,
                    "lastscan": now.strftime("%H:%M:%S"),
                }
            )

            opportunities = scanner.scan_for_opportunities()
            if not opportunities:
                write_scan_state(
                    {
                        "scanning": False,
                        "stocks": [],
                        "liquidcount": 0,
                        "oppcount": 0,
                        "lastscan": now.strftime("%H:%M:%S"),
                    }
                )
                time.sleep(settings.REFRESH_SECONDS)
                continue

            logger.info(f"Found {len(opportunities)} opportunities")

            # ── Manage existing open positions ───────────────────────────────
            import redis
            r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)

            with get_session() as session:
                for pos in (
                    session.query(Position)
                    .filter(Position.quantity != 0)
                    .all()
                ):
                    raw_data = r.hgetall(f"live_state:{pos.symbol}")
                    if not raw_data:
                        continue
                    current_price = float(raw_data.get("ltp", 0))
                    if current_price == 0:
                        continue

                    risk_manager.update_trailing_stop(
                        pos.symbol, current_price, pos.avg_price
                    )
                    should_close, close_reason = (
                        risk_manager.should_close_position(
                            pos.symbol, current_price, pos.avg_price
                        )
                    )
                    if should_close:
                        logger.info(f"Closing {pos.symbol}: {close_reason}")
                        if pos.quantity > 0:
                            engine.sell(pos.symbol, pos.quantity, current_price, product_type="INTRADAY")
                        else:
                            engine.cover(
                                pos.symbol, abs(pos.quantity), current_price, product_type="INTRADAY"
                            )
                        risk_manager.cleanup_closed_position(pos.symbol)

            # ── Analyse & trade new opportunities ────────────────────────────
            analyzed_stocks = []

            for opp in opportunities[:10]:
                symbol = opp["symbol"]
                logger.info(f"--- {symbol} ---")
                time.sleep(0.3)

                df = fetch_candles(dhan, symbol)
                if df.empty:
                    continue

                strategy_name, market_info = selector.select_strategy(symbol, df)
                if strategy_name == "HOLD":
                    # Enhanced Logging for HOLDs
                    condition = market_info.get("condition", "")
                    rsi_v = market_info.get("rsi")

                    log_msg = f"[HOLD] {symbol}: "
                    if condition == "OVERSOLD" and rsi_v is not None:
                        log_msg += f"RSI is {rsi_v:.1f} (Threshold < 30)"
                    elif condition == "OVERBOUGHT" and rsi_v is not None:
                        log_msg += f"RSI is {rsi_v:.1f} (Threshold > 70)"
                    elif "VWAP" in condition or condition == "STRONG_DOWNTREND":
                        log_msg += "Below VWAP / Strong Downtrend"
                    else:
                        log_msg += f"Condition: {condition}"

                    logger.info(log_msg)

                    analyzed_stocks.append(
                        {
                            "symbol": symbol,
                            "signal": "HOLD",
                            "strategy": "HOLD",
                            "condition": condition,
                            "strength": opp.get("signal_strength", "-"),
                            "rsi": rsi_v,
                        }
                    )
                    continue

                with get_session() as session:
                    pos = (
                        session.query(Position)
                        .filter(Position.symbol == symbol)
                        .one_or_none()
                    )
                    current_qty = pos.quantity if pos else 0
                    entry_price = (
                        pos.avg_price if pos and pos.quantity != 0 else None
                    )

                strategy = get_strategy(strategy_name, engine.cash)
                signal: Signal = strategy.generate_signal(
                    symbol=symbol,
                    df=df,
                    current_position_qty=current_qty,
                    entry_price=entry_price,
                )
                logger.info(f"{symbol} -> {signal.action}: {signal.reason}")

                analyzed_stocks.append(
                    {
                        "symbol": symbol,
                        "signal": signal.action,
                        "strategy": strategy_name,
                        "condition": market_info.get("condition", "-"),
                        "strength": opp.get("signal_strength", "-"),
                        "rsi": market_info.get("rsi"),
                    }
                )
                write_scan_state(
                    {
                        "scanning": True,
                        "lastscan": datetime.now().strftime("%H:%M:%S"),
                        "liquidcount": len(opportunities),
                        "oppcount": len(opportunities),
                        "stocks": analyzed_stocks,
                    }
                )

                raw_data = r.hgetall(f"live_state:{symbol}")
                current_price = float(raw_data.get("ltp", 0)) if raw_data else opp["ltp"]
                atr = get_atr(df, current_price)

                # Check can_open PER SYMBOL
                can_open, open_reason = risk_manager.can_open_new_position()

                # ── BUY — long entry ─────────────────────────────────────────
                if signal.action == "BUY" and current_qty == 0 and can_open:
                    qty = risk_manager.calculate_position_size(
                        symbol, current_price, atr, engine.cash
                    )
                    # No separate MAX_POSITION_VALUE guard needed.
                    # Sizing is already capped at:
                    #   POSITION_SIZE_CAPITAL_PCT (25%) x cash x per-symbol leverage
                    if qty > 0:
                        logger.info(
                            f"BUY {symbol} x{qty} @ Rs.{current_price:.2f}  "
                            f"notional=Rs.{qty * current_price:,.0f}"
                        )
                        sl = current_price - (atr * settings.STOP_LOSS_ATR_MULTIPLIER)
                        tp = current_price + (atr * settings.TAKE_PROFIT_ATR_MULTIPLIER)
                        trade = engine.buy(
                            symbol, qty, current_price,
                            order_type="BRACKET", stop_loss=sl, take_profit=tp,
                            product_type="INTRADAY"
                        )
                        if trade:
                            risk_manager.set_stop_loss(
                                symbol, current_price, atr
                            )
                            risk_manager.set_take_profit(
                                symbol, current_price, atr
                            )
                    else:
                        logger.info(
                            f"[SIZE] {symbol} BUY skipped — qty=0 "
                            f"(price too high or below MIN_POSITION_SIZE)"
                        )

                # ── SELL — long exit ─────────────────────────────────────────
                elif signal.action == "SELL" and current_qty > 0:
                    logger.info(
                        f"SELL {symbol} x{current_qty} @ Rs.{current_price:.2f}"
                    )
                    trade = engine.sell(
                        symbol, signal.quantity or current_qty, current_price, product_type="INTRADAY"
                    )
                    if trade:
                        logger.info(f"  P&L=Rs.{trade.pnl:.2f}")
                    risk_manager.cleanup_closed_position(symbol)

                # ── SHORT — short entry ──────────────────────────────────────
                elif signal.action == "SHORT" and current_qty == 0 and can_open:
                    qty = risk_manager.calculate_position_size(
                        symbol, current_price, atr, engine.cash
                    )
                    if qty > 0:
                        logger.info(
                            f"SHORT {symbol} x{qty} @ Rs.{current_price:.2f}  "
                            f"notional=Rs.{qty * current_price:,.0f}"
                        )
                        sl = current_price + (atr * settings.STOP_LOSS_ATR_MULTIPLIER)
                        tp = current_price - (atr * settings.TAKE_PROFIT_ATR_MULTIPLIER)
                        trade = engine.short(
                            symbol, qty, current_price,
                            order_type="BRACKET", stop_loss=sl, take_profit=tp,
                            product_type="INTRADAY"
                        )
                        if trade:
                            risk_manager.set_short_stop_loss(
                                symbol, current_price, atr
                            )
                            risk_manager.set_short_take_profit(
                                symbol, current_price, atr
                            )
                    else:
                        logger.info(
                            f"[SIZE] {symbol} SHORT skipped — qty=0 after sizing"
                        )

                # ── COVER — short exit ───────────────────────────────────────
                elif signal.action == "COVER" and current_qty < 0:
                    logger.info(
                        f"COVER {symbol} x{abs(current_qty)} "
                        f"@ Rs.{current_price:.2f}"
                    )
                    trade = engine.cover(
                        symbol,
                        abs(signal.quantity or current_qty),
                        current_price,
                        product_type="INTRADAY"
                    )
                    if trade:
                        logger.info(f"  P&L=Rs.{trade.pnl:.2f}")
                    risk_manager.cleanup_closed_position(symbol)

                # ── HOLD — manage trailing stops on existing positions ────────
                elif current_qty != 0:
                    risk_manager.update_trailing_stop(
                        symbol, current_price, entry_price
                    )
                    should_close, close_reason = (
                        risk_manager.should_close_position(
                            symbol, current_price, entry_price
                        )
                    )
                    if should_close:
                        logger.info(
                            f"Auto-close {symbol}: {close_reason}"
                        )
                        if current_qty > 0:
                            trade = engine.sell(
                                symbol, current_qty, current_price, product_type="INTRADAY"
                            )
                        else:
                            trade = engine.cover(
                                symbol, abs(current_qty), current_price, product_type="INTRADAY"
                            )
                        if trade:
                            logger.info(f"  P&L=Rs.{trade.pnl:.2f}")
                        risk_manager.cleanup_closed_position(symbol)

            # ── Final scan state / unrealized P&L update ─────────────────────
            write_scan_state(
                {
                    "scanning": False,
                    "lastscan": datetime.now().strftime("%H:%M:%S"),
                    "liquidcount": len(opportunities),
                    "oppcount": len(opportunities),
                    "stocks": analyzed_stocks,
                }
            )

            with get_session() as session:
                positions = (
                    session.query(Position)
                    .filter(Position.quantity != 0)
                    .all()
                )
                if positions:
                    update_dict = {}
                    for p in positions:
                        raw_data = r.hgetall(f"live_state:{p.symbol}")
                        if raw_data and raw_data.get("ltp"):
                            update_dict[p.symbol] = float(raw_data["ltp"])
                    if update_dict:
                        engine.update_unrealized_pnls(update_dict)

            m = risk_manager.get_portfolio_risk()
            logger.info(
                f"Pos={m['total_positions']} "
                f"Exp=Rs.{m['total_exposure']:,.0f} "
                f"Margin={m['margin_used_pct']:.1f}% "
                f"UPnL=Rs.{m['unrealized_pnl']:.2f} "
                f"RPnL=Rs.{m['realized_pnl']:.2f}"
            )

            time.sleep(settings.REFRESH_SECONDS)

        except KeyboardInterrupt:
            bot_running = False
            break
        except Exception as e:
            logger.exception(f"Main loop error: {e}")
            time.sleep(5)

    logger.info("PRIMA PRO STOPPED")


if __name__ == "__main__":
    main()