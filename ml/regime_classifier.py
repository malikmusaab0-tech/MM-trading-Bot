"""
Real-Time Market Regime Classification Engine
Uses Gaussian Mixture Model (GMM) to classify market regimes from OHLCV features.
"""

import logging
import os
import warnings
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MODEL_PATH = Path("ml/models/regime_gmm.joblib")
N_REGIMES = 4
RANDOM_STATE = 42
MIN_SAMPLES_FOR_TRAINING = 100
MIN_SAMPLES_FOR_INFERENCE = 100 # Changed from 20 to 100 for proper indicator warmup

# ── Regime Mapping ─────────────────────────────────────────────────────────────
# Populated after training via _assign_regime_labels()
# Each regime maps to adaptive strategy parameter overrides.
REGIME_STRATEGY_OVERRIDES: dict[int, dict] = {
    0: {
        "label": "Low-Vol Trend",
        "rsi_oversold": 35,
        "rsi_overbought": 65,
        "bb_std_dev": 2.0,
        "vwap_band_pct": 0.5,
        "description": "Quiet directional trend — momentum strategies preferred",
    },
    1: {
        "label": "High-Vol Momentum",
        "rsi_oversold": 40,
        "rsi_overbought": 60,
        "bb_std_dev": 2.5,
        "vwap_band_pct": 1.0,
        "description": "Volatile trending — wider bands, tighter RSI triggers",
    },
    2: {
        "label": "Mean-Reverting Sideways",
        "rsi_oversold": 25,
        "rsi_overbought": 75,
        "bb_std_dev": 1.8,
        "vwap_band_pct": 0.3,
        "description": "Choppy range — reversal strategies preferred, tight bands",
    },
    3: {
        "label": "High-Vol Choppy",
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "bb_std_dev": 3.0,
        "vwap_band_pct": 1.5,
        "description": "Erratic high-vol — reduce position size, widen all bands",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. FEATURE EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.ewm(span=period, adjust=False).mean()


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Session VWAP that handles multi-day dataframes by resetting daily."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    tp_vol = typical_price * df["volume"]

    # Group by the date portion of the index and calculate cumulative sums per day
    group = df.index.date if isinstance(df.index, pd.DatetimeIndex) else df['timestamp'].dt.date

    cum_tp_vol = tp_vol.groupby(group).cumsum()
    cum_vol = df["volume"].groupby(group).cumsum().replace(0, np.nan)

    return cum_tp_vol / cum_vol


def compute_macd_histogram(df: pd.DataFrame,
                            fast: int = 12,
                            slow: int = 26,
                            signal: int = 9) -> pd.Series:
    """MACD Histogram (MACD line minus signal line)."""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def compute_volume_zscore(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Volume Z-Score: how many std devs current volume is from rolling mean."""
    rolling_mean = df["volume"].rolling(period).mean()
    rolling_std = df["volume"].rolling(period).std().replace(0, np.nan)
    return (df["volume"] - rolling_mean) / rolling_std


def extract_features(df: pd.DataFrame,
                     atr_period: int = 14,
                     vol_zscore_period: int = 20) -> pd.DataFrame:
    """
    Extract regime features from OHLCV DataFrame.

    Required columns: open, high, low, close, volume
    Returns a DataFrame of features with no NaN rows.
    """
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # ── Raw features ──────────────────────────────────────────────────────────
    atr = compute_atr(df, atr_period)
    vwap = compute_vwap(df)
    macd_hist = compute_macd_histogram(df)
    vol_zscore = compute_volume_zscore(df, vol_zscore_period)

    # ── Normalized ATR (as % of price) ────────────────────────────────────────
    norm_atr = atr / df["close"].replace(0, np.nan) * 100

    # ── Price distance from VWAP (as % of VWAP) ──────────────────────────────
    vwap_distance = (df["close"] - vwap) / vwap.replace(0, np.nan) * 100

    # ── MACD histogram slope (1-period difference) ────────────────────────────
    macd_slope = macd_hist.diff()

    features = pd.DataFrame({
        "norm_atr": norm_atr,
        "macd_slope": macd_slope,
        "vwap_distance": vwap_distance,
        "volume_zscore": vol_zscore,
    }, index=df.index)

    # Drop rows with NaN (warm-up period for rolling indicators)
    features = features.dropna()

    if len(features) == 0:
        raise ValueError(
            f"Feature extraction produced 0 rows. "
            f"Input had {len(df)} rows — need at least {max(atr_period, vol_zscore_period, 26) + 2}."
        )

    logger.debug(f"Extracted {len(features)} feature rows from {len(df)} candles")
    return features


# ══════════════════════════════════════════════════════════════════════════════
# 2. MODEL TRAINING
# ══════════════════════════════════════════════════════════════════════════════

def build_pipeline(n_components: int = N_REGIMES) -> Pipeline:
    """Build a StandardScaler + GMM pipeline."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("gmm", GaussianMixture(
            n_components=n_components,
            covariance_type="full",
            n_init=5,
            max_iter=300,
            random_state=RANDOM_STATE,
        )),
    ])


