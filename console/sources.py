"""Sources: everything the system reads, how far it is trusted, and whether it answered when last checked.

Read from evidence/source_grades.csv (grades confirmed) and evidence/source_candidates.csv (feeds and pages, with the
grade proposed for each); evidence/source_overview.py joins them. A grade is confirmed through a pull request, decided
under Approvals, so this page only shows grades and points there. A grade set on this page is set by a person, so the
weekly source record keeps testing it but never moves it (it raises a disagreement finding instead).
"""
from collections import Counter
from html import escape

import streamlit as st

from console import common
from evidence import decisions, grade_change
from evidence.decision_settings import REPOSITORY
from evidence.settings import RELIABILITY_GRADES
from evidence.source_overview import (GROUPS, ago_words, archive_read_times, archived_address_groups, source_rows)
from ui import console

SHOW = {"all": "All", "graded": "Graded", "awaiting a grade": "Awaiting a grade", "no grade": "No grade",
        "not answering": "Not answering", "held": "Held by rule"}
RAMP = {"A": "g-a", "B": "g-b", "C": "g-c", "D": "g-d"}   # the validated ordered ramp; any other grade is drawn neutral
GRADE_FILTER = ("A", "B", "C", "D", "E", "F", "none")

config = common.settings()
email = st.user.get("email")
who = st.user.get("name") or email
may_change = decisions.access(st.user.is_logged_in, email, config.get("allowed", [])) == "in"

seen = common.read()
rows = source_rows()
counts = {group: sum(r["group"] == group for r in rows) for group in GROUPS}
confirmed_sites = {r["source"] for r in rows if r["confirmed"]}   # a grade belongs to a site, whatever its last check
confirmed_grade = {r["source"]: r["grade"] for r in rows if r["confirmed"]}
names = {r["source"]: r["name"] for r in rows}
grade_waits = [i for i in decisions.pending(seen["prs"], common.now()) if i["kind"] == "source grade"]
archive_ok = seen.get("archive_versions") is not None
read_times = archive_read_times(seen.get("archive_versions") or [], seen.get("log", [])) if archive_ok else {}
archived = archived_address_groups()
now = seen["read_at"]

body, actions = common.layout("sources", "Sources", "Everything the system reads, how far each is trusted, and whether it "
                                                    "answered when last checked.")


def grade_html(row):
    """The grade as a swatch in the blue ramp beside the letter in ink, and 'proposed' until a person confirms it."""
    if not row["grade"]:
        return '<span class="muted">none</span>'
    meaning = RELIABILITY_GRADES.get(row["grade"], "")
    swatch = f'<span class="c-label" title="{escape(meaning, quote=True)}"><b style="background:var(--{RAMP.get(row["grade"], "g-none")})"></b>'
    return swatch + f'{escape(row["grade"])}</span>' + ("" if row["confirmed"] else '<span class="muted">proposed</span>')


def name_html(row):
    address = row["address"]
    link = (f'<br><a href="{escape(address, quote=True)}" target="_blank" rel="noopener noreferrer" class="muted">'
            f'{escape(address)}</a>' if address.startswith(("https://", "http://")) else "")
    return f"<b>{escape(row['name'])}</b>{link}"


def last_read_html(row):
    """When the archive last read this address, and when its content last changed."""
    address = row["address"]
    if not address or address not in archived:
        return '<span class="muted">not read here</span>'
    if not archive_ok:
        return '<span class="muted">not known</span>'
    times = read_times.get(address, {})
    read_line = ago_words(times.get("last_read"), now)
    changed = times.get("last_changed")
    sub = (f'<br><span class="muted">changed {ago_words(changed, now)}</span>' if changed else "")
    return escape(read_line) + sub


def grade_key(row):
    return row["grade"] if row["grade"] else "none"


