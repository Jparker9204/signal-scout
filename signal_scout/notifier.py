"""Telegram notifier (and a dry-run stand-in)."""

from __future__ import annotations

import html
import logging

import requests

from .models import Item

log = logging.getLogger(__name__)


def format_item(item: Item) -> str:
    parts = [f"<b>[{html.escape(item.source)}]</b> {html.escape(item.title)}"]
    if item.summary:
        parts.append(html.escape(item.summary))
    if item.url:
        parts.append(html.escape(item.url))
    return "\n".join(parts)


class DryRunNotifier:
    def send(self, item: Item) -> bool:
        print("---- DRY RUN ----\n" + format_item(item))
        return True


class TelegramNotifier:
    API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, token: str, chat_id: str, session: requests.Session) -> None:
        if not token or not chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
        self._token = token
        self._chat_id = chat_id
        self._session = session

    def send(self, item: Item) -> bool:
        try:
            resp = self._session.post(
                self.API.format(token=self._token),
                json={
                    "chat_id": self._chat_id,
                    "text": format_item(item),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            # Never include the URL (it embeds the token); log only the error type/status.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            log.error(
                "telegram send failed",
                extra={"ctx": {"error": type(exc).__name__, "status": status}},
            )
            return False
