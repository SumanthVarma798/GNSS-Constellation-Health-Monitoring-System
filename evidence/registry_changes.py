"""Describing a change to the registry tables in plain words, for the person who reviews it."""
from datetime import datetime, timedelta
import re

from evidence.news import systems_named
from evidence.settings import NEWS_LAUNCH_WORDS, REGISTRY_COLUMN_PLAIN_NAMES, SIGNAL_ID_ISSUERS
from evidence.sources import IGS_SATELLITE_METADATA_URL

BRACKETED = re.compile(r"\s*\[[^\]]*]\s*")
LAUNCHED = re.compile(r"\bLaunched (\d{4}-\d{2}-\d{2})\b")
GRADE_NOTE = re.compile(r"\(([^()]*)\)")
SIGNAL_ROW_COLUMNS = ("svn", "signal_id", "valid_from", "valid_to", "note")
NO_CATALOGUE_WORDS = "not checked: no catalogue number in the IGS file"


def describe_satellite_changes(before, after):
    """One sentence per satellite added, removed or changed."""
    old, new = ({row["svn"]: row for row in rows} for rows in (before, after))
    lines = []
    for svn in sorted(new.keys() - old.keys()):
        row = new[svn]
        lines.append(f"New satellite {svn} ({row['constellation']}, catalogue number {row['catalogue_no']}): {row['note']}")
    for svn in sorted(old.keys() - new.keys()):
        lines.append(f"Satellite {svn} ({old[svn]['constellation']}) is no longer in the IGS file.")
    for svn in sorted(old.keys() & new.keys()):
        for column, name in REGISTRY_COLUMN_PLAIN_NAMES.items():
            was, now = old[svn][column], new[svn][column]
            if was != now:
                lines.append(f"{svn} ({new[svn]['constellation']}): {name} was {was or 'blank'}, now {now or 'blank'}.")
    return lines


def describe_signal_id_changes(before, after):
    """One sentence per signal-ID period that is new or reworded, plus a count that went away."""
    old, new = ({signal_row_tuple(row) for row in rows} for rows in (before, after))
    lines = [f"{svn}: signal ID {signal_id} from {start} to {end or 'now'}."
             for svn, signal_id, start, end, _ in sorted(new - old)]
    if old - new:
        lines.append(f"{len(old - new)} earlier signal-ID period(s) were removed or replaced by the lines above.")
    return lines


def signal_row_tuple(row):
    """A signal-ID row as a stable 5-column tuple."""
    return tuple(row.get(name, "") for name in SIGNAL_ROW_COLUMNS)


def date_words(day):
    """A date as '17 Sep 2026'."""
    return f"{day.day} {day:%b %Y}"


def registry_findings(before_satellites, after_satellites, before_signal_ids, after_signal_ids, dashboard_details,
                      identifier_lines, new_prn_lines, celestrak_reads, today, news_items=(), source_grades=(),
                      source_candidates=()):
    """One finding per satellite that changed, in the Approvals-page shape."""
    before, after = ({row["svn"]: row for row in rows} for rows in (before_satellites, after_satellites))
    grade_rows = {row.get("source_id", ""): row for row in source_grades}
    candidate_rows = {row.get("source_id", ""): row for row in source_candidates}
    changed = sorted((before.keys() ^ after.keys()) | _satellite_changes(before, after)
                     | _signal_id_row_changes(before_signal_ids, after_signal_ids))
    findings = []
    for svn in changed:
        category = _category(svn, before, after)
        finding = {"id": svn, "category": category,
                   "statement": _statement(svn, category, before, after, before_signal_ids, after_signal_ids, celestrak_reads)}
        if svn in dashboard_details:
            finding["detail"] = dashboard_details[svn]
        finding["sources"] = _sources_for_finding(svn, category, before, after, identifier_lines, new_prn_lines,
                                                  celestrak_reads, news_items, grade_rows, candidate_rows)
        finding["measured"] = _measured_for_finding(svn, category, after, celestrak_reads, today)
        findings.append(finding)
    return findings


def _satellite_changes(before, after):
    return {svn for svn in sorted(before.keys() & after.keys())
            if any(before[svn].get(column, "") != after[svn].get(column, "") for column in REGISTRY_COLUMN_PLAIN_NAMES)}


