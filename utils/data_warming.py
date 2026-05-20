import logging
import redis
import json
from datetime import datetime, timedelta
from dhanhq import dhanhq
from utils.dhan_helper import dhan_helper
from utils.rate_limiter import retry_with_backoff
from utils.nifty_100_symbols import NIFTY_100_SYMBOLS
from config import settings

logger = logging.getLogger(__name__)

def warm_data(dhan: dhanhq, r: redis.Redis):
    """
    Fetches the last 100 5-min and daily candles for the Nifty 100 universe
    and caches them in Redis Lists to prevent 'Regime Unknown' errors on boot.
    """
    logger.info("Starting Data Warming Routine...")

    to_dt = datetime.now()
    # Fetch enough days back to guarantee 100 5-min candles (approx 2-3 trading days)
    # and 100 daily candles (approx 150 calendar days)
    from_dt_5min = to_dt - timedelta(days=5)
    from_dt_daily = to_dt - timedelta(days=150)

    for symbol in NIFTY_100_SYMBOLS:
        sec_id = dhan_helper.get_security_id(symbol)
        if not sec_id:
            continue

        try:
            # 1. Warm 5-min candles
            @retry_with_backoff(retries=3)
            def _fetch_5min():
                return dhan.historical_minute_charts(
                    symbol=sec_id,
                    exchange_segment='NSE_EQ',
                    instrument_type='EQUITY',
                    expiry_code=0,
                    from_date=from_dt_5min.strftime('%Y-%m-%d'),
                    to_date=to_dt.strftime('%Y-%m-%d')
                )

            data_5min = _fetch_5min()

            if data_5min and data_5min.get('data'):
                # Extract the actual historical records
                records = data_5min['data']
                # Dhan API returns lists per field. We need to zip them or store them.
                # Actually, according to docs, historical charts return dict of lists:
                # {'open': [], 'high': [], 'low': [], 'close': [], 'volume': [], 'start_Time': []}
                # Let's verify and process this properly.

                # We will store them as a JSON string of the dataframe in Redis or as lists.
                # The prompt requested Redis Lists for rolling indicators.

                # Delete existing list first
                r.delete(f"historical:5min:{symbol}:close")
                r.delete(f"historical:5min:{symbol}:volume")
                r.delete(f"historical:5min:{symbol}:high")
                r.delete(f"historical:5min:{symbol}:low")

                closes = records.get('close', [])[-100:]
                volumes = records.get('volume', [])[-100:]
                highs = records.get('high', [])[-100:]
                lows = records.get('low', [])[-100:]

                if closes:
                    r.rpush(f"historical:5min:{symbol}:close", *closes)
                if volumes:
                    r.rpush(f"historical:5min:{symbol}:volume", *volumes)
                if highs:
                    r.rpush(f"historical:5min:{symbol}:high", *highs)
                if lows:
                    r.rpush(f"historical:5min:{symbol}:low", *lows)

            # 2. Warm Daily candles
            @retry_with_backoff(retries=3)
            def _fetch_daily():
                return dhan.historical_daily_data(
                    symbol=sec_id,
                    exchange_segment='NSE_EQ',
                    instrument_type='EQUITY',
                    expiry_code=0,
                    from_date=from_dt_daily.strftime('%Y-%m-%d'),
                    to_date=to_dt.strftime('%Y-%m-%d')
                )

            data_daily = _fetch_daily()

            if data_daily and data_daily.get('data'):
                records = data_daily['data']

                r.delete(f"historical:daily:{symbol}:close")
                r.delete(f"historical:daily:{symbol}:volume")
                r.delete(f"historical:daily:{symbol}:high")
                r.delete(f"historical:daily:{symbol}:low")

                closes = records.get('close', [])[-100:]
                volumes = records.get('volume', [])[-100:]
                highs = records.get('high', [])[-100:]
                lows = records.get('low', [])[-100:]

                if closes:
                    r.rpush(f"historical:daily:{symbol}:close", *closes)
                if volumes:
                    r.rpush(f"historical:daily:{symbol}:volume", *volumes)
                if highs:
                    r.rpush(f"historical:daily:{symbol}:high", *highs)
                if lows:
                    r.rpush(f"historical:daily:{symbol}:low", *lows)

        except Exception as e:
            logger.error(f"Error warming data for {symbol}: {e}")

    logger.info("Data Warming Routine completed.")
