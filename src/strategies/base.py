"""Base strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.config import StrategyConfig
from src.data.models import Signal
from src.indicators.technical import IndicatorSet


class StrategyBase(ABC):
    """Interface for all trading strategies."""

    name: str = "base"

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    @abstractmethod
    def check_entry(self, symbol: str, indicators: IndicatorSet) -> Signal | None:
        """Check for entry signal. Returns Signal or None."""

    @abstractmethod
    def check_exit(self, symbol: str, indicators: IndicatorSet, direction: str) -> bool:
        """Check if an existing position should be closed."""
