import sys
import time
from sqlalchemy import inspect
from data.database import engine, Base

def initialize_schema():
    # Attempt to wait for DB connection if not immediately available
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # Check for required tables existence using inspector
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()

            required_tables = [
                'historical_data',
                'trades',
                'portfolio_holdings',
                'system_audit',
                'bot_state'
            ]

            missing_tables = [table for table in required_tables if table not in existing_tables]

            # Use Base metadata to generate tables if missing
            if missing_tables:
                Base.metadata.create_all(bind=engine)

            # Verify they were actually created
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            missing_tables = [table for table in required_tables if table not in existing_tables]

            if not missing_tables:
                print("[DB ENGINE] PostgreSQL database tables initialized successfully.")
                break
            else:
                print(f"[DB ENGINE] Failed to create tables: {missing_tables}")
                sys.exit(1)

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[DB ENGINE] Attempt {attempt + 1} failed: {e}. Retrying in 2 seconds...")
                time.sleep(2)
            else:
                print(f"[DB ENGINE] Failed to connect and initialize database: {e}")
                sys.exit(1)

if __name__ == "__main__":
    initialize_schema()
