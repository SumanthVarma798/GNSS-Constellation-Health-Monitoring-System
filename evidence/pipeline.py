"""The live pipeline for the admin console: stage states, upcoming runs, and proof events."""
from datetime import timedelta
import re

from evidence import decisions, jobs
from evidence.console_settings import JOBS, TESTS_WORKFLOW

_OK_RESULTS = {"ok", "success"}
_COMMIT_URL = re.compile(r"(https://github\.com/[^/\s]+/[^/\s]+/(?:commit|tree|blob)/([0-9a-fA-F]{7,40}))")
_SHA = re.compile(r"\b([0-9a-fA-F]{7,40})\b")
_ARCHIVE_RUN = re.compile(r"^Archive run (\d+),")
_RUN_NUMBER = re.compile(r"/actions/runs/(\d+)")
_LABEL_WAITING = "decision: "
_LOG_TO_WORKFLOW = {log_name: workflow for workflow, _, _, _, log_name in JOBS if log_name}
_LOG_TO_WORKFLOW["archive all"] = "archive.yml"
_STAGE_KEYS = {
    "Archive: documents": "archive_documents",
    "Archive: catalogues": "archive_catalogues",
    "Archive: orbit records": "archive_orbital",
    "Archive: news": "archive_news",
    "Archive: social": "archive_social",
    "Registry update": "registry_update",
    "Orbit ages": "orbit_ages",
    "Pull request waiting for a decision": "decision_waiting",
    "Decided on the Approvals page": "decision_made",
    "Merged to main": "merged_main",
    "Dashboard": "dashboard",
}


def _file(path):
    return path.rsplit("/", 1)[-1]


def _run_time(run, name):
    if run is None:
        return None
    text = run.get(name) or run.get("created_at")
    return jobs.parse_time(text) if text else None


def _workflow_rows(runs):
    rows = {}
    for run in runs:
        rows.setdefault(_file(run["path"]), []).append(run)
    for workflow in rows:
        rows[workflow].sort(key=lambda row: row.get("created_at") or "")
    return rows


def _workflow_states(workflows):
    return {_file(workflow["path"]): workflow.get("state", "active") for workflow in workflows}


def _line_for(log, job_name):
    lines = sorted((line for line in log if line["job"] == job_name), key=lambda line: line["started"])
    return lines[-1] if lines else None


def _run_for(workflow_runs, when):
    completed = [run for run in workflow_runs if run.get("status") == "completed"]
    if not completed:
        return None
    if when is None:
        return completed[-1]
    before = [run for run in completed if _run_time(run, "created_at") <= when]
    return before[-1] if before else None


def _commit_from_changed(changed):
    if not changed:
        return None, None
    if found := _COMMIT_URL.search(changed):
        return found.group(2), found.group(1)
    if found := _SHA.search(changed):
        return found.group(1), None
    return None, None


def _run_words(run):
    url = (run or {}).get("html_url")
    if not url:
        return "GitHub run"
    if found := _RUN_NUMBER.search(url):
        return f"run {found.group(1)}"
    return "GitHub run"


def archive_commits(commits):
    """Archive commit proof keyed by run id from messages like 'Archive run 123,'. GitHub lists commits newest first,
    and a re-run keeps its run id, so the newest commit of a run wins."""
    rows = {}
    for commit in commits:
        message = ((commit.get("commit") or {}).get("message") or "")
        if not (found := _ARCHIVE_RUN.match(message)):
            continue
        rows.setdefault(int(found.group(1)), {"sha": commit.get("sha"), "url": commit.get("html_url")})
    return rows


def _proof(run, changed, archive_commits_by_run=None):
    found = (archive_commits_by_run or {}).get((run or {}).get("id"))
    commit, commit_url = (found["sha"], found["url"]) if found else _commit_from_changed(changed)
    return {"run_url": (run or {}).get("html_url"), "run_words": _run_words(run), "archive_commit": commit,
            "archive_commit_url": commit_url}


