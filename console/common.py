"""What every console page shares: settings, cached GitHub readers, plain error words, and the shared page layout."""
import csv
import io
from datetime import datetime, timedelta, timezone
from html import escape

import requests
import streamlit as st

from console import pages
from evidence import decisions, github_api, jobs, pipeline, work
from evidence.console_settings import (ARCHIVE_REPOSITORY, JOBS, RELIABILITY_DAYS, RUN_LOGS, RUNS_READ, TESTS_WORKFLOW,
                                       WORKFLOWS_DIR)
from evidence.decision_settings import READ_EVERY_SECONDS, SECRETS_SECTION
from evidence.settings import ARCHIVE_VERSIONS_FILE
from ui import console

# What Google sign-in (st.login) needs in [auth]; one left empty means it is not set up.
SIGN_IN_FIELDS = ("redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url")
NOT_SET_UP = ("This copy of the console is not set up. It needs Google sign-in, the list of people who may sign in, and "
              "a GitHub token, in its secrets: .streamlit/secrets.toml on a computer, or the secret file secrets.toml in "
              "Render (see .streamlit/secrets.example.toml).")
NEEDED_ADMIN = ("allowed", "github_token")
REFRESH_PENDING = "console_refresh_pending"   # set when Refresh is pressed; cleared after the toast for the new reading
CONSOLE_SCHEME_KEY = "console_scheme"
CONSOLE_SCHEME_DEFAULT = "auto"
CONSOLE_SCHEME_PICK_KEY = "console_scheme_pick"


def secret_section(name):
    """One secrets section as a dict; empty when secrets are absent on this copy."""
    try:
        return dict(st.secrets.get(name, {}))
    except FileNotFoundError:
        return {}


def settings():
    """The [admin] settings; empty without a secrets file."""
    return secret_section(SECRETS_SECTION)


def missing():
    """The secrets the console needs that are absent or empty, by name only, never their values."""
    try:
        auth, admin = st.secrets.get("auth", {}), st.secrets.get(SECRETS_SECTION, {})
    except FileNotFoundError as error:   # Streamlit raises it too for a file it cannot read, with the reason as its cause
        if error.__cause__:   # the reader's message gives the line and position, never a value
            return [f"a readable secrets file ({error.__cause__}): a key set twice, or a line that is not key = value"]
        return ["the secrets themselves"]
    return ([f"[auth] {field}" for field in SIGN_IN_FIELDS if not auth.get(field)]
            + [f"[{SECRETS_SECTION}] {field}" for field in NEEDED_ADMIN if not admin.get(field)])


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading GitHub…")
def _run_log_reading(token):
    problems, log = [], []
    for path in RUN_LOGS:
        try:
            log += jobs.run_log(github_api.file_text(token, ARCHIVE_REPOSITORY, path))
        except requests.RequestException:
            problems.append(f"The run log {path} could not be read from the archive repository: the token may not "
                            "have access to it. Jobs show GitHub's own record instead.")
    return {"log": log, "problems": problems, "read_at": now()}


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading GitHub…")
def _runs_reading(token):
    problems, runs = [], []
    for workflow in dict.fromkeys(job.workflow for job in JOBS):
        try:
            runs += _runs(token, workflow)
        except requests.HTTPError as error:
            if getattr(error.response, "status_code", None) != 404:
                raise
            problems.append(f"GitHub has no workflow {workflow}: it may have been renamed or removed.")
    return {"runs": runs, "problems": problems, "read_at": now()}


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading GitHub…")
def _workflows_reading(token):
    return {"workflows": github_api.ask("GET", "/actions/workflows", token)["workflows"], "problems": [], "read_at": now()}


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading GitHub…")
def _archive_commits_reading(token):
    try:
        return {"archive_commits": _archive_commits(token), "problems": [], "read_at": now()}
    except requests.RequestException:
        return {"archive_commits": {},
                "problems": ["The archive's commits could not be read, so the Live pipeline cannot link each run's commit."]}


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading GitHub…")
def _archive_versions_reading(token):
    try:
        versions = list(csv.DictReader(io.StringIO(github_api.file_text(token, ARCHIVE_REPOSITORY, ARCHIVE_VERSIONS_FILE))))
        return {"archive_versions": versions, "problems": [], "read_at": now()}
    except requests.RequestException:
        return {"archive_versions": None,
                "problems": ["The archive's versions.csv could not be read from the archive repository: the token may not "
                             "have access to it. Last read times on Sources cannot be shown."]}


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading GitHub…")
def _open_prs_reading(token):
    return {"prs": decisions.fetch_open(token), "problems": [], "read_at": now()}


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading GitHub…")
def _decision_prs_reading(token):
    prs = _open_prs_reading(token)["prs"]
    return {"prs": prs, "decision_prs": prs + decisions.fetch_recent_closed(token), "problems": [], "read_at": now()}


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading GitHub…")
def _approvals_reading(token):
    prs = _open_prs_reading(token)["prs"]
    problems, comments, reviews = [], {}, {}
    for pr in prs:
        if decisions.kind_of(pr) is None:
            continue
        try:
            reviews[pr["number"]] = decisions.review_reading(token, pr)
        except requests.RequestException:
            problems.append(f"GitHub did not give the changes or checks of pull request {pr['number']}, so Approvals "
                            "shows its description only.")
        if decisions.has_findings_block(pr.get("body") or ""):
            comments[pr["number"]] = decisions.fetch_comments(token, pr["number"])
    return {"prs": prs, "comments": comments, "reviews": reviews, "problems": problems, "read_at": now()}


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading GitHub…")
def _issues_reading(token):
    return {"issues": work.fetch_open_issues(token), "problems": [], "read_at": now()}


