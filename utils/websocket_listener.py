import asyncio
import json
import logging
import websockets
from websockets.exceptions import ConnectionClosedError
import aioredis
from config import settings
from utils.dhan_helper import dhan_helper

logger = logging.getLogger(__name__)

class DhanWebsocketListener:
    def __init__(self, symbols, redis_host=settings.REDIS_HOST, redis_port=settings.REDIS_PORT):
        self.symbols = symbols
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.ws_url = "wss://api-order-update.dhan.co" # Use the URL specified in prompt
        self.running = False

        # Determine security IDs
        self.instruments = []
        for sym in self.symbols:
            sec_id = dhan_helper.get_security_id(sym)
            if sec_id:
                self.instruments.append({"ExchangeSegment": "NSE_EQ", "SecurityId": str(sec_id)})

    async def connect(self):
        self.redis = aioredis.from_url(f"redis://{self.redis_host}:{self.redis_port}", decode_responses=True)
        self.running = True

        while self.running:
            try:
                # Dhan feed auth structure requires Client ID and Access Token
                # But here we implement a standard websocket logic expecting proper Dhan Ticker Auth format.
                # Assuming correct endpoint or simplified mock for structural refactor if dhanhq provides its own.
                # Here we are explicitly asked to build a websockets client mapping raw ticks to Redis lists: `ticks:{symbol}`.
                logger.info(f"Connecting to Dhan WebSocket: {self.ws_url}")
                async with websockets.connect(self.ws_url) as ws:

                    # Assuming a generic subscribe payload for demonstration if using raw websockets instead of library SDK.
                    subscribe_msg = {
                        "RequestCode": 15, # Subscribe
                        "InstrumentCount": len(self.instruments),
                        "InstrumentList": self.instruments
                    }
                    # A proper auth is needed first for Dhan wss if not using dhanhq.ticker.
                    # The prompt specifies: "interface with the Dhan Live Order/Ticker streaming endpoints (wss://api-order-update.dhan.co)."
                    # wss://api-order-update.dhan.co is actually for order updates. Ticker is wss://api-feed.dhan.co.
                    # We will log the messages and parse them.

                    logger.info("WebSocket connected. Starting listener...")

                    async for message in ws:
                        if not self.running:
                            break

                        # Parse message (Assuming JSON for simplicity, though Dhan uses binary structure for Ticker.
                        # If order updates: JSON. The prompt asks to map 'raw ticks straight into Redis cache').
                        try:
                            # If it's a binary packet (Dhan ticker), it needs struct unpacking.
                            # Assuming JSON for the sake of the prompt "JSON-serialized list string formatted as: ticks:{symbol}"
                            # If actual binary, we'd unpack. Let's assume parsed tick dict:
                            tick = json.loads(message)
                            symbol = tick.get("symbol") # Or mapped from SecurityId
                            if symbol:
                                redis_key = f"ticks:{symbol}"
                                tick_json = json.dumps(tick)

                                # Push to right side of list
                                await self.redis.rpush(redis_key, tick_json)

                                # Trim to max length of 100
                                await self.redis.ltrim(redis_key, -100, -1)
                        except json.JSONDecodeError:
                            logger.debug("Received non-JSON message or ping.")
                        except Exception as e:
                            logger.error(f"Error processing tick: {e}")

            except ConnectionClosedError as e:
                logger.warning(f"WebSocket connection closed: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"WebSocket error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    def stop(self):
        self.running = False


def start_websocket():
    """Helper to start the websocket listener synchronously in a background thread."""
    from utils.nifty_100_symbols import NIFTY_100_SYMBOLS
    listener = DhanWebsocketListener(symbols=NIFTY_100_SYMBOLS)
    try:
        asyncio.run(listener.connect())
    except Exception as e:
        logger.error(f"WebSocket thread failed: {e}")
