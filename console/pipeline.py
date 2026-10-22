"""Live pipeline: what is running now, what happens next, and proof links for each stage."""
from html import escape

import streamlit as st
from streamlit.components.v1 import html as component_html

from console import common
from evidence import pipeline
from evidence.console_settings import PIPELINE_FEED_EVENTS, PIPELINE_LOOK_AHEAD_HOURS, PIPELINE_READ_EVERY_SECONDS
from evidence.pipeline_words import PLAIN_STATES, STAGES
from ui import console
from ui.components.live_pipeline import live_pipeline_html, payload as pipeline_payload

_STATE_TONE = {"running now": "info", "done": "ok", "failed": "bad", "waiting": "warn", "off": "idle"}
_EVENT_STAGE_KEY = {
    "archive documents": "archive_documents",
    "archive catalogues": "archive_catalogues",
    "archive orbital": "archive_orbital",
    "archive news": "archive_news",
    "archive social": "archive_social",
    "archive all": "archive",
    "registry update": "registry_update",
}


def _link(url, words):
    if not url:
        return '<span class="muted">none</span>'
    safe_url = escape(url, quote=True)
    return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{escape(words)}</a>'


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


def _plain_state(words):
    return PLAIN_STATES.get(words, words)


def _plain_name(stage):
    return STAGES.get(stage.get("key"), {}).get("plain_name", stage["name"])


def _stage_cell(stage):
    plain, technical = _plain_name(stage), stage["name"]
    if plain == technical:
        return escape(plain)
    return (f'<div title="{escape(technical, quote=True)}"><b>{escape(plain)}</b>'
            f'<div class="muted">{escape(technical)}</div></div>')


def _stage_what(stage):
    return STAGES.get(stage.get("key"), {}).get("what_happens", [stage["what"]])[0]


def _event_stage_key(words):
    lowered = words.lower()
    for prefix, key in _EVENT_STAGE_KEY.items():
        if lowered.startswith(prefix):
            return key
    if lowered.startswith("tests on main"):
        return "dashboard"
    if lowered.startswith("pull request #") and " merged" in lowered:
        return "merged_main"
    if lowered.startswith("pull request #") and " decided " in lowered:
        return "decision_made"
    if lowered.startswith("pull request #") and " opened" in lowered:
        return "decision_waiting"
    return None


def _event_words(event, stage_by_key):
    key = _event_stage_key(event["words"])
    if key is None or key not in STAGES:
        return escape(event["words"])
    technical = stage_by_key.get(key, {}).get("name", "technical stage")
    plain = STAGES[key]["plain_name"]
    return (f'<div title="{escape(technical, quote=True)}"><b>{escape(plain)}</b>'
            f'<div class="muted">{escape(event["words"])}</div></div>')


@st.fragment(run_every=PIPELINE_READ_EVERY_SECONDS)
def live_page():
    body, actions = common.layout("pipeline", "Live pipeline", "The pipeline from archive runs to approvals and dashboard, "
                                                                "with what is running now, what happens next, and proof links.")
    seen = common.read()
    now = common.now()
    workflow_texts = common.workflow_texts()
    stages = pipeline.stages(seen["workflows"], seen["runs"], seen["log"], seen["decision_prs"], workflow_texts, now)
    upcoming = pipeline.what_next(stages, now, hours=PIPELINE_LOOK_AHEAD_HOURS)
    running = [stage for stage in stages if stage["state"] == "running now"]
    feed = pipeline.proof_feed(seen["runs"], seen["log"], seen["decision_prs"], limit=PIPELINE_FEED_EVENTS)
    stage_by_key = {stage["key"]: stage for stage in stages}
    next_key, next_at = ((upcoming[0]["key"], upcoming[0]["at"]) if upcoming else (None, None))
    with body:
        for problem in seen["problems"]:
            st.html(console.notice(problem, "warn"))
        st.caption(f"Read from GitHub {seen['read_at']:%H:%M} UTC")
        component_html(live_pipeline_html(console.token_css(st.session_state.get("console_scheme", "auto")), console.FONT,
                                          pipeline_payload(stages, next_key, next_at, workflow_texts)),
                       height=1220, scrolling=True)

        left, right = st.columns(2)
        with left:
            st.html(console.section("Running now", console.list_view(
                ["Stage", "State", "Started"],
                [[_stage_cell(stage), console.status(_STATE_TONE[stage["state"]], _plain_state(stage["state"])),
                  escape(console.when(stage.get("running_start") or (stage["last"] or {}).get("start")))] for stage in running], numeric=())
                if running else console.notice("No stage is running now.", "info"), flush=bool(running)))
        with right:
            st.html(console.section("Next up", console.list_view(
                ["Stage", "When (UTC)", "What it does"],
                [[_stage_cell(next(stage for stage in stages if stage["key"] == item["key"])),
                  escape(console.when(item["at"])),
                  escape(_stage_what(next(stage for stage in stages if stage["key"] == item["key"])))]
                 for item in upcoming], numeric=())
                if upcoming else console.notice(f"No scheduled runs in the next {PIPELINE_LOOK_AHEAD_HOURS} hours.", "info"),
                right="soonest first", flush=bool(upcoming)))

        st.html(console.section("Proof of work", console.list_view(
            ["Time (UTC)", "Event", "Link"],
            [[escape(console.when(event["time"])), _event_words(event, stage_by_key),
              _link(event.get("link"), _proof_link_words(event))]
             for event in feed], numeric=()) if feed else console.notice("No proof events yet.", "info"),
            right=f"newest {PIPELINE_FEED_EVENTS}", flush=bool(feed)))
    with actions:
        common.refresh_action()
        st.html('<p class="c-actions-sub">Go to</p>')
        st.page_link("console/jobs.py", label="Jobs", icon=":material/schedule:")
        st.page_link("console/approvals.py", label="Approvals", icon=":material/task_alt:")


live_page()
