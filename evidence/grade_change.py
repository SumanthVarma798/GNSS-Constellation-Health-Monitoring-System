"""Change a source's confirmed grade from the administration console: a pull request with one finding, like other decisions."""
import base64
import csv
import io
import re
from datetime import datetime, timezone

import requests

from evidence import decisions
from evidence.decision_settings import LABEL_PREFIX, REPOSITORY
from evidence.github_api import ask as _ask
from evidence.settings import SOURCE_GRADE_COLUMNS

GRADES_PATH = "evidence/source_grades.csv"
GRADE_LABEL = f"{LABEL_PREFIX}source grade"
VALID_GRADES = tuple("ABCDEF")
_MIN_REASON_WORDS = 3


def safe_source_id(source_id):
    """A source id safe in a branch name and a finding id."""
    return re.sub(r"[^A-Za-z0-9_-]+", "-", source_id).strip("-") or "source"


def new_grades_csv(text, source_id, name, grade, reason, who, today):
    """Replace one source's row in source_grades.csv, or add it at the end; columns and order unchanged."""
    rows = list(csv.DictReader(io.StringIO(text)))
    day = today if isinstance(today, str) else today.isoformat()
    new_row = {"source_id": source_id, "name": name, "reliability": grade, "graded_by": f"{who} (from the console)",
               "graded_on": day, "reason": reason}
    out, replaced = [], False
    for row in rows:
        if row.get("source_id") == source_id:
            out.append(new_row)
            replaced = True
        else:
            out.append({column: row.get(column, "") for column in SOURCE_GRADE_COLUMNS})
    if not replaced:
        out.append(new_row)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SOURCE_GRADE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(out)
    return buf.getvalue()


def validate(source_id, grade, reason, known_sources, confirmed_grade):
    """Plain words when the form cannot be sent; None when it can."""
    if source_id not in known_sources:
        return "That source is not known."
    if grade not in VALID_GRADES:
        return "Choose a grade from A to F."
    words = (reason or "").strip()
    if len(words.split()) < _MIN_REASON_WORDS:
        return "Write a short reason in plain words (at least a few words)."
    if grade == (confirmed_grade or ""):
        return "The new grade must differ from the grade already confirmed for this source."
    return None


def submit(token, source_id, name, confirmed_grade, grade, reason, who, today, now=None, ask=_ask):
    """Open a pull request that changes one source grade; ('ok', words) or ('warn', words), never raises."""
    now = now or datetime.now(timezone.utc)
    try:
        main = ask("GET", "/git/ref/heads/main", token)["object"]["sha"]
        file_info = ask("GET", f"/contents/{GRADES_PATH}", token)
        old_text = base64.b64decode(file_info["content"]).decode("utf-8")
        new_text = new_grades_csv(old_text, source_id, name, grade, reason.strip(), who, today)
        stamp = now.strftime("%Y%m%d%H%M%S")
        branch = f"grade-change/{safe_source_id(source_id)}-{stamp}"
        ask("POST", "/git/refs", token, json={"ref": f"refs/heads/{branch}", "sha": main})
        ask("PUT", f"/contents/{GRADES_PATH}", token, json={"message": f"Source grade: {name} to {grade} ({who})",
                                                             "content": base64.b64encode(new_text.encode()).decode(),
                                                             "sha": file_info["sha"], "branch": branch})
        old_words = confirmed_grade or "none"
        finding_id = f"grade-change-{safe_source_id(source_id)}"
        finding = {"id": finding_id, "category": "Source grade",
                   "statement": f"Set {name} from {old_words} to {grade}: {reason.strip()}",
                   "sources": [{"source": name, "line": reason.strip(), "grade": grade}], "measured": []}
        body = (f"A person asked to set {name}'s grade to {grade} from the console.\n\n"
                + decisions.findings_block([finding]))
        title = f"Source grade: {name} to {grade} (from the console)"
        pr = ask("POST", "/pulls", token, json={"title": title, "head": branch, "base": "main", "body": body})
        ask("POST", f"/issues/{pr['number']}/labels", token, json={"labels": [GRADE_LABEL]})
        link = pr.get("html_url") or f"https://github.com/{REPOSITORY}/pull/{pr['number']}"
        return "ok", f"Pull request {pr['number']} is open for a decision under Approvals: {link}"
    except requests.RequestException as error:
        return "warn", _github_words(error)
    except (KeyError, TypeError, ValueError):   # a reply without the fields expected
        return "warn", "GitHub answered in a way the console did not expect, so the grade was not changed. Try again later."


def _github_words(error):
    code = getattr(getattr(error, "response", None), "status_code", None)
    if code in (401, 403):
        return "GitHub refused the console's token: it may have expired or lost its access."
    if code in (404, 405, 409, 422):
        return ("GitHub would not open the pull request, so the grade was not changed. A branch named grade-change/... "
                "may be left on GitHub; it can be deleted.")
    return "GitHub did not answer, so the grade could not be changed now. Try again in a few minutes."
