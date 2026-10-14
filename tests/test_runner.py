import json
import logging

import responses

from signal_scout.logging_setup import JsonFormatter, redact
from signal_scout.models import Item
from signal_scout.notifier import TelegramNotifier, format_item
from signal_scout.runner import build_sources, run_once
from signal_scout.sources.base import Source


class FakeSource(Source):
    name = "fake"

    def fetch(self):
        return [Item("fake", "1", "one"), Item("fake", "2", "two")]


class BoomSource(Source):
    name = "boom"

    def fetch(self):
        raise ConnectionError("down")


class Collect:
    def __init__(self):
        self.sent = []

    def send(self, item):
        self.sent.append(item)
        return True


def test_dedup_across_runs(store, session):
    n = Collect()
    run_once([FakeSource({}, session)], store, n)
    run_once([FakeSource({}, session)], store, n)
    assert len(n.sent) == 2


def test_dry_run_does_not_persist(store, session):
    n = Collect()
    run_once([FakeSource({}, session)], store, n, dry_run=True)
    run_once([FakeSource({}, session)], store, n, dry_run=True)
    assert len(n.sent) == 4


def test_failing_source_isolated(store, session):
    n = Collect()
    stats = run_once([BoomSource({}, session), FakeSource({}, session)], store, n)
    assert stats.failed == ["boom"] and stats.sent == 2


def test_max_alerts(store, session):
    stats = run_once([FakeSource({}, session)], store, Collect(), max_alerts=1)
    assert stats.sent == 1 and stats.new == 2


def test_build_sources_respects_enabled(session):
    cfg = {"sources": {"crypto": {"enabled": False}, "jobs": {"enabled": True}, "nope": {}}}
    assert [s.name for s in build_sources(cfg, session)] == ["jobs"]


def test_format_escapes_html():
    assert "&lt;b&gt;" in format_item(Item("s", "1", "<b>x</b>"))


TOKEN = "123456789:" + "A" * 35


@responses.activate
def test_telegram_send_and_no_token_in_logs(session, caplog):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    responses.post(url, status=500)
    n = TelegramNotifier(TOKEN, "42", session)
    with caplog.at_level(logging.ERROR):
        assert n.send(Item("s", "1", "t")) is False
    assert TOKEN not in caplog.text
    responses.replace(responses.POST, url, json={"ok": True})
    assert n.send(Item("s", "1", "t")) is True
    assert json.loads(responses.calls[-1].request.body)["chat_id"] == "42"


def test_redaction(monkeypatch):
    monkeypatch.setenv("USAJOBS_API_KEY", "supersecretkey")
    assert "supersecretkey" not in redact("key=supersecretkey")
    assert TOKEN not in redact(f"url bot{TOKEN}/x")
    rec = logging.LogRecord("x", logging.INFO, "", 0, f"tok {TOKEN}", None, None)
    assert TOKEN not in JsonFormatter().format(rec)
