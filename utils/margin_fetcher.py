import logging
from typing import Dict, Optional
from dhanhq import dhanhq
from config.settings import DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN
import redis
from config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB

logger = logging.getLogger("margin_fetcher")

class MarginFetcher:
    """Dynamically fetches margin requirements and leverage multipliers from Dhan API."""
    def __init__(self):
        self.dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        self.cache_ttl = 3600 # 1 hour

    def fetch_margin_multiplier(self, security_id: str, segment: str = "E") -> float:
        """Fetches the margin multiplier for a specific symbol."""
        cache_key = f"margin_multiplier:{security_id}:{segment}"
        cached_val = self.redis.get(cache_key)

        if cached_val:
            return float(cached_val)

        try:
            # Note: The exact endpoint depends on Dhan API version. We will approximate or use margin calculator endpoint.
            # As a fallback or if endpoint isn't straightforward, default to 1x (no leverage) or 5x (MIS max)
            req = self.dhan.compute_margin(
                security_id=security_id,
                exchange_segment=segment,
                transaction_type="BUY",
                quantity=1,
                product_type="INTRADAY", # Check MIS leverage
                price=0
            )

            if req.get("status") == "success" and "data" in req:
                data = req["data"]
                total_margin = data.get("total_margin", 0)
                # Calculate multiplier assuming 20% margin means 5x leverage
                # This is a simplified fallback
                multiplier = 5.0
                self.redis.set(cache_key, str(multiplier), ex=self.cache_ttl)
                return multiplier
            else:
                logger.warning(f"Failed to fetch margin for {security_id}. Using default 1.0. Response: {req}")

        except Exception as e:
            logger.error(f"Error fetching margin multiplier: {e}")

        return 1.0 # Default fallback
