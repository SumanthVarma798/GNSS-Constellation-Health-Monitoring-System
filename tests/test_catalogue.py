"""The catalogue table: built correctly from a sample, sound as committed, and its disagreements with the IGS file."""
import pytest

from evidence.catalogue_check import disagreement_report, disagreements
from evidence.gcat import catalogue_rows, read_rows
from evidence.registry_tables import read_table
from evidence.settings import (GCAT_CITATION, REGISTRY_CATALOGUE_COLUMNS, REGISTRY_CATALOGUE_FILE,
                               REGISTRY_SATELLITES_FILE)

# The same shape as the real files: tab-separated, padded with spaces, a '#' header and a '#' date line.
OBJECTS = "\n".join([
    "#JCAT\tSatcat\tPiece\tPLName\tOwner\tState\tStatus\tOpOrbit\tExtra",
    "# Updated 2026 Oct  8 2357:56",
    "S39635    \t39635\t2014-017A\tIRNSS-1B\tISRO\tIN\tO\tGEO/NS\t-",
    "S40547    \t40547\t2015-018A\tIRNSS-1D\tISRO\tIN\tO\tGEO/T\t-",
    "S00900    \t00900\t1964-063C\tCalsphere 1\tNRL\tUS\tO\tLEO/P\t-",
    "A00001    \t\t1990-000A\tNo number\tX\tUS\tO\tLEO\t-",
    "",
])
PAYLOADS = "\n".join([
    "#JCAT\tPiece\tTLast\tTOp\tResult",
    "# Updated 2026 Oct  8 2358:02",
    "S39635    \t2014-017A\t2023 Feb 22\t*\tS",
    "S40547    \t2015-018A\t2025 Jul  8\t2025 Jul 10\tS",
    "",
])
SATELLITES = [
    {"svn": "I002", "constellation": "NavIC", "cospar_id": "2014-017A", "catalogue_no": "39635", "signal_id_now": ""},
    {"svn": "I004", "constellation": "NavIC", "cospar_id": "2015-018X", "catalogue_no": "40547", "signal_id_now": "I04"},
    {"svn": "J008", "constellation": "QZSS", "cospar_id": "2025-999A", "catalogue_no": "100270", "signal_id_now": "J05"},
]


def test_table_from_sample():
    rows = catalogue_rows(SATELLITES, OBJECTS, PAYLOADS)

    assert rows == [
        ["I002", "2014-017A", "IRNSS-1B", "ISRO", "IN", "O", "GEO/NS", "2023 Feb 22", "*", "S"],
        ["I004", "2015-018A", "IRNSS-1D", "ISRO", "IN", "O", "GEO/T", "2025 Jul  8", "2025 Jul 10", "S"],
        ["J008", "", "", "", "", "", "", "", "", ""],   # not in the catalogue yet: a row of blanks, not an error
    ]
    assert all(len(row) == len(REGISTRY_CATALOGUE_COLUMNS) for row in rows)


def test_a_changed_layout_stops_the_build():
    with pytest.raises(ValueError, match="no column named Owner"):
        read_rows(OBJECTS.replace("Owner", "Operator"), ["Owner"])


def test_disagreements_name_each_kind_and_pick_no_winner():
    catalogue = [dict(zip(REGISTRY_CATALOGUE_COLUMNS, row)) for row in catalogue_rows(SATELLITES, OBJECTS, PAYLOADS)]
    missing, designator, not_in_service, still_operating = disagreements(SATELLITES, catalogue).values()

    assert missing == ["J008 (QZSS, catalogue number 100270)."]
    assert designator == ["I004 (NavIC, catalogue number 40547): the IGS file says 2015-018X, the catalogue says 2015-018A."]
    assert not_in_service == ["I004 (NavIC, catalogue number 40547), IRNSS-1D, signal ID I04: "
                              "the catalogue says regular operations ended 2025 Jul 10."]
    assert still_operating == ["I002 (NavIC, catalogue number 39635), IRNSS-1B: last known active 2023 Feb 22."]


def test_the_report_cites_the_catalogue_as_its_licence_requires():
    report = disagreement_report(disagreements(SATELLITES, []))

    assert GCAT_CITATION in report
    assert "In the registry, not in the catalogue yet (3)" in report


def test_committed_table_is_sound():
    catalogue, satellites = read_table(REGISTRY_CATALOGUE_FILE), read_table(REGISTRY_SATELLITES_FILE)

    assert list(catalogue[0]) == REGISTRY_CATALOGUE_COLUMNS
    # The same satellites as the registry may differ for a while: each table is approved
    # by a person in its own time. Every catalogue row must still be a registry satellite.
    assert {row["svn"] for row in catalogue} <= {row["svn"] for row in satellites}
    assert len({row["svn"] for row in catalogue}) == len(catalogue)
