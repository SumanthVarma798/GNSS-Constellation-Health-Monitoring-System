"""The Alerts logic: Healthchecks rows, green streak, failed runs, and plain trouble words."""
from datetime import datetime, timezone
from types import SimpleNamespace

import requests

from evidence import alerts

NOW = datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)


def run(workflow, created, conclusion="success", event="schedule", status="completed", updated=None):
    return {
        "path": f".github/workflows/{workflow}",
        "event": event,
        "status": status,
        "conclusion": conclusion,
        "created_at": created,
        "updated_at": updated or created,
        "html_url": f"https://github.com/x/{workflow}/{created}",
        "name": workflow,
    }


def test_check_rows_cover_every_status_and_list_missing_and_extra_checks():
    checks = [
        {"slug": "archive-documents", "unique_key": "a-docs", "status": "up",
         "last_ping": "2026-10-20T10:00:00Z", "next_ping": "2026-10-20T13:00:00Z"},
        {"slug": "archive-catalogues", "unique_key": "a-catalogues", "status": "grace",
         "last_ping": "2026-10-20T09:00:00Z", "next_ping": "2026-10-20T12:00:00Z"},
        {"slug": "archive-orbital", "unique_key": "a-orbital", "status": "down",
         "last_ping": "2026-10-20T08:00:00Z", "next_ping": "2026-10-20T11:00:00Z"},
        {"slug": "archive-news", "unique_key": "a-news", "status": "new", "last_ping": None, "next_ping": None},
        {"slug": "archive-social", "unique_key": "a-social", "status": "paused", "last_ping": None, "next_ping": None},
        {"slug": "extra-watch", "unique_key": "x-watch", "status": "up", "last_ping": "2026-10-20T07:00:00Z", "next_ping": None},
    ]
    flips = {
        "archive-orbital": [{"timestamp": "t1", "up": 1}, {"timestamp": "t2", "up": 0}, {"timestamp": "t3", "up": 0}],
        "archive-news": [{"timestamp": "t4", "up": 0}],
        "extra-watch": [{"timestamp": "t5", "up": 0}, {"timestamp": "t6", "up": 1}],
    }

    rows = alerts.check_rows(checks, flips)
    by_slug = {row["slug"]: row for row in rows}

    assert by_slug["archive-documents"]["tone"] == "ok"
    assert by_slug["archive-documents"]["words"] == "Up"
    assert by_slug["archive-catalogues"]["words"] == "Late, within grace time"
    assert by_slug["archive-orbital"]["tone"] == "bad"
    assert by_slug["archive-orbital"]["down_times"] == 2
    assert by_slug["archive-news"]["words"] == "No report yet"
    assert by_slug["archive-news"]["down_times"] == 1
    assert by_slug["archive-social"]["words"] == "Paused"
    assert by_slug["registry-update"]["words"] == "No check: its reports are lost"
    assert by_slug["update-tle-data"]["words"] == "No check: its reports are lost"
    assert by_slug["extra-watch"]["job"] == "not one of our jobs"
    assert by_slug["extra-watch"]["down_times"] == 1


def test_missing_slugs_are_reported_in_checks_order():
    checks = [{"slug": "archive-documents"}, {"slug": "archive-orbital"}, {"slug": "update-tle-data"}]

    assert alerts.missing_slugs(checks) == [
        "archive-catalogues",
        "archive-news",
        "archive-social",
        "registry-update",
        "orbit-ages",
        "orbit-fresh",
        "rinex-check",
    ]


def test_a_failed_scheduled_run_sets_the_streak_start_from_its_updated_time():
    failed = run("registry-update.yml", "2026-10-20T10:00:00Z", conclusion="failure", updated="2026-10-20T10:30:00Z")
    runs = [run("archive.yml", "2026-10-20T08:00:00Z"), failed]

    streak = alerts.green_streak(runs, NOW)

    assert streak["since"] == datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)
    assert streak["broke_on"] == failed
    assert streak["at_least"] is False