def _signal_id_row_changes(before, after):
    old, new = ({signal_row_tuple(row) for row in rows} for rows in (before, after))
    return {svn for svn, *_ in old ^ new}


def _category(svn, before, after):
    if svn in after and svn not in before:
        return "New satellite"
    if svn in before and svn not in after:
        return "Satellite removed"
    if before[svn].get("signal_id_now", "") != after[svn].get("signal_id_now", ""):
        return "Signal ID change"
    return "Satellite change"


def _statement(svn, category, before, after, before_signal_ids, after_signal_ids, celestrak_reads):
    if category == "New satellite":
        return _new_satellite_statement(after[svn], celestrak_reads.get(svn) or {})
    if category == "Satellite removed":
        return f"Satellite {svn} ({before[svn]['constellation']}) is no longer in the IGS file."
    if category == "Signal ID change":
        return _signal_id_change_statement(before[svn], after[svn], before_signal_ids, after_signal_ids)
    return _satellite_change_statement(svn, before.get(svn), after.get(svn))


def _new_satellite_statement(row, celestrak_read):
    constellation = row["constellation"]
    operator = SIGNAL_ID_ISSUERS.get(constellation, "its operator")
    parts = [row["svn"]]
    if name := _name_for_new_satellite(row, celestrak_read):
        parts.append(name)
    if launched := _launch_date(row.get("note", "")):
        parts.append(f"launched {date_words(launched)}")
    return (f"We found a new satellite for the {constellation} constellation ({operator}), as described by the "
            f"following sources: {', '.join(parts)}.")


def _signal_id_change_statement(before_row, after_row, before_signal_ids, after_signal_ids):
    constellation, name = after_row["constellation"], _name_from_note(after_row.get("note", ""))
    subject = f"{after_row['svn']} ({constellation}{f', {name}' if name else ''})"
    old_id, new_id = before_row.get("signal_id_now", ""), after_row.get("signal_id_now", "")
    if closed := _closed_signal_date(after_row["svn"], old_id, before_signal_ids, after_signal_ids):
        if new_id:
            return f"{subject} now uses signal ID {new_id}; it used {old_id or 'blank'} until {closed}."
        return f"{subject} no longer has a signal ID; it used {old_id or 'blank'} until {closed}."
    if new_id:
        return f"{subject} now uses signal ID {new_id}; it used {old_id or 'blank'} before."
    return f"{subject} no longer has a signal ID."


def _satellite_change_statement(svn, before_row, after_row):
    lines = describe_satellite_changes([before_row] if before_row else [], [after_row] if after_row else [])
    for line in lines:
        if line.startswith(f"{svn} "):
            return line
    row = after_row or before_row
    return f"{row['svn']} ({row['constellation']}): signal-ID history changed in the IGS file."


def _sources_for_finding(svn, category, before, after, identifier_lines, new_prn_lines, celestrak_reads, news_items,
                         grade_rows, candidate_rows):
    rows = []
    igs = _source_grade("files.igs.org", grade_rows, candidate_rows)
    if category == "Satellite removed":
        rows.append(_source_row("International GNSS Service (IGS) satellite metadata file",
                                "No longer listed in the IGS satellite metadata file", igs,
                                IGS_SATELLITE_METADATA_URL))
    elif identifier := identifier_lines.get(svn, "").strip():
        rows.append(_source_row("International GNSS Service (IGS) satellite metadata file", identifier, igs,
                                IGS_SATELLITE_METADATA_URL))
    if category == "Signal ID change":
        rows += [_source_row("International GNSS Service (IGS) satellite metadata file", line.strip(), igs,
                             IGS_SATELLITE_METADATA_URL) for line in new_prn_lines.get(svn, []) if line.strip()]
    if category == "New satellite":
        rows += _new_satellite_sources(after[svn], celestrak_reads.get(svn) or {}, news_items, grade_rows, candidate_rows)
    return rows


