"""Each satellite's life as steps on a timeline: what happened when, from which source, and how far along it is.

Every satellite in the registry gets its launch, signal-ID periods and end of regular operations from the registry
tables (registry_events); rows from registry/lifecycle_events.csv (kept by hand) replace those step by step and add
the detail: burns, sources, pictures. The steps and design lives are in evidence/library_settings.py. Times stay
ISO 8601 text in UTC; the page places them. No clock here: the caller passes today.
"""
import re
from datetime import datetime
from urllib.parse import quote

from evidence.library_settings import (COMMONS_LARGE, COMMONS_PAGE, COMMONS_PICTURE, DAYS_PER_YEAR, DESIGN_LIFE_YEARS,
                                       END_STEP, FAILED, LIFECYCLE_SERIES, LIFECYCLE_STEPS, NOTE_STEP, REGISTRY_STEPS,
                                       SERIES_SYSTEM, SERVICE_STEP, SYSTEM_ORDER)
from evidence.settings import GCAT_CITATION
from evidence.sources import IGS_SATELLITE_METADATA_URL

IGS = {"name": "International GNSS Service (IGS) satellite metadata file", "link": IGS_SATELLITE_METADATA_URL}
GCAT = {"name": GCAT_CITATION, "link": "https://planet4589.org/space/gcat/"}
LAUNCHED = re.compile(r"\bLaunched (\d{4}-\d{2}-\d{2})\b")
GCAT_DATE = re.compile(r"^(\d{4}) ([A-Z][a-z]{2})(?: +(\d{1,2}))?$")   # "2025 Jul 10", "2023 Feb"; "?" means unsure: unused

DONE, IMPLIED, FAILED_STATE, MISSED, AHEAD = "done", "done, date not published", "failed", "not reached", "ahead"


def _time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None


def _picture(name, credit):
    if not name:
        return None
    file = quote(name.replace(" ", "_"))
    return {"src": COMMONS_PICTURE.format(name=file), "large": COMMONS_LARGE.format(name=file),
            "page": COMMONS_PAGE.format(name=file), "credit": credit}


def _event(row):
    return {"step": row["step"], "title": row["title"], "from": row["from_utc"], "at": row["at_utc"], "when": row["when"],
            "evidence": row["evidence"], "failed": row["result"] == FAILED, "detail": row["detail"],
            "picture": _picture(row["picture"], row["picture_credit"]),
            "source": {"name": row["source_name"], "link": row["source_link"]}}


def checklist(steps, events):
    """One entry per step: its state, and for the service step how much of the design life is used (0 to 1)."""
    dated = {e["step"] for e in events if e["at"] and not e["failed"]}
    failed_at = next((i for i, (step, _) in enumerate(steps) if any(e["step"] == step and e["failed"] for e in events)), None)
    # The furthest step known to have been reached, or tried: every step before it happened, dated or not.
    last_dated = max([i for i, (step, _) in enumerate(steps) if step in dated] + [failed_at if failed_at is not None else -1])
    out = []
    for i, (step, title) in enumerate(steps):
        if failed_at is not None and i >= failed_at:
            state = FAILED_STATE if i == failed_at else MISSED
        elif step in dated:
            state = DONE
        elif i < last_dated:
            state = IMPLIED          # a later step happened, so this one did too
        else:
            state = AHEAD
        out.append({"step": step, "title": title, "state": state})
    return out


def life_used(series, events, today):
    """Share of the design life spent in service so far (capped at 1), or None if service has not started."""
    start = next((_time(e["at"]) for e in events if e["step"] == SERVICE_STEP and e["at"]), None)
    if not start or series not in DESIGN_LIFE_YEARS:
        return None
    end = next((_time(e["at"]) for e in events if e["step"] == END_STEP and e["at"]), None) or today
    return min(1.0, (end - start).days / DAYS_PER_YEAR / DESIGN_LIFE_YEARS[series])


def _made(step, title, at, when, evidence, detail, source, failed=False):
    return {"step": step, "title": title, "from": "", "at": at, "when": when, "evidence": evidence, "failed": failed,
            "detail": detail, "picture": None, "source": source}


def _gcat_date(text):
    """('2025-07-10T00:00:00Z', 'on') or ('2023-02-01T00:00:00Z', 'in') from GCAT's date text; None when unsure."""
    found = GCAT_DATE.match((text or "").strip())
    if not found:
        return None
    year, month, day = found.groups()
    at = datetime.strptime(f"{year} {month} {day or 1}", "%Y %b %d")
    return f"{at:%Y-%m-%d}T00:00:00Z", "on" if day else "in"


def _when(iso):
    return "on" if iso.endswith("T00:00:00Z") else "at"


