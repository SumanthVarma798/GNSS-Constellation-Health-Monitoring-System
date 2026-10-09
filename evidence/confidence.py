"""How sure we are: the source table, the bar, and the three labels.

Two things are graded apart, as in the Admiralty code. Reliability (A to F)
belongs to the source and is set by a person in the source table. Credibility
(1 to 6) belongs to a single statement and is set when the statement is
extracted. This module turns grades and corroboration into two answers: does
the item clear the bar for the dashboard, and which label does a reader see.

The bar itself is a handful of lines in evidence/settings.py.
"""
import csv
from typing import NamedTuple

from evidence.settings import (GRADES_LIFTED_BY_A_SECOND_SOURCE, GRADES_LIFTED_BY_OBSERVATION,
                               GRADES_THAT_CLEAR_ALONE, GRADES_THAT_COUNT_AS_A_SECOND_SOURCE, LABEL_CONFIRMED,
                               LABEL_PROBABLE, LABEL_UNCONFIRMED, SOURCE_GRADES_FILE)


class Assessment(NamedTuple):
    clears_bar: bool
    label: str
    reason: str  # one plain sentence, for the person reviewing


def read_source_grades():
    """The source table as a list of rows, each a dict keyed by column name."""
    with open(SOURCE_GRADES_FILE, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def assess(reliabilities, is_observed=False):
    """Judge one item from the grade of each distinct source that supports it.

    `reliabilities` holds one grade per supporting source ("A" to "F", or None
    for a source nobody has graded). `is_observed` says whether our own orbit
    or signal data agrees.
    """
    grades = list(reliabilities)
    corroborating = [grade for grade in grades if grade in GRADES_THAT_COUNT_AS_A_SECOND_SOURCE]
    has_second_source = len(corroborating) >= 2

    if any(grade in GRADES_THAT_CLEAR_ALONE for grade in grades):
        if has_second_source or is_observed:
            return Assessment(True, LABEL_CONFIRMED, "The operator said it, and a second source or our own data agrees.")
        return Assessment(True, LABEL_PROBABLE, "The operator said it. Nothing else confirms it yet.")
    if has_second_source and any(grade in GRADES_LIFTED_BY_A_SECOND_SOURCE for grade in grades):
        return Assessment(True, LABEL_CONFIRMED, "A usually-reliable source said it, and a second independent source agrees.")
    if is_observed and any(grade in GRADES_LIFTED_BY_OBSERVATION for grade in grades):
        return Assessment(True, LABEL_CONFIRMED, "A usually-reliable source said it, and our own data agrees.")
    if not grades:
        return Assessment(False, LABEL_UNCONFIRMED, "No source has said it.")
    return Assessment(False, LABEL_UNCONFIRMED, "No source that supports it is reliable enough, alone or together, to clear the bar.")


def assess_event(store, event_id):
    """Judge one event in the query store from the claims that support it and what we observed."""
    grades = [grade for (grade,) in store.execute(
        """SELECT source.reliability FROM event_claim
           JOIN claim ON claim.id = event_claim.claim_id
           JOIN document ON document.id = claim.document_id
           JOIN source ON source.id = document.source_id
           WHERE event_claim.event_id = ? AND event_claim.stance = 'supports'
           GROUP BY source.id""", (event_id,))]
    (seen,) = store.execute("SELECT COUNT(*) FROM observation WHERE event_id = ?", (event_id,)).fetchone()
    return assess(grades, is_observed=seen > 0)
