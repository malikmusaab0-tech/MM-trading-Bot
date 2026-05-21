import logging
import redis
import time
import asyncio
from dhanhq import marketfeed
from config import settings
from utils.auth import load_access_token
from utils.dhan_helper import dhan_helper

logger = logging.getLogger(__name__)

client_id = settings.DHAN_CLIENT_ID
access_token = load_access_token()

r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)

instruments = []
from utils.nifty_100_symbols import NIFTY_100_SYMBOLS
for symbol in NIFTY_100_SYMBOLS:
    sec_id = dhan_helper.get_security_id(symbol)
    if sec_id:
        # Tuple format: (exchange_segment, security_id, ticker_type)
        instruments.append((marketfeed.NSE, str(sec_id), marketfeed.Ticker))


async def fetch_and_process_loop(ws):
    while True:
        try:
            # We bypass get_data() because it creates a new loop running event which raises "Event loop already running"
            # Instead we use the internal async methods
            data = await ws.get_instrument_data()
            if data and data.get('type') == 'Ticker Data':
                sec_id = str(data.get('security_id'))
                ltp = float(data.get('LTP', 0))

                symbol = dhan_helper.get_symbol(sec_id)
                if symbol:
                    state = {
                        "ltp": ltp,
                        "timestamp": time.time()
                    }
                    if 'volume' in data:
                         state['volume'] = data['volume']
                    if 'open' in data:
                         state['open'] = data['open']
                    if 'high' in data:
                         state['high'] = data['high']
                    if 'low' in data:
                         state['low'] = data['low']

                    r.hset(f"live_state:{symbol}", mapping=state)
        except Exception as e:
            logger.error(f"Dhan WebSocket message processing error: {e}")
            await asyncio.sleep(1)


def start_websocket():
    if not instruments:
        logger.warning("No instruments to subscribe to. Please check dhan_helper logic.")
        return

    try:
        # DhanHQ 1.3.3 DhanFeed initialization
        ws = marketfeed.DhanFeed(
            client_id,
            access_token,
            instruments
        )

        async def main_loop():
            await ws.connect()
            logger.info("Connected to Dhan WebSocket.")
            await fetch_and_process_loop(ws)

        asyncio.run(main_loop())

    except Exception as e:
         logger.error(f"WebSocket execution failed: {e}")

if __name__ == "__main__":
    start_websocket()
