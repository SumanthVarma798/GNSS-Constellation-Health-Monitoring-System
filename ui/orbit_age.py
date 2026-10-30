"""Orbit record age tags and details section for one constellation."""
from datetime import datetime
from html import escape

from data import spacetrack
from evidence.settings import ORBIT_ALERT_DAYS, ORBIT_STALE_DAYS, QZSS_HEALTH_BITS, TIME_CORRECTION_WORDS
from ui import data as dashboard_data
from ui import measures, reveal, surfaces, tooltip


def _tag_words(row):
    return "no orbit record" if row["age_days"] is None else f"orbit {row['age_days']:.1f} days old"


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


def _status_by_satellite(gap):
    """{satellite: the gap row with broadcast status} for every row in the published payload."""
    if not isinstance(gap, dict):
        return {}
    out = {}
    for row in gap.get("satellites", []):
        if not isinstance(row, dict):
            continue
        satellite = row.get("satellite")
        if satellite is not None:
            out[str(satellite)] = row
    return out


def _qzss_health_words(health):
    """QZSS's six health bits, one signal each; a set bit means that signal must not be used."""
    if health & 32:
        # The L1 signal being sent is unusable and the other one of the pair is not sent, so neither counts.
        usable = [QZSS_HEALTH_BITS[bit] for bit in (8, 4, 2) if not health & bit]
        if not usable:
            return f"unhealthy (code {health}): no signal usable", "bad"
        return f"unhealthy (code {health}): only {', '.join(usable)} usable", "bad"

    sends_a, sends_b = health & 16, health & 1
    if bool(sends_a) != bool(sends_b) and health & ~(16 | 1) == 0:
        return f"healthy (sends {'L1C/B' if sends_a else 'L1C/A'})", "ok"

    off = []
    for bit in (16, 8, 4, 2, 1):
        if health & bit:
            # A single L1C/A or L1C/B bit just says which of the pair is being sent, not a fault.
            if bit == 16 and sends_a and not sends_b:
                continue
            if bit == 1 and sends_b and not sends_a:
                continue
            off.append(QZSS_HEALTH_BITS[bit])
    return f"{', '.join(off)} off (code {health})", "warn"


def health_words(status):
    """(words, status) for one satellite's broadcast health; "unhealthy" only where a non-zero code means it."""
    health = (status or {}).get("health")
    if health is None:
        missing = (status or {}).get("note") == "not in the day's broadcast file"
        return ("not in the day's file", "idle") if missing else ("-", "idle")
    if health == 0:
        return "healthy", "ok"
    signal_id = (status or {}).get("signal_id") or ""
    if signal_id[:1] == "J" and isinstance(health, int) and not isinstance(health, bool):
        return _qzss_health_words(health)
    return f"unhealthy (code {health})", "bad"


def _broadcast_cell(status):
    """The broadcast health cell for one satellite."""
    words, colour = health_words(status)
    return measures.cell(words) if words == "-" else measures.cell(words, status=colour)


def _accuracy_cell(status):
    """The signal accuracy cell for one satellite."""
    if not status:
        return measures.cell("-")
    accuracy = status.get("accuracy_m")
    if isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool):
        return measures.cell(f"{accuracy:.1f} m")
    return measures.cell("-")


def _broadcast_words(status):
    """One tooltip line for a satellite's broadcast health and accuracy."""
    if not status:
        return ""
    words, _ = health_words(status)
    line = f"Broadcast health: {'unknown' if words == '-' else words}"
    accuracy = status.get("accuracy_m")
    if isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool):
        line += f" · accuracy {accuracy:.1f} m"
    return line


def _satellite_label(name, status):
    """'GSAT0202 (E14)' for a satellite name and its published gap row."""
    signal_id = status.get("signal_id")
    return f"{name} ({signal_id})" if signal_id else name


def _unhealthy_notice(gap, rows):
    """The warning shown when any satellite of this constellation broadcasts unhealthy, or None."""
    if not isinstance(gap, dict):
        return None
    statuses = _status_by_satellite(gap)
    names = [_satellite_label(row["satellite"], statuses[row["satellite"]])
             for row in rows if health_words(statuses.get(row["satellite"]))[1] == "bad"]
    if not names:
        return None
    day = _day_words(gap.get("day"))
    file_words = f" of {day}" if day else ""
    return (f"Broadcasting unhealthy: {', '.join(names)}. "
            f"From the IGS broadcast file{file_words}; work in progress, not yet part of the score.")


def _missing_notice(gap, rows):
    """The idle notice shown when any satellite of this constellation is absent from the day's file."""
    if not isinstance(gap, dict):
        return None
    statuses = _status_by_satellite(gap)
    names = [_satellite_label(row["satellite"], statuses[row["satellite"]])
             for row in rows if (status := statuses.get(row["satellite"]))
             and status.get("health") is None and status.get("note") == "not in the day's broadcast file"]
    if not names:
        return None
    return f"Not in the day's broadcast file: {', '.join(names)}."


