"""Core scan loop: fetch -> dedup -> notify, isolating failures per source."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests

from .models import Item
from .sources import REGISTRY, Source
from .store import SeenStore

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def send(self, item: Item) -> bool: ...


@dataclass
class RunStats:
    fetched: dict[str, int] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)
    new: int = 0
    sent: int = 0


def build_sources(cfg: dict[str, Any], session: requests.Session) -> list[Source]:
    sources: list[Source] = []
    for name, scfg in cfg.get("sources", {}).items():
        scfg = scfg or {}
        if not scfg.get("enabled", False):
            continue
        cls = REGISTRY.get(name)
        if cls is None:
            log.warning("unknown source in config", extra={"ctx": {"source": name}})
            continue
        sources.append(cls(scfg, session))
    return sources


def run_once(
    sources: list[Source],
    store: SeenStore,
    notifier: Notifier,
    max_alerts: int = 20,
    dry_run: bool = False,
) -> RunStats:
    stats = RunStats()
    for src in sources:
        try:
            items = src.fetch()
        except Exception as exc:  # graceful per-source failure
            stats.failed.append(src.name)
            log.error("source failed", extra={"ctx": {"source": src.name, "error": repr(exc)}})
            continue
        stats.fetched[src.name] = len(items)
        log.info("source fetched", extra={"ctx": {"source": src.name, "matched": len(items)}})
        for item in items:
            if store.is_seen(item.key):
                continue
            stats.new += 1
            if stats.sent >= max_alerts:
                continue
            if notifier.send(item):
                stats.sent += 1
                # In dry-run we don't persist, so a real run later still alerts.
                if not dry_run:
                    store.mark_seen(item.key)
    log.info(
        "run complete",
        extra={
            "ctx": {
                "fetched": stats.fetched,
                "failed": stats.failed,
                "new": stats.new,
                "sent": stats.sent,
                "dry_run": dry_run,
            }
        },
    )
    return stats
