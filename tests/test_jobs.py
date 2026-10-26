"""The console's jobs (evidence/jobs.py): schedules read from the workflows, in words, what ran, and what needs a look."""
from datetime import datetime, timezone

import pytest

from evidence import jobs
from evidence.console_settings import JOBS, WORKFLOWS_DIR

NOW = datetime(2026, 10, 20, 14, 40, tzinfo=timezone.utc)   # a Tuesday
ARCHIVE = """on:
  schedule:
    - cron: '30 0 * * *'  # documents: once a day
    - cron: '50 */3 * * *'  # news: every 3 hours
  workflow_dispatch:
"""


def test_each_schedule_is_read_with_its_group():
    assert jobs.schedules(ARCHIVE) == {"documents": ["30 0 * * *"], "news": ["50 */3 * * *"]}
    assert jobs.schedules("on:\n  schedule:\n    - cron: '0 1 * * 0'\n") == {"": ["0 1 * * 0"]}
    assert jobs.schedules("on:\n  push:\n") == {}


def test_every_job_in_the_settings_has_its_workflow_and_schedule_group():
    for workflow, group, *_ in JOBS:
        text = (WORKFLOWS_DIR / workflow).read_text()
        assert not group or group in jobs.schedules(text), (workflow, group)


@pytest.mark.parametrize("cron, words", [
    ("30 0 * * *", "daily 00:30"), ("50 */3 * * *", "every 3 hours from 00:50"), ("0 1 * * 0", "Sundays 01:00"),
    ("15 4 1 * *", "15 4 1 * * (cron)")])
def test_a_schedule_is_said_in_words(cron, words):
    assert jobs.schedule_words(cron) == words


@pytest.mark.parametrize("crons, expected", [
    (["30 0 * * *"], datetime(2026, 10, 21, 0, 30, tzinfo=timezone.utc)),
    (["50 */3 * * *"], datetime(2026, 10, 20, 15, 50, tzinfo=timezone.utc)),
    (["0 1 * * 0"], datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)),
    (["0 1 * * 0", "50 */3 * * *"], datetime(2026, 10, 20, 15, 50, tzinfo=timezone.utc)),
    (["0 0 31 2 *"], None)])
def test_the_next_run_is_the_first_minute_a_schedule_matches(crons, expected):
    assert jobs.next_run(crons, NOW) == expected


LOG = """job,started,ended,result,changed
archive news,2026-10-20T05:22:24Z,2026-10-20T05:24:06Z,failed: 6 of 44 sources,https://a https://b
archive orbital,2026-10-20T06:00:22Z,2026-10-20T06:00:37Z,ok,https://celestrak.org
archive news,2026-10-20T12:15:54Z,2026-10-20T12:17:35Z,failed: 6 of 44 sources,https://c
"""
WORKFLOWS = [{"path": ".github/workflows/archive.yml", "state": "active"},
             {"path": ".github/workflows/update-tle-data.yml", "state": "disabled_manually"},
             {"path": ".github/workflows/tests.yml", "state": "active"}]


def run(workflow, created, conclusion="success", event="schedule", status="completed", branch="main"):
    return {"path": f".github/workflows/{workflow}", "created_at": created, "run_started_at": created, "event": event,
            "status": status, "conclusion": conclusion, "head_branch": branch, "html_url": "https://github.com/x"}


RUNS = [run("tests.yml", "2026-10-20T14:35:09Z", event="push"),
        run("tests.yml", "2026-10-20T12:48:01Z", conclusion="failure", event="pull_request", branch="some-branch"),
        run("archive.yml", "2026-10-20T12:15:00Z", conclusion="failure"),
        run("archive.yml", "2026-10-19T06:00:00Z"), run("archive.yml", "2026-10-19T12:00:00Z", conclusion="failure")]


def rows():
    texts = {"archive.yml": (WORKFLOWS_DIR / "archive.yml").read_text(), "registry-update.yml": "",
             "orbit-ages.yml": (WORKFLOWS_DIR / "orbit-ages.yml").read_text(),
             "update-tle-data.yml": (WORKFLOWS_DIR / "update-tle-data.yml").read_text(), "tests.yml": ""}
    return {r["name"]: r for r in jobs.job_rows(WORKFLOWS, RUNS, jobs.run_log(LOG), texts, NOW)}


