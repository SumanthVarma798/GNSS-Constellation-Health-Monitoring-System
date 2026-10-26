"""Orbit record age strip and details section for one constellation."""
from html import escape

from data import spacetrack
from evidence.settings import ORBIT_ALERT_DAYS, ORBIT_STALE_DAYS
from ui import data as dashboard_data
from ui import measures, reveal, surfaces, tooltip


def _age_words(row):
    return "no record" if row["age_days"] is None else f"{row['age_days']:.1f} days old"


def _when(epoch):
    return "not known" if epoch is None else f"{epoch.day} {epoch:%b %H:%M} UTC"


def _dot_card(row):
    if row["epoch"] is None:
        return f"{row['satellite']} · no record"
    return f"{row['satellite']} · {_age_words(row)} · {row['source']} · {_when(row['epoch'])}"


def strip_html(rows):
    """The dot strip with one tooltip per satellite."""
    dots = ""
    for row in rows:
        trigger = f'<span class="oa-dot {row["status"]}" aria-hidden="true"></span><span class="oa-sr">{escape(row["satellite"])}</span>'
        dots += tooltip.tip_html(trigger, escape(_dot_card(row)), key=row["satellite"])
    legend = tooltip.legend(
        [
            ("var(--ok)", f"under {ORBIT_ALERT_DAYS:g} days"),
            ("var(--warn)", f"{ORBIT_ALERT_DAYS:g} days or more: alert"),
            ("var(--bad)", f"{ORBIT_STALE_DAYS:g} days or more: stale"),
            ("var(--idle)", "no record"),
        ],
        label="Legend",
    )
    return (f'<div class="oa-strip"><span class="oa-label">Orbit record age</span><span class="oa-dots">{dots}</span>'
            f'<span class="oa-legend">{legend}</span></div>')


def section_markup(rows, spacetrack_note="ok"):
    """(summary, table html, stale notice text or None) for the orbit age section."""
    total = len(rows)
    under = sum(row["status"] == "ok" for row in rows)
    look = sum(row["status"] in ("warn", "bad", "idle") for row in rows)
    summary = f"{total} satellites · {under} under {ORBIT_ALERT_DAYS:g} days · {look} need a look"
    if spacetrack_note and spacetrack_note != "ok":
        summary += f" · Space-Track: {spacetrack_note}"

    table_rows = []
    for row in rows:
        table_rows.append((row["satellite"], [
            measures.cell(_when(row["epoch"])),
            measures.cell("no record" if row["age_days"] is None else f"{row['age_days']:.1f} days", status=row["status"]),
            measures.cell(row["source"] or "-"),
        ]))
    body = surfaces.table(
        [("Satellite", ""), ("Record from (date and time, UTC)", ""), ("Age", ""), ("Source", "")],
        table_rows,
    )

    stale = [f'{row["satellite"]} since {_when(row["epoch"])}' for row in rows if row["status"] == "bad" and row["epoch"]]
    notice = f"Stale orbit records: {', '.join(stale)}." if stale else None
    return summary, body, notice


def show(constellation, result):
    """Draw stale warnings, the strip, and the details section."""
    rows = dashboard_data.orbit_ages(constellation, result)
    summary, body, stale_notice = section_markup(rows, spacetrack.state.get("note", "ok"))
    if stale_notice:
        surfaces.show(surfaces.notice(stale_notice, "warn"))
    surfaces.show(strip_html(rows))
    reveal.section(f"orbit_age_{constellation}", "Orbit record age and source", summary, body)
