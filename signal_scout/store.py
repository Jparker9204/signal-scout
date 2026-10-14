"""SQLite-backed dedup store."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class SeenStore:
    def __init__(self, path: str | Path = "data/seen.db") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, first_seen REAL NOT NULL)"
        )
        self.conn.commit()

    def is_seen(self, key: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM seen WHERE key = ?", (key,)).fetchone()
        return row is not None

    def mark_seen(self, key: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO seen (key, first_seen) VALUES (?, ?)", (key, time.time())
        )
        self.conn.commit()

    def prune(self, max_age_days: float) -> int:
        cutoff = time.time() - max_age_days * 86400
        cur = self.conn.execute("DELETE FROM seen WHERE first_seen < ?", (cutoff,))
        self.conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self.conn.close()
