"""Source plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import requests

from ..models import Item


class Source(ABC):
    """Every source fetches public data and returns normalized, already-filtered Items."""

    name: ClassVar[str] = "base"

    def __init__(self, config: dict[str, Any], session: requests.Session) -> None:
        self.config = config or {}
        self.session = session
        self.timeout = float(self.config.get("timeout", 20))

    @abstractmethod
    def fetch(self) -> list[Item]:
        """Return items. May raise; the runner isolates failures per source."""

    def get_json(self, url: str, **kwargs: Any) -> Any:
        resp = self.session.get(url, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp.json()
