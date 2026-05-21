"""
Offline training script — run once before starting the live bot.

Usage:
    python -m ml.train_regimes --symbol NIFTY --days 365
"""

import argparse
import logging
import sys
from datetime import datetime, timedelta

import pandas as pd

from ml.regime_classifier import train_model, N_REGIMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger("train_regimes")


def fetch_historical_data(symbol: str, days: int) -> pd.DataFrame:
    """
    Fetch historical OHLCV from DB, downloading from Dhan API if missing.
    """
    import os
    from data.database import get_session
    from data.database import HistoricalData as MarketData
    from utils.auth import get_dhan_client
    from utils.dhan_helper import dhan_helper

    csv_path = f"data/historical/{symbol}_1min.csv"

    # 1. Download if missing
    if not os.path.exists(csv_path):
        logger.info(f"CSV not found — fetching {days} days of historical data from Dhan API for {symbol}")

        dhan = get_dhan_client()
        sec_id = dhan_helper.get_security_id(symbol)
        if not sec_id:
            raise ValueError(f"Could not find security ID for {symbol}")

        all_data = []
        to_date = datetime.now()
        days_fetched = 0

        while days_fetched < days:
            days_to_fetch = min(5, days - days_fetched)
            from_date = to_date - timedelta(days=days_to_fetch)

            logger.info(f"Fetching from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
            try:
                res = dhan.intraday_minute_data(
                    security_id=sec_id,
                    exchange_segment='NSE_EQ',
                    instrument_type='EQUITY',
                    from_date=from_date.strftime('%Y-%m-%d'),
                    to_date=to_date.strftime('%Y-%m-%d'),
                    interval=1
                )

                if res and isinstance(res, dict) and res.get('status') == 'success' and 'data' in res:
                    data = res['data']
                    if data and all(k in data for k in ['start_Time', 'open', 'high', 'low', 'close', 'volume']):
                        for i in range(len(data['start_Time'])):
                            ts = dhan.convert_to_date_time(data['start_Time'][i])
                            all_data.append({
                                'symbol': symbol,
                                'timestamp': ts,
                                'open': data['open'][i],
                                'high': data['high'][i],
                                'low': data['low'][i],
                                'close': data['close'][i],
                                'volume': data['volume'][i],
                                'interval': '1min'
                            })
            except Exception as e:
                logger.error(f"Error fetching data chunk: {e}")

            to_date = from_date - timedelta(days=1)
            days_fetched += days_to_fetch

        if not all_data:
            raise ValueError(f"Failed to fetch any data for {symbol}")

        df = pd.DataFrame(all_data)
        df.drop_duplicates(subset=['timestamp'], inplace=True)
        df.sort_values('timestamp', inplace=True)

        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        logger.info(f"Saving {len(df)} rows to {csv_path}")
        df.set_index('timestamp', inplace=False).to_csv(csv_path)

        logger.info("Bulk inserting into database...")
        try:
            with get_session() as session:
                session.execute(
                    MarketData.__table__.insert(),
                    df.to_dict(orient='records')
                )
                session.commit()
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")

    # 2. Process data directly from DB as required
    logger.info(f"Attempting DB fetch for {symbol} to process with GMM")
    try:
        from data.database import get_session
        from data.database import HistoricalData as MarketData

        with get_session() as session:
            cutoff = datetime.now() - timedelta(days=days)
            rows = (
                session.query(MarketData)
                .filter(
                    MarketData.symbol == symbol,
                    MarketData.timestamp >= cutoff,
                )
                .order_by(MarketData.timestamp)
                .all()
            )
        db_df = pd.DataFrame([{
            "open": r.open, "high": r.high, "low": r.low,
            "close": r.close, "volume": r.volume,
            "timestamp": r.timestamp
        } for r in rows])
        db_df.set_index("timestamp", inplace=True)
        logger.info(f"Fetched {len(db_df)} rows from DB for {symbol}")

        if len(db_df) == 0:
            raise ValueError(f"Database contains no data for {symbol} after cutoff {cutoff}")

        return db_df
    except Exception as e:
        logger.error(f"DB fetch failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Train regime classifier")
    parser.add_argument("--symbol", default="NIFTY", help="Symbol to train on")
    parser.add_argument("--days", type=int, default=365, help="Days of history")
    parser.add_argument("--components", type=int, default=N_REGIMES,
                        help="Number of GMM components")
    args = parser.parse_args()

    logger.info(f"Training on {args.symbol} | {args.days} days | {args.components} regimes")

    df = fetch_historical_data(args.symbol, args.days)
    pipeline, label_map = train_model(df, n_components=args.components, save=True)

    logger.info("Training complete. Regime map:")
    for cluster_id, info in label_map.items():
        logger.info(f"  Cluster {cluster_id} → {info['label']}: {info['description']}")

    logger.info("Model ready for live inference.")


if __name__ == "__main__":
    main()
