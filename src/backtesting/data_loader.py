"""Load historical data for backtesting from CSV files or generate synthetic data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger("forex_bot.data_loader")


def load_csv(filepath: str | Path, date_column: str = "timestamp") -> pd.DataFrame:
    """
    Load OHLCV data from CSV file.

    Expected columns: timestamp (or date_column), open, high, low, close, volume
    """
    df = pd.read_csv(filepath)

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    if date_column.lower() in df.columns:
        df["timestamp"] = pd.to_datetime(df[date_column.lower()])
    elif "date" in df.columns:
        df["timestamp"] = pd.to_datetime(df["date"])
    elif "time" in df.columns:
        df["timestamp"] = pd.to_datetime(df["time"])

    required = ["open", "high", "low", "close"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    if "volume" not in df.columns:
        df["volume"] = 0

    df = df[["timestamp", "open", "high", "low", "close", "volume"]].dropna()
    df = df.sort_values("timestamp").reset_index(drop=True)

    logger.info("Loaded %d candles from %s", len(df), filepath)
    return df


def generate_synthetic_data(
    symbol: str = "EURUSD",
    start_price: float = 1.0850,
    num_bars: int = 5000,
    timeframe_minutes: int = 60,
    volatility: float = 0.0005,
    trend: float = 0.0,
    seed: int | None = None,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data for backtesting.

    Args:
        symbol: Symbol name (used for seed if seed is None)
        start_price: Starting price
        num_bars: Number of candles to generate
        timeframe_minutes: Candle timeframe in minutes
        volatility: Per-bar volatility (std of returns)
        trend: Drift per bar (positive = uptrend)
        seed: Random seed for reproducibility
    """
    if seed is not None:
        np.random.seed(seed)
    else:
        np.random.seed(hash(symbol) % (2**31))

    # Generate returns with optional trend
    returns = np.random.normal(trend, volatility, num_bars)

    # Add some mean reversion and trending regimes
    regime = np.zeros(num_bars)
    regime_length = 0
    current_regime = 0  # 0 = ranging, 1 = trending up, -1 = trending down
    for i in range(num_bars):
        regime_length += 1
        if regime_length > np.random.randint(50, 200):
            current_regime = np.random.choice([-1, 0, 1], p=[0.3, 0.4, 0.3])
            regime_length = 0
        regime[i] = current_regime

    returns += regime * volatility * 0.3

    # Price series
    prices = start_price * np.exp(np.cumsum(returns))

    # Generate OHLCV
    start_time = pd.Timestamp("2021-01-04 00:00:00", tz="UTC")
    data = []
    for i in range(num_bars):
        o = prices[i]
        intra_vol = abs(np.random.normal(0, volatility * start_price, 4))
        h = o + intra_vol[0]
        low_val = o - intra_vol[1]
        c = o + np.random.normal(0, volatility * start_price * 0.5)
        c = max(low_val, min(c, h))  # Clamp close within high-low
        v = max(100, np.random.normal(1500, 500))

        data.append({
            "timestamp": start_time + pd.Timedelta(minutes=timeframe_minutes * i),
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(low_val, 5),
            "close": round(c, 5),
            "volume": round(v, 0),
        })

    df = pd.DataFrame(data)
    logger.info(
        "Generated %d synthetic bars for %s (start=%.5f, end=%.5f)",
        num_bars, symbol, prices[0], prices[-1],
    )
    return df
