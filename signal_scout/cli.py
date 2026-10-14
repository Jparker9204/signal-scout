"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading

from dotenv import load_dotenv

from .config import load_config
from .http import build_session
from .logging_setup import setup_logging
from .notifier import DryRunNotifier, TelegramNotifier
from .runner import build_sources, run_once
from .store import SeenStore

log = logging.getLogger("signal_scout")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="signal-scout", description=__doc__)
    p.add_argument("-c", "--config", default="config.yaml", help="path to config YAML")
    p.add_argument("--once", action="store_true", help="run a single scan and exit")
    p.add_argument("--dry-run", action="store_true", help="print alerts instead of sending")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv()
    cfg = load_config(args.config)
    setup_logging(os.environ.get("LOG_LEVEL", cfg["log_level"]))

    session = build_session()
    if args.dry_run:
        notifier = DryRunNotifier()
    else:
        try:
            notifier = TelegramNotifier(
                os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                os.environ.get("TELEGRAM_CHAT_ID", ""),
                session,
            )
        except ValueError as exc:
            log.error(str(exc))
            return 2

    sources = build_sources(cfg, session)
    if not sources:
        log.error("no sources enabled in config")
        return 2
    store = SeenStore(cfg["db_path"])
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    try:
        while True:
            stats = run_once(sources, store, notifier, cfg["max_alerts_per_run"], args.dry_run)
            if args.once:
                return 1 if len(stats.failed) == len(sources) else 0
            if stop.wait(cfg["interval_minutes"] * 60):
                break
    except KeyboardInterrupt:
        pass
    finally:
        store.close()
    log.info("shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
