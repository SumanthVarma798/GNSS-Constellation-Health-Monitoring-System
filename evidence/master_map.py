"""The master map: which physical spacecraft is this, under every identifier.

The master identifier is the space vehicle number (SVN), such as C217. Agencies name
the same spacecraft differently, and a signal ID (PRN) can pass from one spacecraft to
its replacement, so this module answers two questions: what are all the names of one
spacecraft, and who held a given signal ID, and when.

Every function takes lists of rows as evidence.registry_tables.read_table returns them
and gives back plain dicts and lists, so each can be tested with a few hand-made rows.
Only orbit_feed_names and orbit_feed_checked read files. Text in the tables is passed along, never interpreted.
"""
import json
import re
from datetime import date
from pathlib import Path

from evidence.settings import (GCAT_MISSION_FAILED, GCAT_STILL_OPERATING, IDENTITY_AGREE, IDENTITY_DIFFER,
                               IDENTITY_ONE_SOURCE, MAP_ACCENT, MAP_IDLE, MAP_OK, MAP_WARN, NOT_RECORDED,
                               ORBIT_FEED_FILES, SCHEME_COSPAR, SCHEME_DASHBOARD, SCHEME_GCAT, SCHEME_ISSUERS,
                               SCHEME_NORAD, SCHEME_ORBIT_FEED, SCHEME_SIGNAL_ID, SERVICE_AGREE_NOT_IN_SERVICE,
                               SERVICE_AGREE_OPERATING, SERVICE_DISAGREE, SERVICE_NOT_IN_CATALOGUE,
                               SIGNAL_ID_ISSUERS, SOURCE_DASHBOARD, SOURCE_GCAT, SOURCE_IGS, SOURCE_ORBIT_FEED,
                               SOURCE_SILENT)

NUMBER_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
SIGNAL_ID_IN_BRACKETS = re.compile(r"\(([^()\s]+)\)\s*$")  # "BEIDOU-3 G1 (C59)" -> "C59"


def _by_svn(rows):
    """{svn: row}."""
    return {row["svn"]: row for row in rows}


def _in_catalogue(entry):
    """True when the catalogue lists this spacecraft; a row of blanks means it does not yet."""
    return bool(entry and entry["cospar_id"])


def _day(stamp):
    """'2018-11-01T00:00:00Z' -> '2018-11-01'; a blank stays blank."""
    return stamp[:10]


def _words(count):
    """A small number in words: 2 -> 'two'."""
    return NUMBER_WORDS[count] if count < len(NUMBER_WORDS) else str(count)


def _name(svn, satellite, entry, tracked_row):
    """The best name for one spacecraft, from the rows already found for it."""
    if tracked_row and tracked_row["dashboard_name"]:
        return tracked_row["dashboard_name"]
    if entry and entry["name"]:
        return entry["name"]
    if satellite and ";" in satellite["note"]:
        named = satellite["note"].split(";")[1].strip()
        if named:
            return named
    return svn


def display_name(svn, satellites, catalogue, tracked):
    """The name to show for a spacecraft: the dashboard's own name, else the catalogue's,
    else the part of the IGS note right after its first semicolon, else the SVN itself."""
    return _name(svn, _by_svn(satellites).get(svn), _by_svn(catalogue).get(svn), _by_svn(tracked).get(svn))


def signal_ids_of(svn, signal_ids):
    """One spacecraft's signal-ID periods, oldest first."""
    mine = sorted((row for row in signal_ids if row["svn"] == svn), key=lambda row: row["valid_from"])
    return [{"label": row["signal_id"], "start": _day(row["valid_from"]), "end": _day(row["valid_to"]),
             "current": not row["valid_to"]} for row in mine]


def holders_of(signal_id, signal_ids, satellites, catalogue, tracked):
    """Every period in which a signal ID was held, oldest first, with who held it.

    A spacecraft that gets the signal ID back appears once for each stretch it held it.
    """
    by_satellite, by_entry, by_tracked = _by_svn(satellites), _by_svn(catalogue), _by_svn(tracked)
    held = sorted((row for row in signal_ids if row["signal_id"] == signal_id), key=lambda row: row["valid_from"])
    holders = []
    for row in held:
        svn = row["svn"]
        name = _name(svn, by_satellite.get(svn), by_entry.get(svn), by_tracked.get(svn))
        holders.append({"label": f"{svn}, {name}", "svn": svn, "start": _day(row["valid_from"]),
                        "end": _day(row["valid_to"]), "current": not row["valid_to"]})
    return holders


def _feed_remark(feed_name, periods):
    """(status, remark) for an orbit feed name, judged by the signal ID in its brackets.

    The count is how many times the spacecraft's signal ID has changed since the one the
    feed still shows. A spacecraft whose last period has ended counts that as one more change.
    """
    found = SIGNAL_ID_IN_BRACKETS.search(feed_name)
    if not found:
        return MAP_IDLE, "the name carries no signal ID to compare"
    shown = found.group(1)
    history = [period["label"] for period in periods]
    if not (periods and periods[-1]["current"]):
        history.append("none")
    if shown not in history:
        return MAP_WARN, "the signal ID in the name is not in this spacecraft's history"
    behind = len(history) - 1 - max(i for i, label in enumerate(history) if label == shown)
    if behind == 0:
        return MAP_OK, "current"
    return MAP_WARN, f"{_words(behind)} signal ID{'' if behind == 1 else 's'} out of date"


