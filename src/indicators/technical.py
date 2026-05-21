"""Technical indicator calculations using pandas and numpy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class MACDResult:
    line: pd.Series
    signal: pd.Series
    histogram: pd.Series


@dataclass
class BollingerResult:
    upper: pd.Series
    middle: pd.Series
    lower: pd.Series


@dataclass
class IndicatorSet:
    """All computed indicators for a symbol."""

    close: pd.Series
    high: pd.Series
    low: pd.Series
    ema_fast: pd.Series
    ema_slow: pd.Series
    ema_trend: pd.Series
    rsi: pd.Series
    macd: MACDResult
    atr: pd.Series
    bollinger: BollingerResult


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    # When avg_loss is 0 (all gains), RSI = 100
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_values = 100 - (100 / (1 + rs))
    # Fill NaN from zero-loss periods with 100 (pure uptrend)
    mask = (avg_loss == 0) & (avg_gain > 0)
    rsi_values = rsi_values.where(~mask, 100.0)
    return rsi_values


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> MACDResult:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return MACDResult(line=macd_line, signal=signal_line, histogram=histogram)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(span=period, adjust=False).mean()


def bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> BollingerResult:
    middle = sma(series, period)
    rolling_std = series.rolling(window=period).std()
    upper = middle + (rolling_std * std_dev)
    lower = middle - (rolling_std * std_dev)
    return BollingerResult(upper=upper, middle=middle, lower=lower)


def stochastic(
    high: pd.Series, low: pd.Series, close: pd.Series,
    k_period: int = 14, d_period: int = 3,
) -> tuple[pd.Series, pd.Series]:
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(window=d_period).mean()
    return k, d


def adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr_val = atr(high, low, close, period)

    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr_val)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr_val)

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
    return dx.ewm(span=period, adjust=False).mean()


def compute_indicators(
    df: pd.DataFrame,
    ema_fast_period: int = 20,
    ema_slow_period: int = 50,
    ema_trend_period: int = 200,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    atr_period: int = 14,
    bb_period: int = 20,
    bb_std: float = 2.0,
) -> IndicatorSet:
    """Compute all indicators from an OHLCV DataFrame."""
    close = df["close"]
    high = df["high"]
    low = df["low"]

    return IndicatorSet(
        close=close,
        high=high,
        low=low,
        ema_fast=ema(close, ema_fast_period),
        ema_slow=ema(close, ema_slow_period),
        ema_trend=ema(close, ema_trend_period),
        rsi=rsi(close, rsi_period),
        macd=macd(close, macd_fast, macd_slow, macd_signal),
        atr=atr(high, low, close, atr_period),
        bollinger=bollinger_bands(close, bb_period, bb_std),
    )