def _system_times_html(gap):
    """The system-time line under the table, or None when the old payload has no time corrections."""
    if not isinstance(gap, dict):
        return None
    corrections = gap.get("time_corrections")
    if not isinstance(corrections, dict) or not corrections:
        return None
    parts = []
    for code, words in TIME_CORRECTION_WORDS.items():
        if code in corrections and isinstance(corrections[code], (int, float)):
            parts.append(f"{words} {corrections[code]:.2f} ns")
    if not parts:
        return None
    line = "System times from the broadcast file: " + " · ".join(parts)
    leap = gap.get("leap_seconds")
    if leap is not None:
        line += f" · {leap} leap seconds"
    return line


def _gap_cell(gap):
    return measures.cell("–") if gap is None else measures.cell(f"{gap[0]:.1f} km", note=gap[1] or "")


def _tag_card(row, gap=None, status=None):
    """The tooltip card's words for one satellite, with the source, any published gap, and the age limits."""
    if row["epoch"] is None:
        card = "No orbit record"
        broadcast = _broadcast_words(status)
        return card + (f" · {broadcast}" if broadcast else "")
    card = f"Orbit record from {_when(row['epoch'])}, {row['source']}"
    if gap is not None:
        card += f" · off by {gap[0]:.1f} km" + (f" on {gap[1]}" if gap[1] else "")
    card += f" · alert at {ORBIT_ALERT_DAYS:g} days, stale at {ORBIT_STALE_DAYS:g}"
    broadcast = _broadcast_words(status)
    if broadcast:
        card += f" · {broadcast}"
    return card


def tag(row, gap=None, scope="", status=None):
    """One satellite's orbit-record age as a chip in the tile's tag row, opening its tooltip card. scope (the
    constellation) keeps each card's id unique where tiles of several constellations share a page (Compare)."""
    trigger = surfaces.chip(_tag_words(row), row["status"])
    return tooltip.tip_html(trigger, escape(_tag_card(row, gap, status)), key=f"{scope}:{row['satellite']}")


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
    statuses = _status_by_satellite(gap or {})
    table_rows = []
    for row in rows:
        table_rows.append((row["satellite"], [
            measures.cell(_when(row["epoch"])),
            measures.cell("no record" if row["age_days"] is None else f"{row['age_days']:.1f} days", status=row["status"]),
            measures.cell(row["source"] or "-"),
            _broadcast_cell(statuses.get(row["satellite"])),
            _accuracy_cell(statuses.get(row["satellite"])),
            _gap_cell(gaps.get(row["satellite"])),
        ]))
    body = surfaces.table(
        [("Satellite", ""), ("Record from (date and time, UTC)", ""), ("Age", ""), ("Source", ""),
         ("Broadcast health", ""), ("Signal accuracy", ""),
         ("Off from its broadcast orbit", "Typical gap over the day")],
        table_rows,
    )
    system_times = _system_times_html(gap)
    if system_times:
        body += f'<p class="small">{system_times}</p>'

    stale = [f'{row["satellite"]} since {_when(row["epoch"])}' for row in rows if row["status"] == "bad" and row["epoch"]]
    notice = f"Stale orbit records: {', '.join(stale)}." if stale else None
    return summary, body, notice


def tags(constellation, result):
    """{satellite name: orbit-age tag html} for one constellation's tiles."""
    rows = dashboard_data.orbit_ages(constellation, result)
    gap = dashboard_data.orbit_gap() or {}
    gaps = _gap_by_satellite(gap)
    statuses = _status_by_satellite(gap)
    return {row["satellite"]: tag(row, gaps.get(row["satellite"]), constellation, statuses.get(row["satellite"]))
            for row in rows}


def show(constellation, result):
    """Draw stale warnings and the details section; the tiles carry the orbit-age tags."""
    rows = dashboard_data.orbit_ages(constellation, result)
    gap = dashboard_data.orbit_gap()
    own_note = dashboard_data.own_note()
    summary, body, stale_notice = section_markup(rows, own_note or spacetrack.state.get("note", "ok"), gap)
    if stale_notice:
        surfaces.show(surfaces.notice(stale_notice, "warn"))
    unhealthy = _unhealthy_notice(gap, rows)
    if unhealthy:
        surfaces.show(surfaces.notice(unhealthy, "warn"))
    missing = _missing_notice(gap, rows)
    if missing:
        surfaces.show(surfaces.notice(missing, "idle"))
    reveal.section(f"orbit_age_{constellation}", "Orbit record age and source", summary, body)
