"""Alerts logic: Healthchecks.io status rows, green streak, and recent failed runs."""
from datetime import datetime, timezone

import requests

from evidence.alert_settings import CHECKS, HEALTHCHECKS_API
from evidence.console_settings import JOBS, TESTS_WORKFLOW
from evidence.jobs import conclusion, parse_time

_MIN_TIME = datetime.min.replace(tzinfo=timezone.utc)
_MAX_TIME = datetime.max.replace(tzinfo=timezone.utc)

def read_checks(key):
    """Reads every check in the Healthchecks.io project for this key."""
    answer = requests.get(f"{HEALTHCHECKS_API}/checks/", headers={"X-Api-Key": key}, timeout=20)
    answer.raise_for_status()
    return answer.json()["checks"]


def read_flips(key, unique_key, seconds):
    """Reads up/down flips for one check over `seconds`."""
    answer = requests.get(
        f"{HEALTHCHECKS_API}/checks/{unique_key}/flips/",
        headers={"X-Api-Key": key},
        params={"seconds": seconds},
        timeout=20,
    )
    answer.raise_for_status()
    return answer.json()["flips"]


def _status_words(status):
    words = {
        "up": ("ok", "Up"),
        "grace": ("warn", "Late, within grace time"),
        "down": ("bad", "Down: failed or did not report"),
        "new": ("idle", "No report yet"),
        "paused": ("idle", "Paused"),
    }
    return words.get((status or "").lower(), ("idle", "Unknown"))


def _when(text):
    return parse_time(text) if text else None


def missing_slugs(checks):
    """The CHECKS slugs that do not exist in Healthchecks.io."""
    present = {check.get("slug") for check in checks}
    return [slug for slug, _ in CHECKS if slug not in present]


def _row(slug, job, check, flips):
    if check is None:
        return {"slug": slug, "job": job, "tone": "bad", "words": "No check: its reports are lost", "last_report": None,
                "next_expected": None, "down_times": 0}
    tone, words = _status_words(check.get("status"))
    down_times = 0
    for flip in flips:
        if not isinstance(flip, dict):
            raise TypeError("Healthchecks flip is not an object")
        down_times += flip.get("up") == 0
    return {"slug": slug, "job": job, "tone": tone, "words": words, "last_report": _when(check.get("last_ping")),
            "next_expected": _when(check.get("next_ping")), "down_times": down_times}


def _check_name(check):
    return check.get("slug") or check.get("name") or "unnamed"


def check_rows(checks, flips_by_slug):
    """Rows for the Alerts page: CHECKS in order, then any other check on Healthchecks.io."""
    by_slug = {check.get("slug"): check for check in checks}
    ours = dict(CHECKS)
    return ([_row(slug, job, by_slug.get(slug), flips_by_slug.get(slug, [])) for slug, job in CHECKS]
            + [_row(_check_name(check), "not one of our jobs", check, flips_by_slug.get(_check_name(check), []))
               for check in checks if check.get("slug") not in ours])


# The scheduled workflows by name; a run of archive.yml is one group, which GitHub does not name, so it reads "Archive".
JOB_NAMES = {"archive.yml": "Archive",
             **{w: name for w, _, name, *_ in JOBS if w not in (TESTS_WORKFLOW, "archive.yml")}}


def job_name(run):
    return JOB_NAMES.get(_workflow_file(run), _workflow_file(run))


def _workflow_file(run):
    return run["path"].rsplit("/", 1)[-1]


def _scheduled_workflows():
    return {workflow for workflow, *_ in JOBS if workflow != TESTS_WORKFLOW}


def _run_time(run, field):
    text = run.get(field) or run.get("created_at")
    return parse_time(text) if text else None


def green_streak(runs, now):
    """How long scheduled workflows have stayed green.

    Only runs started by schedule count. Runs started by hand (for example failure drills) do not break the streak.
    """
    scheduled_workflows = _scheduled_workflows()
    scheduled = []
    for run in runs:
        if run.get("event") != "schedule" or _workflow_file(run) not in scheduled_workflows or run.get("status") != "completed":
            continue
        tone = conclusion(run)[0]
        if tone in ("ok", "bad"):
            scheduled.append(run)
    if not scheduled:
        return {"since": None, "hours": 0.0, "at_least": False, "broke_on": None}
    failed = [run for run in scheduled if conclusion(run)[0] == "bad"]
    if failed:
        newest = max(failed, key=lambda run: _run_time(run, "updated_at") or _MIN_TIME)
        since = _run_time(newest, "updated_at")
        at_least = False
        broke_on = newest
    else:
        oldest = min(scheduled, key=lambda run: _run_time(run, "created_at") or _MAX_TIME)
        since = _run_time(oldest, "created_at")
        at_least = True
        broke_on = None
    hours = max(0.0, (now - since).total_seconds() / 3600) if since else 0.0
    return {"since": since, "hours": hours, "at_least": at_least, "broke_on": broke_on}


def failed_runs(runs):
    """Every failed completed run for scheduled workflows, newest first."""
    scheduled_workflows = _scheduled_workflows()
    rows = []
    for run in runs:
        workflow = _workflow_file(run)
        tone, words = conclusion(run)
        if (
            workflow not in scheduled_workflows
            or run.get("status") != "completed"
            or tone != "bad"
        ):
            continue
        event = run.get("event") or "unknown"
        rows.append(
            {
                "job": job_name(run),
                "when": parse_time(run["created_at"]),
                "words": words,
                "started": "on schedule" if event == "schedule" else "started by hand" if event == "workflow_dispatch" else event,
                "html_url": run.get("html_url"),
            }
        )
    return sorted(rows, key=lambda row: row["when"], reverse=True)


def trouble(error):
    """Healthchecks.io errors in plain words, never the key."""
    code = getattr(getattr(error, "response", None), "status_code", None)
    if code in (401, 403):
        return "Healthchecks.io refused the key: it may be wrong, deleted, or not a read-only key of this project."
    return "Healthchecks.io did not answer, so the checks cannot be shown now. Try again in a few minutes."