def _assign_regime_labels(pipeline: Pipeline, features: pd.DataFrame) -> dict[int, dict]:
    """
    After training, assign human-readable labels to cluster IDs
    by ranking on volatility (norm_atr) and trend strength (|macd_slope|).
    Returns a mapping: {cluster_id: regime_override_dict}
    """
    labels = pipeline.predict(features.values)
    feature_df = features.copy()
    feature_df["cluster"] = labels

    cluster_stats = feature_df.groupby("cluster").agg(
        mean_atr=("norm_atr", "mean"),
        mean_trend=("macd_slope", lambda x: x.abs().mean()),
    )

    # Rank by ATR (volatility) ascending
    cluster_stats["vol_rank"] = cluster_stats["mean_atr"].rank()
    # High ATR + low trend  → Choppy; High ATR + high trend → Momentum
    # Low ATR + high trend  → Trending; Low ATR + low trend → Sideways

    n = len(cluster_stats)
    mapping: dict[int, dict] = {}
    for cid in cluster_stats.index:
        row = cluster_stats.loc[cid]
        high_vol = row["vol_rank"] > n / 2
        high_trend = row["mean_trend"] > cluster_stats["mean_trend"].median()

        if not high_vol and high_trend:
            regime_key = 0  # Low-Vol Trend
        elif high_vol and high_trend:
            regime_key = 1  # High-Vol Momentum
        elif not high_vol and not high_trend:
            regime_key = 2  # Mean-Reverting Sideways
        else:
            regime_key = 3  # High-Vol Choppy

        mapping[int(cid)] = REGIME_STRATEGY_OVERRIDES[regime_key]

    return mapping


def train_model(historical_df: pd.DataFrame,
                n_components: int = N_REGIMES,
                save: bool = True) -> tuple[Pipeline, dict[int, dict]]:
    """
    Train the GMM on historical OHLCV data.

    Args:
        historical_df: DataFrame with OHLCV columns covering at least ~500 candles.
        n_components:  Number of regime clusters.
        save:          Persist model + label map to MODEL_PATH.

    Returns:
        (pipeline, cluster_to_regime_map)
    """
    if len(historical_df) < MIN_SAMPLES_FOR_TRAINING:
        raise ValueError(
            f"Need at least {MIN_SAMPLES_FOR_TRAINING} candles for training, "
            f"got {len(historical_df)}"
        )

    logger.info(f"Training GMM with {n_components} components on {len(historical_df)} candles...")

    features = extract_features(historical_df)
    X = features.values

    pipeline = build_pipeline(n_components)
    pipeline.fit(X)

    bic = pipeline.named_steps["gmm"].bic(
        pipeline.named_steps["scaler"].transform(X)
    )
    logger.info(f"GMM training complete. BIC={bic:.2f} on {len(X)} samples")

    label_map = _assign_regime_labels(pipeline, features)

    if save:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": pipeline, "label_map": label_map}, MODEL_PATH)
        logger.info(f"Model saved to {MODEL_PATH}")

    return pipeline, label_map


def load_model() -> tuple[Optional[Pipeline], dict[int, dict]]:
    """Load saved model from disk. Returns (None, {}) if not found."""
    if not MODEL_PATH.exists():
        logger.warning(f"No model found at {MODEL_PATH}. Run train_model() first.")
        return None, {}
    artifact = joblib.load(MODEL_PATH)
    logger.info(f"Loaded regime model from {MODEL_PATH}")
    return artifact["pipeline"], artifact["label_map"]


# ══════════════════════════════════════════════════════════════════════════════
# 3. LIVE INFERENCE
# ══════════════════════════════════════════════════════════════════════════════

class RegimeClassifier:
    """
    Stateful wrapper that tracks current regime and logs transitions.
    Use one instance per symbol or one shared instance for index-level regime.
    """

    def __init__(self):
        self.pipeline: Optional[Pipeline] = None
        self.label_map: dict[int, dict] = {}
        self.current_regime_id: Optional[int] = None
        self.current_regime_info: dict = {}
        self._loaded = False

    def load(self) -> bool:
        """Load model from disk. Returns True if successful."""
        self.pipeline, self.label_map = load_model()
        self._loaded = self.pipeline is not None
        return self._loaded

    def is_ready(self) -> bool:
        return self._loaded and self.pipeline is not None

    def predict(self, candle_df: pd.DataFrame) -> Optional[dict]:
        """
        Run inference on a candle DataFrame.

        Args:
            candle_df: Recent OHLCV candles (at least MIN_SAMPLES_FOR_INFERENCE rows).

        Returns:
            Dict with keys: regime_id, label, rsi_oversold, rsi_overbought,
                            bb_std_dev, vwap_band_pct, description
            Returns None if inference fails.
        """
        if not self.is_ready():
            logger.warning("RegimeClassifier.predict() called before model is loaded.")
            return None

        if len(candle_df) < MIN_SAMPLES_FOR_INFERENCE:
            logger.debug(
                f"Not enough candles for inference: {len(candle_df)} < {MIN_SAMPLES_FOR_INFERENCE}"
            )
            return None

        try:
            features = extract_features(candle_df)
            if len(features) == 0:
                return None

            # Use the most recent feature row for live inference
            latest = features.iloc[[-1]].values  # shape (1, 4)

            raw_id = int(self.pipeline.predict(latest)[0])
            regime_info = self.label_map.get(raw_id, REGIME_STRATEGY_OVERRIDES[0])
            regime_info = dict(regime_info)  # copy
            regime_info["regime_id"] = raw_id

            # ── Log regime transitions ────────────────────────────────────────
            if self.current_regime_id is not None and raw_id != self.current_regime_id:
                old_label = self.current_regime_info.get("label", str(self.current_regime_id))
                new_label = regime_info.get("label", str(raw_id))
                logger.info(
                    f"[REGIME CHANGE] Shifted from State {self.current_regime_id} ({old_label}) "
                    f"to State {raw_id} ({new_label}). "
                    f"Adjusting RSI oversold→{regime_info['rsi_oversold']}, "
                    f"BB std→{regime_info['bb_std_dev']}"
                )

            self.current_regime_id = raw_id
            self.current_regime_info = regime_info
            return regime_info

        except Exception as e:
            logger.exception(f"Regime inference error: {e}")
            return None


# Module-level singleton — import and use directly
classifier = RegimeClassifier()
