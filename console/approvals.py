"""Approvals: the changes waiting for a person, with their context, and the decision on each.

Each item is an open pull request labelled "decision: <kind>" (evidence/decisions.py). The decision is written on the
pull request as a comment, then it is merged, left open or closed (decided 20 Oct 2026, issue 17).
"""
from html import escape

import requests
import streamlit as st

from console import common
from evidence import decisions
from evidence.decision_settings import ACTIONS, AFTER_CHANGES, CHOICES, REPOSITORY
from ui import admin, console


def waiting(days):
    """How long an item has waited, as a status: decisions.waited gives (words, tone)."""
    words, tone = decisions.waited(days)
    return console.status(tone, words)


def decide(item, config, who):
    """The call on one item: a choice, then the reason (and the changes asked for), then one button that records it."""
    number = item["number"]
    with st.container(key=f"decide_{number}"):
        said = st.session_state.get("admin_result")
        if said and said[0] == number:   # why the last try on this item did not go through, beside it
            st.html(console.notice(said[2], said[1]))
            del st.session_state["admin_result"]
        choice = st.radio("Decision", list(CHOICES), format_func=CHOICES.get, key=f"choice_{number}", index=None,
                          horizontal=True)
        if choice is None:
            return
        reason = st.text_area("Reason (every decision needs one)", key=f"reason_{number}", height=80)
        changes = (st.text_area("Changes asked for", key=f"changes_{number}", height=80) if choice == AFTER_CHANGES
                   else "")
        st.html(f'<p class="c-legend">This writes the decision on pull request {number}, {escape(ACTIONS[choice])}.</p>')
        if st.button(f"Record: {CHOICES[choice]}", key=f"record_{number}", type="primary"):
            try:
                result = decisions.decide(config["github_token"], item, choice, reason, changes, who, common.now())
            except requests.RequestException as error:
                result = "bad", common.github_trouble(error)
            st.session_state["admin_result"] = (number, *result)
            common.github.clear()   # read again: GitHub may have changed, whatever the outcome
            if result[0] == "ok":
                for key in (f"choice_{number}", f"reason_{number}", f"changes_{number}"):
                    st.session_state.pop(key, None)
            st.rerun()


config = common.settings()
email = st.user.get("email")
who = st.user.get("name") or email
seen = common.read()
items = decisions.pending(seen["prs"], common.now())

body, actions = common.layout("approvals", "Approvals", "Changes the system proposes, and changes made from this "
                                                        "console. Each is a pull request; approving merges it.")
with body:
    said = st.session_state.get("admin_result")
    if said and (said[1] == "ok" or said[0] not in {i["number"] for i in items}):   # its item has left the list
        st.html(console.notice(said[2], said[1]))
        del st.session_state["admin_result"]
    if not items:
        st.html(console.notice("Nothing is waiting for a decision.", "ok"))
    for group, its in decisions.grouped(items):
        st.html(console.section(group, console.list_view(
            ["Item", "Kind", "Raised by", "Waiting"],
            [[escape(i["title"]), escape(i["kind"]), escape(i["raised_by"]), waiting(i["waited_days"])]
             for i in its]), right=f"{len(its)} waiting, the longest first", flush=True))
        for item in its:
            opened = item["opened"]
            st.html(console.section(f"Pull request {item['number']}: {item['title']}", console.key_values([
                ("What it says", admin.text_html(item["summary"]) if item["summary"] else "<span class='muted'>no summary</span>"),
                ("Kind", escape(item["kind"])),
                ("Raised by", f"{escape(item['raised_by'])}, {opened.day} {opened:%b %Y}"),
                ("Waiting", waiting(item["waited_days"])),
                ("On GitHub", f'<a href="{escape(item["link"], quote=True)}" target="_blank" rel="noopener noreferrer">'
                              f'pull request {item["number"]}</a>')])))
            with st.expander("What the pull request says, in full"):
                st.html(admin.text_html(item["body"]))
            decide(item, config, who)

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">On GitHub</p>')
    st.link_button("Open pull requests", f"https://github.com/{REPOSITORY}/pulls", icon=":material/open_in_new:")
