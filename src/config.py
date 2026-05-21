"""Bot configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class BrokerConfig(BaseSettings):
    broker_type: str = Field(default="demo", description="mt5 | oanda | demo")

    # MetaTrader 5
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""

    # OANDA
    oanda_api_key: str = ""
    oanda_account_id: str = ""
    oanda_environment: str = "practice"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("mt5_login", mode="before")
    @classmethod
    def parse_mt5_login(cls, v: object) -> int:
        if isinstance(v, str) and v.strip() == "":
            return 0
        return int(v)


class TradingConfig(BaseSettings):
    symbols: str = "EURUSD,GBPUSD"
    timeframe: str = "H1"
    risk_per_trade: float = 1.0
    max_open_trades: int = 3
    max_daily_loss_pct: float = 5.0
    max_weekly_loss_pct: float = 10.0
    max_drawdown_pct: float = 20.0
    rr_ratio: float = 2.0

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip() for s in self.symbols.split(",") if s.strip()]


class StrategyConfig(BaseSettings):
    active_strategies: str = "trend_following"

    # Trend Following
    ema_fast: int = 20
    ema_slow: int = 50
    ema_trend: int = 200
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_period: int = 14
    atr_sl_multiplier: float = 1.5

    # Mean Reversion
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_oversold: int = 30
    rsi_overbought: int = 70

    # Breakout
    breakout_lookback: int = 20
    breakout_atr_multiplier: float = 0.5

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def strategy_list(self) -> list[str]:
        return [s.strip() for s in self.active_strategies.split(",") if s.strip()]


class SessionConfig(BaseSettings):
    trading_sessions: str = "london,new_york"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def session_list(self) -> list[str]:
        return [s.strip() for s in self.trading_sessions.split(",") if s.strip()]


class TelegramConfig(BaseSettings):
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


class BacktestConfig(BaseSettings):
    backtest_start: str = "2021-01-01"
    backtest_end: str = "2024-12-31"
    backtest_initial_balance: float = 10000.0

    model_config = {"env_file": ".env", "extra": "ignore"}


class LogConfig(BaseSettings):
    log_level: str = "INFO"
    log_file: str = "logs/trading.log"

    model_config = {"env_file": ".env", "extra": "ignore"}


class BotConfig:
    """Aggregated bot configuration."""

    def __init__(self) -> None:
        self.broker = BrokerConfig()
        self.trading = TradingConfig()
        self.strategy = StrategyConfig()
        self.session = SessionConfig()
        self.telegram = TelegramConfig()
        self.backtest = BacktestConfig()
        self.log = LogConfig()
