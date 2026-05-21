"""Main trading bot orchestrator."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from src.alerts.telegram_alert import TelegramAlert
from src.config import BotConfig
from src.data.broker_base import BrokerBase
from src.data.demo_broker import DemoBroker
from src.data.models import Timeframe
from src.execution.trade_manager import TradeManager
from src.indicators.technical import compute_indicators
from src.risk.manager import RiskManager
from src.strategies.base import StrategyBase
from src.strategies.breakout import BreakoutStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.trend_following import TrendFollowingStrategy
from src.utils.logger import get_logger, setup_logger
from src.utils.time_utils import is_in_any_session, is_weekend

logger = get_logger("forex_bot")


class ForexBot:
    """Main trading bot that coordinates all modules."""

    def __init__(self, config: BotConfig | None = None) -> None:
        self.config = config or BotConfig()
        self.broker: BrokerBase | None = None
        self.risk_manager: RiskManager | None = None
        self.trade_manager: TradeManager | None = None
        self.telegram: TelegramAlert | None = None
        self.strategies: list[StrategyBase] = []
        self.running = False

        setup_logger("forex_bot", self.config.log.log_level, self.config.log.log_file)

    def initialize(self) -> bool:
        """Initialize all bot components."""
        logger.info("Initializing Forex Trading Bot...")

        # Initialize broker
        self.broker = self._create_broker()
        if not self.broker.connect():
            logger.error("Failed to connect to broker")
            return False

        # Initialize risk manager
        self.risk_manager = RiskManager(self.config.trading)
        account = self.broker.get_account_info()
        self.risk_manager.update_peak_balance(account.balance)

        # Initialize trade manager
        self.trade_manager = TradeManager(
            self.broker, self.risk_manager, self.config.trading, self.config.strategy
        )

        # Initialize strategies
        self._init_strategies()

        # Initialize Telegram
        self.telegram = TelegramAlert(self.config.telegram)

        logger.info("Bot initialized successfully")
        logger.info("  Broker: %s", self.config.broker.broker_type)
        logger.info("  Symbols: %s", self.config.trading.symbol_list)
        logger.info("  Timeframe: %s", self.config.trading.timeframe)
        logger.info("  Strategies: %s", [s.name for s in self.strategies])
        logger.info("  Risk per trade: %.1f%%", self.config.trading.risk_per_trade)
        logger.info("  Max open trades: %d", self.config.trading.max_open_trades)

        return True

    def run(self) -> None:
        """Main trading loop."""
        if not self.initialize():
            return

        self.running = True
        self.telegram.notify_bot_started()

        logger.info("Bot started. Entering main loop...")

        try:
            while self.running:
                self._tick()
                self._wait_for_next_candle()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            self.telegram.notify_bot_stopped("Manual stop (Ctrl+C)")
        except Exception as e:
            logger.exception("Bot crashed: %s", e)
            self.telegram.notify_error(f"Bot crashed: {e}")
        finally:
            self.shutdown()

    def _tick(self) -> None:
        """Process one iteration of the main loop."""
        now = datetime.now(timezone.utc)

        # Skip weekends
        if is_weekend(now):
            logger.debug("Weekend - market closed")
            return

        # Skip outside trading sessions
        sessions = self.config.session.session_list
        if sessions and not is_in_any_session(sessions, now):
            logger.debug("Outside trading sessions")
            return

        # Check if bot is paused (drawdown limit)
        if self.risk_manager.bot_paused:
            logger.warning("Bot paused: %s", self.risk_manager.pause_reason)
            return

        timeframe = Timeframe(self.config.trading.timeframe)

        for symbol in self.config.trading.symbol_list:
            try:
                self._process_symbol(symbol, timeframe)
            except Exception as e:
                logger.error("Error processing %s: %s", symbol, e)

        # Check SL/TP for demo broker
        if isinstance(self.broker, DemoBroker):
            closed = self.broker.check_sl_tp()
            for trade in closed:
                self.telegram.notify_trade_closed(trade)

    def _process_symbol(self, symbol: str, timeframe: Timeframe) -> None:
        """Process a single symbol - check signals and manage trades."""
        # Get candle data
        candles = self.broker.get_candles(symbol, timeframe, count=250)
        if candles is None or len(candles) < 55:
            logger.debug("Not enough data for %s", symbol)
            return

        # Compute indicators
        indicators = compute_indicators(
            candles,
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

        # Manage existing trades (trailing stop, partial close)
        self.trade_manager.manage_open_trades(symbol, indicators)

        # Check exit signals for open trades
        open_trades = self.broker.get_open_trades(symbol)
        for trade in open_trades:
            for strategy in self.strategies:
                if strategy.check_exit(symbol, indicators, trade.direction.value):
                    self.trade_manager.close_trade_with_reason(
                        trade, f"Exit signal from {strategy.name}"
                    )
                    self.telegram.notify_trade_closed(trade)
                    break

        # Check entry signals
        for strategy in self.strategies:
            signal = strategy.check_entry(symbol, indicators)
            if signal is None:
                continue

            logger.info(
                "Signal: %s %s from %s (strength=%.0f%%)",
                signal.direction.value, symbol, strategy.name, signal.strength * 100,
            )
            self.telegram.notify_signal(signal)

            # Execute trade
            trade = self.trade_manager.execute_signal(signal)
            if trade:
                self.telegram.notify_trade_opened(trade)

    def _wait_for_next_candle(self) -> None:
        """Wait until the next candle based on timeframe."""
        tf = Timeframe(self.config.trading.timeframe)
        sleep_seconds = tf.minutes * 60
        # In demo mode, use shorter intervals for faster simulation
        if self.config.broker.broker_type == "demo":
            sleep_seconds = min(sleep_seconds, 5)
        logger.debug("Waiting %d seconds for next candle...", sleep_seconds)
        time.sleep(sleep_seconds)

    def _create_broker(self) -> BrokerBase:
        broker_type = self.config.broker.broker_type.lower()
        if broker_type == "demo":
            return DemoBroker(self.config.backtest.backtest_initial_balance)
        elif broker_type == "oanda":
            from src.data.oanda_broker import OandaBroker
            return OandaBroker(
                api_key=self.config.broker.oanda_api_key,
                account_id=self.config.broker.oanda_account_id,
                environment=self.config.broker.oanda_environment,
            )
        elif broker_type == "mt5":
            logger.warning("MT5 broker only available on Windows")
            return DemoBroker(self.config.backtest.backtest_initial_balance)
        else:
            logger.warning("Unknown broker type: %s, using demo", broker_type)
            return DemoBroker(self.config.backtest.backtest_initial_balance)

    def _init_strategies(self) -> None:
        strategy_map: dict[str, type[StrategyBase]] = {
            "trend_following": TrendFollowingStrategy,
            "mean_reversion": MeanReversionStrategy,
            "breakout": BreakoutStrategy,
        }
        for name in self.config.strategy.strategy_list:
            cls = strategy_map.get(name)
            if cls:
                self.strategies.append(cls(self.config.strategy))
                logger.info("Loaded strategy: %s", name)
            else:
                logger.warning("Unknown strategy: %s", name)

    def shutdown(self) -> None:
        """Clean shutdown."""
        self.running = False
        if self.broker:
            account = self.broker.get_account_info()
            open_trades = self.broker.get_open_trades()
            logger.info(
                "Shutting down. Balance: $%.2f, Open trades: %d",
                account.balance, len(open_trades),
            )
            self.broker.disconnect()

    def get_status(self) -> dict:
        """Get current bot status."""
        account = self.broker.get_account_info() if self.broker else None
        open_trades = self.broker.get_open_trades() if self.broker else []
        return {
            "running": self.running,
            "paused": self.risk_manager.bot_paused if self.risk_manager else False,
            "balance": account.balance if account else 0,
            "equity": account.equity if account else 0,
            "open_trades": len(open_trades),
            "daily_pnl": self.risk_manager.daily_pnl if self.risk_manager else 0,
            "strategies": [s.name for s in self.strategies],
        }