def _last_from_line(line):
    if line is None:
        return None
    ended = jobs.parse_time(line["ended"])
    return {"start": line["started"], "end": ended, "duration": ended - line["started"], "result": line["result"],
            "changed": line["changed"]}


def _last_from_run(run):
    if run is None:
        return None
    started, ended = _run_time(run, "run_started_at"), _run_time(run, "updated_at")
    ended = ended or started
    tone, words = jobs.conclusion(run)
    return {"start": started, "end": ended, "duration": (ended - started) if started and ended else None, "result": words,
            "changed": "", "tone": tone}


def _state_from_last(last, running, turned_off):
    if turned_off:
        return "off"
    if running:
        return "running now"
    if last is None:
        return "waiting"
    tone = last.get("tone")
    if tone:
        return "done" if tone == "ok" else "failed" if tone == "bad" else "waiting"
    return "done" if last["result"] in _OK_RESULTS else "failed"


def _running_run(workflow_runs):
    running = [run for run in workflow_runs if run.get("status") != "completed"]
    if not running:
        return None
    return max(running, key=lambda run: _run_time(run, "run_started_at") or _run_time(run, "created_at")
               or jobs.parse_time("1970-01-01T00:00:00Z"))


def _next_for(workflow, group, workflow_texts, now):
    crons = jobs.schedules(workflow_texts.get(workflow, "")).get(group, [])
    return jobs.next_run(crons, now) if crons else None


def _job_stage(stage_key, name, what, workflow, group, log_name, runs_by_workflow, workflow_states, workflow_texts, log, now,
               archive_commits_by_run, allow_running=True):
    workflow_runs = runs_by_workflow.get(workflow, [])
    turned_off = workflow_states.get(workflow, "active").startswith("disabled")
    running_run = _running_run(workflow_runs) if allow_running else None
    running = running_run is not None
    line = _line_for(log, log_name) if log_name else None
    archive_group_without_log = workflow == "archive.yml" and bool(group) and line is None
    run = None if archive_group_without_log else _run_for(workflow_runs, line["started"] if line else None)
    last = _last_from_line(line) if line else (None if archive_group_without_log else _last_from_run(run))
    commit_rows = archive_commits_by_run if workflow == "archive.yml" else None
    return {"key": stage_key, "name": name, "what": what, "state": _state_from_last(last, running, turned_off), "last": last,
            "next": None if turned_off else _next_for(workflow, group, workflow_texts, now),
            "proof": _proof(run, (last or {}).get("changed", ""), commit_rows),
            "running_start": _run_time(running_run, "run_started_at") or _run_time(running_run, "created_at"),
            "workflow": workflow, "group": group, "log_job": log_name, "log_line": line}


def _decision_prs(prs):
    rows = [pr for pr in prs if any(label.get("name", "").startswith(_LABEL_WAITING) for label in pr.get("labels", []))]
    rows.sort(key=lambda pr: pr.get("created_at", ""))
    return rows


def _decision_time(pr):
    for field in ("merged_at", "closed_at", "updated_at", "created_at"):
        if pr.get(field):
            return jobs.parse_time(pr[field])
    return jobs.parse_time("1970-01-01T00:00:00Z")


def _pr_stage(stage_key, name, what, pr, state):
    if pr is None:
        return {"key": stage_key, "name": name, "what": what, "state": "waiting", "last": None, "next": None,
                "proof": {"pr_number": None, "pr_url": None, "pr_state": None}, "running_start": None, "workflow": "",
                "group": "", "log_job": "", "log_line": None}
    opened = jobs.parse_time(pr["created_at"])
    merged_at = jobs.parse_time(pr["merged_at"]) if pr.get("merged_at") else None
    closed_at = jobs.parse_time(pr["closed_at"]) if pr.get("closed_at") else None
    end = merged_at or closed_at or opened
    words = "merged" if merged_at else (pr.get("state") or "open")
    return {"key": stage_key, "name": name, "what": what, "state": state,
            "last": {"start": opened, "end": end, "duration": end - opened if end and opened else None, "result": words, "changed": ""},
            "next": None, "running_start": None, "workflow": "", "group": "", "log_job": "", "log_line": None,
            "proof": {"pr_number": pr["number"], "pr_url": pr["html_url"], "pr_state": pr.get("state", "open")}}