def _catalogue_identifier(satellite, entry):
    """The catalogue's name for the spacecraft, and whether its launch designator agrees."""
    if not _in_catalogue(entry):
        return {"scheme": SCHEME_GCAT, "value": "none", "status": MAP_IDLE, "remark": "not in the catalogue yet"}
    value = entry["name"] or "no name given"
    if not satellite["cospar_id"]:
        return {"scheme": SCHEME_GCAT, "value": value, "status": MAP_OK, "remark": "nothing to compare with"}
    if entry["cospar_id"] == satellite["cospar_id"]:
        return {"scheme": SCHEME_GCAT, "value": value, "status": MAP_OK, "remark": "agrees"}
    return {"scheme": SCHEME_GCAT, "value": value, "status": MAP_WARN, "remark": "launch designator differs"}


def _signal_id_identifier(satellite, periods):
    """Today's signal ID and since when, or 'none'."""
    now = [period for period in periods if period["current"]]
    if not satellite["signal_id_now"] or not now:
        return {"scheme": SCHEME_SIGNAL_ID, "value": "none", "status": MAP_IDLE, "remark": ""}
    return {"scheme": SCHEME_SIGNAL_ID, "value": satellite["signal_id_now"], "status": MAP_OK,
            "remark": f"since {now[-1]['start']}"}


def _feed_identifier(feed_name, periods, checked):
    """The orbit feed's name for the spacecraft and the day it was fetched, or None when the feed does not carry it."""
    if feed_name is None:
        return None
    status, remark = _feed_remark(feed_name, periods)
    return {"scheme": SCHEME_ORBIT_FEED, "value": feed_name, "status": status, "remark": remark, "checked": checked}


def _says(source, held, value):
    """What one source holds for an identifier: the same value, another one, or nothing."""
    if not held:
        return {"source": source, "status": MAP_IDLE, "note": SOURCE_SILENT}
    if held == value:
        return {"source": source, "status": MAP_OK, "note": ""}
    return {"source": source, "status": MAP_WARN, "note": f"says {held}"}


def identifiers(svn, satellites, catalogue, tracked, signal_ids, feed_names=None, feed_checked=None):
    """Every identifier of one spacecraft, in a fixed order, each as
    {"scheme", "value", "status", "remark", "issuer", "checked", "sources"}. feed_names is
    orbit_feed_names(); without it the orbit feed line is left out. feed_checked is
    orbit_feed_checked(). Only the orbit feed records when it was last checked; every
    other line says NOT_RECORDED. "sources" lists each of our sources that keeps this kind
    of identifier and whether it holds the same value, another, or none; a "none" line
    lists no sources. An unknown SVN gives an empty list."""
    satellite = _by_svn(satellites).get(svn)
    if satellite is None:
        return []
    entry, tracked_row, periods = _by_svn(catalogue).get(svn), _by_svn(tracked).get(svn), signal_ids_of(svn, signal_ids)
    number = int(satellite["catalogue_no"]) if satellite["catalogue_no"].isdigit() else None
    feed_name = (feed_names or {}).get(number)
    dashboard_name = tracked_row["dashboard_name"] if tracked_row else ""
    found = []
    if satellite["catalogue_no"]:
        found.append({"scheme": SCHEME_NORAD, "value": satellite["catalogue_no"], "status": MAP_OK, "remark": ""})
    if satellite["cospar_id"]:
        found.append({"scheme": SCHEME_COSPAR, "value": satellite["cospar_id"], "status": MAP_OK, "remark": ""})
    found.append(_catalogue_identifier(satellite, entry))
    found.append(_signal_id_identifier(satellite, periods))
    found.append(_feed_identifier(feed_name, periods, (feed_checked or {}).get(number, NOT_RECORDED)))
    if dashboard_name:
        found.append({"scheme": SCHEME_DASHBOARD, "value": dashboard_name, "status": MAP_ACCENT, "remark": ""})
    issuers = {**SCHEME_ISSUERS, SCHEME_SIGNAL_ID: SIGNAL_ID_ISSUERS.get(satellite["constellation"], NOT_RECORDED)}
    in_brackets = SIGNAL_ID_IN_BRACKETS.search(feed_name or "")
    # Which of our sources hold each kind of identifier, and what each holds for this spacecraft.
    held = {SCHEME_NORAD: [(SOURCE_IGS, satellite["catalogue_no"]),
                           (SOURCE_ORBIT_FEED, satellite["catalogue_no"] if feed_name is not None else "")],
            SCHEME_COSPAR: [(SOURCE_IGS, satellite["cospar_id"]), (SOURCE_GCAT, entry["cospar_id"] if entry else "")],
            SCHEME_GCAT: [(SOURCE_GCAT, entry["name"] if _in_catalogue(entry) else "")],
            SCHEME_SIGNAL_ID: [(SOURCE_IGS, satellite["signal_id_now"]),
                               (SOURCE_ORBIT_FEED, in_brackets.group(1) if in_brackets else "")],
            SCHEME_ORBIT_FEED: [(SOURCE_ORBIT_FEED, feed_name)],
            SCHEME_DASHBOARD: [(SOURCE_DASHBOARD, dashboard_name)]}
    return [{"issuer": issuers[item["scheme"]], "checked": NOT_RECORDED, **item,
             "sources": [] if item["value"] == "none" else
             [_says(source, value, item["value"]) for source, value in held[item["scheme"]]]}
            for item in found if item]


