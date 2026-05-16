"""
Live inference pipeline — reads ticks from Redis, runs regime prediction.
Called from main.py's scan loop.
"""

import json
import logging
from typing import Optional

import pandas as pd

from ml.regime_classifier import classifier, MIN_SAMPLES_FOR_INFERENCE

logger = logging.getLogger(__name__)

# Key format in Redis: "ticks:{symbol}" → JSON list of OHLCV dicts
# Note: the current application architecture uses live_state:{symbol} (a hash)
# for the latest tick. But to generate historical indicators, we need the OHLCV list.
# For Nifty we will use the local historical dataframe directly instead.
REDIS_TICK_KEY_TEMPLATE = "ticks:{symbol}"


def get_regime_for_symbol(
    redis_client,
    symbol: str,
    df: pd.DataFrame = None,
    n_ticks: int = MIN_SAMPLES_FOR_INFERENCE,
) -> Optional[dict]:
    """
    Computes features from the provided DataFrame and returns the current regime.

    Args:
        redis_client: synchronous redis client (unused when df is provided)
        symbol:       Trading symbol e.g. "NIFTY"
        df:           Dataframe with OHLCV history
        n_ticks:      Number of recent ticks to use (≥100)

    Returns:
        Regime override dict with keys:
          regime_id, label, rsi_oversold, rsi_overbought, bb_std_dev, vwap_band_pct
        Returns None if inference is not possible.
    """
    if not classifier.is_ready():
        if not classifier.load():
            logger.warning(
                "[REGIME] Model not loaded — using default strategy params. "
                "Run: python -m ml.train_regimes"
            )
            return None

    try:
        if df is None or len(df) < MIN_SAMPLES_FOR_INFERENCE:
            logger.debug(
                f"[REGIME] {symbol}: Not enough data provided "
                f"(need {MIN_SAMPLES_FOR_INFERENCE}) — skipping"
            )
            return None

        # Take the most recent n_ticks
        candle_df = df.tail(n_ticks)

        # ── Sanity checks ──────────────────────────────────────────────────────
        if candle_df[["open", "high", "low", "close"]].eq(0).all().any():
            logger.warning(f"[REGIME] {symbol}: zero-price columns detected — skipping")
            return None

        # ── Run inference ──────────────────────────────────────────────────────
        regime = classifier.predict(candle_df)

        if regime:
            logger.debug(
                f"[REGIME] {symbol} → State {regime['regime_id']} "
                f"({regime['label']})  "
                f"RSI_OS={regime['rsi_oversold']}  "
                f"BB_std={regime['bb_std_dev']}"
            )

        return regime

    except Exception as e:
        logger.exception(f"[REGIME] Inference failed for {symbol}: {e}")
        return None