def stages(workflows, runs, log, prs, workflow_texts, now, archive_commits=None):
    """The pipeline's stages, in order, each with state, last run details, next run, and proof links."""
    archive_commits_by_run = archive_commits or {}
    runs_by_workflow = _workflow_rows(runs)
    workflow_states = _workflow_states(workflows)
    items = []
    for workflow, group, name, what, log_name in JOBS:
        if workflow == TESTS_WORKFLOW or workflow == "update-tle-data.yml":
            continue
        items.append(_job_stage(_STAGE_KEYS.get(name, ""), name, what, workflow, group, log_name, runs_by_workflow, workflow_states,
                                workflow_texts, log, now, archive_commits_by_run, allow_running=(workflow != "archive.yml")))

    archive_stages = [stage for stage in items if stage["name"].startswith("Archive: ")]
    archive_runs = runs_by_workflow.get("archive.yml", [])
    archive_running_row = _running_run(archive_runs)
    archive_running = archive_running_row is not None
    archive_off = all(stage["state"] == "off" for stage in archive_stages)
    archive_failed = any(stage["state"] == "failed" for stage in archive_stages)
    archive_waiting = all(stage["state"] == "waiting" for stage in archive_stages)
    archive_last = max((stage["last"] for stage in archive_stages if stage["last"]), key=lambda last: last["start"], default=None)
    archive_proof = next((stage["proof"] for stage in sorted(archive_stages, key=lambda row: (row["last"] or {}).get("start")
                          or jobs.parse_time("1970-01-01T00:00:00Z"), reverse=True) if stage["proof"].get("run_url")),
                         _proof(archive_running_row, ""))
    archive_with_log = max((stage for stage in archive_stages if stage["last"]),
                           key=lambda stage: stage["last"]["start"], default=None)
    items.insert(5, {"key": "archive", "name": "Archive",
                     "what": "The private archive repository that keeps each changed copy by fingerprint",
                     "state": ("off" if archive_off else "running now" if archive_running else "failed" if archive_failed else
                               "waiting" if archive_waiting else "done"),
                     "last": archive_last, "next": None, "proof": archive_proof, "workflow": "archive.yml", "group": "",
                     "log_job": "archive all", "log_line": archive_with_log["log_line"] if archive_with_log else None,
                     "running_start": _run_time(archive_running_row, "run_started_at")
                     or _run_time(archive_running_row, "created_at")})

    waiting = _decision_prs(prs)
    waiting_open = [pr for pr in waiting if pr.get("state", "open") == "open"]
    decided = [pr for pr in waiting if pr.get("state", "open") != "open" or pr.get("merged_at")]
    merged = [pr for pr in waiting if pr.get("merged_at")]
    decided.sort(key=_decision_time)
    merged.sort(key=lambda pr: jobs.parse_time(pr["merged_at"]) if pr.get("merged_at")
                else jobs.parse_time("1970-01-01T00:00:00Z"))
    latest_waiting = waiting_open[-1] if waiting_open else None
    latest_decided = decided[-1] if decided else None
    latest_merged = merged[-1] if merged else None

    items.append(_pr_stage("decision_waiting", "Pull request waiting for a decision",
                           "A person reviews pull requests labelled for a decision", latest_waiting or latest_decided,
                           "waiting" if latest_waiting else "done" if latest_decided else "waiting"))
    items.append(_pr_stage("decision_made", "Decided on the Approvals page",
                           "A person records the decision and reason on the pull request", latest_decided or latest_waiting,
                           "done" if latest_decided else "waiting"))
    merged_state = "done" if latest_merged else "waiting"
    items.append(_pr_stage("merged_main", "Merged to main", "An approved pull request is merged, then tests run on main",
                           latest_merged or latest_decided or latest_waiting, merged_state))

    tests_runs = [run for run in runs_by_workflow.get(TESTS_WORKFLOW, [])
                  if run.get("head_branch") == "main" and run.get("event") == "push"]
    tests_running_row = _running_run(tests_runs)
    tests_running = any(run.get("status") != "completed" for run in tests_runs)
    tests_last = _run_for(tests_runs, None)
    tests_state = workflow_states.get(TESTS_WORKFLOW, "active")
    tests_off = tests_state.startswith("disabled")
    tests_last_row = _last_from_run(tests_last)
    dashboard_state = _state_from_last(tests_last_row, tests_running, tests_off)
    items.append({"key": "dashboard", "name": "Dashboard",
                  "what": "The merged result is visible on the dashboard after tests on main",
                  "state": dashboard_state, "last": tests_last_row, "next": None, "proof": _proof(tests_last, ""),
                  "workflow": TESTS_WORKFLOW, "group": "", "log_job": "", "log_line": None,
                  "running_start": _run_time(tests_running_row, "run_started_at")
                  or _run_time(tests_running_row, "created_at")})

    registry = next((stage for stage in items if stage["name"] == "Registry update"), None)
    registry_pr = next((pr for pr in reversed(waiting) if decisions.kind_of(pr) == "registry update"), None)
    if registry and registry_pr:
        registry["proof"] |= {"pr_number": registry_pr["number"], "pr_url": registry_pr["html_url"],
                              "pr_state": registry_pr.get("state", "open")}
    return items


