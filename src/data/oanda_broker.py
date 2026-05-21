"""OANDA broker implementation using REST API v20."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
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

logger = get_logger("forex_bot.oanda")

OANDA_TF_MAP = {
    "M1": "M1", "M5": "M5", "M15": "M15", "M30": "M30",
    "H1": "H1", "H4": "H4", "D1": "D", "W1": "W",
}

BASE_URLS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaBroker(BrokerBase):
    """OANDA v20 REST API broker."""

    def __init__(self, api_key: str, account_id: str, environment: str = "practice") -> None:
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = BASE_URLS.get(environment, BASE_URLS["practice"])
        self.client: httpx.Client | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def connect(self) -> bool:
        try:
            self.client = httpx.Client(
                base_url=self.base_url,
                headers=self._headers(),
                timeout=30.0,
            )
            resp = self.client.get(f"/v3/accounts/{self.account_id}/summary")
            resp.raise_for_status()
            logger.info("Connected to OANDA (%s)", self.base_url)
            return True
        except Exception as e:
            logger.error("Failed to connect to OANDA: %s", e)
            return False

    def disconnect(self) -> None:
        if self.client:
            self.client.close()
            self.client = None

    def _convert_symbol(self, symbol: str) -> str:
        """Convert EURUSD -> EUR_USD format for OANDA."""
        if "_" in symbol:
            return symbol
        if len(symbol) == 6:
            return f"{symbol[:3]}_{symbol[3:]}"
        return symbol

    def _revert_symbol(self, instrument: str) -> str:
        """Convert EUR_USD -> EURUSD."""
        return instrument.replace("_", "")

    def get_candles(
        self, symbol: str, timeframe: Timeframe, count: int = 250
    ) -> pd.DataFrame:
        instrument = self._convert_symbol(symbol)
        gran = OANDA_TF_MAP.get(timeframe.value, "H1")

        resp = self.client.get(
            f"/v3/instruments/{instrument}/candles",
            params={"granularity": gran, "count": count, "price": "M"},
        )
        resp.raise_for_status()
        candles = resp.json().get("candles", [])

        data = []
        for c in candles:
            if not c.get("complete", True):
                continue
            mid = c["mid"]
            data.append({
                "timestamp": datetime.fromisoformat(c["time"].replace("Z", "+00:00")),
                "open": float(mid["o"]),
                "high": float(mid["h"]),
                "low": float(mid["l"]),
                "close": float(mid["c"]),
                "volume": int(c.get("volume", 0)),
            })
        return pd.DataFrame(data)

    def get_price(self, symbol: str) -> tuple[float, float]:
        instrument = self._convert_symbol(symbol)
        resp = self.client.get(
            f"/v3/accounts/{self.account_id}/pricing",
            params={"instruments": instrument},
        )
        resp.raise_for_status()
        prices = resp.json().get("prices", [])
        if not prices:
            raise ValueError(f"No price data for {symbol}")
        bid = float(prices[0]["bids"][0]["price"])
        ask = float(prices[0]["asks"][0]["price"])
        return bid, ask

    def get_account_info(self) -> AccountInfo:
        resp = self.client.get(f"/v3/accounts/{self.account_id}/summary")
        resp.raise_for_status()
        acc = resp.json()["account"]
        return AccountInfo(
            balance=float(acc["balance"]),
            equity=float(acc["NAV"]),
            margin=float(acc.get("marginUsed", 0)),
            free_margin=float(acc.get("marginAvailable", 0)),
            currency=acc.get("currency", "USD"),
            leverage=int(1 / float(acc.get("marginRate", 0.01))),
        )

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        instrument = self._convert_symbol(symbol)
        resp = self.client.get(f"/v3/accounts/{self.account_id}/instruments",
                               params={"instruments": instrument})
        resp.raise_for_status()
        instruments = resp.json().get("instruments", [])
        if not instruments:
            raise ValueError(f"Symbol {symbol} not found")
        inst = instruments[0]
        pip_location = int(inst.get("pipLocation", -4))
        pip_size = 10 ** pip_location
        min_units = float(inst.get("minimumTradeSize", 1))
        return SymbolInfo(
            name=symbol,
            pip_size=pip_size,
            lot_size=1.0,  # OANDA uses units, not lots
            min_lot=min_units,
            max_lot=float(inst.get("maximumOrderUnits", 100000000)),
            lot_step=1.0,
        )

    def place_order(
        self,
        symbol: str,
        direction: Direction,
        lot_size: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        comment: str = "",
    ) -> Trade | None:
        instrument = self._convert_symbol(symbol)
        units = int(lot_size * 100000)
        if direction == Direction.SELL:
            units = -units

        order_data: dict = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",
            }
        }
        if stop_loss > 0:
            order_data["order"]["stopLossOnFill"] = {"price": f"{stop_loss:.5f}"}
        if take_profit > 0:
            order_data["order"]["takeProfitOnFill"] = {"price": f"{take_profit:.5f}"}

        try:
            resp = self.client.post(
                f"/v3/accounts/{self.account_id}/orders",
                json=order_data,
            )
            resp.raise_for_status()
            result = resp.json()

            fill = result.get("orderFillTransaction", {})
            trade_id = fill.get("tradeOpened", {}).get("tradeID", str(uuid.uuid4())[:8])
            price = float(fill.get("price", 0))

            trade = Trade(
                id=trade_id,
                symbol=symbol,
                direction=direction,
                lot_size=lot_size,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                open_time=datetime.now(timezone.utc),
                comment=comment,
            )
            logger.info("Opened %s %s %s @ %s", direction.value, lot_size, symbol, price)
            return trade
        except Exception as e:
            logger.error("Failed to place order: %s", e)
            return None

    def close_trade(self, trade_id: str) -> bool:
        try:
            resp = self.client.put(
                f"/v3/accounts/{self.account_id}/trades/{trade_id}/close",
            )
            resp.raise_for_status()
            logger.info("Closed trade %s", trade_id)
            return True
        except Exception as e:
            logger.error("Failed to close trade %s: %s", trade_id, e)
            return False

    def modify_trade(
        self,
        trade_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> bool:
        body: dict = {}
        if stop_loss is not None:
            body["stopLoss"] = {"price": f"{stop_loss:.5f}"}
        if take_profit is not None:
            body["takeProfit"] = {"price": f"{take_profit:.5f}"}

        try:
            resp = self.client.put(
                f"/v3/accounts/{self.account_id}/trades/{trade_id}/orders",
                json=body,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("Failed to modify trade %s: %s", trade_id, e)
            return False

    def get_open_trades(self, symbol: str | None = None) -> list[Trade]:
        resp = self.client.get(f"/v3/accounts/{self.account_id}/openTrades")
        resp.raise_for_status()
        trades = []
        for t in resp.json().get("trades", []):
            sym = self._revert_symbol(t["instrument"])
            if symbol and sym != symbol:
                continue
            units = int(t["currentUnits"])
            direction = Direction.BUY if units > 0 else Direction.SELL
            trades.append(Trade(
                id=t["id"],
                symbol=sym,
                direction=direction,
                lot_size=abs(units) / 100000,
                entry_price=float(t["price"]),
                stop_loss=float(t.get("stopLossOrder", {}).get("price", 0)),
                take_profit=float(t.get("takeProfitOrder", {}).get("price", 0)),
                open_time=datetime.fromisoformat(t["openTime"].replace("Z", "+00:00")),
                profit=float(t.get("unrealizedPL", 0)),
            ))
        return trades

    def get_trade_history(
        self, symbol: str | None = None, limit: int = 100
    ) -> list[Trade]:
        resp = self.client.get(
            f"/v3/accounts/{self.account_id}/trades",
            params={"state": "CLOSED", "count": limit},
        )
        resp.raise_for_status()
        trades = []
        for t in resp.json().get("trades", []):
            sym = self._revert_symbol(t["instrument"])
            if symbol and sym != symbol:
                continue
            units = int(t["initialUnits"])
            direction = Direction.BUY if units > 0 else Direction.SELL
            trades.append(Trade(
                id=t["id"],
                symbol=sym,
                direction=direction,
                lot_size=abs(units) / 100000,
                entry_price=float(t["price"]),
                stop_loss=0.0,
                take_profit=0.0,
                open_time=datetime.fromisoformat(t["openTime"].replace("Z", "+00:00")),
                close_price=float(t.get("averageClosePrice", 0)),
                close_time=datetime.fromisoformat(t["closeTime"].replace("Z", "+00:00"))
                if "closeTime" in t else None,
                profit=float(t.get("realizedPL", 0)),
                status=OrderStatus.CLOSED,
            ))
        return trades
