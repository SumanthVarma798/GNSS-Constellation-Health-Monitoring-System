"""Orbit record age strip and details section for one constellation."""
from datetime import datetime
from html import escape

from data import spacetrack
from evidence.settings import ORBIT_ALERT_DAYS, ORBIT_STALE_DAYS
from ui import data as dashboard_data
from ui import measures, reveal, surfaces, tooltip


def _age_words(row):
    return "no record" if row["age_days"] is None else f"{row['age_days']:.1f} days old"


def _when(epoch):
    return "not known" if epoch is None else f"{epoch.day} {epoch:%b %H:%M} UTC"


def _day_words(day):
    """'25 Oct' for a YYYY-MM-DD day, or None when it cannot be read."""
    if not isinstance(day, str):
        return None
    try:
        at = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError:
        return None
    return f"{at.day} {at:%b}"


def _gap_by_satellite(gap):
    """{satellite: (typical km, day words or None)} for every row with a measured gap."""
    if not isinstance(gap, dict):
        return {}
    day = _day_words(gap.get("day"))
    out = {}
    for row in gap.get("satellites", []):
        if not isinstance(row, dict):
            continue
        satellite, typical = row.get("satellite"), row.get("typical_km")
        # The file comes from outside the app: a number or nothing, never a crash.
        if satellite is not None and isinstance(typical, (int, float)) and not isinstance(typical, bool):
            out[str(satellite)] = (typical, day)
    return out


def _gap_cell(gap):
    return measures.cell("–") if gap is None else measures.cell(f"{gap[0]:.1f} km", note=gap[1] or "")


def _dot_card(row, gap=None):
    if row["epoch"] is None:
        return f"{row['satellite']} · no record"
    card = f"{row['satellite']} · {_age_words(row)} · {row['source']} · {_when(row['epoch'])}"
    if gap is not None:
        card += f" · off by {gap[0]:.1f} km" + (f" on {gap[1]}" if gap[1] else "")
    return card


def strip_html(rows, gap=None):
    """The dot strip with one tooltip per satellite."""
    gaps = _gap_by_satellite(gap or {})
    dots = ""
    for row in rows:
        trigger = f'<span class="oa-dot {row["status"]}" aria-hidden="true"></span><span class="oa-sr">{escape(row["satellite"])}</span>'
        dots += tooltip.tip_html(trigger, escape(_dot_card(row, gaps.get(row["satellite"]))), key=row["satellite"])
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


def section_markup(rows, spacetrack_note="ok", gap=None):
    """(summary, table html, stale notice text or None) for the orbit age section."""
    total = len(rows)
    under = sum(row["status"] == "ok" for row in rows)
    look = sum(row["status"] in ("warn", "bad", "idle") for row in rows)
    summary = f"{total} satellites · {under} under {ORBIT_ALERT_DAYS:g} days · {look} need a look"
    if spacetrack_note and spacetrack_note != "ok":
        summary += f" · Space-Track: {spacetrack_note}"
    gap_day = _day_words(gap.get("day")) if isinstance(gap, dict) else None
    summary += f" · broadcast check {gap_day}" if gap_day else " · broadcast check not available"

    gaps = _gap_by_satellite(gap or {})
    table_rows = []
    for row in rows:
        table_rows.append((row["satellite"], [
            measures.cell(_when(row["epoch"])),
            measures.cell("no record" if row["age_days"] is None else f"{row['age_days']:.1f} days", status=row["status"]),
            measures.cell(row["source"] or "-"),
            _gap_cell(gaps.get(row["satellite"])),
        ]))
    body = surfaces.table(
        [("Satellite", ""), ("Record from (date and time, UTC)", ""), ("Age", ""), ("Source", ""),
         ("Off from its broadcast orbit", "Typical gap over the day")],
        table_rows,
    )

    stale = [f'{row["satellite"]} since {_when(row["epoch"])}' for row in rows if row["status"] == "bad" and row["epoch"]]
    notice = f"Stale orbit records: {', '.join(stale)}." if stale else None
    return summary, body, notice


def show(constellation, result):
    """Draw stale warnings, the strip, and the details section."""
    rows = dashboard_data.orbit_ages(constellation, result)
    gap = dashboard_data.orbit_gap()
    own_note = dashboard_data.own_note()
    summary, body, stale_notice = section_markup(rows, own_note or spacetrack.state.get("note", "ok"), gap)
    if stale_notice:
        surfaces.show(surfaces.notice(stale_notice, "warn"))
    surfaces.show(strip_html(rows, gap))
    reveal.section(f"orbit_age_{constellation}", "Orbit record age and source", summary, body)
