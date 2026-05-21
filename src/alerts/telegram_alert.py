"""Telegram bot integration for trade alerts and status updates."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from src.config import TelegramConfig
from src.data.models import Signal, Trade
from src.utils.logger import get_logger

logger = get_logger("forex_bot.telegram")


class TelegramAlert:
    """Send trading alerts and updates via Telegram bot."""

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(self, config: TelegramConfig) -> None:
        self.config = config
        self.enabled = config.telegram_enabled and bool(config.telegram_bot_token)
        if not self.enabled:
            logger.info("Telegram alerts disabled")

    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.enabled:
            return False

        url = f"{self.BASE_URL.format(token=self.config.telegram_bot_token)}/sendMessage"
        try:
            resp = httpx.post(
                url,
                json={
                    "chat_id": self.config.telegram_chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error("Failed to send Telegram message: %s", e)
            return False

    def notify_signal(self, signal: Signal) -> bool:
        emoji = "\U0001f7e2" if signal.direction.value == "BUY" else "\U0001f534"
        text = (
            f"{emoji} <b>NEW SIGNAL</b>\n\n"
            f"\U0001f4c8 <b>{signal.direction.value} {signal.symbol}</b>\n"
            f"\U0001f3af Strategy: {signal.strategy}\n"
            f"\U0001f4aa Strength: {signal.strength:.0%}\n"
            f"\U0001f6d1 SL: {signal.stop_loss:.5f}\n"
            f"\u2705 TP: {signal.take_profit:.5f}\n"
            f"\U0001f552 Time: {signal.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self._send_message(text)

    def notify_trade_opened(self, trade: Trade) -> bool:
        emoji = "\U0001f7e2" if trade.direction.value == "BUY" else "\U0001f534"
        text = (
            f"{emoji} <b>TRADE OPENED</b>\n\n"
            f"\U0001f4b0 {trade.direction.value} {trade.lot_size} lots {trade.symbol}\n"
            f"\U0001f4cd Entry: {trade.entry_price:.5f}\n"
            f"\U0001f6d1 SL: {trade.stop_loss:.5f}\n"
            f"\u2705 TP: {trade.take_profit:.5f}\n"
            f"\U0001f3af Strategy: {trade.strategy}\n"
            f"\U0001f194 ID: {trade.id}"
        )
        return self._send_message(text)

    def notify_trade_closed(self, trade: Trade) -> bool:
        emoji = "\U0001f4b5" if trade.profit > 0 else "\U0001f4b8"
        pnl_text = f"+${trade.profit:.2f}" if trade.profit > 0 else f"-${abs(trade.profit):.2f}"
        text = (
            f"{emoji} <b>TRADE CLOSED</b>\n\n"
            f"\U0001f4b0 {trade.direction.value} {trade.lot_size} lots {trade.symbol}\n"
            f"\U0001f4cd Entry: {trade.entry_price:.5f}\n"
            f"\U0001f3c1 Exit: {trade.close_price:.5f}\n"
            f"\U0001f4b5 P&L: <b>{pnl_text}</b>\n"
            f"\U0001f194 ID: {trade.id}"
        )
        return self._send_message(text)

    def notify_daily_summary(
        self,
        balance: float,
        daily_pnl: float,
        open_trades: int,
        total_trades_today: int,
    ) -> bool:
        emoji = "\U0001f4c8" if daily_pnl >= 0 else "\U0001f4c9"
        pnl_text = f"+${daily_pnl:.2f}" if daily_pnl >= 0 else f"-${abs(daily_pnl):.2f}"
        text = (
            f"{emoji} <b>DAILY SUMMARY</b>\n\n"
            f"\U0001f4b0 Balance: ${balance:,.2f}\n"
            f"\U0001f4b5 Daily P&L: <b>{pnl_text}</b>\n"
            f"\U0001f4ca Trades today: {total_trades_today}\n"
            f"\U0001f4c2 Open trades: {open_trades}\n"
            f"\U0001f552 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self._send_message(text)

    def notify_error(self, error_msg: str) -> bool:
        text = (
            f"\u26a0\ufe0f <b>BOT ALERT</b>\n\n"
            f"{error_msg}\n"
            f"\U0001f552 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self._send_message(text)

    def notify_bot_started(self) -> bool:
        text = (
            f"\U0001f680 <b>BOT STARTED</b>\n\n"
            f"Forex Trading Bot is now running.\n"
            f"\U0001f552 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self._send_message(text)

    def notify_bot_stopped(self, reason: str = "") -> bool:
        text = (
            f"\U0001f6d1 <b>BOT STOPPED</b>\n\n"
            f"Reason: {reason or 'Manual stop'}\n"
            f"\U0001f552 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self._send_message(text)