def _merge(*readings):
    """One page's reading from several cached ones; it was read when the oldest of them was."""
    merged = {"problems": []}
    for reading in readings:
        merged["problems"] += reading.get("problems", [])
        merged.update((key, value) for key, value in reading.items() if key not in ("problems", "read_at"))
    merged["read_at"] = min((reading["read_at"] for reading in readings if "read_at" in reading), default=now())
    return merged


def _jobs_snapshot(token):
    return _merge(_run_log_reading(token), _runs_reading(token), _workflows_reading(token))


def _summary_snapshot(token):
    status = _status_snapshot(token)
    status.pop("status", None)
    return status


def _status_snapshot(token):
    seen = _merge(_run_log_reading(token), _runs_reading(token), _workflows_reading(token), _open_prs_reading(token))
    rows = jobs.job_rows(seen["workflows"], seen["runs"], seen["log"], workflow_texts(), now())
    waiting = decisions.pending(seen["prs"], now())
    seen["status"] = {
        "failing": sum(r["result"][0] == "bad" for r in rows),
        "off": sum(r["state"] == "Turned off" for r in rows),
        "waiting": len(waiting),
    }
    return seen


def _sources_snapshot(token):
    return _merge(_run_log_reading(token), _archive_versions_reading(token), _open_prs_reading(token))


def _pipeline_snapshot(token):
    return _merge(_run_log_reading(token), _runs_reading(token), _workflows_reading(token), _decision_prs_reading(token),
                  _archive_commits_reading(token))


def _ask_snapshot(token):
    return _merge(_decision_prs_reading(token), _issues_reading(token))


def _design_snapshot(token):
    return _merge(_open_prs_reading(token), _issues_reading(token))


def _work_snapshot(token):
    return _merge(_open_prs_reading(token), _issues_reading(token))


def _approvals_snapshot(token):
    return _merge(_approvals_reading(token))


def _alerts_snapshot(token):
    return _merge(_runs_reading(token))


PAGE_READERS = {
    pages.SUMMARY.path: _summary_snapshot,
    pages.DESIGN.path: _design_snapshot,
    pages.ASK.path: _ask_snapshot,
    pages.SOURCES.path: _sources_snapshot,
    pages.JOBS.path: _jobs_snapshot,
    pages.PIPELINE.path: _pipeline_snapshot,
    pages.ALERTS.path: _alerts_snapshot,
    pages.WORK.path: _work_snapshot,
    pages.APPROVALS.path: _approvals_snapshot,
}

_CACHED_READERS = (_run_log_reading, _runs_reading, _workflows_reading, _archive_commits_reading,
                   _archive_versions_reading, _open_prs_reading, _decision_prs_reading, _approvals_reading,
                   _issues_reading)


def _read(reader):
    """A reader's snapshot, or a plain notice and stop when GitHub cannot be read."""
    try:
        return reader(settings()["github_token"])
    except requests.RequestException as error:
        st.html(console.notice(github_trouble(error, reading=True), "bad"))
    except (KeyError, TypeError, ValueError):   # GitHub answered, but not in the shape the console reads
        st.html(console.notice("GitHub's answer was not in the shape the console expects, so it cannot be shown now. "
                               "Try Refresh; if it stays, the console needs updating.", "bad"))
    st.stop()


