"""Demo broker for paper trading and testing without a real broker connection."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.data.broker_base import BrokerBase
from src.data.models import (
    AccountInfo,
    Direction,
    OrderStatus,
    SymbolInfo,
    Timeframe,
    Trade,
)
from src.utils.logger import get_logger

logger = get_logger("forex_bot.demo_broker")

# Default symbol specifications
DEFAULT_SYMBOLS: dict[str, SymbolInfo] = {
    "EURUSD": SymbolInfo("EURUSD", 0.0001, 100000, spread=1.2),
    "GBPUSD": SymbolInfo("GBPUSD", 0.0001, 100000, spread=1.5),
    "USDJPY": SymbolInfo("USDJPY", 0.01, 100000, spread=1.0),
    "AUDUSD": SymbolInfo("AUDUSD", 0.0001, 100000, spread=1.4),
    "USDCHF": SymbolInfo("USDCHF", 0.0001, 100000, spread=1.6),
    "USDCAD": SymbolInfo("USDCAD", 0.0001, 100000, spread=1.8),
    "NZDUSD": SymbolInfo("NZDUSD", 0.0001, 100000, spread=2.0),
    "EURGBP": SymbolInfo("EURGBP", 0.0001, 100000, spread=1.5),
}


class DemoBroker(BrokerBase):
    """Simulated broker for paper trading. Generates synthetic price data."""

    def __init__(self, initial_balance: float = 10000.0) -> None:
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.open_trades: list[Trade] = []
        self.closed_trades: list[Trade] = []
        self.connected = False

        # Simulated price state
        self._prices: dict[str, float] = {
            "EURUSD": 1.0850,
            "GBPUSD": 1.2650,
            "USDJPY": 149.50,
            "AUDUSD": 0.6550,
            "USDCHF": 0.8750,
            "USDCAD": 1.3650,
            "NZDUSD": 0.6100,
            "EURGBP": 0.8575,
        }

    def connect(self) -> bool:
        self.connected = True
        logger.info("Demo broker connected (paper trading mode)")
        return True

    def disconnect(self) -> None:
        self.connected = False
        logger.info("Demo broker disconnected")

    def get_candles(
        self, symbol: str, timeframe: Timeframe, count: int = 250
    ) -> pd.DataFrame:
        """Generate synthetic OHLCV data for backtesting/demo."""
        base_price = self._prices.get(symbol, 1.0)
        pip = DEFAULT_SYMBOLS.get(symbol, DEFAULT_SYMBOLS["EURUSD"]).pip_size

        now = datetime.now(timezone.utc)
        minutes = timeframe.minutes
        timestamps = [now - timedelta(minutes=minutes * (count - i)) for i in range(count)]

        np.random.seed(hash(symbol + str(now.date())) % (2**31))

        # Random walk for price
        returns = np.random.normal(0, 0.0005, count)
        prices = base_price * np.exp(np.cumsum(returns))

        # Generate OHLCV
        data = []
        for i in range(count):
            o = prices[i]
            noise = abs(np.random.normal(0, 10 * pip))
            h = o + noise
            low_val = o - abs(np.random.normal(0, 10 * pip))
            c = o + np.random.normal(0, 5 * pip)
            if low_val > o:
                low_val = o - noise
            if h < o:
                h = o + abs(np.random.normal(0, 10 * pip))
            v = abs(np.random.normal(1000, 300))
            data.append({
                "timestamp": timestamps[i],
                "open": round(o, 5),
                "high": round(max(h, o, c), 5),
                "low": round(min(low_val, o, c), 5),
                "close": round(c, 5),
                "volume": round(v, 0),
            })

        self._prices[symbol] = data[-1]["close"]
        return pd.DataFrame(data)

    def get_price(self, symbol: str) -> tuple[float, float]:
        info = DEFAULT_SYMBOLS.get(symbol, DEFAULT_SYMBOLS["EURUSD"])
        mid = self._prices.get(symbol, 1.0)
        spread_value = info.spread * info.pip_size
        bid = mid - spread_value / 2
        ask = mid + spread_value / 2
        return round(bid, 5), round(ask, 5)

    def get_account_info(self) -> AccountInfo:
        self._update_equity()
        margin = sum(
            t.lot_size * DEFAULT_SYMBOLS.get(t.symbol, DEFAULT_SYMBOLS["EURUSD"]).lot_size / 100
            for t in self.open_trades
        )
        return AccountInfo(
            balance=round(self.balance, 2),
            equity=round(self.equity, 2),
            margin=round(margin, 2),
            free_margin=round(self.equity - margin, 2),
        )

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        return DEFAULT_SYMBOLS.get(symbol, DEFAULT_SYMBOLS["EURUSD"])

    def place_order(
        self,
        symbol: str,
        direction: Direction,
        lot_size: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        comment: str = "",
    ) -> Trade | None:
        bid, ask = self.get_price(symbol)
        entry_price = ask if direction == Direction.BUY else bid

        trade = Trade(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            direction=direction,
            lot_size=lot_size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            open_time=datetime.now(timezone.utc),
            comment=comment,
        )
        self.open_trades.append(trade)
        logger.info(
            f"[DEMO] Opened {direction.value} {lot_size} {symbol} @ {entry_price} "
            f"SL={stop_loss} TP={take_profit}"
        )
        return trade

    def close_trade(self, trade_id: str) -> bool:
        for i, trade in enumerate(self.open_trades):
            if trade.id == trade_id:
                bid, ask = self.get_price(trade.symbol)
                close_price = bid if trade.direction == Direction.BUY else ask
                profit = self._calculate_profit(trade, close_price)

                trade.close_price = close_price
                trade.close_time = datetime.now(timezone.utc)
                trade.profit = profit
                trade.status = OrderStatus.CLOSED

                self.balance += profit
                self.closed_trades.append(trade)
                self.open_trades.pop(i)

                logger.info(
                    f"[DEMO] Closed {trade.direction.value} {trade.symbol} @ {close_price} "
                    f"P&L={profit:+.2f}"
                )
                return True
        return False

    def modify_trade(
        self,
        trade_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> bool:
        for trade in self.open_trades:
            if trade.id == trade_id:
                if stop_loss is not None:
                    trade.stop_loss = stop_loss
                if take_profit is not None:
                    trade.take_profit = take_profit
                return True
        return False

    def get_open_trades(self, symbol: str | None = None) -> list[Trade]:
        if symbol is None:
            return list(self.open_trades)
        return [t for t in self.open_trades if t.symbol == symbol]

    def get_trade_history(
        self, symbol: str | None = None, limit: int = 100
    ) -> list[Trade]:
        trades = self.closed_trades
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]
        return trades[-limit:]

    def _calculate_profit(self, trade: Trade, close_price: float) -> float:
        info = DEFAULT_SYMBOLS.get(trade.symbol, DEFAULT_SYMBOLS["EURUSD"])
        pip_value = info.lot_size * info.pip_size
        price_diff = close_price - trade.entry_price
        if trade.direction == Direction.SELL:
            price_diff = -price_diff
        pips = price_diff / info.pip_size
        return round(pips * pip_value * trade.lot_size / info.lot_size, 2)

    def _update_equity(self) -> None:
        unrealized = 0.0
        for trade in self.open_trades:
            bid, ask = self.get_price(trade.symbol)
            close_price = bid if trade.direction == Direction.BUY else ask
            unrealized += self._calculate_profit(trade, close_price)
        self.equity = self.balance + unrealized

    def simulate_price_tick(self, symbol: str, new_price: float) -> None:
        """Manually set price for testing."""
        self._prices[symbol] = new_price

    def check_sl_tp(self) -> list[Trade]:
        """Check and trigger stop loss / take profit for open trades."""
        closed = []
        for trade in list(self.open_trades):
            bid, ask = self.get_price(trade.symbol)
            triggered = False
            if trade.direction == Direction.BUY:
                if trade.stop_loss > 0 and bid <= trade.stop_loss:
                    triggered = True
                elif trade.take_profit > 0 and bid >= trade.take_profit:
                    triggered = True
            else:
                if trade.stop_loss > 0 and ask >= trade.stop_loss:
                    triggered = True
                elif trade.take_profit > 0 and ask <= trade.take_profit:
                    triggered = True

            if triggered:
                self.close_trade(trade.id)
                closed.append(trade)
        return closed
