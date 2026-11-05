"""What the checks found (Overview): the health assessment's written findings for each satellite, read at a glance.

The findings say why each satellite scored as it did: inclination, drift, its slot, and its burn pattern, with
what is overdue or due next. They are grouped by outcome, worst first, with a count of each above; in a group, a
satellite's name sits beside its findings, one line each with its status icon. Every finding is kept as written,
without its status sign. Outcomes and their names are in ui/checks_settings.py.
"""
import re
from html import escape

from ui import icons, reveal, surfaces
from ui.checks_settings import OUTCOMES, SIGN_OUTCOME

EMOJI = re.compile(r"[℀-⏿①-➿\U0001F000-\U0001FAFF️]\s?")   # the remarks' status signs; the words stay


def findings(health_row):
    """One satellite's findings as (outcome, line): the outcome from the line's sign, the line without the signs."""
    found = []
    for part in str(health_row.get("Remarks", "")).split(" | "):
        line = EMOJI.sub("", part).strip()
        if line:
            found.append((SIGN_OUTCOME.get(part.strip()[:1], "idle"), line))
    return found


def by_outcome(health):
    """{outcome: {satellite: [line, ...]}} for every outcome, worst first; satellites in the order of `health`."""
    grouped = {outcome: {} for outcome in OUTCOMES}
    for h in health.to_dict("records"):
        for outcome, line in findings(h):
            grouped[outcome].setdefault(str(h["Satellite"]), []).append(line)
    return grouped


def _counts(grouped):
    return {outcome: sum(map(len, found.values())) for outcome, found in grouped.items()}


def summary(grouped, satellites):
    """The section's header line: '8 satellites · 40 findings · needs attention 1 · to watch 6'."""
    counts = _counts(grouped)
    look = [f"{OUTCOMES[o].lower()} {counts[o]}" for o in ("bad", "warn") if counts[o]]
    return " · ".join([reveal.count(satellites, "satellite"), reveal.count(sum(counts.values()), "finding"), *look])


def body(grouped):
    """A count per outcome, then each outcome's findings, worst first."""
    counts = _counts(grouped)
    html = "".join(surfaces.chip(f"{name} {counts[o]}", o) for o, name in OUTCOMES.items() if counts[o])
    html = f'<div class="ck-counts">{html}</div>'
    for outcome, found in grouped.items():
        if found:
            items = "".join(f"<li><b>{escape(name)}</b><span>"
                            + "".join(f"<span>{icons.tag(outcome)}<span>{escape(line)}</span></span>" for line in lines)
                            + "</span></li>" for name, lines in found.items())
            html += f'<h4 class="ck-title">{OUTCOMES[outcome]}</h4><ul class="ck-list">{items}</ul>'
    return html
