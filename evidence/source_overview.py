"""The sources at a glance, for the administration console: how many are graded, what grades are proposed, and which
candidates did not answer when they were checked. Read from evidence/source_grades.csv and source_candidates.csv."""
import csv
from collections import Counter

from evidence.settings import CANDIDATE_WORKED, SOURCE_CANDIDATES_FILE, SOURCE_GRADES_FILE

NOT_CHECKED = "not fetched"   # a candidate held back by rule: never fetched, so not "not answering"
_ANSWER_WORDS = {"403": "refused (403)", "404": "not found (404)"}


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def overview(grades_file=SOURCE_GRADES_FILE, candidates_file=SOURCE_CANDIDATES_FILE):
    """{'graded': n, 'candidates': n, 'proposed': Counter of proposed grades ('' = none), 'not_answering': {words: n}}."""
    graded, candidates = _rows(grades_file), _rows(candidates_file)
    failed = Counter(_ANSWER_WORDS.get(r["check_status"], r["check_status"]) for r in candidates
                     if r["check_status"] not in (CANDIDATE_WORKED, NOT_CHECKED))
    return {"graded": len(graded), "candidates": len(candidates),
            "proposed": Counter(r["proposed_grade"] for r in candidates), "not_answering": dict(failed.most_common())}