def registry_events(satellite, periods, catalogue_row):
    """A satellite's events from the registry tables: launch, signal IDs, and the end of regular operations."""
    events = []
    if launched := LAUNCHED.search(satellite["note"]):
        events.append(_made("launch", "Launch", f"{launched[1]}T00:00:00Z", "on", "IGS file",
                            "The launch date the IGS satellite metadata file gives.", IGS))
    periods = sorted(periods, key=lambda row: row["valid_from"])
    for i, period in enumerate(periods):
        signal_id, start = period["signal_id"], period["valid_from"]
        if i == 0:
            events.append(_made(SERVICE_STEP, f"Signal ID {signal_id} assigned", start, _when(start), "IGS file",
                                f"The IGS file assigns it signal ID {signal_id} from this time. An assignment is not "
                                "proof it was broadcasting.", IGS))
        else:
            again = signal_id == periods[i - 1]["signal_id"]
            events.append(_made(NOTE_STEP, f"Signal ID {signal_id}{' again' if again else ''}", start, _when(start),
                                "IGS file", f"The IGS file assigns it signal ID {signal_id} from this time.", IGS))
    ended = periods[-1]["valid_to"] if periods and periods[-1]["valid_to"] else ""
    row = catalogue_row or {}
    gcat_end = _gcat_date(row.get("operations_ended", ""))
    if row.get("mission_result") == "F":
        at, when = gcat_end or ("", "")
        events.append(_made(END_STEP, "Failed early", at, when, "catalogue",
                            "GCAT records the mission as failed early.", GCAT, failed=True))
    elif gcat_end:
        events.append(_made(END_STEP, "Regular operations ended", *gcat_end, "catalogue",
                            "The date GCAT gives for the end of regular operations.", GCAT))
    if ended:
        withdrawn = _made(NOTE_STEP, f"Signal ID {periods[-1]['signal_id']} withdrawn", ended, _when(ended), "IGS file",
                          "The IGS file ends its last signal-ID period here and gives it no other.", IGS)
        if not any(e["step"] == END_STEP for e in events):
            withdrawn.update(step=END_STEP, title="Signal ID withdrawn")
        events.append(withdrawn)
    return events


def _registry_records(registry):
    """{name: (svn, system, series, events)} for every registry satellite with a launch date, named as the dashboard
    names it, else as the IGS note does, else as GCAT does."""
    tracked = {row["svn"]: row["dashboard_name"] for row in registry["tracked"]}
    catalogue = {row["svn"]: row for row in registry["catalogue"]}
    periods = {}
    for row in registry["signal_ids"]:
        periods.setdefault(row["svn"], []).append(row)
    records = {}
    for satellite in registry["satellites"]:
        svn = satellite["svn"]
        noted = satellite["note"].split("; ")[1].strip() if "; " in satellite["note"] else ""
        name = tracked.get(svn) or noted or (catalogue.get(svn) or {}).get("name") or svn
        events = registry_events(satellite, periods.get(svn, []), catalogue.get(svn))
        if any(e["step"] == "launch" for e in events):
            records[name if name not in records else f"{name} ({svn})"] = (
                svn, satellite["constellation"], satellite["block"], events)
    return records


def timelines(rows, today, registry=None):
    """One record per satellite: its events (dated first, by time) and its checklist. Hand-kept satellites come first,
    in file order, then the registry's by system (SYSTEM_ORDER) and newest launch first."""
    hand = {}
    for row in rows:
        hand.setdefault(row["satellite"], []).append(_event(row))
    made = _registry_records(registry) if registry else {}
    records = []
    for name in [*hand, *(name for name in made if name not in hand)]:
        svn, system, series, events = made.get(name, ("", "", "", []))
        if name in hand:
            series = LIFECYCLE_SERIES[name]
            system = system or SERIES_SYSTEM[series]
            kept = {e["step"] for e in hand[name]} - {NOTE_STEP}   # the table's notes never replace the registry's
            steps = LIFECYCLE_STEPS[series]
            # A registry event for a step the table has is replaced; any other is kept as a note, never a step:
            # the table's steps are the operator's (NVS-02 was given a signal ID but never entered service).
            events = hand[name] + [{**e, "step": NOTE_STEP} for e in events if e["step"] not in kept]
        else:
            steps = REGISTRY_STEPS
        events.sort(key=lambda e: (not e["at"], e["at"]))
        launch = next(e["at"] for e in events if e["step"] == "launch")
        records.append({"name": name, "svn": svn, "system": system, "series": series, "detailed": name in hand,
                        "launch": launch, "design_life_years": DESIGN_LIFE_YEARS.get(series),
                        "life_used": life_used(series, events, today), "service_years": service_years(events, today),
                        "checklist": checklist(steps, [e for e in events if e["step"] != NOTE_STEP]),
                        "events": events})
    order = {system: i for i, system in enumerate(SYSTEM_ORDER)}
    head = [r for r in records if r["detailed"]]
    rest = sorted((r for r in records if not r["detailed"]), key=lambda r: r["launch"], reverse=True)
    return head + sorted(rest, key=lambda r: order.get(r["system"], len(order)))


def service_years(events, today):
    """Years from the service step to the end step (or today), or None before service."""
    start = next((_time(e["at"]) for e in events if e["step"] == SERVICE_STEP and e["at"]), None)
    if not start:
        return None
    end = next((_time(e["at"]) for e in events if e["step"] == END_STEP and e["at"]), None) or today
    return max(0.0, (end - start).days / DAYS_PER_YEAR)
