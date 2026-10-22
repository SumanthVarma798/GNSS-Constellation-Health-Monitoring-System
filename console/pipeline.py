"""Live pipeline: what is running now, what happens next, and proof links for each stage."""
from html import escape
import re

import streamlit as st

from console import common
from evidence import pipeline
from evidence.console_settings import PIPELINE_FEED_EVENTS, PIPELINE_LOOK_AHEAD_HOURS, PIPELINE_READ_EVERY_SECONDS
from ui import console

_STATE_TONE = {"running now": "info", "done": "ok", "failed": "bad", "waiting": "warn", "off": "idle"}
_RUN_NUMBER = re.compile(r"/actions/runs/(\d+)")


def _duration_words(delta):
    if delta is None:
        return "–"
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds} s"
    minutes, left = divmod(seconds, 60)
    return f"{minutes} m {left:02d} s"


def _link(url, words):
    if not url:
        return '<span class="muted">none</span>'
    safe_url = escape(url, quote=True)
    return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{escape(words)}</a>'


def _run_words(url, fallback="run"):
    if not url:
        return fallback if fallback and fallback.lower() != "run" else "GitHub run"
    if found := _RUN_NUMBER.search(url):
        return f"run {found.group(1)}"
    return fallback if fallback and fallback.lower() != "run" else "GitHub run"


def _commit_words(sha=None):
    return f"commit {sha[:7]}" if sha else "GitHub commit"


def _pull_request_words(number=None):
    return f"pull request {number}" if number else "GitHub pull request"


def _proof_link_words(event):
    words = (event.get("link_words") or "").strip()
    if words:
        lowered = words.lower()
        if lowered == "run":
            return "GitHub run"
        if lowered == "commit":
            return "GitHub commit"
        if lowered in {"pull request", "pr"}:
            return "GitHub pull request"
        return words
    happened = (event.get("words") or "").lower()
    if "pull request" in happened:
        return "GitHub pull request"
    if "commit" in happened:
        return "GitHub commit"
    return "GitHub run"


@st.fragment(run_every=PIPELINE_READ_EVERY_SECONDS)
def live_page():
    body, actions = common.layout("pipeline", "Live pipeline", "The pipeline from archive runs to approvals and dashboard, "
                                                                "with what is running now, what happens next, and proof links.")
    seen = common.read()
    now = common.now()
    stages = pipeline.stages(seen["workflows"], seen["runs"], seen["log"], seen["decision_prs"], common.workflow_texts(), now)
    upcoming = pipeline.what_next(stages, now, hours=PIPELINE_LOOK_AHEAD_HOURS)
    running = [stage for stage in stages if stage["state"] == "running now"]
    feed = pipeline.proof_feed(seen["runs"], seen["log"], seen["decision_prs"], limit=PIPELINE_FEED_EVENTS)
    stage_names = [stage["name"] for stage in stages]
    next_name, next_at = ((upcoming[0]["name"], upcoming[0]["at"]) if upcoming else (None, None))
    if stage_names:
        selected = st.session_state.get("pipeline_stage")
        default_stage = (running[0]["name"] if running else next_name) or stage_names[0]
        if selected not in stage_names:
            st.session_state["pipeline_stage"] = default_stage
    with body:
        for problem in seen["problems"]:
            st.html(console.notice(problem, "warn"))
        st.caption(f"Read from GitHub {seen['read_at']:%H:%M} UTC")
        st.html(console.section("Pipeline picture", console.pipeline_diagram(stages, next_name, next_at),
                                right="state in words and colour; the next run is tagged", flush=True))

        left, right = st.columns(2)
        with left:
            st.html(console.section("Running now", console.list_view(
                ["Stage", "State", "Started"],
                [[escape(stage["name"]), console.status(_STATE_TONE[stage["state"]], stage["state"]),
                  escape(console.when(stage.get("running_start") or (stage["last"] or {}).get("start")))] for stage in running], numeric=())
                if running else console.notice("No stage is running now.", "info"), flush=bool(running)))
        with right:
            st.html(console.section("Next up", console.list_view(
                ["Stage", "When (UTC)", "What it does"],
                [[escape(item["name"]), escape(console.when(item["at"])), escape(next(stage["what"] for stage in stages
                                                                                    if stage["name"] == item["name"]))]
                 for item in upcoming], numeric=())
                if upcoming else console.notice(f"No scheduled runs in the next {PIPELINE_LOOK_AHEAD_HOURS} hours.", "info"),
                right="soonest first", flush=bool(upcoming)))

        st.html(console.section("Proof of work", console.list_view(
            ["Time (UTC)", "Event", "Link"],
            [[escape(console.when(event["time"])), escape(event["words"]),
              _link(event.get("link"), _proof_link_words(event))]
             for event in feed], numeric=()) if feed else console.notice("No proof events yet.", "info"),
            right=f"newest {PIPELINE_FEED_EVENTS}", flush=bool(feed)))

        if stage_names:
            st.segmented_control("Show the details of", stage_names, key="pipeline_stage")
            stage_by_name = {stage["name"]: stage for stage in stages}
            selected_name = st.session_state.get("pipeline_stage") or stage_names[0]
            selected = stage_by_name.get(selected_name, stages[0])
            last = selected["last"]
            proof = selected["proof"]
            st.html(console.section("Stage details", console.key_values([
                ("State", console.status(_STATE_TONE[selected["state"]], selected["state"])),
                ("What this stage does", escape(selected["what"])),
                ("Last start", escape(console.when((last or {}).get("start")))),
                ("Last end", escape(console.when((last or {}).get("end")))),
                ("Duration", escape(_duration_words((last or {}).get("duration")))),
                ("Result", escape((last or {}).get("result", "No run recorded yet"))),
                ("What changed", escape((last or {}).get("changed", "nothing") or "nothing")),
                ("Next run", escape(console.when(selected["next"])) if selected["next"] else '<span class="muted">none</span>'),
                ("Last run on GitHub", _link(proof.get("run_url"),
                                             _run_words(proof.get("run_url"), proof.get("run_words") or "GitHub run"))),
                ("Archive commit", (_link(proof.get("archive_commit_url"), _commit_words(proof.get("archive_commit")))
                                    if proof.get("archive_commit_url") else '<span class="muted">not recorded</span>')),
                ("Pull request", (_link(proof.get("pr_url"), _pull_request_words(proof.get("pr_number")))
                                  + (f" ({escape(proof['pr_state'])})" if proof.get("pr_state") else "")
                                  if proof.get("pr_url") else '<span class="muted">none</span>')),
            ]), right="selection is kept while this page refreshes"))
    with actions:
        common.refresh_action()
        st.html('<p class="c-actions-sub">Go to</p>')
        st.page_link("console/jobs.py", label="Jobs", icon=":material/schedule:")
        st.page_link("console/approvals.py", label="Approvals", icon=":material/task_alt:")


live_page()