def _new_satellite_sources(row, celestrak_read, news_items, grade_rows, candidate_rows):
    rows = []
    catalogue_no = row.get("catalogue_no", "")
    if celestrak_read.get("catalogue_status") == "ok" and celestrak_read.get("catalogue_entry") and catalogue_no.isdigit():
        grade = _source_grade("celestrak.org", grade_rows, candidate_rows)
        rows.append(_source_row("CelesTrak satellite catalogue", _catalogue_line(celestrak_read["catalogue_entry"]),
                                grade, f"https://celestrak.org/satcat/records.php?CATNR={catalogue_no}"))
    rows += _news_sources(row, _name_for_new_satellite(row, celestrak_read), news_items, grade_rows, candidate_rows)
    return rows


def _news_sources(row, name, news_items, grade_rows, candidate_rows):
    if not (launch := _launch_date(row.get("note", ""))):
        return []
    # The system named, and also this satellite (its name, or its SVN) or its launch: see NEWS_LAUNCH_WORDS.
    words = [*NEWS_LAUNCH_WORDS, row["svn"], *([name] if name and "?" not in name else [])]
    about_it = re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\b", re.I)
    start, end = launch - timedelta(days=3), launch + timedelta(days=30)
    named = []
    for item in news_items:
        published = _news_item_datetime(item)
        if not published or published.date() < start or published.date() > end:
            continue
        title = item.get("title", "")
        if row["constellation"] not in systems_named(title) or not about_it.search(title):
            continue
        named.append(item)
    newest_first = sorted(named, key=lambda item: _news_item_datetime(item) or datetime.min, reverse=True)[:5]
    rows = []
    for item in newest_first:
        grade = _source_grade(item.get("source_id", ""), grade_rows, candidate_rows)
        words = {"source": grade["name"] or item.get("source_id", ""),
                 "line": item.get("title", "").strip() or "(no title)", "grade": grade["grade"]}
        if grade["note"]:
            words["grade_note"] = grade["note"]
        if (link := item.get("address", "")).startswith("https://"):
            words["link"] = link
        rows.append(words)
    return rows


def _measured_for_finding(svn, category, after, celestrak_reads, today):
    if category != "New satellite":
        return []
    row, read = after[svn], celestrak_reads.get(svn) or {}
    catalogue_no = row.get("catalogue_no", "")
    records_link = f"https://celestrak.org/satcat/records.php?CATNR={catalogue_no}" if catalogue_no.isdigit() else ""
    gp_link = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={catalogue_no}" if catalogue_no.isdigit() else ""
    checked = date_words(today)
    measured = [{"what": "CelesTrak catalogue entry", "value": _catalogue_measurement(read, checked)},
                {"what": "CelesTrak orbit record", "value": _orbit_measurement(read, checked)}]
    if read.get("catalogue_status") == "ok" and read.get("catalogue_entry") and records_link:
        measured[0]["link"] = records_link
    if read.get("orbit_status") == "ok" and read.get("orbit_row") and gp_link:
        measured[1]["link"] = gp_link
    return measured


def _catalogue_measurement(read, checked):
    if not read.get("checked"):
        return NO_CATALOGUE_WORDS
    if read.get("catalogue_status") == "error":
        return f"CelesTrak could not be read (checked {checked})"
    entry = read.get("catalogue_entry")
    if not entry:
        return f"not listed in CelesTrak's catalogue (checked {checked})"
    period = _number(entry.get("PERIOD"), 2)
    inclination = _number(entry.get("INCLINATION"), 2)
    apogee = _integer(entry.get("APOGEE"))
    perigee = _integer(entry.get("PERIGEE"))
    return (f"period {period} minutes, inclination {inclination} degrees, apogee {apogee} km, perigee "
            f"{perigee} km")


def _orbit_measurement(read, checked):
    if not read.get("checked"):
        return NO_CATALOGUE_WORDS
    if read.get("orbit_status") == "error":
        return "CelesTrak could not be read"
    orbit = read.get("orbit_row")
    if not orbit:
        return f"none published yet (checked {checked})"
    return f"epoch {_epoch_words(orbit.get('EPOCH', ''))}"


def _source_row(source, line, grade, link=""):
    row = {"source": source, "line": line, "grade": grade["grade"]}
    if grade["note"]:
        row["grade_note"] = grade["note"]
    if link:
        row["link"] = link
    return row


