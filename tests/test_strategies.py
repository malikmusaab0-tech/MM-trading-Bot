import unittest
import pandas as pd
import numpy as np
from strategies.swing_strategy import SwingStrategy
from strategies.long_term_investing import LongTermInvestingStrategy

class TestStrategies(unittest.TestCase):
    def setUp(self):
        # Create a mock dataframe for testing
        dates = pd.date_range('2023-01-01', periods=250)
        close_prices = np.linspace(100, 200, 250) # Steady uptrend

        self.df_daily = pd.DataFrame({
            'open': close_prices - 1,
            'high': close_prices + 2,
            'low': close_prices - 2,
            'close': close_prices,
            'volume': np.random.randint(100000, 1000000, 250)
        }, index=dates)

        # Weekly aggregation mock
        self.df_weekly = self.df_daily.resample('W').last()

    def test_swing_strategy_gating(self):
        strat = SwingStrategy(capital=100000)

        # Test gating rule rejection
        signal = strat.generate_signal("TEST", self.df_daily, 0, df_weekly=self.df_weekly, macro_regime="CHOPPY")
        self.assertEqual(signal.action, "HOLD")
        self.assertIn("Macro regime is CHOPPY", signal.reason)

    def test_long_term_allocation(self):
        strat = LongTermInvestingStrategy(capital=100000)

        # Create universe
        universe = {
            "STOCK_A": self.df_daily, # Uptrend
            "STOCK_B": self.df_daily * 0.5 # Also uptrend but lower absolute values
        }

        # In this steady synthetic dataset, standard deviation of pct_change will be very close to 0,
        # which might cause division by zero. Let's inject some noise.
        noise_a = np.random.normal(0, 2, 250)
        noise_b = np.random.normal(0, 5, 250)
        universe["STOCK_A"]["close"] += noise_a
        universe["STOCK_B"]["close"] += noise_b

        allocations = strat.rank_and_allocate(universe, top_n=2)

        self.assertIsInstance(allocations, dict)
        if allocations: # Depending on the random noise, one or both might pass the filters
            self.assertAlmostEqual(sum(allocations.values()), 1.0, places=5)

if __name__ == '__main__':
    unittest.main()
