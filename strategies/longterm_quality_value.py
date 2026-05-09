"""
Long-term investing strategy:

- Combines business quality + growth + valuation.
- Expects a 'fundamentals' dict per symbol, with keys like:
  pe, pb, roe, debt_to_equity, revenue_cagr, fair_value, current_price.
- Uses a simple scoring + margin-of-safety check to emit BUY / HOLD / SELL.
"""

from dataclasses import dataclass
from typing import Optional, Dict

from config import settings


@dataclass
class LongTermSignal:
    segment: str
    symbol: str
    action: str       # "BUY", "HOLD", "SELL"
    reason: str
    fair_value: float
    margin_of_safety_pct: float
    timeframe: str    # e.g. "3-5 years"


class LongTermQualityValueStrategy:
    def __init__(self):
        self.min_mos = settings.LONGTERM_MIN_MARGIN_OF_SAFETY_PCT
        self.overvalued_thresh = settings.LONGTERM_OVERVALUED_THRESHOLD_PCT

    def generate_signal(
        self,
        symbol: str,
        fundamentals: Dict[str, float],
    ) -> Optional[Dict]:
        """
        fundamentals keys (example):
            - pe
            - roe
            - debt_to_equity
            - revenue_cagr
            - fair_value
            - current_price
        """
        required = ["fair_value", "current_price"]
        if any(k not in fundamentals or fundamentals[k] is None for k in required):
            return None

        fv = float(fundamentals["fair_value"])
        price = float(fundamentals["current_price"])
        if fv <= 0 or price <= 0:
            return None

        mos_pct = (fv - price) / fv * 100.0

        # BUY: margin of safety high enough (cheap vs fair value)
        if mos_pct >= self.min_mos:
            return {
                "segment": settings.SEGMENT_LONGTERM,
                "symbol": symbol,
                "action": "BUY",
                "reason": f"Price at {price:.2f} is {mos_pct:.1f}% below fair value {fv:.2f}",
                "fair_value": fv,
                "margin_of_safety_pct": mos_pct,
                "timeframe": "3-5 years",
            }

        # SELL/trim: significantly over fair value
        overvalued_pct = (price - fv) / fv * 100.0
        if overvalued_pct >= self.overvalued_thresh:
            return {
                "segment": settings.SEGMENT_LONGTERM,
                "symbol": symbol,
                "action": "SELL",
                "reason": f"Price at {price:.2f} is {overvalued_pct:.1f}% above fair value {fv:.2f}",
                "fair_value": fv,
                "margin_of_safety_pct": mos_pct,
                "timeframe": "3-5 years",
            }

        # Else just HOLD
        return {
            "segment": settings.SEGMENT_LONGTERM,
            "symbol": symbol,
            "action": "HOLD",
            "reason": "Within fair value band",
            "fair_value": fv,
            "margin_of_safety_pct": mos_pct,
            "timeframe": "3-5 years",
        }