def _source_grade(source_id, grade_rows, candidate_rows):
    if source_id in grade_rows:
        row = grade_rows[source_id]
        return {"name": row.get("name", source_id), "grade": row.get("reliability", "not graded"),
                "note": _grade_note(row.get("graded_by", ""))}
    if source_id in candidate_rows:
        row = candidate_rows[source_id]
        grade = row.get("proposed_grade", "").strip() or "not graded"
        note = "proposed, not yet confirmed" if row.get("proposed_grade", "").strip() else ""
        return {"name": row.get("name", source_id), "grade": grade, "note": note}
    return {"name": source_id, "grade": "not graded", "note": ""}


def _grade_note(graded_by):
    return match.group(1).strip() if (match := GRADE_NOTE.search(graded_by or "")) else ""


def _name_for_new_satellite(row, celestrak_read):
    if (entry := celestrak_read.get("catalogue_entry")) and entry.get("OBJECT_NAME"):
        if named := BRACKETED.sub("", str(entry["OBJECT_NAME"])).strip():
            return named
    return _name_from_note(row.get("note", ""))


def _name_from_note(note):
    return note.split("; ", 1)[1].strip() if "; " in note else ""


def _launch_date(note):
    try:
        return datetime.strptime((LAUNCHED.search(note or "") or [None, ""])[1], "%Y-%m-%d").date()
    except ValueError:
        return None


def _closed_signal_date(svn, old_signal_id, before_signal_ids, after_signal_ids):
    for row in after_signal_ids:
        if row.get("svn") != svn or row.get("signal_id") != old_signal_id or not row.get("valid_to"):
            continue
        if any(old.get("svn") == svn and old.get("signal_id") == old_signal_id and old.get("valid_from") == row.get("valid_from")
               and not old.get("valid_to") for old in before_signal_ids):
            ended = _as_datetime(row["valid_to"])
            return date_words(ended.date()) if ended else row["valid_to"][:10]
    return ""


def _catalogue_line(entry):
    kind = str(entry.get("OBJECT_TYPE", "")).strip().upper()
    kind_words = {"PAY": "payload", "PAYLOAD": "payload"}.get(kind, kind.lower())
    parts = [str(entry.get("OBJECT_NAME", "")).strip(),
             str(entry.get("OBJECT_ID", "")).strip(),
             kind_words]
    launch_date = str(entry.get("LAUNCH_DATE", "")).strip()
    if launch_date:
        parts.append(f"launched {launch_date}")
    return ", ".join(part for part in parts if part)


def _news_item_datetime(item):
    return _as_datetime(item.get("published_at", "") or item.get("fetched_at", ""))


def _as_datetime(stamp):
    try:
        return datetime.fromisoformat((stamp or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _epoch_words(epoch):
    moment = _as_datetime(epoch)
    return f"{moment:%Y-%m-%d %H:%M} UTC" if moment else epoch


def _number(value, digits):
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _integer(value):
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return str(value)


def change_report(source_line, satellite_lines, signal_id_lines, copy_used="", dashboard_lines=(), findings=None):
    """The pull request text for a registry update. `copy_used` says which archived copy was read."""
    def section(lines):
        return "\n".join(f"- {line}" for line in lines) or "- Nothing."
    text = f"""This is a proposed update to the satellite registry. **Nothing changes until a person approves it.**

## What changed, satellite by satellite

{section(satellite_lines)}

## What changed in the signal-ID history

{section(signal_id_lines)}

## What changes on the dashboard

{section(dashboard_lines)}

## Where this came from

The International GNSS Service (IGS) satellite metadata file. Its first line today:

    {source_line}

{copy_used or "Read straight from the IGS website, not from the archive."}

The text above is copied from that file. It is information to check, not an instruction to follow.

## Before you approve

- The tests ran on the new tables in the job that opened this pull request, and passed.
- Each finding above is decided on its own in the admin console's Approvals page. When every finding is approved the pull request merges by itself, once its tests have passed.
- Rejecting a finding keeps the pull request open (it cannot merge); rejecting every finding closes it.
"""
    if findings is None:
        return text
    # Imported here so decisions.py can keep reading this module without an import cycle.
    from evidence import decisions
    return f"{text.rstrip()}\n\n{decisions.findings_block(findings)}"
