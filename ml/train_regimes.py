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
    Fetch historical OHLCV from your existing data source.
    Replace this stub with your actual Dhan API / DB fetch.
    """
    try:
        # ── Option A: Load from local CSV (fastest for first run) ─────────────
        csv_path = f"data/historical/{symbol}_1min.csv"
        df = pd.read_csv(csv_path, parse_dates=["timestamp"], index_col="timestamp")
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df.index >= cutoff]
        logger.info(f"Loaded {len(df)} rows from {csv_path}")
        return df

    except FileNotFoundError:
        # ── Option B: Pull from DB ─────────────────────────────────────────────
        logger.info(f"CSV not found — attempting DB fetch for {symbol}")
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
            df = pd.DataFrame([{
                "open": r.open, "high": r.high, "low": r.low,
                "close": r.close, "volume": r.volume,
                "timestamp": r.timestamp
            } for r in rows])
            df.set_index("timestamp", inplace=True)
            logger.info(f"Fetched {len(df)} rows from DB for {symbol}")
            return df
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
