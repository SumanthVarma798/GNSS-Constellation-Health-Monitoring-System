"""What every console page shares: its settings, one cached reading of GitHub, plain words for GitHub's errors, and
the page's layout (its header band, its body, and the Actions pane on the right)."""
from datetime import datetime, timezone

import requests
import streamlit as st

from evidence import decisions, github_api, jobs
from evidence.console_settings import ARCHIVE_REPOSITORY, JOBS, RUN_LOGS, RUNS_READ, WORKFLOWS_DIR
from evidence.decision_settings import READ_EVERY_SECONDS, SECRETS_SECTION
from ui import console

# What Google sign-in (st.login) needs in [auth]; one left empty means it is not set up.
SIGN_IN_FIELDS = ("redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url")
NOT_SET_UP = ("The console is not set up on this computer. It needs Google sign-in, the list of people who may sign in, "
              "and a GitHub token, all in .streamlit/secrets.toml (see .streamlit/secrets.example.toml).")


def settings():
    """The [admin] settings, and whether Google sign-in is set up. Both empty without a secrets file."""
    try:
        auth = st.secrets.get("auth", {})
        return dict(st.secrets.get(SECRETS_SECTION, {})), all(auth.get(field) for field in SIGN_IN_FIELDS)
    except FileNotFoundError:
        return {}, False


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner=False)
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
    return {"workflows": github_api.ask("GET", "/actions/workflows", token)["workflows"],
            # Each workflow's own newest runs, so many test runs never push older scheduled runs out of view.
            "runs": [run for workflow in dict.fromkeys(w for w, *_ in JOBS)
                     for run in github_api.ask("GET", f"/actions/workflows/{workflow}/runs", token,
                                               params={"per_page": RUNS_READ})["workflow_runs"]],
            "log": log, "prs": decisions.fetch_open(token), "problems": problems, "read_at": datetime.now(timezone.utc)}


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
        return github(settings()[0]["github_token"])
    except requests.RequestException as error:
        st.html(console.notice(github_trouble(error, reading=True), "bad"))
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
        st.rerun()


def now():
    return datetime.now(timezone.utc)
