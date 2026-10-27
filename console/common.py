"""What every console page shares: its settings, one cached reading of GitHub, plain words for GitHub's errors, and
the page's layout (its header band, its body, and the Actions pane on the right)."""
import csv
import io
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

from evidence import decisions, github_api, jobs, pipeline, work
from evidence.console_settings import (ARCHIVE_REPOSITORY, JOBS, RELIABILITY_DAYS, RUN_LOGS, RUNS_READ, TESTS_WORKFLOW,
                                       WORKFLOWS_DIR)
from evidence.decision_settings import READ_EVERY_SECONDS, SECRETS_SECTION
from evidence.settings import ARCHIVE_VERSIONS_FILE
from ui import console

# What Google sign-in (st.login) needs in [auth]; one left empty means it is not set up.
SIGN_IN_FIELDS = ("redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url")
NOT_SET_UP = ("This copy of the console is not set up. It needs Google sign-in, the list of people who may sign in, and "
              "a GitHub token, in its secrets: .streamlit/secrets.toml on a computer, or Settings > Secrets on Streamlit "
              "Community Cloud (see .streamlit/secrets.example.toml).")
NEEDED_ADMIN = ("allowed", "github_token")
REFRESH_PENDING = "console_refresh_pending"   # set when Refresh is pressed; cleared after the toast for the new reading


def settings():
    """The [admin] settings; empty without a secrets file."""
    try:
        return dict(st.secrets.get(SECRETS_SECTION, {}))
    except FileNotFoundError:
        return {}


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
def github(token):
    """Everything the console reads from GitHub, kept for READ_EVERY_SECONDS. A run log that cannot be read is left
    out and named in 'problems'; anything else GitHub refuses is raised, since nothing can be shown without it."""
    problems, log = [], []
    for path in RUN_LOGS:
        try:
            log += jobs.run_log(github_api.file_text(token, ARCHIVE_REPOSITORY, path))
        except requests.RequestException:
            problems.append(f"The run log {path} could not be read from the archive repository: the token may not "
                            "have access to it. Jobs show GitHub's own record instead.")
    runs = []
    for workflow in dict.fromkeys(w for w, *_ in JOBS):
        try:
            runs += _runs(token, workflow)
        except requests.HTTPError as error:
            if getattr(error.response, "status_code", None) != 404:
                raise
            problems.append(f"GitHub has no workflow {workflow}: it may have been renamed or removed.")
    try:
        archive_commits = _archive_commits(token)
    except requests.RequestException:
        archive_commits = {}
        problems.append("The archive's commits could not be read, so the Live pipeline cannot link each run's commit.")
    try:
        versions = list(csv.DictReader(io.StringIO(github_api.file_text(token, ARCHIVE_REPOSITORY, ARCHIVE_VERSIONS_FILE))))
    except requests.RequestException:
        versions = None
        problems.append("The archive's versions.csv could not be read from the archive repository: the token may not "
                        "have access to it. Last read times on Sources cannot be shown.")
    open_prs = decisions.fetch_open(token)
    comments = {}
    for pr in open_prs:
        if decisions.kind_of(pr) is None or not decisions.has_findings_block(pr.get("body") or ""):
            continue
        comments[pr["number"]] = decisions.fetch_comments(token, pr["number"])
    return {"workflows": github_api.ask("GET", "/actions/workflows", token)["workflows"], "runs": runs,
            "log": log, "prs": open_prs,
            "decision_prs": open_prs + decisions.fetch_recent_closed(token),
            "comments": comments,
            "issues": work.fetch_open_issues(token), "archive_commits": archive_commits, "archive_versions": versions,
            "problems": problems, "read_at": datetime.now(timezone.utc)}


def _runs(token, workflow):
    """A workflow's runs: the tests' runs on main (pull requests' runs would push them out of a page), every other
    workflow's runs back to the start of the reliability grid, page by page."""
    if workflow == TESTS_WORKFLOW:
        return github_api.ask("GET", f"/actions/workflows/{workflow}/runs", token,
                              params={"branch": "main", "event": "push", "per_page": 10})["workflow_runs"]
    since = _since()
    runs, page = [], 1
    while True:
        got = github_api.ask("GET", f"/actions/workflows/{workflow}/runs", token,
                             params={"per_page": RUNS_READ, "page": page, "created": f">={since}"})["workflow_runs"]
        runs += got
        if len(got) < RUNS_READ:
            return runs
        page += 1


def _since():
    return (datetime.now(timezone.utc) - timedelta(days=RELIABILITY_DAYS)).date().isoformat()


def _archive_commits(token):
    since = _since()
    commits, page = [], 1
    while True:
        got = github_api.ask("GET", "/commits", token, ARCHIVE_REPOSITORY,
                             params={"path": "runs/archive.csv", "since": since, "per_page": RUNS_READ, "page": page})
        commits += got
        if len(got) < RUNS_READ:
            return pipeline.archive_commits(commits)
        page += 1


def workflow_texts():
    return {workflow: (WORKFLOWS_DIR / workflow).read_text(encoding="utf-8") for workflow in dict.fromkeys(w for w, *_ in JOBS)}


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


def read():
    """The cached reading, or a plain notice and a stop when GitHub cannot be read."""
    try:
        return github(settings()["github_token"])
    except requests.RequestException as error:
        st.html(console.notice(github_trouble(error, reading=True), "bad"))
    except (KeyError, TypeError, ValueError):   # GitHub answered, but not in the shape the console reads
        st.html(console.notice("GitHub's answer was not in the shape the console expects, so it cannot be shown now. "
                               "Try Refresh; if it stays, the console needs updating.", "bad"))
    st.stop()


def layout(icon_name, title, line):
    """Draw the page's header band; return (body, actions) containers."""
    st.html(console.view_head(icon_name, title, line))
    with st.container(key="console_page"):
        body, side = st.columns([4.2, 1])
    with side:
        actions = st.container(key="console_actions")
    with actions:
        st.html('<p class="c-actions-head">Actions</p>')
    return body, actions


def refresh_action():
    """The Actions pane's Refresh: read GitHub again now."""
    if st.button("Refresh", key="console_refresh_action", icon=":material/refresh:", help="Read everything again from GitHub"):
        github.clear()
        st.session_state[REFRESH_PENDING] = True
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
