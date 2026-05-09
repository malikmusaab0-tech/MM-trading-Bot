import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def retry_with_backoff(retries=3, backoff_in_seconds=1, backoff_factor=2):
    """
    Retry a function with exponential backoff if it fails.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Rate limit or API error
                    if x == retries:
                        logger.error(f"Failed after {retries} retries: {e}")
                        raise
                    sleep = (backoff_in_seconds * (backoff_factor ** x))
                    logger.warning(f"Error '{e}'. Retrying in {sleep} seconds...")
                    time.sleep(sleep)
                    x += 1
        return wrapper
    return decorator
