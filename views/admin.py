"""Admin: the decisions waiting for the team, in plain words (issue 17). Only people on the list may see it.

Sign-in is Google's, through Streamlit (st.login); the list of addresses allowed in and the GitHub token the page reads
with are in .streamlit/secrets.toml under [admin]. Each item is an open pull request in the private mirror labelled
"decision: <kind>" (evidence/decisions.py). This page only reads; deciding comes in a later step of issue 17.
"""
from datetime import datetime, timezone

import requests
import streamlit as st

from evidence import decisions
from evidence.decision_settings import READ_EVERY_SECONDS, SECRETS_SECTION
from ui import admin, reveal, surfaces


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner=False)
def read(token):
    """The open pull requests and when they were read; kept for READ_EVERY_SECONDS."""
    return decisions.fetch_open(token), datetime.now(timezone.utc)


def settings():
    """The [admin] settings, and whether Google sign-in is set up. Both empty without a secrets file."""
    try:
        return dict(st.secrets.get(SECRETS_SECTION, {})), "auth" in st.secrets
    except FileNotFoundError:
        return {}, False


def sign_out():
    st.button("Sign out", key="admin_sign_out", on_click=st.logout)


def github_trouble(error):
    """What went wrong reading GitHub, in plain words. Never the token."""
    code = getattr(getattr(error, "response", None), "status_code", None)
    if code in (401, 403):
        return "GitHub refused the page's token: it may have expired or lost its access. The list cannot be shown."
    return "GitHub did not answer, so the list cannot be shown. It is read again when the page is next opened."


surfaces.show(admin.CSS)
config, sign_in_ready = settings()
if not (sign_in_ready and config.get("allowed") and config.get("github_token")):
    surfaces.show(surfaces.notice(admin.NOT_SET_UP, "idle"))
    st.stop()

email = st.user.get("email")
state = decisions.access(st.user.is_logged_in, email, config["allowed"])
if state == "sign in":
    surfaces.show(f'<p class="small">{admin.INTRO}</p>')
    st.button("Sign in with Google", key="admin_sign_in", on_click=st.login)
    st.stop()
if state == "not on the list":
    surfaces.show(surfaces.notice(f"You are signed in as {email}, which is not on the list of people who may see "
                                  "this page. Ask for it to be added.", "warn"))
    sign_out()
    st.stop()

surfaces.show(f'<p class="small">Signed in as {st.user.get("name") or email}.</p>')
sign_out()
try:
    prs, read_at = read(config["github_token"])
except requests.RequestException as error:
    surfaces.show(surfaces.notice(github_trouble(error), "bad"))
    st.stop()

items = decisions.pending(prs, datetime.now(timezone.utc))
groups = decisions.grouped(items)
surfaces.show(admin.headline(items, groups))
if not items:
    surfaces.show(surfaces.notice("Nothing is waiting for a decision.", "ok"))
for group, its in groups:
    surfaces.show(surfaces.group_head(group, admin.group_line(its)))
    for item in its:
        surfaces.show(admin.card(item))
        reveal.section(f"admin_{item['number']}", "What the pull request says", "the evidence in full",
                       admin.text_html(item["body"]))
surfaces.show(f'<p class="small">Read from GitHub at {read_at:%H:%M} UTC. It is read again after '
              f'{READ_EVERY_SECONDS // 60} minutes.</p>')
