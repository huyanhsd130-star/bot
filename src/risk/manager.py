"""Risk management module - position sizing, drawdown control, exposure limits."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from src.config import TradingConfig
from src.data.models import AccountInfo, Direction, Signal, SymbolInfo, Trade
from src.utils.logger import get_logger

logger = get_logger("forex_bot.risk")

# Highly correlated pairs - max 2 trades in the same correlation group
CORRELATION_GROUPS = [
    {"EURUSD", "GBPUSD", "NZDUSD", "AUDUSD"},  # USD weakness pairs
    {"USDCHF", "USDCAD", "USDJPY"},              # USD strength pairs
    {"EURGBP", "EURJPY", "EURCHF"},               # EUR crosses
]


class RiskManager:
    """Controls position sizing, drawdown limits, and trade approval."""

    def __init__(self, config: TradingConfig) -> None:
        self.config = config
        self.daily_pnl: float = 0.0
        self.weekly_pnl: float = 0.0
        self.peak_balance: float = 0.0
        self.last_reset_day: int = -1
        self.last_reset_week: int = -1
        self.bot_paused: bool = False
        self.pause_reason: str = ""

    def calculate_lot_size(
        self,
        account: AccountInfo,
        symbol_info: SymbolInfo,
        sl_pips: float,
    ) -> float:
        """
        Calculate position size based on risk percentage.

        Formula: lot_size = (balance * risk%) / (sl_pips * pip_value_per_lot)
        """
        if sl_pips <= 0:
            logger.warning("SL pips <= 0, using minimum lot size")
            return symbol_info.min_lot

        risk_amount = account.balance * (self.config.risk_per_trade / 100)
        pip_value = symbol_info.pip_size * symbol_info.lot_size  # Value per pip per 1 lot
        lot_size = risk_amount / (sl_pips * pip_value)

        # Clamp to valid range and round down to lot step
        lot_size = max(symbol_info.min_lot, min(lot_size, symbol_info.max_lot))
        lot_size = math.floor(lot_size / symbol_info.lot_step) * symbol_info.lot_step
        lot_size = round(lot_size, 2)

        logger.info(
            "Position size: %.2f lots (risk=$%.2f, SL=%.1f pips)",
            lot_size, risk_amount, sl_pips,
        )
        return lot_size

    def can_open_trade(
        self,
        signal: Signal,
        account: AccountInfo,
        open_trades: list[Trade],
    ) -> tuple[bool, str]:
        """
        Check if a new trade is allowed based on risk rules.
        Returns (allowed, reason).
        """
        if self.bot_paused:
            return False, f"Bot paused: {self.pause_reason}"

        self._check_reset(account)

        # Max open trades
        if len(open_trades) >= self.config.max_open_trades:
            return False, f"Max open trades reached ({self.config.max_open_trades})"

        # Daily loss limit
        daily_loss_pct = abs(self.daily_pnl) / account.balance * 100 if account.balance > 0 else 0
        if self.daily_pnl < 0 and daily_loss_pct >= self.config.max_daily_loss_pct:
            return False, f"Daily loss limit reached ({daily_loss_pct:.1f}%)"

        # Weekly loss limit
        weekly_loss_pct = (
            abs(self.weekly_pnl) / account.balance * 100 if account.balance > 0 else 0
        )
        if self.weekly_pnl < 0 and weekly_loss_pct >= self.config.max_weekly_loss_pct:
            return False, f"Weekly loss limit reached ({weekly_loss_pct:.1f}%)"

        # Max drawdown
        if self.peak_balance > 0:
            drawdown_pct = (self.peak_balance - account.equity) / self.peak_balance * 100
            if drawdown_pct >= self.config.max_drawdown_pct:
                self.bot_paused = True
                self.pause_reason = f"Max drawdown reached ({drawdown_pct:.1f}%)"
                return False, self.pause_reason

        # Correlation check
        corr_count = self._count_correlated(signal.symbol, open_trades)
        if corr_count >= 2:
            return False, f"Too many correlated positions ({signal.symbol})"

        # No duplicate symbol+direction
        for trade in open_trades:
            if trade.symbol == signal.symbol and trade.direction == signal.direction:
                return False, f"Already have {signal.direction.value} on {signal.symbol}"

        return True, "OK"

    def update_pnl(self, profit: float) -> None:
        """Update daily/weekly P&L after a trade closes."""
        self.daily_pnl += profit
        self.weekly_pnl += profit

    def update_peak_balance(self, balance: float) -> None:
        """Track peak balance for drawdown calculation."""
        if balance > self.peak_balance:
            self.peak_balance = balance

    def get_trailing_stop(
        self,
        trade: Trade,
        current_price: float,
        atr_value: float,
        trail_multiplier: float = 1.0,
    ) -> float | None:
        """
        Calculate trailing stop level.
        Only trails after profit >= 1:1 R:R.
        Returns new SL or None if no update needed.
        """
        entry = trade.entry_price
        original_sl_dist = abs(entry - trade.stop_loss)

        if trade.direction == Direction.BUY:
            profit_dist = current_price - entry
            if profit_dist < original_sl_dist:
                return None  # Not yet at 1:1 R:R
            trail_distance = atr_value * trail_multiplier
            new_sl = current_price - trail_distance
            if new_sl > trade.stop_loss:
                return round(new_sl, 5)
        else:
            profit_dist = entry - current_price
            if profit_dist < original_sl_dist:
                return None
            trail_distance = atr_value * trail_multiplier
            new_sl = current_price + trail_distance
            if new_sl < trade.stop_loss:
                return round(new_sl, 5)

        return None

    def should_partial_close(self, trade: Trade, current_price: float) -> bool:
        """Check if we should partial close at 1:1 R:R."""
        entry = trade.entry_price
        sl_dist = abs(entry - trade.stop_loss)

        if trade.direction == Direction.BUY:
            return current_price - entry >= sl_dist
        else:
            return entry - current_price >= sl_dist

    def _count_correlated(self, symbol: str, open_trades: list[Trade]) -> int:
        """Count open trades in the same correlation group."""
        my_group = None
        for group in CORRELATION_GROUPS:
            if symbol in group:
                my_group = group
                break
        if my_group is None:
            return 0
        return sum(1 for t in open_trades if t.symbol in my_group)

    def _check_reset(self, account: AccountInfo) -> None:
        """Reset daily/weekly counters at appropriate times."""
        now = datetime.now(timezone.utc)
        day = now.timetuple().tm_yday
        week = now.isocalendar()[1]

        if day != self.last_reset_day:
            self.daily_pnl = 0.0
            self.last_reset_day = day
            logger.debug("Daily P&L reset")

        if week != self.last_reset_week:
            self.weekly_pnl = 0.0
            self.last_reset_week = week
            logger.debug("Weekly P&L reset")

        self.update_peak_balance(account.balance)
