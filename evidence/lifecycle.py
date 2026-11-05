"""Each satellite's life as steps on a timeline: what happened when, from which source, and how far along it is.

Rows come from registry/lifecycle_events.csv (kept by hand); the steps and design lives from
evidence/library_settings.py. Times stay ISO 8601 text in UTC; the page places them. No clock here: the caller
passes today.
"""
from datetime import datetime
from urllib.parse import quote

from evidence.library_settings import (COMMONS_PAGE, COMMONS_PICTURE, DAYS_PER_YEAR, DESIGN_LIFE_YEARS, END_STEP,
                                       FAILED, LIFECYCLE_SERIES, LIFECYCLE_STEPS, NOTE_STEP, SERVICE_STEP)

DONE, IMPLIED, FAILED_STATE, MISSED, AHEAD = "done", "done, date not published", "failed", "not reached", "ahead"


def _time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None


def _picture(name, credit):
    if not name:
        return None
    file = quote(name.replace(" ", "_"))
    return {"src": COMMONS_PICTURE.format(name=file), "page": COMMONS_PAGE.format(name=file), "credit": credit}


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


def timelines(rows, today):
    """One record per satellite, in file order: its events (dated first, by time) and its checklist."""
    out = {}
    for row in rows:
        out.setdefault(row["satellite"], []).append(_event(row))
    records = []
    for name, events in out.items():
        series = LIFECYCLE_SERIES[name]
        steps = LIFECYCLE_STEPS[series]
        launch = next(e["at"] for e in events if e["step"] == "launch")
        events.sort(key=lambda e: (not e["at"], e["at"]))
        records.append({"name": name, "series": series, "launch": launch, "design_life_years": DESIGN_LIFE_YEARS.get(series),
                        "life_used": life_used(series, events, today),
                        "checklist": checklist(steps, [e for e in events if e["step"] != NOTE_STEP]),
                        "events": events})
    return records