def read_page(path):
    """The reading for one console page path from console/pages.py."""
    return _read(PAGE_READERS[path])


def read_status():
    """The status bar's reading: jobs and decision waiting counts."""
    return _read(_status_snapshot)


def read():
    """Backward-compatible alias: the Summary page's reading."""
    return read_page(pages.SUMMARY.path)


def clear_reading():
    """Clears every cached GitHub reader used by the console pages."""
    for reader in _CACHED_READERS:
        reader.clear()


def request_refresh():
    clear_reading()
    st.session_state[REFRESH_PENDING] = True


def _runs(token, workflow):
    """A workflow's runs: the tests' runs on main, every other workflow page-by-page since the reliability window."""
    if workflow == TESTS_WORKFLOW:
        return github_api.ask("GET", f"/actions/workflows/{workflow}/runs", token,
                              params={"branch": "main", "event": "push", "per_page": 10})["workflow_runs"]
    since = _since()
    return github_api.paged(
        lambda page: github_api.ask("GET", f"/actions/workflows/{workflow}/runs", token,
                                    params={"per_page": RUNS_READ, "page": page, "created": f">={since}"})["workflow_runs"],
        page_size=RUNS_READ,
    )


def _since():
    return (datetime.now(timezone.utc) - timedelta(days=RELIABILITY_DAYS)).date().isoformat()


def _archive_commits(token):
    since = _since()
    commits = github_api.paged(
        lambda page: github_api.ask("GET", "/commits", token, ARCHIVE_REPOSITORY,
                                    params={"path": "runs/archive.csv", "since": since, "per_page": RUNS_READ, "page": page}),
        page_size=RUNS_READ,
    )
    return pipeline.archive_commits(commits)


def workflow_texts():
    return {workflow: (WORKFLOWS_DIR / workflow).read_text(encoding="utf-8")
            for workflow in dict.fromkeys(job.workflow for job in JOBS)}


def github_trouble(error, reading=False):
    """What went wrong with GitHub, in plain words. Never the token."""
    code = getattr(getattr(error, "response", None), "status_code", None)
    if code in (401, 403):
        return "GitHub refused the console's token: it may have expired or lost its access."
    if reading and code == 404:   # how GitHub answers a token that cannot see a private repository
        return ("GitHub cannot find the private mirror with the console's token: it may not have access to that "
                "repository. Give it access under Repository access in the token's settings.")
    if code in (404, 405, 409, 422):
        return "GitHub would not do that. Nothing more was written; look at the pull request on GitHub."
    return "GitHub did not answer, so it cannot be shown or changed now. Try again in a few minutes."


def layout(page_path, line):
    """Draws one page's header band from the central pages list; returns (body, actions) containers."""
    page = pages.page(page_path)
    st.html(console.view_head(page.icon_key, page.title, line))
    with st.container(key="console_page"):
        body, side = st.columns([4.2, 1])
    with side:
        actions = st.container(key="console_actions")
    with actions:
        st.html('<p class="c-actions-head">Actions</p>')
    return body, actions


def link(url, words):
    """A safe external link, or a muted 'none' when no URL is present."""
    if not url:
        return '<span class="muted">none</span>'
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(words)}</a>'


def refresh_action():
    """The Actions pane's Refresh: read GitHub again now."""
    if st.button("Refresh", key="console_refresh_action", icon=":material/refresh:", help="Read everything again from GitHub"):
        request_refresh()
        st.rerun()


def follow(trail, path):
    """Moves the console's Back and Forward history to the page at `path`. The page just behind or just ahead is a step
    back or forward (the toolbar's buttons and the browser's own both arrive here); any other page is a new step, which
    clears Forward. `trail` is {"back": [paths], "forward": [paths], "at": path or None}; it is changed and returned."""
    back, forward, at = trail["back"], trail["forward"], trail["at"]
    if at is not None and path != at:
        if back and back[-1] == path:
            back.pop()
            forward.append(at)
        elif forward and forward[-1] == path:
            forward.pop()
            back.append(at)
        else:
            back.append(at)
            forward.clear()
    trail["at"] = path
    return trail


def now():
    return datetime.now(timezone.utc)
