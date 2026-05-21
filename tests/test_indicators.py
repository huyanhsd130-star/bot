"""Tests for technical indicators."""

import numpy as np
import pandas as pd
import pytest

from src.indicators.technical import (
    atr,
    bollinger_bands,
    compute_indicators,
    ema,
    macd,
    rsi,
)


@pytest.fixture
def sample_data():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    n = 300
    prices = 1.085 * np.exp(np.cumsum(np.random.normal(0, 0.001, n)))
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": prices,
        "high": prices + np.abs(np.random.normal(0, 0.001, n)),
        "low": prices - np.abs(np.random.normal(0, 0.001, n)),
        "close": prices + np.random.normal(0, 0.0005, n),
        "volume": np.random.randint(500, 2000, n).astype(float),
    })
    return df


class TestEMA:
    def test_ema_length(self):
        series = pd.Series(range(100), dtype=float)
        result = ema(series, 20)
        assert len(result) == 100

    def test_ema_smoothing(self):
        series = pd.Series([1.0] * 50 + [2.0] * 50)
        result = ema(series, 10)
        # After transitioning to 2.0, EMA should approach 2.0
        assert result.iloc[-1] > 1.9


class TestRSI:
    def test_rsi_range(self, sample_data):
        result = rsi(sample_data["close"], 14)
        valid = result.dropna()
        assert valid.min() >= 0
        assert valid.max() <= 100

    def test_rsi_overbought(self):
        # Monotonically increasing prices with enough data
        series = pd.Series(np.linspace(1.0, 2.0, 200))
        result = rsi(series, 14)
        valid = result.dropna()
        assert len(valid) > 0
        assert valid.iloc[-1] > 90  # Should be very overbought


class TestMACD:
    def test_macd_components(self, sample_data):
        result = macd(sample_data["close"], 12, 26, 9)
        assert len(result.line) == len(sample_data)
        assert len(result.signal) == len(sample_data)
        assert len(result.histogram) == len(sample_data)

    def test_macd_histogram_is_diff(self, sample_data):
        result = macd(sample_data["close"])
        diff = result.line - result.signal
        pd.testing.assert_series_equal(result.histogram, diff)


class TestATR:
    def test_atr_positive(self, sample_data):
        result = atr(sample_data["high"], sample_data["low"], sample_data["close"], 14)
        valid = result.dropna()
        assert (valid >= 0).all()


class TestBollinger:
    def test_bollinger_order(self, sample_data):
        result = bollinger_bands(sample_data["close"], 20, 2.0)
        valid_idx = result.upper.dropna().index
        assert (result.upper[valid_idx] >= result.middle[valid_idx]).all()
        assert (result.middle[valid_idx] >= result.lower[valid_idx]).all()


class TestComputeIndicators:
    def test_compute_all(self, sample_data):
        result = compute_indicators(sample_data)
        assert result.ema_fast is not None
        assert result.ema_slow is not None
        assert result.ema_trend is not None
        assert result.rsi is not None
        assert result.macd is not None
        assert result.atr is not None
        assert result.bollinger is not None