def what_next(stages_rows, now, hours=24):
    """Upcoming stage runs within `hours`, soonest first."""
    until = now + timedelta(hours=hours)
    upcoming = [{"name": stage["name"], "key": stage.get("key"), "at": stage["next"], "state": stage["state"]}
                for stage in stages_rows if stage.get("next") and now < stage["next"] <= until]
    return sorted(upcoming, key=lambda row: row["at"])


def proof_feed(runs, log, prs, limit=20):
    """Run, pull-request and merge events, newest first."""
    runs_by_workflow = _workflow_rows(runs)
    events = []
    for line in log:
        workflow = _LOG_TO_WORKFLOW.get(line["job"])
        if workflow is None and line["job"].startswith("archive "):
            workflow = "archive.yml"
        run = _run_for(runs_by_workflow.get(workflow, []), line["started"]) if workflow else None
        finished = jobs.parse_time(line["ended"])
        events.append({"time": finished, "words": f"{line['job']} finished: {line['result']}", "link": (run or {}).get("html_url"),
                       "link_words": _run_words(run)})
    for run in runs_by_workflow.get(TESTS_WORKFLOW, []):
        if run.get("status") != "completed" or run.get("head_branch") != "main" or run.get("event") != "push":
            continue
        when = _run_time(run, "updated_at") or _run_time(run, "created_at")
        events.append({"time": when, "words": f"Tests on main {jobs.conclusion(run)[1].lower()}", "link": run.get("html_url"),
                       "link_words": _run_words(run)})
    for pr in _decision_prs(prs):
        opened = jobs.parse_time(pr["created_at"])
        number = pr["number"]
        link = pr["html_url"]
        words = f"pull request {number}"
        events.append({"time": opened, "words": f"Pull request #{number} opened", "link": link, "link_words": words})
        if merged_at := pr.get("merged_at"):
            events.append({"time": jobs.parse_time(merged_at), "words": f"Pull request #{number} merged", "link": link,
                           "link_words": words})
        elif pr.get("state") == "closed" and pr.get("closed_at"):
            events.append({"time": jobs.parse_time(pr["closed_at"]), "words": f"Pull request #{number} decided (closed)",
                           "link": link, "link_words": words})
    return sorted(events, key=lambda event: event["time"], reverse=True)[:limit]
