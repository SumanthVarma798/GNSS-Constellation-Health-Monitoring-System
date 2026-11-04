"""The Library page's counts: built from a small GCAT sample (no network), sound as committed, and shown with their sources."""
import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from evidence.library import gcat_updated, library_tables, vague_date
from evidence.library_settings import (LIBRARY_COUNTS_COLUMNS, OTHER_PROGRAMME, LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_COLUMNS,
                                       LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_COLUMNS, LIBRARY_MATCHING_FILE, SYSTEMS)
from evidence.registry_tables import read_table
from evidence.settings import GCAT_CITATION, REGISTRY_DIR, REGISTRY_SATELLITES_FILE
from ui import library

# Same shape as the real files: tab-separated, padded, a '#' header line and a '#' update line.
OBJECTS = "\n".join([
    "#JCAT\tSatcat\tLDate\tName",
    "# Updated 2026 Oct 16 2335:46",
    "S10001    \t10001\t2000 Jan  1\tGPS-A",     # operating
    "S10002    \t10002\t2000 Jan  1\tGPS-B",     # retired in exactly 4 years
    "S10003    \t10003\t2010 Jun 15\tIRNSS-X",   # failed early in orbit; not in the registry, found by programme
    "S10004    \t10004\t2005 Mar  1\tOld-GLO",    # retired, end date known only to the year
    "S20298    \t10005\t1989 Oct 18\tProbe",      # a Jupiter probe whose programme name is "Galileo"
    "S10006    \t10006\t2001 Jan  1\tUnknown",    # no programme listed, but the registry says QZSS
    "S10007    \t10007\t2003 Jan  1\tOther",      # no programme, no registry: not counted
    "S10008    \t10008\t2012 Jan  1\tBlank-end",  # neither operating nor retired: status not recorded
    "",
])
PAYLOADS = "\n".join([
    "#JCAT\tProgram\tTOp\tResult",
    "# Updated 2026 Oct 16 2335:51",
    "S10001    \tGPS IIR\t*\tS",
    "S10002    \tGPS IIR\t2004 Jan  1\tS",
    "S10003    \tIRNSS\t2010 Jun 15\tF",
    "S10004    \tUragan\t2008\tU",
    "S20298    \tGalileo\t2003 Sep 21\tS",
    "S10006    \tNo such programme\t*\tS",
    "S10007    \tNo such programme\t*\tS",
    "S10008    \tUragan-M\t-\tS",
    "",
])
FAILED = "\n".join([
    "#JCAT\tType\tName\tLDate",
    "# Updated 2026 Oct 16 2335:47",
    "F00001    \tP   F\tNavstar 7\t1981 Dec 19",
    "F00002    \tR3  F\tNavstar 7 Stage 3\t1981 Dec 19",   # a rocket stage: not a payload
    "F00003    \tP   F\tGlonass-M 739\t2010 Dec  5",
    "F00004    \tP   F\tSome cubesat\t2010 Dec  5",
    "",
])
REGISTRY = [
    {"svn": "G001", "constellation": "GPS", "catalogue_no": "10001"},
    {"svn": "G002", "constellation": "GPS", "catalogue_no": "10002"},
    {"svn": "J001", "constellation": "QZSS", "catalogue_no": "10006"},
    {"svn": "J002", "constellation": "QZSS", "catalogue_no": "100270"},   # too new for GCAT
]


def sample():
    counts, matching = library_tables(REGISTRY, OBJECTS, PAYLOADS, FAILED)
    as_written = lambda columns, row: dict(zip(columns, map(str, row)))   # the table holds text once written
    return ({(row[0], row[1]): as_written(LIBRARY_COUNTS_COLUMNS, row) for row in counts},
            {row[0]: as_written(LIBRARY_MATCHING_COLUMNS, row) for row in matching})


def test_counts_from_sample():
    counts, _ = sample()

    gps_r = counts["GPS", "GPS IIR"]
    assert (gps_r["launched"], gps_r["operating"], gps_r["retired"]) == ("2", "1", "1")
    assert float(gps_r["years_retired"]) == 4.0                                  # 2000 Jan 1 to 2004 Jan 1, 1461 days / 365.25
    assert float(gps_r["years_operating"]) == round((date(2026, 10, 16) - date(2000, 1, 1)).days / 365.25, 2)
    assert counts["NavIC", "IRNSS"]["failed_in_orbit"] == "1"
    assert counts["GLONASS", "Uragan"]["retired"] == "1"
    assert counts["GLONASS", "Uragan"]["approximate_dates"] == "1"               # end date known to the year only
    assert counts["GLONASS", "Uragan-M"]["status_not_recorded"] == "1"
    assert counts["QZSS", OTHER_PROGRAMME]["operating"] == "1"                        # registry places it; programme does not
    assert not [key for key in counts if key[0] == "Galileo"]                    # the probe is left out


