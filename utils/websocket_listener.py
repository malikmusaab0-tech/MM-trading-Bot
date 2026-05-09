import logging
import redis
import json
import time
from dhanhq import marketfeed
from config import settings
from utils.auth import get_dhan_client, load_access_token
from utils.dhan_helper import dhan_helper

logger = logging.getLogger(__name__)

# Basic config
client_id = settings.DHAN_CLIENT_ID
access_token = load_access_token()

r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)

instruments = []
from utils.nifty_100_symbols import NIFTY_100_SYMBOLS
for symbol in NIFTY_100_SYMBOLS:
    sec_id = dhan_helper.get_security_id(symbol)
    if sec_id:
        instruments.append((marketfeed.NSE, str(sec_id)))

def on_connect(instance):
    logger.info("Connected to Dhan WebSocket.")

def on_message(instance, message):
    if 'LTP' in message:
        # According to dhanhq python package documentation, it parses messages into dicts
        sec_id = str(message.get('security_id'))
        ltp = float(message.get('LTP', 0))
        # Volume might not be in every feed type, need to handle appropriately
        # Fallback to tick volume or just keep LTP for now

        symbol = dhan_helper.get_symbol(sec_id)
        if symbol:
            state = {
                "ltp": ltp,
                "timestamp": time.time()
            }
            # Add volume if it exists
            if 'volume' in message:
                 state['volume'] = message['volume']

            # Push to Redis
            r.hset(f"live_state:{symbol}", mapping=state)

def on_error(instance, error):
    logger.error(f"Dhan WebSocket error: {error}")

def on_close(instance):
    logger.info("Dhan WebSocket closed.")

def start_websocket():
    if not instruments:
        logger.warning("No instruments to subscribe to. Please check dhan_helper logic.")
        return

    try:
        ws = marketfeed.DhanFeed(
            client_id,
            access_token,
            instruments,
            marketfeed.Ticker,
            on_connect=on_connect,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.connect()
    except Exception as e:
         logger.error(f"WebSocket execution failed: {e}")

if __name__ == "__main__":
    start_websocket()
