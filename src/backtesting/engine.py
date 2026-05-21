"""Backtesting engine - simulate trading on historical data."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import BotConfig
from src.data.models import Direction
from src.indicators.technical import compute_indicators
from src.strategies.base import StrategyBase
from src.strategies.breakout import BreakoutStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.trend_following import TrendFollowingStrategy
from src.utils.logger import get_logger

logger = get_logger("forex_bot.backtest")


@dataclass
class BacktestTrade:
    entry_idx: int
    entry_price: float
    direction: Direction
    lot_size: float
    stop_loss: float
    take_profit: float
    strategy: str
    exit_idx: int = 0
    exit_price: float = 0.0
    profit: float = 0.0
    profit_pips: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    initial_balance: float = 10000.0
    final_balance: float = 10000.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_abs: float = 0.0
    sharpe_ratio: float = 0.0
    total_profit: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_trade_duration: float = 0.0  # in bars
    equity_curve: list[float] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"  BACKTEST RESULTS\n"
            f"{'='*60}\n"
            f"  Initial Balance:   ${self.initial_balance:,.2f}\n"
            f"  Final Balance:     ${self.final_balance:,.2f}\n"
            f"  Total Profit:      ${self.total_profit:,.2f} "
            f"({self.total_profit / self.initial_balance * 100:+.1f}%)\n"
            f"{'─'*60}\n"
            f"  Total Trades:      {self.total_trades}\n"
            f"  Winning Trades:    {self.winning_trades}\n"
            f"  Losing Trades:     {self.losing_trades}\n"
            f"  Win Rate:          {self.win_rate:.1f}%\n"
            f"  Profit Factor:     {self.profit_factor:.2f}\n"
            f"{'─'*60}\n"
            f"  Max Drawdown:      {self.max_drawdown_pct:.1f}% "
            f"(${self.max_drawdown_abs:,.2f})\n"
            f"  Sharpe Ratio:      {self.sharpe_ratio:.2f}\n"
            f"{'─'*60}\n"
            f"  Avg Win:           ${self.avg_win:,.2f}\n"
            f"  Avg Loss:          ${self.avg_loss:,.2f}\n"
            f"  Largest Win:       ${self.largest_win:,.2f}\n"
            f"  Largest Loss:      ${self.largest_loss:,.2f}\n"
            f"  Avg Trade Duration: {self.avg_trade_duration:.1f} bars\n"
            f"{'='*60}\n"
        )


class BacktestEngine:
    """Vectorized backtesting engine."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.strategies: list[StrategyBase] = []
        self._init_strategies()

    def _init_strategies(self) -> None:
        strategy_map = {
            "trend_following": TrendFollowingStrategy,
            "mean_reversion": MeanReversionStrategy,
            "breakout": BreakoutStrategy,
        }
        for name in self.config.strategy.strategy_list:
            cls = strategy_map.get(name)
            if cls:
                self.strategies.append(cls(self.config.strategy))
            else:
                logger.warning("Unknown strategy: %s", name)

    def run(
        self,
        data: pd.DataFrame,
        symbol: str = "EURUSD",
        pip_size: float = 0.0001,
        lot_size_contract: float = 100000,
    ) -> BacktestResult:
        """
        Run backtest on historical OHLCV data.

        Args:
            data: DataFrame with columns: timestamp, open, high, low, close, volume
            symbol: Symbol name
            pip_size: Pip size (0.0001 for most pairs, 0.01 for JPY)
            lot_size_contract: Contract size per lot
        """
        balance = self.config.backtest.backtest_initial_balance
        initial_balance = balance
        peak_balance = balance
        max_dd_pct = 0.0
        max_dd_abs = 0.0

        trades: list[BacktestTrade] = []
        open_trades: list[BacktestTrade] = []
        equity_curve = [balance]

        min_bars = max(
            self.config.strategy.ema_trend + 10,
            self.config.strategy.breakout_lookback + 10,
            55,
        )

        logger.info("Running backtest on %s (%d bars)...", symbol, len(data))

        for i in range(min_bars, len(data)):
            # Slice data up to current bar
            window = data.iloc[: i + 1].copy()
            indicators = compute_indicators(
                window,
                ema_fast_period=self.config.strategy.ema_fast,
                ema_slow_period=self.config.strategy.ema_slow,
                ema_trend_period=self.config.strategy.ema_trend,
                rsi_period=self.config.strategy.rsi_period,
                macd_fast=self.config.strategy.macd_fast,
                macd_slow=self.config.strategy.macd_slow,
                macd_signal=self.config.strategy.macd_signal,
                atr_period=self.config.strategy.atr_period,
                bb_period=self.config.strategy.bb_period,
                bb_std=self.config.strategy.bb_std,
            )

            current_high = data.iloc[i]["high"]
            current_low = data.iloc[i]["low"]
            current_close = data.iloc[i]["close"]

            # --- Check SL/TP for open trades ---
            for trade in list(open_trades):
                hit_sl = False
                hit_tp = False

                if trade.direction == Direction.BUY:
                    if trade.stop_loss > 0 and current_low <= trade.stop_loss:
                        hit_sl = True
                        trade.exit_price = trade.stop_loss
                    elif trade.take_profit > 0 and current_high >= trade.take_profit:
                        hit_tp = True
                        trade.exit_price = trade.take_profit
                else:
                    if trade.stop_loss > 0 and current_high >= trade.stop_loss:
                        hit_sl = True
                        trade.exit_price = trade.stop_loss
                    elif trade.take_profit > 0 and current_low <= trade.take_profit:
                        hit_tp = True
                        trade.exit_price = trade.take_profit

                if hit_sl or hit_tp:
                    trade.exit_idx = i
                    trade.exit_reason = "SL" if hit_sl else "TP"
                    trade.profit_pips = self._calc_pips(trade, pip_size)
                    trade.profit = self._calc_profit(
                        trade, pip_size, lot_size_contract
                    )
                    balance += trade.profit
                    trades.append(trade)
                    open_trades.remove(trade)

            # --- Check strategy exit signals ---
            for trade in list(open_trades):
                for strategy in self.strategies:
                    if strategy.check_exit(symbol, indicators, trade.direction.value):
                        trade.exit_idx = i
                        trade.exit_price = current_close
                        trade.exit_reason = f"signal_{strategy.name}"
                        trade.profit_pips = self._calc_pips(trade, pip_size)
                        trade.profit = self._calc_profit(
                            trade, pip_size, lot_size_contract
                        )
                        balance += trade.profit
                        trades.append(trade)
                        open_trades.remove(trade)
                        break

            # --- Check entry signals ---
            if len(open_trades) < self.config.trading.max_open_trades:
                for strategy in self.strategies:
                    signal = strategy.check_entry(symbol, indicators)
                    if signal is None:
                        continue

                    # Check if already have same direction on symbol
                    already_open = any(
                        t.direction == signal.direction for t in open_trades
                    )
                    if already_open:
                        continue

                    # Position sizing
                    sl_pips = abs(signal.stop_loss - current_close) / pip_size
                    if sl_pips <= 0:
                        continue
                    risk_amount = balance * (self.config.trading.risk_per_trade / 100)
                    pip_value = pip_size * lot_size_contract
                    lot = risk_amount / (sl_pips * pip_value)
                    lot = max(0.01, min(lot, 10.0))
                    lot = math.floor(lot * 100) / 100

                    bt_trade = BacktestTrade(
                        entry_idx=i,
                        entry_price=current_close,
                        direction=signal.direction,
                        lot_size=lot,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        strategy=strategy.name,
                    )
                    open_trades.append(bt_trade)

            # Equity tracking
            unrealized = sum(
                self._calc_profit_at(t, current_close, pip_size, lot_size_contract)
                for t in open_trades
            )
            equity = balance + unrealized
            equity_curve.append(equity)

            if equity > peak_balance:
                peak_balance = equity
            dd = peak_balance - equity
            dd_pct = dd / peak_balance * 100 if peak_balance > 0 else 0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd_abs = dd

        # Close remaining open trades at last price
        last_close = data.iloc[-1]["close"]
        for trade in open_trades:
            trade.exit_idx = len(data) - 1
            trade.exit_price = last_close
            trade.exit_reason = "end_of_data"
            trade.profit_pips = self._calc_pips(trade, pip_size)
            trade.profit = self._calc_profit(trade, pip_size, lot_size_contract)
            balance += trade.profit
            trades.append(trade)

        return self._compile_results(
            trades, initial_balance, balance, max_dd_pct, max_dd_abs, equity_curve
        )

    def _calc_pips(self, trade: BacktestTrade, pip_size: float) -> float:
        diff = trade.exit_price - trade.entry_price
        if trade.direction == Direction.SELL:
            diff = -diff
        return diff / pip_size

    def _calc_profit(
        self, trade: BacktestTrade, pip_size: float, lot_size_contract: float
    ) -> float:
        pips = self._calc_pips(trade, pip_size)
        pip_value = pip_size * lot_size_contract
        return round(pips * pip_value * trade.lot_size / lot_size_contract, 2)

    def _calc_profit_at(
        self, trade: BacktestTrade, price: float, pip_size: float, lot_size_contract: float
    ) -> float:
        diff = price - trade.entry_price
        if trade.direction == Direction.SELL:
            diff = -diff
        pips = diff / pip_size
        pip_value = pip_size * lot_size_contract
        return round(pips * pip_value * trade.lot_size / lot_size_contract, 2)

    def _compile_results(
        self,
        trades: list[BacktestTrade],
        initial_balance: float,
        final_balance: float,
        max_dd_pct: float,
        max_dd_abs: float,
        equity_curve: list[float],
    ) -> BacktestResult:
        result = BacktestResult(
            trades=trades,
            initial_balance=initial_balance,
            final_balance=final_balance,
            total_trades=len(trades),
            max_drawdown_pct=round(max_dd_pct, 2),
            max_drawdown_abs=round(max_dd_abs, 2),
            total_profit=round(final_balance - initial_balance, 2),
            equity_curve=equity_curve,
        )

        if not trades:
            return result

        wins = [t for t in trades if t.profit > 0]
        losses = [t for t in trades if t.profit <= 0]

        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate = len(wins) / len(trades) * 100 if trades else 0

        total_wins = sum(t.profit for t in wins)
        total_losses = abs(sum(t.profit for t in losses))
        result.profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        result.avg_win = total_wins / len(wins) if wins else 0
        result.avg_loss = total_losses / len(losses) if losses else 0
        result.largest_win = max(t.profit for t in trades) if trades else 0
        result.largest_loss = min(t.profit for t in trades) if trades else 0

        durations = [t.exit_idx - t.entry_idx for t in trades]
        result.avg_trade_duration = sum(durations) / len(durations) if durations else 0

        # Sharpe ratio (annualized, assuming daily returns)
        if len(equity_curve) > 1:
            returns = pd.Series(equity_curve).pct_change().dropna()
            if returns.std() > 0:
                result.sharpe_ratio = round(
                    (returns.mean() / returns.std()) * np.sqrt(252), 2
                )

        return result