def test_launch_failures_are_found_by_name_and_only_payloads_count():
    counts, _ = sample()

    assert counts["GPS", "GPS I"]["failed_at_launch"] == "1" and counts["GPS", "GPS I"]["launched"] == "1"
    assert counts["GLONASS", "Uragan-M"]["failed_at_launch"] == "1"
    assert counts["GLONASS", "Uragan-M"]["launched"] == "2"                       # one failed launch plus the one with no end date
    assert sum(int(row["failed_at_launch"]) for row in counts.values()) == 2      # the stage and the cubesat are not navigation payloads


def test_every_launched_satellite_is_in_exactly_one_state():
    for row in sample()[0].values():
        states = sum(int(row[name]) for name in ("failed_at_launch", "failed_in_orbit", "retired", "operating", "status_not_recorded"))
        assert states == int(row["launched"])


def test_matching_says_how_each_satellite_was_placed():
    _, matching = sample()

    assert matching["GPS"] == {"system": "GPS", "registry_satellites": "2", "registry_found_in_gcat": "2", "registry_not_in_gcat": "0",
                               "also_found_by_programme": "2", "found_by_programme_only": "0", "registry_and_programme_disagree": "0"}
    assert matching["QZSS"]["registry_not_in_gcat"] == "1"                        # shown as not matched, not hidden
    assert matching["QZSS"]["registry_and_programme_disagree"] == "0"             # a programme that is merely unlisted is no disagreement
    assert matching["QZSS"]["also_found_by_programme"] == "0"
    assert matching["NavIC"]["found_by_programme_only"] == "1"


def test_dates_as_gcat_writes_them():
    assert vague_date("2004 Jan  1 0359") == (date(2004, 1, 1), True)
    assert vague_date("2008") == (date(2008, 7, 15), False)
    assert vague_date("2010?") == (date(2010, 7, 15), False)
    assert vague_date("2025 Feb?") == (date(2025, 2, 15), False)
    assert vague_date("*") is None and vague_date("-") is None
    assert gcat_updated(PAYLOADS) == date(2026, 10, 16)


def test_committed_tables_are_sound():
    counts, matching, figures = (read_table(name) for name in (LIBRARY_COUNTS_FILE, LIBRARY_MATCHING_FILE, LIBRARY_FIGURES_FILE))

    assert list(counts[0]) == LIBRARY_COUNTS_COLUMNS and list(matching[0]) == LIBRARY_MATCHING_COLUMNS
    assert list(figures[0]) == LIBRARY_FIGURES_COLUMNS
    assert [row["system"] for row in matching] == list(SYSTEMS)
    for row in counts:
        states = sum(int(row[name]) for name in ("failed_at_launch", "failed_in_orbit", "retired", "operating", "status_not_recorded"))
        assert states == int(row["launched"]), row
    # Every registry satellite is accounted for once.
    registry = Counter(row["constellation"] for row in read_table(REGISTRY_SATELLITES_FILE))
    for row in matching:
        counted = int(row["registry_satellites"])
        assert int(row["registry_found_in_gcat"]) + int(row["registry_not_in_gcat"]) == counted
        assert counted <= registry[row["system"]]                              # the library can lag behind the registry
        assert row["registry_and_programme_disagree"] == "0"                      # a person looks at any disagreement


def test_every_figure_has_a_source_and_a_status():
    with open(REGISTRY_DIR / LIBRARY_FIGURES_FILE, newline="", encoding="utf-8") as handle:
        figures = list(csv.DictReader(handle))

    assert {row["system"] for row in figures} <= set(SYSTEMS)
    for row in figures:
        assert row["status"] == "source summary" and row["source_name"] and row["covers"]
        if row["value"] != library.NOT_KNOWN:
            assert row["source_link"].startswith("https://") and row["unit"] and row["year_of_figure"]


def test_the_scoreboard_shows_its_sources_and_cites_gcat():
    counts, figures = read_table(LIBRARY_COUNTS_FILE), read_table(LIBRARY_FIGURES_FILE)
    html = library.scoreboard(counts, figures)

    assert GCAT_CITATION in library.notes(counts)
    for note in range(1, 11):
        assert f"<sup>{note}</sup>" in html
    assert "not known" in html                                                   # BeiDou has no stated cost
    rows = {row["system"]: row for row in library.system_rows(counts)}
    assert rows["GPS"]["launched"] == 82
    assert library.launch_success(rows["GPS"]) == 80 / 82
    assert library.orbit_success({"launched": 0, "failed_at_launch": 0, "failed_in_orbit": 0}) is None


def test_the_library_note_says_when_the_registry_now_lists_more_satellites():
    matching = [{
        "system": "GLONASS",
        "registry_satellites": "101",
        "registry_found_in_gcat": "98",
        "registry_not_in_gcat": "3",
        "also_found_by_programme": "98",
        "found_by_programme_only": "10",
        "registry_and_programme_disagree": "0",
    }]
    registry = [{"constellation": "GLONASS"}] * 102

    note = library.registry_lag_note(matching, registry)
    assert note == "The library was counted when the registry listed 101 GLONASS satellites; it now lists 102."

