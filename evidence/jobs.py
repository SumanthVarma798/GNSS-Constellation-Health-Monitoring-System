"""The scheduled jobs, for the administration console: when each runs, whether it is running, how its runs ended.

Schedules are read from the workflow files; states and runs from GitHub's record of them; each job's own result from
the archive's run log, which says more than GitHub does ("6 of 44 sources failed" rather than "failure"). The jobs
and their names are in evidence/console_settings.py.
"""
import csv
import io
import re
from datetime import datetime, timedelta

from evidence.console_settings import JOBS, LOOK_AHEAD_DAYS, RELIABILITY_DAYS, RECENT_EVENTS, TESTS_WORKFLOW

_CRON = re.compile(r"cron:\s*'([^']+)'(?:\s*#\s*([a-z]+):)?")
_DAYS = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"]
_OK_RESULTS = ("ok", "success")   # the archive writes "ok"; jobs logged by scripts/log_run.py write GitHub's word
# How each of GitHub's conclusions reads; anything else ("cancelled", "skipped", ...) is neither a success nor a failure.
_CONCLUSIONS = {"success": ("ok", "Succeeded"), "failure": ("bad", "Failed"), "timed_out": ("bad", "Timed out"),
                "startup_failure": ("bad", "Failed to start")}


def schedules(workflow_text):
    """{group: [cron, ...]} from a workflow file; the group is the word before ':' in the comment after the line."""
    found = {}
    for cron, group in _CRON.findall(workflow_text):
        found.setdefault(group, []).append(cron)
    return found


def _values(field, low, high):
    """The numbers one cron field allows: '*', 'n', 'a-b', any of these '/step', and lists of them."""
    allowed = set()
    for part in field.split(","):
        span, _, step = part.partition("/")
        first, last = (low, high) if span == "*" else map(int, span.split("-")) if "-" in span else (int(span), int(span))
        if step and span != "*" and "-" not in span:
            last = high   # 'n/step': from n to the end
        allowed.update(range(first, last + 1, int(step or 1)))
    return allowed


def _parse(cron):
    minute, hour, day, month, weekday = cron.split()
    return (_values(minute, 0, 59), _values(hour, 0, 23), _values(day, 1, 31), _values(month, 1, 12),
            _values(weekday, 0, 6))


def next_run(crons, now):
    """The first minute after `now` that any of the schedules matches, within LOOK_AHEAD_DAYS; None if none does.

    ponytail: a day-of-month and a weekday both given are both required (cron itself takes either); none of our
    workflows gives both. Checks minute by minute, which is plenty for one look ahead of a week.
    """
    parsed = [_parse(cron) for cron in crons]
    at = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(LOOK_AHEAD_DAYS * 24 * 60):
        if any(at.minute in m and at.hour in h and at.day in d and at.month in mo and at.isoweekday() % 7 in w
               for m, h, d, mo, w in parsed):
            return at
        at += timedelta(minutes=1)
    return None


def schedule_words(cron):
    """'daily 00:30', 'every 3 hours from 00:50', 'Sundays 01:00'; anything else as the cron itself."""
    minute, hour, day, month, weekday = cron.split()
    if minute.isdigit() and day == month == "*":
        if hour.isdigit() and weekday == "*":
            return f"daily {int(hour):02d}:{int(minute):02d}"
        if hour.startswith("*/") and weekday == "*":
            return f"every {hour[2:]} hours from 00:{int(minute):02d}"
        if hour.isdigit() and weekday.isdigit():
            return f"{_DAYS[int(weekday) % 7]} {int(hour):02d}:{int(minute):02d}"
    return f"{cron} (cron)"


def parse_time(text):
    return datetime.fromisoformat(text)


def run_log(text):
    """The archive's run log as rows, each with its start as a time."""
    return [{**row, "started": parse_time(row["started"])} for row in csv.DictReader(io.StringIO(text))]


def _file(run):
    return run["path"].rsplit("/", 1)[-1]


def log_result(line):
    return ("ok", "Succeeded") if line["result"] in _OK_RESULTS else ("bad", line["result"].replace("failure", "failed"))


def changed_words(changed):
    """A run log line's "what changed" for the console: "3 copies" for the addresses, then any other words."""
    words = changed.split()
    addresses = [word for word in words if word.startswith("http")]
    if not addresses:
        return changed
    rest = " ".join(word for word in words if not word.startswith("http"))
    return f"{len(addresses)} {'copy' if len(addresses) == 1 else 'copies'}" + (f", {rest}" if rest else "")


def _on_main(run):
    return run["head_branch"] == "main" and run["event"] == "push"


def conclusion(run):
    """(tone, words) for a finished run, from GitHub's conclusion."""
    return _CONCLUSIONS.get(run["conclusion"], ("idle", (run["conclusion"] or "unknown").replace("_", " ").capitalize()))


