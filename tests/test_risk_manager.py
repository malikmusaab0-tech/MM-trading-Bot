import unittest
from unittest.mock import patch, MagicMock
from utils.risk_manager import RiskManager
from config import settings

class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager()
        # Mock settings to stable values for tests
        self.original_max_val = settings.MAX_POSITION_VALUE
        self.original_min_val = settings.MIN_POSITION_SIZE
        settings.MAX_POSITION_VALUE = 25000
        settings.MIN_POSITION_SIZE = 500
        settings.POSITION_SIZE_PCT = 5.0
        settings.STOP_LOSS_PCT = 1.5
        settings.STOP_LOSS_ATR_MULTIPLIER = 1.5

    def tearDown(self):
        settings.MAX_POSITION_VALUE = self.original_max_val
        settings.MIN_POSITION_SIZE = self.original_min_val

    @patch('utils.risk_manager._margin_cache')
    def test_calculate_position_size(self, mock_cache):
        # Mock margin cache to return leverage of 5
        mock_cache.get_leverage.return_value = 5.0
        mock_cache.get_margin_rate.return_value = 0.2

        # Test case: Standard acceptable size
        # entry=1000, max_val=25000 -> cap_size = 25
        qty = self.rm.calculate_position_size("RELIANCE", 1000.0, 10.0, 100000.0)
        self.assertEqual(qty, 25)

        # Test case: Minimum position size check
        # entry=10, max_val=25000 -> cap_size = 2500
        # If ATR risk is extremely high, risk_size is low
        # But if total value is < 500, it should return 0
        qty2 = self.rm.calculate_position_size("PENNY", 10.0, 5.0, 100000.0)
        # cap_size = 2500,
        # risk_size = int(((100000 * 0.5) * 0.05) / 7.5) = int(2500 / 7.5) = 333
        # margin_size = int((100000 * 0.5 * 5.0) / 10) = 25000
        # final = min(2500, 333, 25000) = 333 -> 333 * 10 = 3330 > 500 -> ok
        self.assertEqual(qty2, 333)

        # Test extreme risk blocking
        # ATR=500 -> risk_per_share = 750
        # risk_size = int(5000 / 750) = 6
        # 6 * 10 = 60 < 500 -> blocked
        qty3 = self.rm.calculate_position_size("PENNY2", 10.0, 500.0, 100000.0)
        self.assertEqual(qty3, 0)

if __name__ == '__main__':
    unittest.main()
