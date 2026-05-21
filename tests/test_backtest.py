"""Tests for backtesting engine."""

import pytest

from src.backtesting.data_loader import generate_synthetic_data
from src.backtesting.engine import BacktestEngine, BacktestResult
from src.config import BotConfig


@pytest.fixture
def config():
    cfg = BotConfig()
    cfg.strategy.active_strategies = "trend_following"
    cfg.trading.risk_per_trade = 1.0
    cfg.trading.max_open_trades = 3
    return cfg


class TestBacktestEngine:
    def test_run_backtest(self, config):
        data = generate_synthetic_data(num_bars=1000, seed=42)
        engine = BacktestEngine(config)
        result = engine.run(data, symbol="EURUSD")

        assert isinstance(result, BacktestResult)
        assert result.initial_balance == config.backtest.backtest_initial_balance
        assert result.total_trades >= 0
        assert len(result.equity_curve) > 0

    def test_backtest_with_multiple_strategies(self, config):
        config.strategy.active_strategies = "trend_following,breakout"
        data = generate_synthetic_data(num_bars=1000, seed=42)
        engine = BacktestEngine(config)
        result = engine.run(data)

        assert result.total_trades >= 0

    def test_backtest_result_summary(self, config):
        data = generate_synthetic_data(num_bars=500, seed=42)
        engine = BacktestEngine(config)
        result = engine.run(data)
        summary = result.summary()
        assert "BACKTEST RESULTS" in summary
        assert "Win Rate" in summary


class TestSyntheticData:
    def test_generate_data_length(self):
        data = generate_synthetic_data(num_bars=100)
        assert len(data) == 100

    def test_generate_data_columns(self):
        data = generate_synthetic_data(num_bars=10)
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        for col in required:
            assert col in data.columns

    def test_generate_data_high_low(self):
        data = generate_synthetic_data(num_bars=100)
        assert (data["high"] >= data["low"]).all()

    def test_reproducibility(self):
        d1 = generate_synthetic_data(num_bars=50, seed=42)
        d2 = generate_synthetic_data(num_bars=50, seed=42)
        assert d1["close"].equals(d2["close"])
