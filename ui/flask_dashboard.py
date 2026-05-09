import os
import sys
import json
from datetime import datetime

from flask import Flask, jsonify, request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.database import get_session, Trade, Position, PortfolioSnapshot
from config import settings
from utils.paper_trading import PaperTradingEngine

UI_DIR        = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(UI_DIR, "templates")

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=UI_DIR)

_engine_instance = None


def get_engine() -> PaperTradingEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PaperTradingEngine()
    return _engine_instance


bot_state       = {"running": True}
optimizer_state = {"enabled": False, "last_updated": None}


def read_scan_state() -> dict:
    path = os.path.join(PROJECT_ROOT, "scan_state.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {
            "scanning": False,
            "stocks": [],
            "liquidcount": 0,
            "oppcount": 0,
            "lastscan": "",
        }


@app.route("/")
def index():
    html_path = os.path.join(TEMPLATES_DIR, "enhanced_dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    return "Dashboard HTML not found", 404


@app.route("/api/bot/state", methods=["GET"])
def get_bot_state():
    return jsonify(bot_state)


@app.route("/api/bot/toggle", methods=["POST"])
def toggle_bot():
    data = request.get_json(silent=True) or {}
    running = data.get("running")
    if isinstance(running, bool):
        bot_state["running"] = running
    return jsonify(bot_state)


@app.route("/api/optimizer/state", methods=["GET"])
def get_optimizer_state():
    return jsonify(optimizer_state)


@app.route("/api/scan-state", methods=["GET"])
def api_scan_state():
    return jsonify(read_scan_state())


@app.route("/api/summary", methods=["GET"])
def api_summary():
    engine = get_engine()
    with get_session() as session:
        snap = (
            session.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.timestamp.desc())
            .first()
        )
        cash   = float(snap.cash)   if snap else float(engine.cash)
        equity = float(snap.equity) if snap else float(engine.cash)

        positions = session.query(Position).filter(Position.quantity != 0).all()
        unrealized = sum(float(p.unrealized_pnl or 0.0) for p in positions)
        realized   = sum(float(p.realized_pnl   or 0.0) for p in positions)
        total_pnl  = unrealized + realized
        long_count  = sum(1 for p in positions if p.quantity > 0)
        short_count = sum(1 for p in positions if p.quantity < 0)
        net_exposure = sum(p.quantity * p.avg_price for p in positions)

        # Segment-wise unrealized for open positions
        intraday_unrealized = sum(
            float(p.unrealized_pnl or 0.0)
            for p in positions
            if (p.segment or settings.SEGMENT_INTRADAY) == settings.SEGMENT_INTRADAY
        )
        swing_unrealized = sum(
            float(p.unrealized_pnl or 0.0)
            for p in positions
            if (p.segment or settings.SEGMENT_INTRADAY) == settings.SEGMENT_SWING
        )

        closed = [
            t
            for t in session.query(Trade).all()
            if t.side in ("SELL", "COVER") and t.pnl is not None
        ]
        wins   = [t.pnl for t in closed if t.pnl > 0]
        losses = [t.pnl for t in closed if t.pnl <= 0]
        win_rate      = round(len(wins) / len(closed) * 100, 1) if closed else 0.0
        best_trade    = float(max((t.pnl for t in closed), default=0.0))
        worst_trade   = float(min((t.pnl for t in closed), default=0.0))
        total_trades  = len(closed)
        gross_profit  = sum(wins)
        gross_loss    = abs(sum(losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0

    starting    = float(settings.INITIAL_CAPITAL or 1.0)
    returns_pct = (equity - starting) / starting * 100.0
    mis_limit   = float(settings.INITIAL_CAPITAL * settings.INTRADAY_MARGIN_MULTIPLIER)

    return jsonify(
        {
            "equity": equity,
            "cash": cash,
            "unrealized_pnl": unrealized,
            "realized_pnl": realized,
            "total_pnl": total_pnl,
            "returns_pct": returns_pct,
            "positions_count": len(positions),
            "long_count": long_count,
            "short_count": short_count,
            "net_exposure": net_exposure,
            "mis_limit": mis_limit,
            "win_rate": win_rate,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "total_trades": total_trades,
            "profit_factor": profit_factor,
            # Segment-wise open unrealized P&L
            "intraday_unrealized_pnl": intraday_unrealized,
            "swing_unrealized_pnl": swing_unrealized,
        }
    )


@app.route("/api/positions", methods=["GET"])
def api_positions():
    engine = get_engine()
    with get_session() as session:
        rows = session.query(Position).filter(Position.quantity != 0).all()
        if not rows:
            return jsonify([])

        ltp_data = {}
        if hasattr(engine, "kite") and engine.kite is not None:
            try:
                symbols = [f"NSE:{p.symbol}" for p in rows]
                ltp_data = engine.kite.ltp(symbols)
            except Exception as e:
                print(f"[DASHBOARD] LTP fetch error: {e}")
                ltp_data = {}

        result = []
        for p in rows:
            ltp = float(
                ltp_data.get(f"NSE:{p.symbol}", {}).get("last_price", p.avg_price or 0.0)
            )
            qty = int(p.quantity)
            avg = float(p.avg_price or 0.0)
            direction = "LONG" if qty > 0 else "SHORT"
            segment = p.segment or settings.SEGMENT_INTRADAY

            if ltp_data:
                unreal = (ltp - avg) * qty if qty > 0 else (avg - ltp) * abs(qty)
            else:
                unreal = float(p.unrealized_pnl or 0.0)

            pnl_pct = 0.0
            if avg != 0:
                pnl_pct = (
                    (ltp - avg) / avg * 100.0
                    if qty > 0
                    else (avg - ltp) / avg * 100.0
                )

            result.append(
                {
                    "symbol": p.symbol,
                    "direction": direction,
                    "qty": abs(qty),
                    "avg_price": avg,
                    "ltp": ltp,
                    "unrealized_pnl": unreal,
                    "pnl_pct": round(pnl_pct, 2),
                    "notional": abs(qty) * ltp,
                    "segment": segment,
                }
            )
    return jsonify(result)


@app.route("/api/trades", methods=["GET"])
def api_trades():
    limit = request.args.get("limit", 50, type=int)
    with get_session() as session:
        trades = (
            session.query(Trade)
            .order_by(Trade.timestamp.desc())
            .limit(limit)
            .all()
        )
        return jsonify(
            [
                {
                    "time": t.timestamp.strftime("%H:%M:%S"),
                    "symbol": t.symbol,
                    "side": t.side,
                    "qty": int(t.quantity),
                    "price": float(t.price),
                    "pnl": float(t.pnl or 0.0),
                    # Could add "segment": t.segment here later if needed.
                }
                for t in trades
            ]
        )


@app.route("/api/reset-paper", methods=["POST"])
def api_reset_paper():
    engine = get_engine()
    with get_session() as session:
        session.query(Trade).delete()
        session.query(Position).delete()
        session.query(PortfolioSnapshot).delete()
    engine.cash = float(settings.INITIAL_CAPITAL)
    return jsonify({"status": "ok", "cash": engine.cash})


@app.route("/api/portfolio-history", methods=["GET"])
def api_portfolio_history():
    """Returns last N equity snapshots for the equity curve chart."""
    limit = request.args.get("limit", 100, type=int)
    with get_session() as session:
        snaps = (
            session.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.timestamp.asc())
            .limit(limit)
            .all()
        )
        return jsonify(
            [
                {
                    "time": s.timestamp.strftime("%H:%M:%S"),
                    "equity": float(s.equity),
                    "cash": float(s.cash),
                }
                for s in snaps
            ]
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.DASHBOARD_PORT, debug=False)