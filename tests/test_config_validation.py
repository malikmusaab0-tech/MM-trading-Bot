from config import settings
def test_config_mode_conflict():
    assert hasattr(settings, "LIVE_TRADING_MODE")
    assert hasattr(settings, "PAPER_TRADING_MODE")