def job_rows(workflows, runs, log, workflow_texts, now):
    """One row per job in JOBS: its schedule in words, state, next run, last run and result, and a link to its runs."""
    state = {_file(w): w["state"] for w in workflows}
    running = {_file(r) for r in runs if r["status"] != "completed"}
    rows = []
    for workflow, group, name, what, log_name in JOBS:
        crons = schedules(workflow_texts.get(workflow, "")).get(group, [])
        turned_off = state.get(workflow, "active").startswith("disabled")
        done = sorted((r for r in runs if _file(r) == workflow and r["status"] == "completed"
                       and (workflow != TESTS_WORKFLOW or _on_main(r))), key=lambda r: r["created_at"])
        lines = sorted((line for line in log if line["job"] == log_name), key=lambda line: line["started"]) if log_name else []
        if lines:
            last, result = lines[-1]["started"], log_result(lines[-1])
        elif log_name and log:
            last, result = None, ("idle", "No run recorded yet")
        elif done:   # no run log to read: GitHub's own record (for an archive group, the whole archive job's last run)
            last, result = parse_time(done[-1]["created_at"]), conclusion(done[-1])
            if workflow == TESTS_WORKFLOW and result[0] == "ok":
                result = ("ok", "Passed")
        else:
            last, result = None, ("idle", "No run in GitHub's recent record")
        rows.append({"name": name, "what": what, "workflow": workflow,
                     "schedule": "on every change" if workflow == TESTS_WORKFLOW else
                     ", ".join(schedule_words(c) for c in crons) or "only when started by hand",
                     "state": "Turned off" if turned_off else "Running" if workflow in running else "Ready",
                     "next": None if turned_off or not crons else next_run(crons, now),
                     "last": last, "result": result, "link": done[-1]["html_url"] if done else None})
    return rows


def reliability(runs, now, days=RELIABILITY_DAYS):
    """{'days': ['7 Oct', ...], 'rows': {workflow: [None or (succeeded, failed) per day]}} for scheduled workflows."""
    dates = [(now - timedelta(days=back)).date() for back in range(days - 1, -1, -1)]
    scheduled = list(dict.fromkeys(w for w, *_ in JOBS if w != TESTS_WORKFLOW))
    rows = {workflow: [None] * days for workflow in scheduled}
    for run in runs:
        workflow, day = _file(run), parse_time(run["created_at"]).date()
        tone = conclusion(run)[0] if run["conclusion"] else "idle"
        if workflow in rows and run["event"] in ("schedule", "workflow_dispatch") and day in dates and tone != "idle":
            i = dates.index(day)   # a cancelled or skipped run counts as neither
            ok, failed = rows[workflow][i] or (0, 0)
            rows[workflow][i] = (ok + (tone == "ok"), failed + (tone == "bad"))
    return {"days": [f"{d.day} {d:%b}" for d in dates], "rows": rows}


def attention(rows, not_answering, waiting):
    """What needs a look, worst first: (tone, title, detail, page to go to)."""
    items = [("bad", f"{r['name']}: {r['result'][1]}",
              f"Last run {r['last']:%d %b %H:%M} UTC. {r['what']}." if r["last"] else r["what"], "jobs")
             for r in rows if r["result"][0] == "bad"]
    items += [("warn", f"{r['name']} is turned off on GitHub", "It will not run until it is turned on again.", "jobs")
              for r in rows if r["state"] == "Turned off"]
    if not_answering:
        count = sum(not_answering.values())
        items.append(("warn", f"{count} candidate source{'' if count == 1 else 's'} do not answer",
                      ", ".join(f"{n} {words}" for words, n in not_answering.items()) + ".", "sources"))
    items.append(("warn", f"{waiting} decision{'' if waiting == 1 else 's'} waiting", "Each is a pull request.", "approvals")
                 if waiting else ("ok", "No decisions waiting", "Nothing is labelled for a decision.", "approvals"))
    return items


def events(log, runs, limit=RECENT_EVENTS):
    """The newest happenings, newest first: every run-log line, and every run of the tests on main."""
    happened = [{"when": line["started"], "tone": log_result(line)[0], "source": line["job"],
                 "text": log_result(line)[1]} for line in log]
    happened += [{"when": parse_time(r["created_at"]), "tone": conclusion(r)[0], "source": "Tests",
                  "text": "Passed on main" if conclusion(r)[0] == "ok" else f"{conclusion(r)[1]} on main"}
                 for r in runs if _file(r) == TESTS_WORKFLOW and _on_main(r) and r["status"] == "completed"]
    return sorted(happened, key=lambda e: e["when"], reverse=True)[:limit]
