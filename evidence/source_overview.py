"""The sources at a glance, for the administration console: how many are graded, what grades are proposed, and which
candidates did not answer when they were checked. Read from evidence/source_grades.csv and source_candidates.csv."""
import csv
from collections import Counter

from evidence.settings import CANDIDATE_WORKED, SOURCE_CANDIDATES_FILE, SOURCE_GRADES_FILE

NOT_CHECKED = "not fetched"   # a candidate held back by rule: never fetched, so not "not answering"
_ANSWER_WORDS = {"403": "refused (403)", "404": "not found (404)"}


def _rows(path):
    """The table's rows; a field a short line leaves out reads as empty, never as None."""
    with open(path, newline="", encoding="utf-8") as handle:
        return [{key: value or "" for key, value in row.items() if key} for row in csv.DictReader(handle)]


def overview(grades_file=SOURCE_GRADES_FILE, candidates_file=SOURCE_CANDIDATES_FILE):
    """{'graded': n, 'candidates': n, 'proposed': Counter of proposed grades ('' = none), 'not_answering': {words: n}}."""
    graded, candidates = _rows(grades_file), _rows(candidates_file)
    failed = Counter(_ANSWER_WORDS.get(r["check_status"], r["check_status"]) for r in candidates
                     if r["check_status"] not in (CANDIDATE_WORKED, NOT_CHECKED))
    return {"graded": len(graded), "candidates": len(candidates),
            "proposed": Counter(r["proposed_grade"] for r in candidates), "not_answering": dict(failed.most_common())}


# The filters of the console's Sources page, in its order. A row falls in the first that fits.
GROUPS = ("not answering", "held", "graded", "awaiting a grade", "no grade")
HELD = "held: not fetched"


def _answer(status, held):
    """(tone, words) for the answer at the last check."""
    if status == CANDIDATE_WORKED:
        return "ok", "answered"
    if status == NOT_CHECKED:
        return "idle", "not fetched: held by rule" if held else "not fetched"
    return "warn", _ANSWER_WORDS.get(status, status or "not checked")


def source_rows(grades_file=SOURCE_GRADES_FILE, candidates_file=SOURCE_CANDIDATES_FILE):
    """One row per candidate feed or page, then one per graded site that has none, in file order.

    A grade belongs to a site (source_id), so a confirmed grade covers every feed of that site; any other grade is
    the one proposed. Each row's group is the first of GROUPS that fits it.
    """
    graded = {r["source_id"]: r for r in _rows(grades_file)}
    rows = []
    for c in _rows(candidates_file):
        confirmed = graded.get(c["source_id"])
        rows.append({"source": c["source_id"], "name": c["name"], "kind": c["kind"], "address": c["address"],
                     "grade": confirmed["reliability"] if confirmed else c["proposed_grade"], "confirmed": bool(confirmed),
                     "reason": confirmed["reason"] if confirmed else c["grade_reason"], "checked_on": c["checked_on"],
                     "answer": _answer(c["check_status"], c["standing"] == HELD), "held": c["standing"] == HELD})
    named = {c["source"] for c in rows}
    rows += [{"source": g["source_id"], "name": g["name"], "kind": "", "address": "", "grade": g["reliability"],
              "confirmed": True, "reason": g["reason"], "checked_on": "", "answer": ("idle", "not checked here"),
              "held": False} for g in graded.values() if g["source_id"] not in named]
    for r in rows:
        r["group"] = ("not answering" if r["answer"][0] == "warn" else "held" if r["held"] else "graded" if r["confirmed"]
                      else "awaiting a grade" if r["grade"] else "no grade")
    return rows
