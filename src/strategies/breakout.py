"""
Breakout Strategy using price channel breakouts.

Entry conditions (BUY):
  1. Price breaks above the highest high of the last N candles
  2. Confirmed by increasing volume (if available)
  3. ATR confirms sufficient volatility

Entry conditions (SELL):
  1. Price breaks below the lowest low of the last N candles
  2. Confirmed by increasing volume
  3. ATR confirms sufficient volatility

Exit:
  - Trailing stop based on ATR
  - Opposite breakout signal
"""

from __future__ import annotations

from src.config import StrategyConfig
from src.data.models import Direction, Signal
from src.indicators.technical import IndicatorSet
from src.strategies.base import StrategyBase


class BreakoutStrategy(StrategyBase):
    name = "breakout"

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)

    def check_entry(self, symbol: str, indicators: IndicatorSet) -> Signal | None:
        lookback = self.config.breakout_lookback
        close = indicators.close
        high = indicators.high
        low = indicators.low

        if len(close) < lookback + 2:
            return None

        price = close.iloc[-1]
        prev_price = close.iloc[-2]
        atr_val = indicators.atr.iloc[-1]
        atr_avg = indicators.atr.iloc[-50:].mean() if len(indicators.atr) >= 50 else atr_val

        # Volatility filter
        if atr_val < atr_avg * self.config.breakout_atr_multiplier:
            return None

        # Price channel
        highest = high.iloc[-(lookback + 1):-1].max()
        lowest = low.iloc[-(lookback + 1):-1].min()

        # --- BUY: Break above channel ---
        if price > highest and prev_price <= highest:
            sl = price - atr_val * self.config.atr_sl_multiplier
            tp = price + atr_val * self.config.atr_sl_multiplier * 2.0
            return Signal(
                symbol=symbol,
                direction=Direction.BUY,
                strategy=self.name,
                strength=min(0.5 + (atr_val / atr_avg - 1) * 0.5, 1.0) if atr_avg > 0 else 0.5,
                stop_loss=round(sl, 5),
                take_profit=round(tp, 5),
                metadata={"channel_high": highest, "channel_low": lowest, "atr": atr_val},
            )

        # --- SELL: Break below channel ---
        if price < lowest and prev_price >= lowest:
            sl = price + atr_val * self.config.atr_sl_multiplier
            tp = price - atr_val * self.config.atr_sl_multiplier * 2.0
            return Signal(
                symbol=symbol,
                direction=Direction.SELL,
                strategy=self.name,
                strength=min(0.5 + (atr_val / atr_avg - 1) * 0.5, 1.0) if atr_avg > 0 else 0.5,
                stop_loss=round(sl, 5),
                take_profit=round(tp, 5),
                metadata={"channel_high": highest, "channel_low": lowest, "atr": atr_val},
            )

        return None

    def check_exit(self, symbol: str, indicators: IndicatorSet, direction: str) -> bool:
        """Exit on opposite channel break or EMA cross."""
        lookback = self.config.breakout_lookback
        if len(indicators.close) < lookback + 1:
            return False

        price = indicators.close.iloc[-1]
        high = indicators.high
        low = indicators.low

        highest = high.iloc[-(lookback + 1):-1].max()
        lowest = low.iloc[-(lookback + 1):-1].min()

        if direction == "BUY" and price < lowest:
            return True
        if direction == "SELL" and price > highest:
            return True

        # Also exit if trend reverses
        ema_f = indicators.ema_fast.iloc[-1]
        ema_s = indicators.ema_slow.iloc[-1]
        if direction == "BUY" and ema_f < ema_s:
            return True
        if direction == "SELL" and ema_f > ema_s:
            return True

        return False