with body:
    for problem in seen["problems"]:
        st.html(console.notice(problem, "warn"))
    st.html(console.tiles([
        console.tile("info", "Sources known", "", str(len(rows)), f"{len({r['source'] for r in rows})} sites"),
        console.tile("ok", "Graded sites", console.status("ok", "confirmed"), str(len(confirmed_sites)), "a person confirmed the grade"),
        console.tile("warn" if grade_waits else "info", "Awaiting a grade",
                     console.status("warn", f"{len(grade_waits)} decision{'' if len(grade_waits) == 1 else 's'} waiting")
                     if grade_waits else "", str(counts["awaiting a grade"]),
                     "a grade is proposed; decide it under Approvals" if grade_waits else "a grade is proposed"),
        console.tile("warn" if counts["not answering"] else "ok", "Not answering",
                     console.status("warn" if counts["not answering"] else "ok", "at the last check"),
                     str(counts["not answering"]), "refused, not found or timed out")]))

    others = sorted({r["grade"] for r in rows if r["grade"] and r["grade"] not in RAMP})   # E and F: one neutral part
    st.html(console.section("Grades", console.stack(
        [(sum(r["grade"] == g for r in rows), RAMP[g], f"{g}: {RELIABILITY_GRADES[g]}") for g in RAMP]
        + ([(sum(r["grade"] in others for r in rows), "g-none", f"{' and '.join(others)}: {', '.join(RELIABILITY_GRADES.get(g, g) for g in others)}")] if others else [])
        + [(sum(1 for r in rows if not r["grade"]), "g-none", "no grade")], "Grades of the feeds and pages, confirmed and proposed"),
        right="per feed or page, confirmed and proposed together; A the most trusted"))

    kinds_present = sorted({r["kind"] or "–" for r in rows})
    kind_n = Counter(r["kind"] or "–" for r in rows)
    st.html(console.section("Kinds", console.stack([(kind_n[k], "g-none", k) for k in kinds_present], "How many of each kind"),
                        right=f"{len(kinds_present)} kinds", flush=True))

    st.session_state.setdefault("sources_show", "all")
    if st.session_state.get("sources_kind_options") != kinds_present:   # a kind came or went: show every kind again
        st.session_state["sources_kind_options"] = kinds_present
        st.session_state["sources_kinds"] = kinds_present
    st.session_state.setdefault("sources_grades", list(GRADE_FILTER))
    filter_row = st.columns([1.1, 1.4, 1.4, 2])
    with filter_row[0]:
        shown_as = st.segmented_control("Show", list(SHOW), format_func=lambda k: f"{SHOW[k]} ({len(rows) if k == 'all' else counts[k]})",
                                        key="sources_show", label_visibility="collapsed") or "all"
    with filter_row[1]:
        picked_kinds = st.multiselect("Kind", kinds_present, format_func=lambda k: f"{k} ({kind_n[k]})",
                                      key="sources_kinds", label_visibility="collapsed", placeholder="Kind")
    with filter_row[2]:
        grade_n = Counter(grade_key(r) for r in rows)
        picked_grades = st.multiselect("Grade", list(GRADE_FILTER), format_func=lambda g: f"{g} ({grade_n[g]})",
                                       key="sources_grades", label_visibility="collapsed", placeholder="Grade")
    with filter_row[3]:
        find = st.text_input("Find a source by its name or address", key="sources_find",
                             placeholder="for example: ISRO, galileo, reddit", label_visibility="collapsed")
    shown = [r for r in rows if (shown_as == "all" or r["group"] == shown_as)
             and (r["kind"] or "–") in picked_kinds and grade_key(r) in picked_grades
             and find.lower() in (r["name"] + " " + r["address"]).lower()]
    st.html(console.section(SHOW[shown_as], console.list_view(
        ["Source", "Kind", "Grade", "Why this grade", "Last check", "Last read"],
        [[name_html(r), escape(r["kind"] or "–"), grade_html(r), escape(r["reason"] or "–"),
          console.status(*r["answer"]) + (f'<br><span class="muted">{escape(r["checked_on"])}</span>' if r["checked_on"] else ""),
          last_read_html(r)]
         for r in shown]) if shown else console.notice("No source matches." if find or picked_kinds != kinds_present
                                                     or picked_grades != list(GRADE_FILTER) else "None in this group.", "info"),
        right=f"{len(shown)} of {len(rows)}", flush=bool(shown)))

    if may_change:
        with st.expander("Change a source grade", expanded=False):
            said = st.session_state.pop("sources_grade_result", None)
            if said:
                st.html(console.notice(said[1], said[0]))
            options = sorted({r["source"] for r in shown}, key=lambda s: names.get(s, s))
            if not options:
                st.caption("Choose at least one source in the list above.")
            else:
                labels = {s: f"{names.get(s, s)} ({s})" for s in options}
                source_id = st.selectbox("Source", options, format_func=lambda s: labels[s], key="sources_grade_pick")
                new_grade = st.selectbox("New grade", list("ABCDEF"), key="sources_grade_new")
                reason = st.text_area("Reason (required)", key="sources_grade_reason", height=80)
                if st.button("Open a pull request for this grade", key="sources_grade_submit", type="primary"):
                    problem = grade_change.validate(source_id, new_grade, reason, names, confirmed_grade.get(source_id))
                    if problem:
                        st.session_state["sources_grade_result"] = ("warn", problem)
                    else:
                        st.session_state["sources_grade_result"] = grade_change.submit(
                            config["github_token"], source_id, names[source_id], confirmed_grade.get(source_id),
                            new_grade, reason, who, common.now().date(), now=now)
                        common.github.clear()
                    st.rerun()
            st.page_link("console/approvals.py", label="Decide under Approvals", icon=":material/task_alt:")

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">Go to</p>')
    st.page_link("console/approvals.py", label=f"Grades waiting ({len(grade_waits)})", icon=":material/task_alt:")
    st.html('<p class="c-actions-sub">On GitHub</p>')
    st.link_button("The candidates table", f"https://github.com/{REPOSITORY}/blob/main/evidence/source_candidates.csv",
                   icon=":material/open_in_new:")
