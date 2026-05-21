"""Trade execution and management - order placement, trailing stops, partial closes."""

from __future__ import annotations

from src.config import StrategyConfig, TradingConfig
from src.data.broker_base import BrokerBase
from src.data.models import Direction, Signal, Trade
from src.indicators.technical import IndicatorSet
from src.risk.manager import RiskManager
from src.utils.logger import get_logger

logger = get_logger("forex_bot.execution")


class TradeManager:
    """Handles trade execution, modification, and lifecycle management."""

    def __init__(
        self,
        broker: BrokerBase,
        risk_manager: RiskManager,
        trading_config: TradingConfig,
        strategy_config: StrategyConfig,
    ) -> None:
        self.broker = broker
        self.risk = risk_manager
        self.trading_config = trading_config
        self.strategy_config = strategy_config
        self._partial_closed: set[str] = set()  # Trade IDs already partial-closed

    def execute_signal(self, signal: Signal) -> Trade | None:
        """Validate and execute a trading signal."""
        account = self.broker.get_account_info()
        open_trades = self.broker.get_open_trades()

        # Risk check
        allowed, reason = self.risk.can_open_trade(signal, account, open_trades)
        if not allowed:
            logger.info("Trade rejected: %s", reason)
            return None

        # Calculate position size
        symbol_info = self.broker.get_symbol_info(signal.symbol)
        sl_distance = abs(signal.stop_loss - self._get_entry_price(signal))
        sl_pips = sl_distance / symbol_info.pip_size

        lot_size = self.risk.calculate_lot_size(account, symbol_info, sl_pips)
        if lot_size <= 0:
            logger.warning("Calculated lot size is 0, skipping trade")
            return None

        # Place order
        trade = self.broker.place_order(
            symbol=signal.symbol,
            direction=signal.direction,
            lot_size=lot_size,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            comment=f"{signal.strategy}|str={signal.strength:.2f}",
        )

        if trade:
            trade.strategy = signal.strategy
            logger.info(
                "TRADE OPENED: %s %s %.2f lots @ %.5f | SL=%.5f TP=%.5f | Strategy=%s",
                signal.direction.value,
                signal.symbol,
                lot_size,
                trade.entry_price,
                signal.stop_loss,
                signal.take_profit,
                signal.strategy,
            )

        return trade

    def manage_open_trades(self, symbol: str, indicators: IndicatorSet) -> None:
        """Update trailing stops and check for partial close opportunities."""
        open_trades = self.broker.get_open_trades(symbol)
        if not open_trades:
            return

        atr_val = indicators.atr.iloc[-1]
        bid_ask = self.broker.get_price(symbol)

        for trade in open_trades:
            current_price = bid_ask[0] if trade.direction == Direction.BUY else bid_ask[1]

            # Partial close at 1:1 R:R
            if trade.id not in self._partial_closed:
                if self.risk.should_partial_close(trade, current_price):
                    self._do_partial_close(trade)

            # Trailing stop
            new_sl = self.risk.get_trailing_stop(
                trade, current_price, atr_val, trail_multiplier=1.0
            )
            if new_sl is not None:
                success = self.broker.modify_trade(trade.id, stop_loss=new_sl)
                if success:
                    logger.info(
                        "Trailing stop updated: %s %s SL -> %.5f",
                        trade.symbol, trade.direction.value, new_sl,
                    )

    def close_trade_with_reason(self, trade: Trade, reason: str) -> bool:
        """Close a trade and log the reason."""
        success = self.broker.close_trade(trade.id)
        if success:
            logger.info(
                "TRADE CLOSED: %s %s | Reason: %s",
                trade.symbol, trade.direction.value, reason,
            )
            # Get updated trade info for P&L
            history = self.broker.get_trade_history(trade.symbol, limit=1)
            if history:
                self.risk.update_pnl(history[-1].profit)
        return success

    def close_all_trades(self, symbol: str | None = None, reason: str = "") -> int:
        """Close all open trades. Returns count of closed trades."""
        trades = self.broker.get_open_trades(symbol)
        closed = 0
        for trade in trades:
            if self.broker.close_trade(trade.id):
                closed += 1
                logger.info("Closed %s %s | %s", trade.symbol, trade.direction.value, reason)
        return closed

    def _do_partial_close(self, trade: Trade) -> None:
        """Close 50% of position and move SL to breakeven."""
        # For demo/backtest: just move SL to breakeven (partial close not supported everywhere)
        self.broker.modify_trade(trade.id, stop_loss=trade.entry_price)
        self._partial_closed.add(trade.id)
        logger.info(
            "Partial close (breakeven): %s %s SL -> entry @ %.5f",
            trade.symbol, trade.direction.value, trade.entry_price,
        )

    def _get_entry_price(self, signal: Signal) -> float:
        """Get expected entry price for lot size calculation."""
        bid, ask = self.broker.get_price(signal.symbol)
        return ask if signal.direction == Direction.BUY else bid
