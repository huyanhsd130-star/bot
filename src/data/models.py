"""Data models used across the bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"

    @property
    def minutes(self) -> int:
        mapping = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 60, "H4": 240, "D1": 1440, "W1": 10080,
        }
        return mapping[self.value]


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Trade:
    id: str
    symbol: str
    direction: Direction
    lot_size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    open_time: datetime
    status: OrderStatus = OrderStatus.OPEN
    close_price: float = 0.0
    close_time: datetime | None = None
    profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    strategy: str = ""
    comment: str = ""


@dataclass
class Signal:
    symbol: str
    direction: Direction
    strategy: str
    strength: float = 1.0  # 0.0 - 1.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class AccountInfo:
    balance: float
    equity: float
    margin: float
    free_margin: float
    currency: str = "USD"
    leverage: int = 100


@dataclass
class SymbolInfo:
    name: str
    pip_size: float  # e.g., 0.0001 for EUR/USD, 0.01 for USD/JPY
    lot_size: float  # Contract size, e.g., 100000
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01
    spread: float = 0.0  # Current spread in pips
