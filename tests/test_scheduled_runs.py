"""Scheduled runs: a failed download is tried again, never faster than the source allows, and every run
leaves one line in the run log. No network: replies are canned; the clock is frozen."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
import time_machine

from evidence import archive
from evidence.archive import FetchFailed, fetch, latest_version, object_path, read_runs, record
from evidence.settings import DOWNLOAD_TRIES, WAIT_BETWEEN_TRIES_SECONDS
from evidence.sources import CELESTRAK_GNSS_URL, IGS_SATELLITE_METADATA_URL

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import archive_sources  # noqa: E402

RUN_TIME = datetime(2026, 10, 19, 5, 18, 51, tzinfo=timezone.utc)   # when the documents job ran today (checked)
ARCHIVE_WORKFLOW = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "archive.yml").read_text()


class Reply:
    def __init__(self, status, body=b"here"):
        self.status_code, self.content, self.headers = status, body, {"Content-Type": "text/plain"}


def answers(monkeypatch, *replies):
    """requests.get gives these replies in turn, raising any that is an exception. Returns (addresses asked, waits)."""
    replies, asked, waits = list(replies), [], []

    def get(address, timeout, headers, **_):   # **_: the redirect check (issue 13)
        asked.append(address)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(archive.requests, "get", get)
    monkeypatch.setattr(archive.time, "sleep", waits.append)
    return asked, waits


def run_job(monkeypatch, folder, group):
    monkeypatch.setattr(sys, "argv", ["archive_sources.py", "--archive", str(folder), "--group", group])
    with time_machine.travel(RUN_TIME, tick=False):
        archive_sources.main()


def test_two_failures_then_a_success(monkeypatch):
    asked, waits = answers(monkeypatch, requests.ConnectionError("reset"), Reply(503), Reply(200, b"third time"))

    assert fetch(IGS_SATELLITE_METADATA_URL)[:2] == (200, b"third time")
    assert len(asked) == 3 and waits == [WAIT_BETWEEN_TRIES_SECONDS] * 2


def test_it_gives_up_after_the_set_number_of_tries(monkeypatch):
    asked, _ = answers(monkeypatch, *[requests.Timeout("slow")] * DOWNLOAD_TRIES)

    with pytest.raises(FetchFailed, match=f"tried {DOWNLOAD_TRIES} times"):
        fetch(IGS_SATELLITE_METADATA_URL)
    assert len(asked) == DOWNLOAD_TRIES


def test_a_refusal_is_the_sources_answer_and_is_not_asked_again(monkeypatch):
    asked, _ = answers(monkeypatch, Reply(403))

    assert fetch(IGS_SATELLITE_METADATA_URL)[0] == 403
    assert len(asked) == 1


def test_celestrak_is_tried_once_a_run_because_a_retry_would_come_sooner_than_its_two_hours(monkeypatch):
    asked, waits = answers(monkeypatch, Reply(503))

    assert fetch(CELESTRAK_GNSS_URL)[0] == 503
    assert len(asked) == 1 and waits == []


def test_a_failed_run_keeps_the_last_saved_copy_and_says_so_in_the_log(monkeypatch, tmp_path):
    record(tmp_path, CELESTRAK_GNSS_URL, "2026-10-18T05:20:00Z", 200, b"yesterday's records")
    answers(monkeypatch, requests.ConnectionError("blocked"))

    with pytest.raises(SystemExit):
        run_job(monkeypatch, tmp_path, "orbital")

    latest = latest_version(tmp_path, CELESTRAK_GNSS_URL)
    assert object_path(tmp_path, latest["sha256"]).read_bytes() == b"yesterday's records"
    assert read_runs(tmp_path, "archive") == [{"job": "archive orbital", "started": "2026-10-19T05:18:51Z",
                                               "ended": "2026-10-19T05:18:51Z", "result": "failed: 1 of 1 sources",
                                               "changed": "nothing"}]


def test_each_run_adds_one_line_saying_what_changed(monkeypatch, tmp_path):
    answers(monkeypatch, Reply(200, b"first"), Reply(200, b"first"))

    run_job(monkeypatch, tmp_path, "documents")
    run_job(monkeypatch, tmp_path, "documents")

    lines = read_runs(tmp_path, "archive")
    assert [(line["job"], line["result"], line["changed"]) for line in lines] == [
        ("archive documents", "ok", IGS_SATELLITE_METADATA_URL),
        ("archive documents", "ok", "nothing"),
    ]


def test_a_run_that_stops_unexpectedly_still_leaves_its_line(monkeypatch, tmp_path):
    def disk_full(*args):
        raise OSError("disk full")

    answers(monkeypatch, Reply(200))
    monkeypatch.setattr(archive_sources, "record", disk_full)

    with pytest.raises(OSError):
        run_job(monkeypatch, tmp_path, "documents")
    assert [line["result"] for line in read_runs(tmp_path, "archive")] == ["stopped early"]


def test_provisional_source_failures_are_logged_but_do_not_fail_the_job(monkeypatch, tmp_path):
    addresses = ["https://celestrak.org/one", "https://celestrak.org/two"]
    monkeypatch.setattr(archive_sources, "archived_addresses", lambda group: addresses)
    answers(monkeypatch, Reply(200, b"kept"), requests.ConnectionError("blocked"))

    run_job(monkeypatch, tmp_path, "news")

    assert latest_version(tmp_path, addresses[0])["sha256"]
    assert read_runs(tmp_path, "archive") == [{"job": "archive news", "started": "2026-10-19T05:18:51Z",
                                               "ended": "2026-10-19T05:18:51Z", "result": "failed: 1 of 2 sources",
                                               "changed": addresses[0]}]


def test_a_provisional_run_that_fetches_nothing_fails(monkeypatch, tmp_path):
    addresses = ["https://news.example/one"]
    monkeypatch.setattr(archive_sources, "archived_addresses", lambda group: addresses)
    answers(monkeypatch, Reply(403))

    with pytest.raises(SystemExit):
        run_job(monkeypatch, tmp_path, "news")
    assert read_runs(tmp_path, "archive")[0]["result"] == "failed: 1 of 1 sources"


def test_the_alert_ping_does_not_fail_for_a_missing_check_or_an_unset_key():
    health_step = ARCHIVE_WORKFLOW.split("Tell Healthchecks.io how the run went", 1)[1]

    assert 'if [ -z "$KEY" ]' in health_step and "exit 0" in health_step
    assert '|| echo "::warning::Healthchecks.io did not take this report.' in health_step
