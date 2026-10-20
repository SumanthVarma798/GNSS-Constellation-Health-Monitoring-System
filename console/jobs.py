"""Jobs: every scheduled job, when it runs, whether it is running, and how its runs ended. Times are UTC."""
from html import escape

import streamlit as st

from console import common
from evidence import jobs
from evidence.console_settings import JOBS, RELIABILITY_DAYS
from evidence.decision_settings import REPOSITORY
from ui import console

LOG_LINES = 15   # the newest lines of the run log shown
STATE_TONE = {"Ready": "ok", "Running": "info", "Turned off": "idle"}

seen = common.read()
now = common.now()
rows = jobs.job_rows(seen["workflows"], seen["runs"], seen["log"], common.workflow_texts(), now)

body, actions = common.layout("jobs", "Jobs", "Every scheduled job: when it runs, whether it is running, and how each "
                                              "run ended. Times in UTC.")
with body:
    for problem in seen["problems"]:
        st.html(console.notice(problem, "warn"))
    st.html(console.section("Scheduled jobs", console.list_view(
        ["Name", "Runs", "State", "Next run", "Last run", "Last result"],
        [[f"<b>{escape(r['name'])}</b><br><span class='muted'>{escape(r['what'])}</span>", escape(r["schedule"]),
          console.status(STATE_TONE[r["state"]], r["state"]),
          escape(console.when(r["next"]) if r["next"] else "none" if r["state"] == "Turned off" else "on the next change"
                 if r["workflow"] == "tests.yml" else "none in the next week"),
          escape(console.when(r["last"])), console.status(*r["result"])] for r in rows]),
        right="GitHub often starts scheduled runs late", flush=True))

    names = {"archive.yml": "Archive (all groups)", **{w: name for w, _, name, *_ in JOBS if w != "archive.yml"}}
    st.html(console.section("Reliability, day by day", console.reliability_grid(jobs.reliability(seen["runs"], now), names)
                            + '<div class="c-legend" style="margin-top:6px"><span>✓ every run that day succeeded</span>'
                              '<span>✕ n: n runs failed</span><span>– did not run</span></div>',
                            right=f"scheduled runs on GitHub, last {RELIABILITY_DAYS} days"))

    newest = sorted(seen["log"], key=lambda line: line["started"], reverse=True)[:LOG_LINES]
    st.html(console.section("Run log", console.list_view(
        ["Started", "Job", "Took", "Result", "What changed"],
        [[escape(console.when(line["started"])), escape(line["job"]),
          escape(f"{(jobs.parse_time(line['ended']) - line['started']).total_seconds():.0f} s"),
          console.status(*jobs.log_result(line)),
          escape(f"{len(line['changed'].split())} copies" if line["changed"].startswith("http") else line["changed"])]
         for line in newest], numeric=("Took",)) if newest else console.notice("No run log lines yet.", "info"),
        right="from the archive, newest first", flush=bool(newest)))

with actions:
    common.refresh_action()
    st.html('<p class="c-actions-sub">On GitHub</p>')
    st.link_button("Every run", f"https://github.com/{REPOSITORY}/actions", icon=":material/open_in_new:")
