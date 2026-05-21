"""
Multi-Indicator Trend Following Strategy.

Entry conditions (BUY):
  1. Price > EMA 200 (long-term uptrend)
  2. EMA fast > EMA slow (medium-term uptrend)
  3. MACD line crosses above signal line (momentum confirmation)
  4. RSI between 40-70 (not overbought/oversold)
  5. ATR > 50-period average ATR * 0.5 (sufficient volatility)

Entry conditions (SELL): Mirror of BUY.

Exit:
  - EMA fast crosses EMA slow against the trade direction
  - RSI extreme (>80 for longs, <20 for shorts)
  - MACD histogram weakening for 3 consecutive bars
"""

from __future__ import annotations

from src.config import StrategyConfig
from src.data.models import Direction, Signal
from src.indicators.technical import IndicatorSet
from src.strategies.base import StrategyBase


class TrendFollowingStrategy(StrategyBase):
    name = "trend_following"

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)

    def check_entry(self, symbol: str, indicators: IndicatorSet) -> Signal | None:
        close = indicators.close
        if len(close) < 2:
            return None

        price = close.iloc[-1]
        ema_f = indicators.ema_fast.iloc[-1]
        ema_s = indicators.ema_slow.iloc[-1]
        ema_t = indicators.ema_trend.iloc[-1]
        rsi_val = indicators.rsi.iloc[-1]
        macd_line = indicators.macd.line.iloc[-1]
        macd_signal = indicators.macd.signal.iloc[-1]
        macd_line_prev = indicators.macd.line.iloc[-2]
        macd_signal_prev = indicators.macd.signal.iloc[-2]
        atr_val = indicators.atr.iloc[-1]
        atr_avg = indicators.atr.iloc[-50:].mean() if len(indicators.atr) >= 50 else atr_val

        volatility_ok = atr_val > atr_avg * 0.5

        # --- BUY ---
        buy_trend = price > ema_t and ema_f > ema_s
        buy_momentum = macd_line > macd_signal and macd_line_prev <= macd_signal_prev
        buy_rsi = 40 < rsi_val < 70

        if buy_trend and buy_momentum and buy_rsi and volatility_ok:
            sl = price - atr_val * self.config.atr_sl_multiplier
            tp = price + atr_val * self.config.atr_sl_multiplier * 2.0
            strength = self._calc_strength(rsi_val, atr_val, atr_avg, is_buy=True)
            return Signal(
                symbol=symbol,
                direction=Direction.BUY,
                strategy=self.name,
                strength=strength,
                stop_loss=round(sl, 5),
                take_profit=round(tp, 5),
                metadata={"rsi": rsi_val, "atr": atr_val, "ema_trend": ema_t},
            )

        # --- SELL ---
        sell_trend = price < ema_t and ema_f < ema_s
        sell_momentum = macd_line < macd_signal and macd_line_prev >= macd_signal_prev
        sell_rsi = 30 < rsi_val < 60

        if sell_trend and sell_momentum and sell_rsi and volatility_ok:
            sl = price + atr_val * self.config.atr_sl_multiplier
            tp = price - atr_val * self.config.atr_sl_multiplier * 2.0
            strength = self._calc_strength(rsi_val, atr_val, atr_avg, is_buy=False)
            return Signal(
                symbol=symbol,
                direction=Direction.SELL,
                strategy=self.name,
                strength=strength,
                stop_loss=round(sl, 5),
                take_profit=round(tp, 5),
                metadata={"rsi": rsi_val, "atr": atr_val, "ema_trend": ema_t},
            )

        return None

    def check_exit(self, symbol: str, indicators: IndicatorSet, direction: str) -> bool:
        if len(indicators.close) < 4:
            return False

        ema_f = indicators.ema_fast.iloc[-1]
        ema_s = indicators.ema_slow.iloc[-1]
        rsi_val = indicators.rsi.iloc[-1]
        hist = indicators.macd.histogram

        if direction == "BUY":
            if ema_f < ema_s:
                return True
            if rsi_val > 80:
                return True
            # MACD histogram declining 3 bars
            if len(hist) >= 4:
                if hist.iloc[-1] < hist.iloc[-2] < hist.iloc[-3] < hist.iloc[-4]:
                    return True
        elif direction == "SELL":
            if ema_f > ema_s:
                return True
            if rsi_val < 20:
                return True
            if len(hist) >= 4:
                if hist.iloc[-1] > hist.iloc[-2] > hist.iloc[-3] > hist.iloc[-4]:
                    return True

        return False

    def _calc_strength(
        self, rsi: float, atr: float, atr_avg: float, is_buy: bool
    ) -> float:
        """Signal strength 0-1 based on indicator confluence."""
        score = 0.5  # base

        # RSI distance from neutral (50)
        if is_buy:
            if 50 < rsi < 65:
                score += 0.15
        else:
            if 35 < rsi < 50:
                score += 0.15

        # Volatility ratio
        if atr > atr_avg:
            score += 0.15
        if atr > atr_avg * 1.5:
            score += 0.1

        return min(score, 1.0)
