"""Tests for trading strategies."""

import numpy as np
import pandas as pd
import pytest

from src.config import StrategyConfig
from src.indicators.technical import compute_indicators
from src.strategies.breakout import BreakoutStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.trend_following import TrendFollowingStrategy


@pytest.fixture
def config():
    return StrategyConfig()


def make_uptrend_data(n=300):
    """Generate data with a clear uptrend."""
    np.random.seed(123)
    trend = np.linspace(0, 0.03, n)
    noise = np.random.normal(0, 0.001, n)
    prices = 1.08 + trend + np.cumsum(noise) * 0.01
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": prices,
        "high": prices + 0.001,
        "low": prices - 0.001,
        "close": prices + np.random.normal(0, 0.0003, n),
        "volume": np.random.randint(500, 2000, n).astype(float),
    })


def make_ranging_data(n=300):
    """Generate data that oscillates around a mean."""
    np.random.seed(456)
    t = np.linspace(0, 20 * np.pi, n)
    prices = 1.085 + 0.005 * np.sin(t) + np.random.normal(0, 0.0005, n)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": prices,
        "high": prices + 0.002,
        "low": prices - 0.002,
        "close": prices + np.random.normal(0, 0.0003, n),
        "volume": np.random.randint(500, 2000, n).astype(float),
    })


class TestTrendFollowing:
    def test_strategy_name(self, config):
        strategy = TrendFollowingStrategy(config)
        assert strategy.name == "trend_following"

    def test_returns_signal_or_none(self, config):
        strategy = TrendFollowingStrategy(config)
        data = make_uptrend_data()
        indicators = compute_indicators(data)
        result = strategy.check_entry("EURUSD", indicators)
        # Result is either None or a Signal
        assert result is None or result.symbol == "EURUSD"

    def test_signal_has_sl_tp(self, config):
        strategy = TrendFollowingStrategy(config)
        data = make_uptrend_data()
        indicators = compute_indicators(data)
        result = strategy.check_entry("EURUSD", indicators)
        if result is not None:
            assert result.stop_loss > 0
            assert result.take_profit > 0


class TestMeanReversion:
    def test_strategy_name(self, config):
        strategy = MeanReversionStrategy(config)
        assert strategy.name == "mean_reversion"

    def test_returns_signal_or_none(self, config):
        strategy = MeanReversionStrategy(config)
        data = make_ranging_data()
        indicators = compute_indicators(data)
        result = strategy.check_entry("EURUSD", indicators)
        assert result is None or result.symbol == "EURUSD"


class TestBreakout:
    def test_strategy_name(self, config):
        strategy = BreakoutStrategy(config)
        assert strategy.name == "breakout"

    def test_returns_signal_or_none(self, config):
        strategy = BreakoutStrategy(config)
        data = make_uptrend_data()
        indicators = compute_indicators(data)
        result = strategy.check_entry("EURUSD", indicators)
        assert result is None or result.symbol == "EURUSD"
