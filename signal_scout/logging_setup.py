"""Structured (JSON) logging with secret redaction."""

from __future__ import annotations

import json
import logging
import os
import re

_SECRET_ENV = ("TELEGRAM_BOT_TOKEN", "USAJOBS_API_KEY")
# Telegram bot tokens look like 123456789:AA... ; scrub them even if not in env.
_TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{30,}\b")


def redact(text: str) -> str:
    for name in _SECRET_ENV:
        value = os.environ.get(name)
        if value and len(value) >= 6:
            text = text.replace(value, "***")
    return _TOKEN_RE.sub("***", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in getattr(record, "ctx", {}).items():
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return redact(json.dumps(payload, default=str))


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # urllib3 debug logs can include full URLs (with the bot token); keep them quiet.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
