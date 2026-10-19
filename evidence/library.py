"""Counting the navigation satellites each system has launched, lost and kept, from GCAT.

GCAT is kept by Jonathan McDowell and released under CC-BY; anything shown from it carries GCAT_CITATION
(evidence/settings.py). Three of its files are read: the object catalogue (launch date), the payload
catalogue (programme, when regular operations ended, whether the mission failed early) and the catalogue
of launches that never reached orbit. Settings are in evidence/library_settings.py.
"""
import calendar
import re
from datetime import date

from evidence.gcat import read_rows
from evidence.library_settings import (DAYS_PER_YEAR, FAILED_LAUNCH_NAMES, LIBRARY_MATCHING_COLUMNS, NOT_THESE,
                                       OTHER_PROGRAMME, SYSTEMS)
from evidence.settings import GCAT_MISSION_FAILED, GCAT_STILL_OPERATING

MONTHS = {name: number for number, name in enumerate(calendar.month_abbr) if name}
# GCAT's "vague date": a year, then perhaps a month, a day and a time; "?" marks a doubtful one.
VAGUE_DATE = re.compile(r"^(\d{4})(?: ([A-Z][a-z]{2}))?(?: +(\d{1,2}))?")
UPDATED = re.compile(r"^# Updated (\d{4}) ([A-Z][a-z]{2}) +(\d{1,2})", re.M)
PROGRAMME_SYSTEM = {programme: system for system, one in SYSTEMS.items() for programme in one["programmes"]}


def vague_date(text):
    """(date, exact) for a GCAT date, or None if it holds none. A missing month is taken as July, a missing day
    as the 15th, so that the error is at most half a year or half a month either way; `exact` is False then,
    and for a date marked doubtful."""
    found = VAGUE_DATE.match(text or "")
    if not found:
        return None
    year, month, day = found.groups()
    month = MONTHS.get(month)
    return date(int(year), month or 7, int(day) if month and day else 15), bool(month and day) and "?" not in text


def gcat_updated(text):
    """The date GCAT's own '# Updated' line gives, so the same files always give the same table."""
    found = UPDATED.search(text)
    return date(int(found[1]), MONTHS[found[2]], int(found[3])) if found else None


def _tally(rows, system, programme):
    """The counts row for one system and programme, made on first use."""
    return rows.setdefault((system, programme), {"launched": 0, "failed_at_launch": 0, "failed_in_orbit": 0, "retired": 0,
                                                 "operating": 0, "status_not_recorded": 0, "years_retired": 0.0,
                                                 "years_operating": 0.0, "approximate_dates": 0, "launches": []})


def library_tables(satellites, objects_text, payloads_text, failed_text):
    """(counts, matching): rows for registry/library_counts.csv and registry/library_matching.csv.

    A spacecraft is put in a system by the registry when the registry lists it (by catalogue number), else by its
    GCAT programme. Those it lists are checked against the programme; an unlisted one is counted only if its
    programme is one of SYSTEMS. Every row is a sum, so the table's totals add up by construction.
    """
    objects = read_rows(objects_text, ["JCAT", "Satcat", "LDate"])
    launches = {row["JCAT"]: row["LDate"] for row in objects}
    jcat_of = {int(row["Satcat"]): row["JCAT"] for row in objects if row["Satcat"].isdigit()}
    payloads = read_rows(payloads_text, ["JCAT", "Program", "TOp", "Result"])
    as_of = gcat_updated(payloads_text)

    registry = {jcat_of.get(int(row["catalogue_no"])): row["constellation"] for row in satellites}
    matching = {system: dict.fromkeys(LIBRARY_MATCHING_COLUMNS[1:], 0) for system in SYSTEMS}
    for row in satellites:
        found = matching[row["constellation"]]
        found["registry_satellites"] += 1
        found["registry_found_in_gcat" if int(row["catalogue_no"]) in jcat_of else "registry_not_in_gcat"] += 1

    tally = {}
    for payload in payloads:
        jcat, programme = payload["JCAT"], payload["Program"]
        if jcat in NOT_THESE:
            continue
        by_programme = PROGRAMME_SYSTEM.get(programme)
        system = registry.get(jcat) or by_programme
        if not system:
            continue
        if jcat not in registry:
            matching[system]["found_by_programme_only"] += 1
        elif by_programme == system:
            matching[system]["also_found_by_programme"] += 1
        elif by_programme:   # the registry and the programme name different systems; a programme not listed is no disagreement
            matching[system]["registry_and_programme_disagree"] += 1
        row = _tally(tally, system, programme if by_programme == system else OTHER_PROGRAMME)
        row["launched"] += 1
        row["launches"].append(launches[jcat][:4])
        start, end = vague_date(launches[jcat]), vague_date(payload["TOp"])
        if payload["Result"] == GCAT_MISSION_FAILED:
            row["failed_in_orbit"] += 1
        elif payload["TOp"] == GCAT_STILL_OPERATING and as_of and start:
            row["operating"] += 1
            row["years_operating"] += (as_of - start[0]).days / DAYS_PER_YEAR
            row["approximate_dates"] += not start[1]
        elif end and start:
            row["retired"] += 1
            row["years_retired"] += max(0.0, (end[0] - start[0]).days / DAYS_PER_YEAR)
            row["approximate_dates"] += not (start[1] and end[1])
        else:
            row["status_not_recorded"] += 1

    for failed in read_rows(failed_text, ["Type", "Name", "LDate"]):
        for system, programme, pattern in FAILED_LAUNCH_NAMES:
            if failed["Type"].startswith("P") and re.search(pattern, failed["Name"]):
                row = _tally(tally, system, programme)
                row["launched"] += 1
                row["failed_at_launch"] += 1
                row["launches"].append(failed["LDate"][:4])

    order = [(system, programme) for system, one in SYSTEMS.items() for programme in [*one["programmes"], OTHER_PROGRAMME]]
    counts = []
    for key in sorted(tally, key=order.index):
        row = tally[key]
        years = sorted(row["launches"])
        counts.append([*key, *(row[name] for name in ("launched", "failed_at_launch", "failed_in_orbit", "retired", "operating",
                                                      "status_not_recorded")),
                       f"{row['years_retired']:.2f}", f"{row['years_operating']:.2f}", row["approximate_dates"],
                       years[0], years[-1], as_of.isoformat() if as_of else ""])
    return counts, [[system, *found.values()] for system, found in matching.items()]
