import pandas as pd
import numpy as np

class InvestingMomentumStrategy:
    """
    Investing strategy based on ranking Nifty 100 stocks
    by 6-month momentum and low volatility.
    """
    def __init__(self, momentum_months=6, top_n=10):
        self.momentum_months = momentum_months
        self.top_n = top_n

    def calculate_momentum_score(self, dfs: dict):
        """
        Expects a dict of DataFrames mapped by symbol,
        each containing daily historical 'close' prices.
        """
        scores = []
        for symbol, df in dfs.items():
            if df.empty or len(df) < self.momentum_months * 21: # Approx 21 trading days per month
                continue

            # 6-month return
            start_price = df['close'].iloc[-(self.momentum_months * 21)]
            end_price = df['close'].iloc[-1]
            momentum = (end_price - start_price) / start_price

            # Volatility (standard deviation of daily returns over 6 months)
            returns = df['close'].iloc[-(self.momentum_months * 21):].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252) # Annualized volatility

            # Simple combined score: High momentum, low volatility
            # We can rank by momentum / volatility (Sharpe-like ratio)
            if volatility > 0:
                score = momentum / volatility
            else:
                score = 0

            scores.append({
                'symbol': symbol,
                'momentum': momentum,
                'volatility': volatility,
                'score': score,
                'price': end_price
            })

        # Rank and get top N
        ranked = sorted(scores, key=lambda x: x['score'], reverse=True)[:self.top_n]
        return ranked
