from utils.market_scanner import MarketScanner
from unittest.mock import MagicMock, patch

def test_liquid_stocks_cache():
    scanner = MarketScanner(MagicMock())
    scanner.instruments = ['A', 'B']

    with patch('utils.market_scanner.time.sleep') as mock_sleep:
        scanner.dhan_helper.get_security_id = MagicMock(return_value="123")
        scanner.dhan.historical_daily_data = MagicMock(return_value={'data': {'close': [100]*10, 'volume': [10000000]*10}})

        res1 = scanner.get_liquid_stocks()
        calls_after_first = mock_sleep.call_count

        res2 = scanner.get_liquid_stocks()
        calls_after_second = mock_sleep.call_count

        assert calls_after_first > 0
        assert calls_after_second == calls_after_first
