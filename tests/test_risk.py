"""Tests for risk management module."""

from datetime import datetime, timezone

import pytest

from src.config import TradingConfig
from src.data.models import AccountInfo, Direction, Signal, SymbolInfo, Trade
from src.risk.manager import RiskManager


@pytest.fixture
def config():
    return TradingConfig(
        risk_per_trade=1.0,
        max_open_trades=3,
        max_daily_loss_pct=5.0,
        max_weekly_loss_pct=10.0,
        max_drawdown_pct=20.0,
    )


@pytest.fixture
def risk_manager(config):
    rm = RiskManager(config)
    rm.peak_balance = 10000.0
    return rm


@pytest.fixture
def account():
    return AccountInfo(balance=10000, equity=10000, margin=0, free_margin=10000)


@pytest.fixture
def eurusd_info():
    return SymbolInfo("EURUSD", 0.0001, 100000)


class TestPositionSizing:
    def test_basic_lot_size(self, risk_manager, account, eurusd_info):
        # Risk $100 (1% of $10000), SL = 30 pips
        # pip_value = 0.0001 * 100000 = 10 per pip per lot
        # lot_size = 100 / (30 * 10) = 0.33
        lot = risk_manager.calculate_lot_size(account, eurusd_info, 30)
        assert lot == 0.33

    def test_min_lot(self, risk_manager, eurusd_info):
        small_account = AccountInfo(balance=100, equity=100, margin=0, free_margin=100)
        lot = risk_manager.calculate_lot_size(small_account, eurusd_info, 100)
        assert lot >= eurusd_info.min_lot

    def test_zero_sl(self, risk_manager, account, eurusd_info):
        lot = risk_manager.calculate_lot_size(account, eurusd_info, 0)
        assert lot == eurusd_info.min_lot


class TestCanOpenTrade:
    def test_allowed(self, risk_manager, account):
        signal = Signal(symbol="EURUSD", direction=Direction.BUY, strategy="test")
        allowed, reason = risk_manager.can_open_trade(signal, account, [])
        assert allowed is True

    def test_max_trades_reached(self, risk_manager, account):
        trades = [
            Trade(id=str(i), symbol=f"SYM{i}", direction=Direction.BUY,
                  lot_size=0.1, entry_price=1.0, stop_loss=0.99,
                  take_profit=1.02, open_time=datetime.now(timezone.utc))
            for i in range(3)
        ]
        signal = Signal(symbol="EURUSD", direction=Direction.BUY, strategy="test")
        allowed, reason = risk_manager.can_open_trade(signal, account, trades)
        assert allowed is False
        assert "Max open trades" in reason

    def test_duplicate_symbol_direction(self, risk_manager, account):
        trades = [
            Trade(id="1", symbol="EURUSD", direction=Direction.BUY,
                  lot_size=0.1, entry_price=1.085, stop_loss=1.08,
                  take_profit=1.09, open_time=datetime.now(timezone.utc))
        ]
        signal = Signal(symbol="EURUSD", direction=Direction.BUY, strategy="test")
        allowed, reason = risk_manager.can_open_trade(signal, account, trades)
        assert allowed is False

    def test_daily_loss_limit(self, risk_manager, account):
        # Set the last_reset_day to today so it doesn't reset daily_pnl
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        risk_manager.last_reset_day = now.timetuple().tm_yday
        risk_manager.last_reset_week = now.isocalendar()[1]
        risk_manager.daily_pnl = -600  # 6% loss
        signal = Signal(symbol="EURUSD", direction=Direction.BUY, strategy="test")
        allowed, reason = risk_manager.can_open_trade(signal, account, [])
        assert allowed is False
        assert "Daily loss" in reason


class TestTrailingStop:
    def test_no_trail_before_1r(self, risk_manager):
        trade = Trade(
            id="1", symbol="EURUSD", direction=Direction.BUY,
            lot_size=0.1, entry_price=1.0850, stop_loss=1.0820,
            take_profit=1.0910, open_time=datetime.now(timezone.utc),
        )
        # Price only moved 10 pips (need 30 pips for 1:1)
        result = risk_manager.get_trailing_stop(trade, 1.0860, 0.0015)
        assert result is None

    def test_trail_after_1r(self, risk_manager):
        trade = Trade(
            id="1", symbol="EURUSD", direction=Direction.BUY,
            lot_size=0.1, entry_price=1.0850, stop_loss=1.0820,
            take_profit=1.0910, open_time=datetime.now(timezone.utc),
        )
        # Price moved 40 pips (> 30 pip SL distance)
        result = risk_manager.get_trailing_stop(trade, 1.0890, 0.0015)
        assert result is not None
        assert result > trade.stop_loss
