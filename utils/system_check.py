import sys
import redis
from sqlalchemy import create_engine
from config import settings
import logging

logger = logging.getLogger(__name__)

def preflight_check():
    """
    Pings local Redis and PostgreSQL before allowing the application to start.
    If either fails, execution is blocked and the application exits.
    """
    logger.info("Running pre-flight system checks...")

    # 1. Check Redis
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_connect_timeout=3
        )
        r.ping()
        logger.info("Pre-flight: Redis is reachable.")
    except redis.ConnectionError:
        logger.critical(f"CRITICAL: Redis server offline. Please start local Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}.")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"CRITICAL: Unexpected error connecting to Redis: {e}")
        sys.exit(1)

    # 2. Check PostgreSQL
    try:
        db_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        engine = create_engine(db_url, connect_args={'connect_timeout': 3})
        connection = engine.connect()
        connection.close()
        logger.info("Pre-flight: PostgreSQL is reachable.")
    except Exception as e:
        logger.critical(f"CRITICAL: PostgreSQL server offline or unreachable. Please start local PostgreSQL at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}. Error: {e}")
        sys.exit(1)

    logger.info("All pre-flight system checks passed.")
