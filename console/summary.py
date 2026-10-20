"""Summary: the state of the whole system, and what needs attention first."""
from html import escape

import streamlit as st

from console import common
from evidence import decisions, jobs
from evidence.console_settings import ORBIT_LOG_JOB, RELIABILITY_DAYS
from evidence.source_overview import overview
from ui import console
from ui.shell import STALE_DAYS

seen = common.read()
now = common.now()
rows = jobs.job_rows(seen["workflows"], seen["runs"], seen["log"], common.workflow_texts(), now)
sources = overview()
waiting = len(decisions.pending(seen["prs"], now))
items = jobs.attention(rows, sources["not_answering"], waiting)
looks = sum(tone != "ok" for tone, *_ in items)

body, actions = common.layout("summary", "Summary", "The state of the whole system, and what needs attention first.")
with body:
    for problem in seen["problems"]:
        st.html(console.notice(problem, "warn"))
    st.html(console.section("Needs attention", console.attention(items),
                            right=f"{looks} item{'' if looks == 1 else 's'}" if looks else "nothing"))

    grid = jobs.reliability(seen["runs"], now)
    ok = sum(day[0] for days in grid["rows"].values() for day in days if day)
    failed = sum(day[1] for days in grid["rows"].values() for day in days if day)
    runs_tile = console.tile("bad" if failed else "ok", f"Scheduled runs, last {RELIABILITY_DAYS} days",
                             console.status("bad" if failed else "ok", f"{failed} failed" if failed else "none failed"),
                             f"{ok} of {ok + failed}", "succeeded",
                             console.stack([(ok, "c-ok", "succeeded"), (failed, "c-bad", "failed")], f"{ok} succeeded, {failed} failed"))
    proposed = sources["proposed"]
    not_answering = sum(sources["not_answering"].values())
    sources_tile = console.tile("warn" if not_answering else "ok", "Sources",
                                console.status("warn", f"{not_answering} not answering") if not_answering else console.status("ok", "all answer"),
                                f"{sources['graded']} graded · {sources['candidates']} candidates", "proposed grades of the candidates",
                                console.stack([(proposed.get("A", 0), "c-ok", "A"), (proposed.get("B", 0), "c-info", "B"),
                                               (proposed.get("C", 0), "c-c", "C"), (proposed.get("D", 0), "c-warn", "D"),
                                               (proposed.get("", 0), "c-idle", "no grade")], "Proposed grades"))
    orbit_runs = [line for line in seen["log"] if line["job"] == ORBIT_LOG_JOB and line["result"] in ("ok", "success")]
    if orbit_runs:
        latest = max(line["started"] for line in orbit_runs)
        hours = (now - latest).total_seconds() / 3600
        fresh = hours <= STALE_DAYS * 24
        orbit_tile = console.tile("ok" if fresh else "warn", "Orbit data archived", console.status("ok" if fresh else "warn", "fresh" if fresh else "old"),
                                  console.when(latest) + " UTC", f"{hours:.0f} hours ago; warns after {STALE_DAYS} days",
                                  console.stack([(min(round(hours), STALE_DAYS * 24), "c-ok" if fresh else "c-warn", "hours old"),
                                                 (max(0, STALE_DAYS * 24 - round(hours)), "c-idle", "hours to the warning")], "Age of the orbit data"))
    else:
        orbit_tile = console.tile("warn", "Orbit data archived", console.status("warn", "not known"), "–", "no orbit run in the run log")
    tests = next(r for r in rows if r["workflow"] == "tests.yml")
    tests_tile = console.tile(tests["result"][0] if tests["result"][0] != "idle" else "info", "Tests on main",
                              console.status(*tests["result"]), tests["result"][1], f"last run {console.when(tests['last'])} UTC")
    st.html(console.section("At a glance", console.tiles([runs_tile, sources_tile, orbit_tile, tests_tile]),
                            right=f"read {seen['read_at']:%H:%M} UTC"))

    happened = jobs.events(seen["log"], seen["runs"])
    level = {"ok": "Information", "bad": "Error", "warn": "Warning"}
    st.html(console.section("Recent events", console.list_view(
        ["Time (UTC)", "Level", "Source", "Event"],
        [[escape(console.when(e["when"])), console.status(e["tone"], level.get(e["tone"], "Information")), escape(e["source"]),
          escape(e["text"])] for e in happened]) if happened else console.notice("No runs recorded yet.", "info"),
        right="newest first", flush=bool(happened)))

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">Go to</p>')
    st.page_link("console/jobs.py", label="Jobs", icon=":material/schedule:")
    st.page_link("console/approvals.py", label=f"Approvals ({waiting})", icon=":material/task_alt:")
