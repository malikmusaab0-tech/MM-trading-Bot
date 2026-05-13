import logging
import requests
from typing import Dict, Optional
from datetime import datetime, time, date
from data.database import get_session, Position, Trade
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Margin Cache — fetches per-security margin from NSE VaR file or Kite API
# ---------------------------------------------------------------------------

_DEFAULT_MARGIN_RATE = 1.0  # 100% margin = 1x leverage (safe fallback)
_NSE_VAR_URL = "https://nsearchives.nseindia.com/archives/nsccl/var/C_VAR1_0_6.DAT"


class MarginCache:
    """
    Loads per-symbol margin rates once per session.
    Primary : NSE VaR+ELM daily file (no broker auth needed).
    Fallback : Conservative 1x (100% margin) for any symbol not found.
    """

    def __init__(self):
        self._cache: Dict[str, float] = {}    # symbol -> margin rate (0.0–1.0)
        self._loaded_date: Optional[date] = None

    def _load_from_nse(self) -> bool:
        try:
            resp = requests.get(
                _NSE_VAR_URL,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            for line in resp.text.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 4:
                    continue
                sym = parts[0].upper()
                try:
                    rate = float(parts[3]) / 100.0
                    if sym and rate > 0:
                        self._cache[sym] = min(rate, 1.0)
                except ValueError:
                    continue
            logger.info("[MARGIN] NSE VaR file: loaded %d symbols", len(self._cache))
            return bool(self._cache)
        except Exception as e:
            logger.warning("[MARGIN] NSE VaR load failed: %s", e)
            return False

    def load(self):
        """Call once at session start (or auto-triggered on first use)."""
        today = date.today()
        if self._loaded_date == today:
            return  # already fresh for today
        self._cache.clear()
        if not self._load_from_nse():
            logger.error(
                "[MARGIN] NSE source failed — all symbols use %.0f%% margin fallback",
                _DEFAULT_MARGIN_RATE * 100,
            )
        self._loaded_date = today

    def get_margin_rate(self, symbol: str) -> float:
        """Returns margin rate fraction e.g. 0.20 means 20% margin = 5x leverage."""
        if self._loaded_date != date.today():
            self.load()
        rate = self._cache.get(symbol.upper(), _DEFAULT_MARGIN_RATE)
        return max(0.05, min(rate, 1.0))  # clamp: min 5% (20x cap), max 100%

    def get_leverage(self, symbol: str) -> float:
        """Returns leverage multiplier e.g. 5.0 for 20% margin."""
        return 1.0 / self.get_margin_rate(symbol)


# Module-level singleton — swap dhan client when going live
_margin_cache = MarginCache()


def set_dhan_client(dhan):
    """We don't use margin API directly from Dhan for now, fallback to NSE."""
    global _margin_cache
    _margin_cache = MarginCache()


# ---------------------------------------------------------------------------
# RiskManager
# ---------------------------------------------------------------------------

class RiskManager:
    def __init__(self):
        self.trailing_stops: Dict[str, float]  = {}
        self.position_high_prices: Dict[str, float] = {}
        self.position_low_prices: Dict[str, float]  = {}
        self.stop_losses: Dict[str, float]     = {}
        self.take_profits: Dict[str, float]    = {}
        self.short_flags: Dict[str, bool]      = {}

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        atr: float,
        available_capital: float, # Note: this should be the total account cash, we apply segment allocation inside
        margin_multiplier: Optional[float] = None,  # kept for back-compat / test overrides
        segment: str = settings.SEGMENT_INTRADAY
    ) -> int:

        # Determine allocated capital for the segment
        if segment == settings.SEGMENT_INTRADAY:
            allocated_capital = available_capital * getattr(settings, 'ALLOCATION_INTRADAY', 1.0)
        elif segment == settings.SEGMENT_SWING:
            allocated_capital = available_capital * getattr(settings, 'ALLOCATION_SWING', 1.0)
        elif segment == settings.SEGMENT_LONGTERM:
            allocated_capital = available_capital * getattr(settings, 'ALLOCATION_LONGTERM', 1.0)
        else:
            allocated_capital = available_capital

        # ── Per-security leverage ────────────────────────────────────────────
        if margin_multiplier is None:
            leverage = _margin_cache.get_leverage(symbol)
            logger.debug(
                "[MARGIN] %s  margin=%.1f%%  leverage=%.2fx",
                symbol,
                _margin_cache.get_margin_rate(symbol) * 100,
                leverage,
            )
        else:
            leverage = float(margin_multiplier)

        import math

        # ── Risk-based sizing (ATR / % stop) ────────────────────────────────
        # How many shares can we afford given our stop-loss risk budget?
        risk_per_share = max(
            atr * settings.STOP_LOSS_ATR_MULTIPLIER,
            entry_price * settings.STOP_LOSS_PCT / 100,
        )
        risk_capital  = allocated_capital * (settings.POSITION_SIZE_PCT / 100.0)
        risk_based_size  = int(risk_capital / max(risk_per_share, 0.01))

        # ── Capital-based sizing ──────────────────────────────────
        cap_based_size = math.floor(settings.MAX_POSITION_VALUE / entry_price)

        # ── Margin-based sizing ──────────────────────────────────
        max_notional = allocated_capital * settings.POSITION_SIZE_CAPITAL_PCT * leverage
        margin_based_size  = int(max_notional / entry_price)

        logger.debug(
            "[SIZE] %s  risk_size=%d  cap_size=%d  margin_size=%d  notional_margin_cap=Rs.%.0f  leverage=%.2fx",
            symbol, risk_based_size, cap_based_size, margin_based_size, max_notional, leverage,
        )

        final = min(risk_based_size, cap_based_size, margin_based_size)
        notional_value = final * entry_price

        if notional_value < settings.MIN_POSITION_SIZE:
            logger.warning(
                f"[SIZE VETO] {symbol} rejected. Computed notional Rs.{notional_value:,.0f} "
                f"is below MIN_POSITION_SIZE Rs.{settings.MIN_POSITION_SIZE:,.0f}. "
                f"(risk_size={risk_based_size}, cap_size={cap_based_size}, margin_size={margin_based_size})"
            )
            return 0

        logger.info(f"[SIZE OK] {symbol} qty={final} (notional: Rs.{notional_value:,.0f})")
        return max(1, final)

    # ------------------------------------------------------------------
    # Stop-loss / take-profit helpers
    # ------------------------------------------------------------------

    def set_stop_loss(self, symbol, entry_price, atr):
        dist = atr * settings.STOP_LOSS_ATR_MULTIPLIER
        self.stop_losses[symbol] = entry_price - dist
        self.position_high_prices[symbol] = entry_price
        self.short_flags[symbol] = False
        logger.info(f"{symbol} [LONG] SL={self.stop_losses[symbol]:.2f}")

    def set_take_profit(self, symbol, entry_price, atr):
        dist = atr * settings.TAKE_PROFIT_ATR_MULTIPLIER
        self.take_profits[symbol] = entry_price + dist
        logger.info(f"{symbol} [LONG] TP={self.take_profits[symbol]:.2f}")

    def set_short_stop_loss(self, symbol, entry_price, atr):
        dist = atr * settings.STOP_LOSS_ATR_MULTIPLIER
        self.stop_losses[symbol] = entry_price + dist
        self.position_low_prices[symbol] = entry_price
        self.short_flags[symbol] = True
        logger.info(f"{symbol} [SHORT] SL={self.stop_losses[symbol]:.2f}")

    def set_short_take_profit(self, symbol, entry_price, atr):
        dist = atr * settings.TAKE_PROFIT_ATR_MULTIPLIER
        self.take_profits[symbol] = entry_price - dist
        logger.info(f"{symbol} [SHORT] TP={self.take_profits[symbol]:.2f}")

    def update_trailing_stop(self, symbol, current_price, entry_price):
        is_short = self.short_flags.get(symbol, False)
        if is_short:
            profit_pct = (entry_price - current_price) / entry_price * 100
            if profit_pct < settings.TRAILING_STOP_ACTIVATION_PCT:
                return False
            self.position_low_prices[symbol] = min(
                self.position_low_prices.get(symbol, current_price), current_price
            )
            new_trail = self.position_low_prices[symbol] * (
                1 + settings.TRAILING_STOP_DISTANCE_PCT / 100
            )
            if symbol not in self.trailing_stops or new_trail < self.trailing_stops[symbol]:
                self.trailing_stops[symbol] = new_trail
                if symbol in self.stop_losses:
                    self.stop_losses[symbol] = min(self.stop_losses[symbol], new_trail)
        else:
            profit_pct = (current_price - entry_price) / entry_price * 100
            if profit_pct < settings.TRAILING_STOP_ACTIVATION_PCT:
                return False
            self.position_high_prices[symbol] = max(
                self.position_high_prices.get(symbol, current_price), current_price
            )
            new_trail = self.position_high_prices[symbol] * (
                1 - settings.TRAILING_STOP_DISTANCE_PCT / 100
            )
            if symbol not in self.trailing_stops or new_trail > self.trailing_stops[symbol]:
                old = self.trailing_stops.get(symbol, 0)
                self.trailing_stops[symbol] = new_trail
                if symbol in self.stop_losses:
                    self.stop_losses[symbol] = max(self.stop_losses[symbol], new_trail)
                logger.info(f"{symbol} Trailing {old:.2f}→{new_trail:.2f}")
                return True
        return False

    def check_stop_loss(self, symbol, current_price):
        if symbol not in self.stop_losses:
            return False
        sl       = self.stop_losses[symbol]
        is_short = self.short_flags.get(symbol, False)
        if is_short and current_price >= sl:
            logger.warning(f"{symbol} [SHORT] SL hit {current_price:.2f}>={sl:.2f}")
            return True
        if not is_short and current_price <= sl:
            logger.warning(f"{symbol} [LONG] SL hit {current_price:.2f}<={sl:.2f}")
            return True
        return False

    def check_trailing_stop(self, symbol, current_price):
        if symbol not in self.trailing_stops:
            return False
        tsl      = self.trailing_stops[symbol]
        is_short = self.short_flags.get(symbol, False)
        if is_short and current_price >= tsl:
            return True
        if not is_short and current_price <= tsl:
            return True
        return False

    def check_take_profit(self, symbol, current_price):
        if symbol not in self.take_profits:
            return False
        tp       = self.take_profits[symbol]
        is_short = self.short_flags.get(symbol, False)
        if is_short and current_price <= tp:
            logger.info(f"{symbol} [SHORT] TP hit {current_price:.2f}<={tp:.2f}")
            return True
        if not is_short and current_price >= tp:
            logger.info(f"{symbol} [LONG] TP hit {current_price:.2f}>={tp:.2f}")
            return True
        return False

    def should_close_position(self, symbol, current_price, entry_price):
        if self.check_stop_loss(symbol, current_price):     return True, "STOP_LOSS"
        if self.check_trailing_stop(symbol, current_price): return True, "TRAILING_STOP"
        if self.check_take_profit(symbol, current_price):   return True, "TAKE_PROFIT"
        if self.is_square_off_time():                        return True, "SQUARE_OFF_TIME"
        return False, ""

    def is_square_off_time(self):
        return datetime.now().time() >= time.fromisoformat(settings.SQUARE_OFF_TIME)

    # ------------------------------------------------------------------
    # Portfolio-level risk
    # ------------------------------------------------------------------

    def get_portfolio_risk(self):
        with get_session() as session:
            positions      = session.query(Position).filter(Position.quantity != 0).all()
            total_exposure = sum(abs(p.quantity) * p.avg_price for p in positions)
            margin_pct     = (
                total_exposure / settings.MAX_INTRADAY_EXPOSURE * 100
                if settings.MAX_INTRADAY_EXPOSURE else 0
            )
            return dict(
                total_positions=len(positions),
                total_exposure=total_exposure,
                margin_used_pct=margin_pct,
                unrealized_pnl=sum(p.unrealized_pnl for p in positions),
                realized_pnl=sum(p.realized_pnl for p in positions),
                at_max_positions=len(positions) >= settings.MAX_CONCURRENT_POSITIONS,
            )

    def can_open_new_position(self):
        m = self.get_portfolio_risk()
        if m["at_max_positions"]:      return False, "MAX_POSITIONS_REACHED"
        if m["margin_used_pct"] >= 95: return False, "MARGIN_LIMIT"
        if self.is_square_off_time():  return False, "SQUARE_OFF_TIME"
        return True, "OK"

    def cleanup_closed_position(self, symbol):
        for d in [
            self.stop_losses, self.trailing_stops, self.take_profits,
            self.position_high_prices, self.position_low_prices, self.short_flags,
        ]:
            d.pop(symbol, None)
        logger.info(f"{symbol} cleanup done")