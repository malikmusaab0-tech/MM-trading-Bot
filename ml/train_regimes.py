"""
Offline training script — run once before starting the live bot.

Usage:
    python -m ml.train_regimes --symbol NIFTY --days 365
"""

import argparse
import logging
import asyncio
from datetime import datetime, timedelta
import pandas as pd
from dhanhq import dhanhq
from sqlalchemy import select, insert

from ml.regime_classifier import train_model, N_REGIMES
from utils.dhan_helper import DhanHelper
from data.database import get_async_session, HistoricalData as MarketData
from config.settings import DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger("train_regimes")

async def fetch_and_store_dhan_data(symbol: str, days: int) -> pd.DataFrame:
    """
    Downloads historical data from Dhan API in chunks and bulk-inserts into PostgreSQL.
    """
    logger.info(f"Downloading {days} days of historical data for {symbol} from Dhan API...")

    helper = DhanHelper()
    security_id = helper.get_security_id(symbol)
    if not security_id:
        logger.error(f"Could not find security ID for {symbol}")
        raise ValueError(f"Security ID not found for {symbol}")

    exchange = helper.get_exchange_segment(symbol)

    dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    current_end = end_date
    all_data = []

    # Dhan API allows max 100 days per request for intraday data
    chunk_days = 90

    while current_end > start_date:
        current_start = max(start_date, current_end - timedelta(days=chunk_days))

        from_date = current_start.strftime("%Y-%m-%d")
        to_date = current_end.strftime("%Y-%m-%d")

        logger.info(f"Fetching chunk: {from_date} to {to_date}")

        try:
            # Depending on Dhan API version, the call might slightly vary. Standard form:
            req = dhan.historical_minute_charts(
                symbol=symbol,
                exchange_segment=exchange,
                instrument_type='INDEX' if symbol == 'NIFTY' else 'EQUITY',
                expiry_code=0,
                from_date=from_date,
                to_date=to_date
            )

            if req.get("status") == "success" and "data" in req:
                data = req["data"]
                if "start_Time" in data:
                    df_chunk = pd.DataFrame({
                        "timestamp": pd.to_datetime(data["start_Time"]),
                        "open": data["open"],
                        "high": data["high"],
                        "low": data["low"],
                        "close": data["close"],
                        "volume": data["volume"]
                    })
                    all_data.append(df_chunk)
            else:
                logger.warning(f"Failed chunk fetch or empty data: {req}")
        except Exception as e:
            logger.error(f"Error fetching chunk from Dhan: {e}")

        current_end = current_start - timedelta(days=1)
        await asyncio.sleep(0.5) # Rate limiting

    if not all_data:
        raise ValueError(f"Failed to fetch any data for {symbol} from Dhan API")

    final_df = pd.concat(all_data).drop_duplicates(subset=['timestamp']).sort_values('timestamp')

    logger.info(f"Total downloaded rows: {len(final_df)}. Bulk inserting to PostgreSQL...")

    records = []
    for _, row in final_df.iterrows():
        records.append({
            "symbol": symbol,
            "timestamp": row['timestamp'],
            "open": row['open'],
            "high": row['high'],
            "low": row['low'],
            "close": row['close'],
            "volume": row['volume'],
            "interval": "1min"
        })

    # Bulk insert in chunks to avoid overwhelming the DB
    chunk_size = 5000
    async with get_async_session() as session:
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]
            await session.execute(insert(MarketData).values(chunk))
        await session.commit()

    logger.info("Bulk insert complete.")
    final_df.set_index("timestamp", inplace=True)
    return final_df

async def fetch_historical_data_async(symbol: str, days: int) -> pd.DataFrame:
    """
    Checks DB first, falls back to local CSV, and ultimately fetches from Dhan API if neither has sufficient data.
    """
    cutoff = datetime.now() - timedelta(days=days)

    # ── Option 1: Try fetching from Database ─────────────
    logger.info(f"Attempting to fetch {symbol} from database...")
    async with get_async_session() as session:
        stmt = select(MarketData).filter(
            MarketData.symbol == symbol,
            MarketData.timestamp >= cutoff
        ).order_by(MarketData.timestamp)

        result = await session.execute(stmt)
        rows = result.scalars().all()

    if rows and len(rows) > 500: # Ensure we have a reasonable amount of data
        df = pd.DataFrame([{
            "open": r.open, "high": r.high, "low": r.low,
            "close": r.close, "volume": r.volume,
            "timestamp": r.timestamp
        } for r in rows])
        df.set_index("timestamp", inplace=True)
        logger.info(f"Fetched {len(df)} rows from DB for {symbol}")
        return df

    # ── Option 2: Try local CSV ─────────────
    csv_path = f"data/historical/{symbol}_1min.csv"
    try:
        df = pd.read_csv(csv_path, parse_dates=["timestamp"], index_col="timestamp")
        df = df[df.index >= cutoff]
        if len(df) > 500:
            logger.info(f"Loaded {len(df)} rows from local CSV: {csv_path}")
            return df
    except FileNotFoundError:
        logger.info(f"Local CSV not found at {csv_path}")

    # ── Option 3: Download from Dhan API and populate DB ─────────────
    return await fetch_and_store_dhan_data(symbol, days)


async def async_main():
    parser = argparse.ArgumentParser(description="Train regime classifier")
    parser.add_argument("--symbol", default="NIFTY", help="Symbol to train on")
    parser.add_argument("--days", type=int, default=365, help="Days of history")
    parser.add_argument("--components", type=int, default=N_REGIMES,
                        help="Number of GMM components")
    args = parser.parse_args()

    logger.info(f"Training on {args.symbol} | {args.days} days | {args.components} regimes")

    try:
        df = await fetch_historical_data_async(args.symbol, args.days)
    except Exception as e:
        logger.error(f"Critical error fetching data: {e}")
        return

    if len(df) < 1000:
        logger.warning(f"Warning: Only {len(df)} rows of data available. The GMM might not train well.")

    pipeline, label_map = train_model(df, n_components=args.components, save=True)

    logger.info("Training complete. Regime map:")
    for cluster_id, info in label_map.items():
        logger.info(f"  Cluster {cluster_id} → {info['label']}: {info['description']}")

    logger.info("Model ready for live inference.")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