def test_a_group_takes_its_last_run_from_the_run_log():
    news = rows()["Archive: news"]

    assert news["result"] == ("bad", "failed: 6 of 44 sources") and news["last"] == datetime(2026, 10, 20, 12, 15, 54, tzinfo=timezone.utc)
    assert news["state"] == "Ready" and news["next"] == datetime(2026, 10, 20, 15, 50, tzinfo=timezone.utc)
    assert rows()["Archive: orbit records"]["result"] == ("ok", "Succeeded")


def test_a_job_with_no_run_log_line_says_so():
    assert rows()["Archive: social"]["result"] == ("idle", "No run recorded yet") and rows()["Archive: social"]["last"] is None


def test_a_workflow_turned_off_on_github_says_so_and_has_no_next_run():
    tle = rows()["Update orbit data"]

    assert tle["state"] == "Turned off" and tle["next"] is None


def test_the_tests_job_reports_its_last_run_on_main_only():
    tests = rows()["Tests"]

    assert tests["result"] == ("ok", "Passed") and tests["schedule"] == "on every change"


def test_a_workflow_with_a_run_in_progress_is_running():
    running = jobs.job_rows(WORKFLOWS, [run("archive.yml", "2026-10-20T14:30:00Z", status="in_progress")], [],
                            {"archive.yml": ARCHIVE}, NOW)

    assert {r["state"] for r in running if r["workflow"] == "archive.yml"} == {"Running"}


def test_the_reliability_grid_counts_scheduled_runs_per_day():
    grid = jobs.reliability(RUNS, NOW, days=3)

    assert grid["days"] == ["18 Oct", "19 Oct", "20 Oct"]
    assert grid["rows"]["archive.yml"] == [None, (1, 1), (0, 1)]   # (succeeded, failed); None: no run that day
    assert "tests.yml" not in grid["rows"]   # runs on changes, not on a schedule


def test_what_needs_attention_comes_worst_first():
    items = jobs.attention(list(rows().values()), not_answering={"refused (403)": 3, "timed out": 1}, waiting=0)

    assert [(tone, title) for tone, title, _, _ in items] == [
        ("bad", "Archive: news: failed: 6 of 44 sources"),
        ("warn", "Update orbit data is turned off on GitHub"),
        ("warn", "4 candidate sources do not answer"),
        ("ok", "No decisions waiting")]


def test_recent_events_mix_the_run_log_and_the_tests_on_main_newest_first():
    events = jobs.events(jobs.run_log(LOG), RUNS, limit=3)

    assert [(e["when"].strftime("%H:%M"), e["tone"], e["source"]) for e in events] == [
        ("14:35", "ok", "Tests"), ("12:15", "bad", "archive news"), ("06:00", "ok", "archive orbital")]


@pytest.mark.parametrize("conclusion, said", [("success", ("ok", "Succeeded")), ("failure", ("bad", "Failed")),
                                              ("timed_out", ("bad", "Timed out")), ("cancelled", ("idle", "Cancelled"))])
def test_each_conclusion_is_said_in_words(conclusion, said):
    assert jobs.conclusion({"conclusion": conclusion}) == said


def test_a_cancelled_run_is_neither_a_success_nor_a_failure_in_the_grid():
    grid = jobs.reliability([run("archive.yml", "2026-10-20T01:00:00Z", conclusion="cancelled")], NOW, days=1)

    assert grid["rows"]["archive.yml"] == [None]


def test_without_a_readable_run_log_a_job_shows_githubs_own_record():
    texts = {"archive.yml": (WORKFLOWS_DIR / "archive.yml").read_text()}
    news = {r["name"]: r for r in jobs.job_rows(WORKFLOWS, RUNS, [], texts, NOW)}["Archive: news"]

    assert news["result"] == ("bad", "Failed") and news["last"] == datetime(2026, 10, 20, 12, 15, tzinfo=timezone.utc)
