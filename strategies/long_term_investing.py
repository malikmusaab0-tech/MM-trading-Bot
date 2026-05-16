import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy
import logging

logger = logging.getLogger(__name__)

class LongTermInvestingStrategy(BaseStrategy):
    """
    Institutional Multi-Factor Trend & Momentum alpha generation model (PRI-18)
    Designed for multi-month or quarterly rebalancing horizons.
    """

    def generate_signal(self, symbol, df, current_position_qty, entry_price=None, **kwargs):
        # This strategy is typically used as a portfolio screener/allocator,
        # but we implement standard signal generation interface for completeness.
        pass

    def rank_and_allocate(self, universe_data: dict[str, pd.DataFrame], top_n=30) -> dict[str, float]:
        """
        Calculates allocations across the universe based on momentum and volatility.

        - Universe: Expected to be pre-filtered Nifty 100 components.
        - Momentum Scoring: 60-day price momentum (40%) + 180-day price momentum (60%).
        - Trend Filter: Close > 200-day SMA.
        - Allocation: Proportional to (Momentum Score / 30-day Volatility).
        """
        scores = {}
        for symbol, df in universe_data.items():
            if len(df) < 200:
                logger.debug(f"{symbol}: Insufficient data for 200 SMA")
                continue

            close = df["close"]
            price_now = close.iloc[-1]
            sma_200 = close.rolling(200).mean().iloc[-1]

            # Trend Filter
            if price_now <= sma_200:
                logger.debug(f"{symbol}: Below 200 SMA, skipping")
                continue

            # Momentum Scores
            mom_60 = (price_now / close.iloc[-60] - 1) if len(close) >= 60 else 0
            mom_180 = (price_now / close.iloc[-180] - 1) if len(close) >= 180 else 0

            combined_momentum = (mom_60 * 0.4) + (mom_180 * 0.6)

            # 30-day Historical Volatility (standard deviation of daily returns)
            returns = close.pct_change().dropna()
            vol_30 = returns.tail(30).std() * np.sqrt(252) # Annualized

            if vol_30 <= 0:
                continue

            # Final Score
            risk_adjusted_score = combined_momentum / vol_30

            if risk_adjusted_score > 0:
                scores[symbol] = risk_adjusted_score

        if not scores:
            return {}

        # Select Top N
        sorted_symbols = sorted(scores, key=scores.get, reverse=True)[:top_n]

        # Calculate proportional weights
        total_score = sum(scores[sym] for sym in sorted_symbols)
        allocations = {sym: (scores[sym] / total_score) for sym in sorted_symbols}

        return allocations
