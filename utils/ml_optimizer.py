"""
PRIMA PRO — ML Optimizer
File: utils/ml_optimizer.py   (new file, drop into utils/ folder)

Reads your existing Trade DB table — no new tables needed.
Scores every strategy using:  score = win_rate × profit_factor  (clamped 0.1–2.0)
Writes results to weights.json in project root.
Also enforces max daily loss circuit-breaker.

Run standalone to test:  python utils/ml_optimizer.py
"""

import json
import logging
import os
from datetime import date, datetime

from sqlalchemy import func

from config import settings
from data.database import Trade, get_session

WEIGHTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weights.json"
)

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def load_weights() -> dict:
    try:
        with open(WEIGHTS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("weights.json not found — using defaults")
        return _default_weights()


def save_weights(w: dict):
    w["last_updated"] = datetime.now().isoformat(timespec="seconds")
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(w, f, indent=2)
    logger.info("weights.json saved")


def _default_weights() -> dict:
    return {
        "version": 1,
        "last_updated": None,
        "optimizer_enabled": False,
        "strategy_weights": {
            s: {"score": 1.0, "trades": 0, "wins": 0, "losses": 0}
            for s in ["VWAPMOMENTUM", "RSIREVERSAL", "MACDMOMENTUM",
                      "BOLLINGERREVERSAL", "EMACROSSOVER", "SUPERTREND",
                      "VOLUMEBREAKOUT", "ATRBREAKOUT", "HOLD"]
        },
        "market_condition_weights": {},
        "indicator_thresholds": {
            "rsi_oversold": 30, "rsi_overbought": 70, "min_signal_strength": 3,
            "atr_multiplier_sl": 1.5, "atr_multiplier_tp": 3.0,
        },
        "risk_limits": {
            "max_drawdown_pct": 2.0, "max_daily_loss_pct": 2.0,
            "position_size_pct": 2.0, "max_concurrent_positions": 10,
        },
    }


# ── bot-facing helpers (imported in main.py) ──────────────────────────────────

def get_strategy_score(strategy_name: str) -> float:
    """Returns learned score. 1.0 = neutral. <0.4 = suppress. >1.5 = boost."""
    w = load_weights()
    if not w.get("optimizer_enabled", False):
        return 1.0  # optimizer off → always allow
    return w.get("strategy_weights", {}).get(strategy_name, {}).get("score", 1.0)


def is_daily_halted() -> tuple:
    """Returns (halted: bool, reason: str). Call once per scan cycle in main.py."""
    w = load_weights()
    if not w.get("optimizer_enabled", False):
        return False, ""
    try:
        with get_session() as session:
            daily_pnl = (
                session.query(func.sum(Trade.pnl))
                .filter(func.date(Trade.timestamp) == date.today())
                .filter(Trade.pnl.isnot(None))
                .scalar() or 0.0
            )
        limit = -(settings.INITIAL_CAPITAL * w["risk_limits"]["max_daily_loss_pct"] / 100)
        if float(daily_pnl) <= limit:
            return True, f"Daily loss ₹{daily_pnl:.2f} hit limit ₹{limit:.2f}"
    except Exception as e:
        logger.error(f"is_daily_halted error: {e}")
    return False, ""


# ── main optimizer class ──────────────────────────────────────────────────────

class MLOptimizer:

    def __init__(self):
        self.weights = load_weights()
        self.initial_capital = settings.INITIAL_CAPITAL

    def run(self) -> dict:
        logger.info("MLOptimizer: starting pass")
        all_trades   = self._fetch_all_trades()
        today_trades = self._fetch_today_trades()

        if not all_trades:
            logger.info("MLOptimizer: no closed trades yet — nothing to learn from")
            return {"status": "no_trades", "halted": False}

        # ── circuit-breaker ───────────────────────────────────────────────────
        halted, reason = self._check_daily_loss(today_trades)
        if halted:
            self.weights["optimizer_enabled"] = False
            save_weights(self.weights)
            logger.warning(f"MLOptimizer HALTED: {reason}")
            return {"status": "halted", "reason": reason, "halted": True}

        # ── per-strategy scoring ──────────────────────────────────────────────
        stats = {}
        for t in all_trades:
            # Trade table stores strategy name — fall back to VWAPMOMENTUM if missing
            key = getattr(t, "strategy", None) or "VWAPMOMENTUM"
            if key not in stats:
                stats[key] = {"trades": 0, "wins": 0, "losses": 0,
                               "gross_profit": 0.0, "gross_loss": 0.0}
            s = stats[key]
            s["trades"] += 1
            if t.pnl > 0:
                s["wins"] += 1
                s["gross_profit"] += t.pnl
            else:
                s["losses"] += 1
                s["gross_loss"] += t.pnl

        for strategy, s in stats.items():
            if s["trades"] < 3:
                continue  # not enough data yet
            win_rate      = s["wins"] / s["trades"]
            profit_factor = (s["gross_profit"] / abs(s["gross_loss"])
                             if s["gross_loss"] != 0 else 2.0)
            new_score = round(min(2.0, max(0.1, win_rate * profit_factor)), 3)

            if strategy not in self.weights["strategy_weights"]:
                self.weights["strategy_weights"][strategy] = {
                    "score": 1.0, "trades": 0, "wins": 0, "losses": 0
                }
            sw = self.weights["strategy_weights"][strategy]
            sw.update(score=new_score, trades=s["trades"],
                      wins=s["wins"], losses=s["losses"])
            logger.info(
                f"  {strategy:<22} score={new_score:.3f}  "
                f"WR={win_rate*100:.1f}%  PF={profit_factor:.2f}  n={s['trades']}"
            )

        self.weights["optimizer_enabled"] = True
        save_weights(self.weights)

        total      = len(all_trades)
        total_wins = sum(1 for t in all_trades if t.pnl and t.pnl > 0)
        total_pnl  = sum(t.pnl for t in all_trades if t.pnl)

        return {
            "status":        "optimized",
            "halted":        False,
            "total_trades":  total,
            "win_rate":      round(total_wins / total * 100, 2) if total else 0,
            "total_pnl":     round(total_pnl, 2),
            "strategies":    {
                k: {"score": v["score"], "trades": v["trades"]}
                for k, v in self.weights["strategy_weights"].items()
            },
        }

    # ── DB helpers ────────────────────────────────────────────────────────────
    def _fetch_all_trades(self):
        with get_session() as session:
            return session.query(Trade).filter(Trade.pnl.isnot(None)).all()

    def _fetch_today_trades(self):
        with get_session() as session:
            return (
                session.query(Trade)
                .filter(func.date(Trade.timestamp) == date.today())
                .filter(Trade.pnl.isnot(None))
                .all()
            )

    def _check_daily_loss(self, today_trades):
        if not today_trades:
            return False, ""
        daily_pnl = sum(t.pnl for t in today_trades if t.pnl)
        limit = -(self.initial_capital
                  * self.weights["risk_limits"]["max_daily_loss_pct"] / 100)
        if daily_pnl <= limit:
            return True, f"Daily loss ₹{daily_pnl:.2f} hit limit ₹{limit:.2f}"
        return False, ""


# ── standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    result = MLOptimizer().run()
    print(json.dumps(result, indent=2))
