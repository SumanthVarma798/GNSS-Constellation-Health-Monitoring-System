"""Sources: everything the system reads, how far it is trusted, and whether it answered when last checked.

Read from evidence/source_grades.csv (grades confirmed) and evidence/source_candidates.csv (feeds and pages, with the
grade proposed for each); evidence/source_overview.py joins them. A grade is confirmed through a pull request, decided
under Approvals, so this page only shows grades and points there.
"""
from html import escape

import streamlit as st

from console import common
from evidence import decisions
from evidence.decision_settings import REPOSITORY
from evidence.settings import RELIABILITY_GRADES
from evidence.source_overview import GROUPS, source_rows
from ui import console

SHOW = {"all": "All", "graded": "Graded", "awaiting a grade": "Awaiting a grade", "no grade": "No grade",
        "not answering": "Not answering", "held": "Held by rule"}
RAMP = {"A": "g-a", "B": "g-b", "C": "g-c", "D": "g-d"}   # the validated ordered ramp; any other grade is drawn neutral

seen = common.read()
rows = source_rows()
counts = {group: sum(r["group"] == group for r in rows) for group in GROUPS}
confirmed_sites = {r["source"] for r in rows if r["confirmed"]}   # a grade belongs to a site, whatever its last check
grade_waits = [i for i in decisions.pending(seen["prs"], common.now()) if i["kind"] == "source grade"]

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

    st.session_state.setdefault("sources_show", "all")
    shown_as = st.segmented_control("Show", list(SHOW), format_func=lambda k: f"{SHOW[k]} ({len(rows) if k == 'all' else counts[k]})",
                                    key="sources_show", label_visibility="collapsed") or "all"
    find = st.text_input("Find a source by its name or address", key="sources_find", placeholder="for example: ISRO, galileo, reddit")
    shown = [r for r in rows if (shown_as == "all" or r["group"] == shown_as)
             and find.lower() in (r["name"] + " " + r["address"]).lower()]
    st.html(console.section(SHOW[shown_as], console.list_view(
        ["Source", "Kind", "Grade", "Why this grade", "Last check"],
        [[name_html(r), escape(r["kind"] or "–"), grade_html(r), escape(r["reason"] or "–"),
          console.status(*r["answer"]) + (f'<br><span class="muted">{escape(r["checked_on"])}</span>' if r["checked_on"] else "")]
         for r in shown]) if shown else console.notice("No source matches." if find else "None in this group.", "info"),
        right=f"{len(shown)} of {len(rows)}", flush=bool(shown)))

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">Go to</p>')
    st.page_link("console/approvals.py", label=f"Grades waiting ({len(grade_waits)})", icon=":material/task_alt:")
    st.html('<p class="c-actions-sub">On GitHub</p>')
    st.link_button("The candidates table", f"https://github.com/{REPOSITORY}/blob/main/evidence/source_candidates.csv",
                   icon=":material/open_in_new:")
