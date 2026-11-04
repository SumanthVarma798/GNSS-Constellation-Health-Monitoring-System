"""Alerts: green streak, Healthchecks.io status, and failed runs from GitHub."""
import math
from html import escape

import requests
import streamlit as st

from console import common
from evidence import alerts
from evidence.alert_settings import (
    CHECKS,
    DEMO_SHARE,
    FLIPS_DAYS,
    READ_EVERY_SECONDS,
    SECRETS_SECTION,
    STREAK_FULL_HOURS,
    STREAK_GOAL_HOURS,
)
from evidence.console_settings import RELIABILITY_DAYS
from ui import console

def _link(url, words):
    if not url:
        return '<span class="muted">none</span>'
    safe_url = escape(url, quote=True)
    return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{escape(words)}</a>'


def _streak_hours_words(hours):
    whole = max(0, int(hours))
    if whole >= STREAK_GOAL_HOURS:
        days, rest = divmod(whole, 24)
        return f"{days} d {rest} h"
    return f"{whole} h"


def _alerts_key():
    try:
        return str(st.secrets.get(SECRETS_SECTION, {}).get("key") or "").strip()
    except FileNotFoundError:
        return ""


@st.cache_data(ttl=READ_EVERY_SECONDS, show_spinner="Reading Healthchecks.io…")
def _healthchecks(key):
    checks = alerts.read_checks(key)
    if not isinstance(checks, list):
        raise TypeError("Healthchecks checks is not a list")
    seconds = FLIPS_DAYS * 86400
    flips_by_slug = {}
    for check in checks:
        if not isinstance(check, dict):
            raise TypeError("Healthchecks check is not an object")
        unique_key = check.get("unique_key")
        if unique_key:
            slug = check.get("slug") or check.get("name") or "unnamed"
            flips = alerts.read_flips(key, unique_key, seconds)
            if not isinstance(flips, list):
                raise TypeError("Healthchecks flips is not a list")
            flips_by_slug[slug] = flips
    return checks, flips_by_slug


def _checks_table(rows):
    return console.list_view(
        ["Check", "Job", "Status", "Last report (UTC)", "Next expected (UTC)", f"Down, last {FLIPS_DAYS} days"],
        [
            [
                escape(row["slug"]),
                escape(row["job"]),
                console.status(row["tone"], row["words"]),
                escape(console.when(row["last_report"])),
                escape(console.when(row["next_expected"])),
                str(row["down_times"]),
            ]
            for row in rows
        ],
        numeric=(f"Down, last {FLIPS_DAYS} days",),
    )


seen = common.read()
now = common.now()
streak = alerts.green_streak(seen["runs"], now)

body, actions = common.layout(
    "alerts",
    "Alerts",
    "Green streak, Healthchecks.io checks, and failed scheduled runs. Times in UTC.",
)

with body:
    for problem in seen["problems"]:
        st.html(console.notice(problem, "warn"))

    goal_met = streak["hours"] >= STREAK_GOAL_HOURS
    tone = "ok" if goal_met else "warn"
    left = max(0, math.ceil(STREAK_GOAL_HOURS - streak["hours"]))
    meter_words = f"{int(streak['hours'])} of {STREAK_FULL_HOURS} hours"
    goal_words = (
        f"Goal: {STREAK_GOAL_HOURS} h green before the demo is shared {DEMO_SHARE} (met); "
        "7 days for the full bar."
        if goal_met
        else f"Goal: {STREAK_GOAL_HOURS} h green before the demo is shared {DEMO_SHARE} (not yet: {left} h to go); "
        "7 days for the full bar."
    )
    broke = ""
    if streak["broke_on"] and streak["since"]:
        broke = (
            f"<p>Since {escape(console.when(streak['since']))} UTC, the last failed scheduled run: "
            f"{escape(alerts.job_name(streak['broke_on']))} ({_link(streak['broke_on'].get('html_url'), 'link')}).</p>"
        )
    green = (
        console.hero(_streak_hours_words(streak["hours"]), "green, at least" if streak["at_least"] else "green", tone)
        + f"<p>{console.status(tone, 'Goal met' if goal_met else 'Not yet')}</p>"
        + console.meter(streak["hours"] / STREAK_FULL_HOURS, tone, meter_words)
        + f"<p class='muted'>{escape(meter_words)}</p>"
        + f"<p>{escape(goal_words)}</p>"
        + broke
        + "<p>Only scheduled runs count; runs started by hand, such as failure drills, do not.</p>"
    )
    st.html(console.section("Green streak", green))

    key = _alerts_key()
    if not key:
        st.html(
            console.notice(
                "No Healthchecks.io key is set, so the checks cannot be read. To add one: on healthchecks.io open the project, "
                "then Settings, API Access, and create a read-only API key. Put it in the console's secrets as [alerts] key = "
                "\"...\": on Render in the console's secret file secrets.toml; on a computer in .streamlit/secrets.toml. "
                "Healthchecks.io still emails on failures without it.",
                "info",
            )
        )
        keyless_rows = [
            {
                "slug": slug,
                "job": job,
                "tone": "idle",
                "words": "Unknown: no key",
                "last_report": None,
                "next_expected": None,
                "down_times": 0,
            }
            for slug, job in CHECKS
        ]
        checks_body = _checks_table(keyless_rows)
    else:
        try:
            checks, flips_by_slug = _healthchecks(key)
            rows = alerts.check_rows(checks, flips_by_slug)
            checks_body = _checks_table(rows)
            missing = alerts.missing_slugs(checks)
            if missing:
                st.html(
                    console.notice(
                        "No check on Healthchecks.io for: "
                        + ", ".join(missing)
                        + ". Their reports are lost until a check with that slug is made.",
                        "bad",
                    )
                )
        except (requests.RequestException, KeyError, TypeError, ValueError) as error:
            st.html(console.notice(alerts.trouble(error), "bad"))
            checks_body = console.notice("Checks are not available right now.", "warn")

    st.html(console.section("Healthchecks.io checks", checks_body, right="emails when a run fails or is late", flush=True))

    failed = alerts.failed_runs(seen["runs"])[:15]
    if failed:
        failed_body = console.list_view(
            ["When (UTC)", "Job", "How it ended", "Started", "Link"],
            [
                [
                    escape(console.when(row["when"])),
                    escape(row["job"]),
                    console.status("bad", row["words"]),
                    escape(row["started"]),
                    _link(row["html_url"], "Open"),
                ]
                for row in failed
            ],
        )
    else:
        failed_body = console.notice("No failed runs in GitHub's recent record.", "ok")
    st.html(console.section("Failed runs on GitHub", failed_body, right=f"last {RELIABILITY_DAYS} days", flush=bool(failed)))

with actions:
    common.refresh_action()
    st.link_button("Healthchecks.io", "https://healthchecks.io/", icon=":material/open_in_new:")
