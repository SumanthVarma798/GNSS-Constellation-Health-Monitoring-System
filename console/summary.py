"""Summary: the state of the whole system, and what needs attention first.

One figure leads (how many things need a look), then what they are, then four stat tiles, each with a small picture,
then recent events. The pictures follow the dataviz skill: thin marks, gaps of surface between parts, the status
colours kept for good and bad and always said in words, and the source grades as one ordered blue ramp.
"""
from html import escape

import streamlit as st

from console import common
from evidence import decisions, jobs
from evidence.console_settings import ORBIT_LOG_JOB, RELIABILITY_DAYS, TESTS_WORKFLOW
from evidence.source_overview import overview
from ui import console
from ui.shell import STALE_DAYS

TESTS_SHOWN = 10   # the newest runs of the tests on main, as marks

seen = common.read()
now = common.now()
rows = jobs.job_rows(seen["workflows"], seen["runs"], seen["log"], common.workflow_texts(), now)
sources = overview()
waiting = len(decisions.pending(seen["prs"], now))
items = jobs.attention(rows, sources["not_answering"], waiting)
looks = sum(tone != "ok" for tone, *_ in items)
worst = "bad" if any(tone == "bad" for tone, *_ in items) else "warn" if looks else "ok"

body, actions = common.layout("summary", "Summary", "The state of the whole system, and what needs attention first.")
with body:
    for problem in seen["problems"]:
        st.html(console.notice(problem, "warn"))
    failing = sum(tone == "bad" for tone, *_ in items)
    st.html(console.hero(looks, ("thing needs a look" if looks == 1 else "things need a look")
                         + (f", {failing} of them failing" if failing else ", none failing" if looks else ""), worst)
            + console.section("Needs attention", console.attention(items), right="worst first"))

    grid = jobs.reliability(seen["runs"], now)
    per_day = [None if not any(d[i] for d in grid["rows"].values()) else
               (sum(d[i][0] for d in grid["rows"].values() if d[i]), sum(d[i][1] for d in grid["rows"].values() if d[i]))
               for i in range(len(grid["days"]))]
    ok, failed = sum(d[0] for d in per_day if d), sum(d[1] for d in per_day if d)
    runs_tile = console.tile(
        "bad" if failed else "ok", f"Scheduled runs, last {RELIABILITY_DAYS} days",
        console.status("bad" if failed else "ok", f"{failed} failed" if failed else "none failed"),
        f"{ok} of {ok + failed}", "succeeded",
        console.day_columns(per_day, grid["days"])
        + '<div class="c-legend"><span><b style="background:var(--c-quiet)"></b>succeeded</span>'
          '<span><b style="background:var(--c-bad)"></b>failed</span></div>')

    proposed = sources["proposed"]
    not_answering = sum(sources["not_answering"].values())
    sources_tile = console.tile(
        "warn" if not_answering else "ok", "Sources",
        console.status("warn", f"{not_answering} not answering") if not_answering else console.status("ok", "all answer"),
        f"{sources['graded']} graded · {sources['candidates']} candidates", "proposed grades of the candidates, A the most trusted",
        console.stack([(proposed.get("A", 0), "g-a", "A"), (proposed.get("B", 0), "g-b", "B"), (proposed.get("C", 0), "g-c", "C"),
                       (proposed.get("D", 0), "g-d", "D"), (proposed.get("", 0), "g-none", "no grade")], "Proposed grades"))

    orbit_runs = [line for line in seen["log"] if line["job"] == ORBIT_LOG_JOB and line["result"] in ("ok", "success")]
    if orbit_runs:
        latest = max(line["started"] for line in orbit_runs)
        hours = (now - latest).total_seconds() / 3600
        share = hours / (STALE_DAYS * 24)
        tone = "ok" if share < 0.5 else "warn" if share < 1 else "bad"
        orbit_tile = console.tile(tone, "Orbit data archived",
                                  console.status(tone, {"ok": "fresh", "warn": "getting old", "bad": "old"}[tone]),
                                  console.when(latest) + " UTC", f"{hours:.0f} hours ago; warns after {STALE_DAYS} days",
                                  console.meter(share, tone, f"{hours:.0f} of {STALE_DAYS * 24} hours"))
    else:
        orbit_tile = console.tile("warn", "Orbit data archived", console.status("warn", "not known"), "–",
                                  "no orbit run in the run log")

    tests = next(r for r in rows if r["workflow"] == TESTS_WORKFLOW)
    on_main = sorted((r for r in seen["runs"] if r["path"].endswith(TESTS_WORKFLOW) and r["head_branch"] == "main"
                      and r["event"] == "push" and r["status"] == "completed"), key=lambda r: r["created_at"])[-TESTS_SHOWN:]
    looks_of = {"ok": ("ok", "✓"), "bad": ("bad", "✕"), "idle": ("none", "–")}   # a cancelled run is neither
    marks = "".join(
        f'<span class="m {looks_of[jobs.conclusion(r)[0]][0]}" '
        f'title="{escape(console.when(jobs.parse_time(r["created_at"])) + ": " + jobs.conclusion(r)[1], quote=True)}">'
        f'{looks_of[jobs.conclusion(r)[0]][1]}</span>' for r in on_main)
    said = ", ".join(f"{console.when(jobs.parse_time(r['created_at']))} {jobs.conclusion(r)[1].lower()}" for r in on_main)
    tests_tile = console.tile(tests["result"][0] if tests["result"][0] != "idle" else "info", "Tests on main",
                              console.status(*tests["result"]), tests["result"][1], f"last run {console.when(tests['last'])} UTC",
                              f'<div class="c-marks" role="img" aria-label="{escape(f"The last {len(on_main)} runs on main: {said}", quote=True)}">{marks}</div>')
    st.html(console.section("At a glance", console.tiles([runs_tile, sources_tile, orbit_tile, tests_tile]),
                            right=f"read {seen['read_at']:%H:%M} UTC"))

    happened = jobs.events(seen["log"], seen["runs"])
    level = {"ok": "Information", "bad": "Error", "warn": "Warning", "idle": "Information"}
    st.html(console.section("Recent events", console.list_view(
        ["Time (UTC)", "Level", "Source", "Event"],
        [[escape(console.when(e["when"])), console.status(e["tone"], level[e["tone"]]), escape(e["source"]), escape(e["text"])]
         for e in happened]) if happened else console.notice("No runs recorded yet.", "info"),
        right="newest first", flush=bool(happened)))

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">Go to</p>')
    st.page_link("console/jobs.py", label="Jobs", icon=":material/schedule:")
    st.page_link("console/work.py", label="Issues and pull requests", icon=":material/list_alt:")
    st.page_link("console/approvals.py", label=f"Approvals ({waiting})", icon=":material/task_alt:")
