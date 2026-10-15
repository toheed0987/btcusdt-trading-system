"""
Feature engineering: turns raw OHLCV candles into a technical-indicator
feature matrix used for both training and live inference.

All features are computed with pandas/numpy only (no TA-Lib dependency,
so the container builds without native compilation issues).
"""
import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "ret_1", "ret_5", "ret_15", "ret_60",
    "sma_9", "sma_21", "sma_50",
    "ema_9", "ema_21",
    "rsi_14",
    "macd", "macd_signal", "macd_hist",
    "bb_width", "bb_pct_b",
    "atr_14",
    "volume_zscore_20",
    "momentum_10",
    "volatility_20",
    "high_low_range_pct",
]


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    df must be sorted ascending by open_time and contain columns:
    open, high, low, close, volume
    Returns a new DataFrame with feature columns appended (NaNs for warmup rows).
    """
    out = df.copy()
    close = out["close"].astype(float)
    volume = out["volume"].astype(float)

    out["ret_1"] = close.pct_change(1)
    out["ret_5"] = close.pct_change(5)
    out["ret_15"] = close.pct_change(15)
    out["ret_60"] = close.pct_change(60)

    out["sma_9"] = close.rolling(9).mean() / close - 1
    out["sma_21"] = close.rolling(21).mean() / close - 1
    out["sma_50"] = close.rolling(50).mean() / close - 1

    ema_9 = close.ewm(span=9, adjust=False).mean()
    ema_21 = close.ewm(span=21, adjust=False).mean()
    out["ema_9"] = ema_9 / close - 1
    out["ema_21"] = ema_21 / close - 1

    out["rsi_14"] = _rsi(close, 14)

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    out["macd"] = macd / close
    out["macd_signal"] = macd_signal / close
    out["macd_hist"] = (macd - macd_signal) / close

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper = sma20 + 2 * std20
    lower = sma20 - 2 * std20
    out["bb_width"] = (upper - lower) / sma20
    out["bb_pct_b"] = (close - lower) / (upper - lower).replace(0, np.nan)

    out["atr_14"] = _atr(out, 14) / close

    vol_mean20 = volume.rolling(20).mean()
    vol_std20 = volume.rolling(20).std()
    out["volume_zscore_20"] = (volume - vol_mean20) / vol_std20.replace(0, np.nan)

    out["momentum_10"] = close - close.shift(10)
    out["volatility_20"] = close.pct_change().rolling(20).std()
    out["high_low_range_pct"] = (out["high"] - out["low"]) / close

    return out


def make_label(df: pd.DataFrame, horizon: int = 15) -> pd.Series:
    """
    Binary label: 1 if close price `horizon` candles ahead is higher than
    the current close, else 0. Used only for training/backtesting — never
    available at live-inference time.
    """
    future_close = df["close"].shift(-horizon)
    return (future_close > df["close"]).astype("Int64")


def latest_feature_row(df: pd.DataFrame) -> pd.DataFrame:
    """Returns the most recent fully-formed feature row for live inference."""
    feats = build_features(df)
    row = feats.iloc[[-1]][FEATURE_COLUMNS]
    return row.fillna(0)
