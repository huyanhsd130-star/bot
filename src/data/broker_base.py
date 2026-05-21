"""Abstract base class for broker implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from src.data.models import AccountInfo, Direction, SymbolInfo, Timeframe, Trade


class BrokerBase(ABC):
    """Interface that all broker implementations must follow."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the broker. Returns True on success."""

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the broker."""

    @abstractmethod
    def get_candles(
        self, symbol: str, timeframe: Timeframe, count: int = 250
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles. Returns DataFrame with columns:
        timestamp, open, high, low, close, volume
        """

    @abstractmethod
    def get_price(self, symbol: str) -> tuple[float, float]:
        """Get current bid/ask price. Returns (bid, ask)."""

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """Get current account information."""

    @abstractmethod
    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Get symbol specifications."""

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        direction: Direction,
        lot_size: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        comment: str = "",
    ) -> Trade | None:
        """Place a market order. Returns Trade on success, None on failure."""

    @abstractmethod
    def close_trade(self, trade_id: str) -> bool:
        """Close an open trade by ID. Returns True on success."""

    @abstractmethod
    def modify_trade(
        self,
        trade_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> bool:
        """Modify SL/TP of an open trade. Returns True on success."""

    @abstractmethod
    def get_open_trades(self, symbol: str | None = None) -> list[Trade]:
        """Get all open trades, optionally filtered by symbol."""

    @abstractmethod
    def get_trade_history(
        self, symbol: str | None = None, limit: int = 100
    ) -> list[Trade]:
        """Get closed trade history."""
