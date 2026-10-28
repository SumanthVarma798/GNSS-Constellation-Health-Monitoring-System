"""The bar and the labels, one test for each rule Sumanth set on 8 Oct 2026."""
import csv
import datetime
from urllib.parse import urlsplit

import pytest

from evidence.confidence import assess, assess_event, read_source_grades
from evidence.settings import (CANDIDATE_GRADED, CANDIDATE_STANDINGS, RELIABILITY_GRADES, SOURCE_CANDIDATE_COLUMNS,
                               SOURCE_CANDIDATES_FILE, SOURCE_GRADE_COLUMNS)
from evidence.sources import ARCHIVED_SOURCES, PROVISIONAL_GROUPS, archived_addresses, candidate_rows
from evidence.store import new_store


@pytest.mark.parametrize("grades, is_observed, clears, label", [
    # Rule 1: the operator itself clears the bar alone.
    (["A"], False, True, "probable"),
    (["A"], True, True, "confirmed"),
    (["A", "C"], False, True, "confirmed"),
    # Rule 2: a usually-reliable source clears it with a second independent source, or with observation.
    (["B"], False, False, "unconfirmed"),
    (["B", "D"], False, True, "confirmed"),
    (["B", "B"], False, True, "confirmed"),
    (["B"], True, True, "confirmed"),
    # Social media and unattributed posts do not count as the second source.
    (["B", "E"], False, False, "unconfirmed"),
    (["B", "F"], False, False, "unconfirmed"),
    (["B", None], False, False, "unconfirmed"),
    # Press and news never clear it, whatever we observe or however many agree. Known and accepted.
    (["C"], True, False, "unconfirmed"),
    (["D"], True, False, "unconfirmed"),
    (["C", "D"], False, False, "unconfirmed"),
    (["E", "F"], True, False, "unconfirmed"),
    # Nobody said it. What we observed alone does not clear the bar as it is written today.
    ([], True, False, "unconfirmed"),
    ([], False, False, "unconfirmed"),
])
def test_the_bar(grades, is_observed, clears, label):
    assessment = assess(grades, is_observed)

    assert (assessment.clears_bar, assessment.label) == (clears, label)
    assert assessment.reason.endswith(".")


def test_the_source_table_is_complete_and_well_formed():
    rows = read_source_grades()

    assert rows and list(rows[0]) == SOURCE_GRADE_COLUMNS
    assert len({row["source_id"] for row in rows}) == len(rows)  # one row per source
    for row in rows:
        assert row["reliability"] in RELIABILITY_GRADES
        assert row["name"] and row["graded_by"] and row["reason"]
        datetime.date.fromisoformat(row["graded_on"])


def test_every_archived_source_has_been_graded_or_is_a_provisional_candidate():
    graded = {row["source_id"] for row in read_source_grades()}
    settled = [address for group in ARCHIVED_SOURCES if group not in PROVISIONAL_GROUPS
               for address in archived_addresses(group)]
    ungraded = {urlsplit(address).hostname for address in settled} - graded
    assert ungraded == set(), "add these sources to evidence/source_grades.csv before archiving them"
    # News and social sources are collected before they are graded (19 Oct 2026): each must be on the candidate list.
    candidates = {row["address"] for row in candidate_rows()}   # as the archive reads them: {year} filled in
    assert {address for group in PROVISIONAL_GROUPS for address in archived_addresses(group)} <= candidates


def test_the_candidate_list_is_well_formed():
    with open(SOURCE_CANDIDATES_FILE, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    graded = {row["source_id"]: row["reliability"] for row in read_source_grades()}

    assert rows and list(rows[0]) == SOURCE_CANDIDATE_COLUMNS
    for row in rows:
        assert row["name"] and row["grade_reason"] and row["standing"] in CANDIDATE_STANDINGS
        assert row["proposed_grade"] in ("", *RELIABILITY_GRADES)
        assert (row["standing"] == CANDIDATE_GRADED) == (row["source_id"] in graded)
        if row["standing"] == CANDIDATE_GRADED:
            assert row["proposed_grade"] == graded[row["source_id"]]
        # The Russian and Chinese tracker sites are never fetched, so never listed (issue 13, 17 Oct).
        assert not any(name in " ".join(row.values()).lower() for name in ("vimpel", "spacemapper"))


@pytest.fixture
def store():
    store = new_store()
    store.execute("INSERT INTO constellation VALUES ('C', 'BeiDou')")
    store.execute("INSERT INTO satellite VALUES ('C217', 'BeiDou', 'BDS-3G', '2018-085A', 43683, 'C04', 'G', '140E', NULL)")
    store.executemany("INSERT INTO source VALUES (?, ?, ?)",
                      [("operator.example", "The operator", "A"), ("igs.example", "A scientific body", "B"),
                       ("press.example", "A newspaper", "D")])
    store.executemany("INSERT INTO document VALUES (?, ?, 'https://x', '2026-04-22T06:00:00Z', 200, ?, 1, NULL, NULL)",
                      [(1, "operator.example", "a" * 64), (2, "igs.example", "b" * 64), (3, "igs.example", "c" * 64),
                       (4, "press.example", "d" * 64)])
    store.executemany("INSERT INTO claim VALUES (?, ?, 'C217', 'A statement', NULL)", [(1, 1), (2, 2), (3, 3), (4, 4)])
    store.execute("INSERT INTO event VALUES (1, 'C217', '2026-04-21', 'Changed signal ID')")
    return store


def test_an_event_is_judged_from_its_supporting_sources_and_what_we_saw(store):
    assert assess_event(store, 1).label == "unconfirmed"  # nothing attached yet

    store.execute("INSERT INTO event_claim VALUES (1, 2, 'supports'), (1, 3, 'supports')")
    assert assess_event(store, 1).label == "unconfirmed"  # two documents from ONE source are still one source

    store.execute("INSERT INTO observation VALUES (1, 1, 'signal', '2026-04-21T12:00:00Z', 'Heard C04 from that position')")
    assert assess_event(store, 1) == (True, "confirmed", "A usually-reliable source said it, and our own data agrees.")


def test_a_claim_that_contests_an_event_does_not_count_as_support(store):
    store.execute("INSERT INTO event_claim VALUES (1, 2, 'supports'), (1, 4, 'contests')")
    assert assess_event(store, 1).clears_bar is False

    store.execute("UPDATE event_claim SET stance = 'supports' WHERE claim_id = 4")
    assert assess_event(store, 1).clears_bar is True
