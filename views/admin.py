"""Admin: the decisions waiting for the team, in plain words (issue 17). Only people on the list may see it.

Sign-in is Google's, through Streamlit (st.login); the list of addresses allowed in and the GitHub token the page reads
with are in .streamlit/secrets.toml under [admin]. Each item is an open pull request in the private mirror labelled
"decision: <kind>" (evidence/decisions.py). Under each item the team makes its call: the decision is written on the
pull request, which is then merged, left open or closed (decided 20 Oct 2026, issue 17).
"""
from datetime import datetime, timezone
from html import escape

import requests
import streamlit as st

from evidence import decisions
from evidence.decision_settings import ACTIONS, AFTER_CHANGES, CHOICES, READ_EVERY_SECONDS, SECRETS_SECTION
from ui import admin, reveal, sign_in_fix, surfaces

# What Google sign-in (st.login) needs in [auth]; one left empty means it is not set up.
SIGN_IN_FIELDS = ("redirect_uri", "cookie_secret", "client_id", "client_secret", "server_metadata_url")


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner=False)
def read(token):
    """The open pull requests and when they were read; kept for READ_EVERY_SECONDS."""
    return decisions.fetch_open(token), datetime.now(timezone.utc)


def settings():
    """The [admin] settings, and whether Google sign-in is set up. Both empty without a secrets file."""
    try:
        auth = st.secrets.get("auth", {})
        return dict(st.secrets.get(SECRETS_SECTION, {})), all(auth.get(field) for field in SIGN_IN_FIELDS)
    except FileNotFoundError:
        return {}, False


def sign_out():
    st.button("Sign out", key="admin_sign_out", on_click=st.logout)


def decide_controls(item, config, who, email):
    """The call on one item: a choice, then the reason (and the changes asked for), then one button that records it."""
    number = item["number"]
    with st.container(key=f"decide_{number}"):
        said = st.session_state.get("admin_result")
        if said and said[0] == number:   # why the last try on this item did not go through, beside it
            surfaces.show(surfaces.notice(said[2], said[1]))
            del st.session_state["admin_result"]
        choice = st.segmented_control("Decision", list(CHOICES), format_func=CHOICES.get, key=f"choice_{number}",
                                      label_visibility="collapsed")
        if choice is None:
            return
        reason = st.text_area("Reason (every decision needs one)", key=f"reason_{number}", height=80)
        changes = (st.text_area("Changes asked for", key=f"changes_{number}", height=80) if choice == AFTER_CHANGES
                   else "")
        surfaces.show(f'<p class="small">This writes the decision on pull request {number}, {ACTIONS[choice]}.</p>')
        if st.button(f"Record: {CHOICES[choice]}", key=f"record_{number}", type="primary"):
            try:
                result = decisions.decide(config["github_token"], item, choice, reason, changes, who, email,
                                          dict(config.get("accounts", {})), datetime.now(timezone.utc))
            except requests.RequestException as error:
                result = "bad", github_trouble(error)
            st.session_state["admin_result"] = (number, *result)
            if result[0] == "ok":
                read.clear()   # the list has changed on GitHub
                for key in (f"choice_{number}", f"reason_{number}", f"changes_{number}"):
                    st.session_state.pop(key, None)
            st.rerun()


def github_trouble(error):
    """What went wrong reading GitHub, in plain words. Never the token."""
    code = getattr(getattr(error, "response", None), "status_code", None)
    if code in (401, 403):
        return "GitHub refused the page's token: it may have expired or lost its access."
    if code in (404, 405, 409, 422):
        return "GitHub would not do that. Nothing more was written; look at the pull request on GitHub."
    return "GitHub did not answer, so it cannot be shown or changed now. Try again when the page is next opened."


sign_in_fix.apply()   # before anyone presses Sign in
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

who = st.user.get("name") or email
surfaces.show(f'<p class="small">Signed in as {escape(who)}.</p>')
sign_out()
try:
    prs, read_at = read(config["github_token"])
except requests.RequestException as error:
    surfaces.show(surfaces.notice(github_trouble(error), "bad"))
    st.stop()

items = decisions.pending(prs, datetime.now(timezone.utc))
said = st.session_state.get("admin_result")
if said and (said[1] == "ok" or said[0] not in {i["number"] for i in items}):   # its item has left the list
    surfaces.show(surfaces.notice(said[2], said[1]))
    del st.session_state["admin_result"]
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
        decide_controls(item, config, who, email)
surfaces.show(f'<p class="small">Read from GitHub at {read_at:%H:%M} UTC. It is read again after '
              f'{READ_EVERY_SECONDS // 60} minutes.</p>')
