"""
Mean Reversion Strategy using Bollinger Bands + RSI.

Entry conditions (BUY):
  1. Price touches or closes below lower Bollinger Band
  2. RSI < oversold threshold (default 30)
  3. Price is within a ranging market (ADX < 25 or EMA flat)

Entry conditions (SELL):
  1. Price touches or closes above upper Bollinger Band
  2. RSI > overbought threshold (default 70)
  3. Price is within a ranging market

Exit:
  - Price returns to middle Bollinger Band (SMA 20)
  - RSI returns to neutral zone (40-60)
"""

from __future__ import annotations

from src.config import StrategyConfig
from src.data.models import Direction, Signal
from src.indicators.technical import IndicatorSet
from src.strategies.base import StrategyBase


class MeanReversionStrategy(StrategyBase):
    name = "mean_reversion"

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)

    def check_entry(self, symbol: str, indicators: IndicatorSet) -> Signal | None:
        close = indicators.close
        if len(close) < 2:
            return None

        price = close.iloc[-1]
        rsi_val = indicators.rsi.iloc[-1]
        bb_upper = indicators.bollinger.upper.iloc[-1]
        bb_lower = indicators.bollinger.lower.iloc[-1]
        bb_middle = indicators.bollinger.middle.iloc[-1]
        atr_val = indicators.atr.iloc[-1]

        # Check if market is ranging (EMA fast and slow are close together)
        ema_diff = abs(indicators.ema_fast.iloc[-1] - indicators.ema_slow.iloc[-1])
        is_ranging = ema_diff < atr_val * 0.5

        if not is_ranging:
            return None

        # --- BUY: Price at lower band + RSI oversold ---
        if price <= bb_lower and rsi_val < self.config.rsi_oversold:
            sl = price - atr_val * self.config.atr_sl_multiplier
            tp = bb_middle  # Target: middle band
            return Signal(
                symbol=symbol,
                direction=Direction.BUY,
                strategy=self.name,
                strength=min(0.5 + (self.config.rsi_oversold - rsi_val) / 100, 1.0),
                stop_loss=round(sl, 5),
                take_profit=round(tp, 5),
                metadata={"rsi": rsi_val, "bb_lower": bb_lower, "bb_middle": bb_middle},
            )

        # --- SELL: Price at upper band + RSI overbought ---
        if price >= bb_upper and rsi_val > self.config.rsi_overbought:
            sl = price + atr_val * self.config.atr_sl_multiplier
            tp = bb_middle
            return Signal(
                symbol=symbol,
                direction=Direction.SELL,
                strategy=self.name,
                strength=min(0.5 + (rsi_val - self.config.rsi_overbought) / 100, 1.0),
                stop_loss=round(sl, 5),
                take_profit=round(tp, 5),
                metadata={"rsi": rsi_val, "bb_upper": bb_upper, "bb_middle": bb_middle},
            )

        return None

    def check_exit(self, symbol: str, indicators: IndicatorSet, direction: str) -> bool:
        if len(indicators.close) < 1:
            return False

        price = indicators.close.iloc[-1]
        rsi_val = indicators.rsi.iloc[-1]
        bb_middle = indicators.bollinger.middle.iloc[-1]

        if direction == "BUY":
            # Close when price returns to middle band or RSI neutral
            if price >= bb_middle or rsi_val > 55:
                return True
        elif direction == "SELL":
            if price <= bb_middle or rsi_val < 45:
                return True

        return False
