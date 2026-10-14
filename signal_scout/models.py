"""Normalized data model shared by all sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Item:
    """A normalized alert candidate produced by any source.

    ``uid`` must be stable across runs so the dedup store can recognize repeats.
    """

    source: str
    uid: str
    title: str
    url: str = ""
    summary: str = ""
    extra: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.uid}"
