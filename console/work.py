"""Issues and pull requests: the open work in the private mirror, with what each is and how old it is."""
from html import escape

import streamlit as st

from console import common
from evidence import work
from evidence.decision_settings import REPOSITORY
from ui import console

seen = common.read()
now = common.now()
pulls = work.pull_rows(seen["prs"], now)
issues = seen["issues"]

body, actions = common.layout("work", "Issues and pull requests", "The open work in the project's private mirror: "
                                                                 "what is being built, and what is waiting.")


def labels_html(found):
    """Each label as a swatch in its GitHub colour beside its name in ink."""
    return " ".join(f'<span class="c-label"><b style="background:{colour}"></b>{escape(name)}</span>' for name, colour in found)


def link(row):
    return (f'<a href="{escape(row["link"], quote=True)}" target="_blank" rel="noopener noreferrer">{row["number"]}</a>')


with body:
    for problem in seen["problems"]:
        st.html(console.notice(problem, "warn"))
    waiting = sum(1 for p in pulls if p["decision"])
    stale = max((i["updated_days"] for i in work.issue_rows(issues, now)), default=0)
    st.html(console.tiles([
        console.tile("info", "Open pull requests", "", str(len(pulls)), "drafts included"),
        console.tile("warn" if waiting else "ok", "Waiting on a decision", console.status("warn" if waiting else "ok", "see Approvals" if waiting else "none"),
                     str(waiting), "labelled 'decision: …'"),
        console.tile("info", "Open issues", "", str(len(issues)), "pull requests not counted"),
        console.tile("warn" if stale > 30 else "info", "Longest without an update", "", work.age_words(stale), "among the open issues")]))

    st.html(console.section("Open pull requests", console.list_view(
        ["No.", "Title", "Raised by", "Open for", "Labels", "State"],
        [[link(p), escape(p["title"]), escape(p["by"]), escape(work.age_words(p["opened_days"])), labels_html(p["labels"]),
          console.status("warn", f"waits on a decision: {p['decision']}") if p["decision"] else
          console.status("idle", "draft") if p["draft"] else console.status("info", "open")] for p in pulls],
        numeric=("No.",)) if pulls else console.notice("No pull request is open.", "ok"),
        right="newest first", flush=bool(pulls)))

    find = st.text_input("Find an issue by its title", key="work_find", placeholder="for example: registry, NavIC, archive")
    shown = work.issue_rows(issues, now, find)
    st.html(console.section("Open issues", console.list_view(
        ["No.", "Title", "Updated", "Open for", "Comments", "Labels"],
        [[link(i), escape(i["title"]), escape(work.age_words(i["updated_days"]) + (" ago" if i["updated_days"] else "")),
          escape(work.age_words(i["opened_days"])), str(i["comments"]), labels_html(i["labels"])] for i in shown],
        numeric=("No.", "Comments")) if shown else console.notice("No open issue matches." if find else "No issue is open.", "info"),
        right=f"{len(shown)} of {len(issues)}, the most recently updated first", flush=bool(shown)))

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">On GitHub</p>')
    st.link_button("All issues", f"https://github.com/{REPOSITORY}/issues", icon=":material/open_in_new:")
    st.link_button("All pull requests", f"https://github.com/{REPOSITORY}/pulls", icon=":material/open_in_new:")