def _identity(satellite, entry):
    """(how the two sources stand on who this is, a remark)."""
    if not _in_catalogue(entry):
        return IDENTITY_ONE_SOURCE, "not in the catalogue yet"
    if entry["cospar_id"] != satellite["cospar_id"]:
        return IDENTITY_DIFFER, (f"the IGS file says {satellite['cospar_id'] or 'nothing'}, "
                                 f"the catalogue says {entry['cospar_id']}")
    return IDENTITY_AGREE, ""


def _service(satellite, entry):
    """(how the two sources stand on being in service, a remark saying why they disagree)."""
    if not _in_catalogue(entry):
        return SERVICE_NOT_IN_CATALOGUE, ""
    ended, failed = entry["operations_ended"], entry["mission_result"] == GCAT_MISSION_FAILED
    igs_says_in_service = bool(satellite["signal_id_now"])
    catalogue_says_operating = ended == GCAT_STILL_OPERATING and not failed
    if igs_says_in_service == catalogue_says_operating:
        return (SERVICE_AGREE_OPERATING if igs_says_in_service else SERVICE_AGREE_NOT_IN_SERVICE), ""
    if not igs_says_in_service:
        return SERVICE_DISAGREE, "the catalogue believes it is still operating"
    if failed:
        return SERVICE_DISAGREE, "the catalogue records the mission as failed"
    return SERVICE_DISAGREE, f"the catalogue says regular operations ended {ended or 'at a date it does not give'}"


def agreement(satellites, catalogue):
    """One line per spacecraft, in registry order: do the IGS file and the catalogue agree
    about who it is, and about whether it is in service? Neither is treated as right."""
    said = _by_svn(catalogue)
    lines = []
    for satellite in satellites:
        entry = said.get(satellite["svn"])
        identity, identity_remark = _identity(satellite, entry)
        service, service_remark = _service(satellite, entry)
        remark = "; ".join(part for part in (identity_remark, service_remark) if part)
        lines.append({"svn": satellite["svn"], "constellation": satellite["constellation"], "identity": identity,
                      "service": service, "remark": remark})
    return lines


def summary(satellites, catalogue, signal_ids):
    """Headline counts: spacecraft, systems, those both sources agree on, and signal IDs
    (and how many of them have been held by more than one spacecraft)."""
    holders = {}
    for row in signal_ids:
        holders.setdefault(row["signal_id"], set()).add(row["svn"])
    return {"spacecraft": len(satellites),
            "systems": len({row["constellation"] for row in satellites}),
            "confirmed": sum(line["identity"] == IDENTITY_AGREE for line in agreement(satellites, catalogue)),
            "signal_ids": len(holders),
            "signal_ids_reused": sum(len(svns) > 1 for svns in holders.values())}


def _feed_names_in(text):
    """{catalogue number: name} from three-line element sets: a name, then line 1, then line 2."""
    lines = text.splitlines()
    names = {}
    for first in range(0, len(lines) - 2, 3):
        name, line_one = lines[first].strip(), lines[first + 1]
        number = line_one[2:7].strip()  # characters 3 to 7 of line 1
        if line_one.startswith("1 ") and number.isdigit():
            names[int(number)] = name
    return names


def _feeds(data_dir, read):
    """{catalogue number: read(file contents, its names)} over every bundled orbit-feed file
    in a folder. A file that is missing or cannot be read is skipped."""
    found = {}
    for path in sorted(Path(data_dir).glob(ORBIT_FEED_FILES)):
        try:
            feed = json.loads(path.read_text(encoding="utf-8"))
            names = _feed_names_in(feed["tle_data"])
            found.update({number: read(feed, name) for number, name in names.items()})
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    return found


def orbit_feed_names(data_dir):
    """{catalogue number: name} from every bundled orbit-feed file in a folder."""
    return _feeds(data_dir, lambda feed, name: name)


def orbit_feed_checked(data_dir):
    """{catalogue number: 'YYYY-MM-DD'}: the day each feed file was fetched, from its own
    timestamp. A file whose timestamp is missing or not a date gives nothing."""
    return _feeds(data_dir, lambda feed, name: date.fromisoformat(feed["timestamp"][:10]).isoformat())
