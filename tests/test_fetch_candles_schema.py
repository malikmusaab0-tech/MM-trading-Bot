import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from main import fetch_candles

@patch('redis.Redis')
def test_fetch_candles_returns_full_ohlcv(mock_redis):
    mock_instance = MagicMock()
    mock_redis.return_value = mock_instance
    mock_instance.lrange.side_effect = lambda key, start, end: ['10', '11']
    df = fetch_candles(MagicMock(), 'NIFTY', mock_instance)
    assert {'open', 'high', 'low', 'close', 'volume'}.issubset(set(df.columns))
    assert len(df) == 2
