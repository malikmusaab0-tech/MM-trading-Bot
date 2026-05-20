import sys
import logging
from config import settings

logger = logging.getLogger(__name__)

def validate_config():
    """
    Validates essential configuration parameters on startup to fail fast.
    """
    logger.info("Running Configuration Startup Validation...")

    # 1. Validate required env vars
    required_vars = ["DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN"]
    missing = [var for var in required_vars if not getattr(settings, var) or getattr(settings, var) == "dummy_client_id" or getattr(settings, var) == "dummy_access_token"]

    if missing:
        logger.warning(f"Missing or dummy required environment variables: {missing}. Ensure you have a proper .env file.")

    # 2. Validate Capital Allocations sum to <= 1.0
    total_allocation = getattr(settings, 'ALLOCATION_INTRADAY', 0) + getattr(settings, 'ALLOCATION_SWING', 0) + getattr(settings, 'ALLOCATION_LONGTERM', 0)
    if total_allocation > 1.0:
        logger.critical(f"CRITICAL: Segment capital allocations sum to {total_allocation}, which is > 1.0. Please check ALLOCATION_INTRADAY, ALLOCATION_SWING, ALLOCATION_LONGTERM in settings.py.")
        sys.exit(1)

    # 3. Validate Sizing Constraints
    min_pos = getattr(settings, 'MIN_POSITION_SIZE', 0)
    max_pos = getattr(settings, 'MAX_POSITION_VALUE', 0)

    if min_pos >= max_pos:
        logger.critical(f"CRITICAL: MIN_POSITION_SIZE ({min_pos}) is >= MAX_POSITION_VALUE ({max_pos}). Please correct this in settings.py.")
        sys.exit(1)

    logger.info("Configuration Startup Validation passed.")