def test_a_failed_run_started_by_hand_does_not_break_the_green_streak():
    runs = [
        run("archive.yml", "2026-10-20T08:00:00Z", conclusion="success", event="schedule"),
        run("archive.yml", "2026-10-20T11:00:00Z", conclusion="failure", event="workflow_dispatch"),
    ]

    streak = alerts.green_streak(runs, NOW)

    assert streak["at_least"] is True
    assert streak["broke_on"] is None
    assert streak["since"] == datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)


def test_without_a_scheduled_failure_the_streak_is_at_least_since_the_oldest_scheduled_run():
    runs = [
        run("registry-update.yml", "2026-10-20T08:00:00Z"),
        run("archive.yml", "2026-10-20T09:00:00Z"),
        run("tests.yml", "2026-10-20T07:00:00Z", conclusion="failure"),  # excluded
    ]

    streak = alerts.green_streak(runs, NOW)

    assert streak["at_least"] is True
    assert streak["since"] == datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
    assert streak["hours"] == 4.5


def test_without_scheduled_runs_the_streak_is_zero():
    runs = [run("tests.yml", "2026-10-20T08:00:00Z", conclusion="failure")]

    streak = alerts.green_streak(runs, NOW)

    assert streak == {"since": None, "hours": 0.0, "at_least": False, "broke_on": None}


def test_green_streak_ignores_in_progress_and_cancelled_runs():
    runs = [
        run("archive.yml", "2026-10-20T08:00:00Z", conclusion="success", status="completed"),
        run("archive.yml", "2026-10-20T09:00:00Z", conclusion="cancelled", status="completed"),
        run("registry-update.yml", "2026-10-20T10:00:00Z", conclusion="failure", status="in_progress"),
    ]

    streak = alerts.green_streak(runs, NOW)

    assert streak["at_least"] is True
    assert streak["broke_on"] is None
    assert streak["since"] == datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)


def test_green_streak_returns_no_runs_when_only_non_counting_runs_exist():
    runs = [
        run("archive.yml", "2026-10-20T09:00:00Z", conclusion="cancelled", status="completed"),
        run("registry-update.yml", "2026-10-20T10:00:00Z", conclusion="failure", status="in_progress"),
    ]

    streak = alerts.green_streak(runs, NOW)

    assert streak == {"since": None, "hours": 0.0, "at_least": False, "broke_on": None}


def test_failed_runs_are_newest_first_and_exclude_tests_and_successes():
    runs = [
        run("archive.yml", "2026-10-20T10:00:00Z", conclusion="failure", event="schedule"),
        run("registry-update.yml", "2026-10-20T11:00:00Z", conclusion="timed_out", event="workflow_dispatch"),
        run("update-tle-data.yml", "2026-10-20T12:00:00Z", conclusion="success", event="schedule"),
        run("tests.yml", "2026-10-20T13:00:00Z", conclusion="failure", event="schedule"),
    ]

    rows = alerts.failed_runs(runs)

    assert [row["job"] for row in rows] == ["Registry update", "Archive"]
    assert [row["words"] for row in rows] == ["Timed out", "Failed"]
    assert [row["started"] for row in rows] == ["started by hand", "on schedule"]


def test_failed_runs_use_unknown_when_event_is_missing():
    rows = alerts.failed_runs([run("archive.yml", "2026-10-20T10:00:00Z", conclusion="failure", event=None)])

    assert rows[0]["started"] == "unknown"


def test_healthchecks_trouble_words_never_leak_the_key():
    key = "secret-token-value"
    refused = alerts.trouble(requests.HTTPError("no", response=SimpleNamespace(status_code=401)))
    timeout = alerts.trouble(requests.RequestException("timed out"))

    assert "refused the key" in refused and key not in refused
    assert "did not answer" in timeout and key not in timeout
