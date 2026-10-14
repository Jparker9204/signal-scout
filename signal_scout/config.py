"""Config loading (YAML) + secrets from environment (.env)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    cfg.setdefault("sources", {})
    cfg.setdefault("db_path", "data/seen.db")
    cfg.setdefault("interval_minutes", 30)
    cfg.setdefault("max_alerts_per_run", 20)
    cfg.setdefault("log_level", "INFO")
    return cfg
