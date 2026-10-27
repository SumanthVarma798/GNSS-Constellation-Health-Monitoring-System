"""Checked claims per source: read and append rows, score them, and raise source-grade findings."""
import csv
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

from evidence.news_settings import (CHECK_GIVE_UP_DAYS, CORROBORATING_GRADES, CORROBORATION_DAYS, CORROBORATION_WEIGHT,
                                    DISAGREEMENT_MIN_CLAIMS, DISAGREEMENT_STEPS, GRADE_BARS, GRADE_DROP_MARGIN,
                                    GRADE_E_MIN_CLAIMS, LAUNCH_DAYS_AFTER, LAUNCH_DAYS_BEFORE, RECORD_WINDOW_DAYS,
                                    SHORTLIST_FOR_A)
from evidence.registry_tables import read_table
from evidence.settings import REGISTRY_SATELLITES_FILE, SOURCE_RECORD_FILE

RECORD_COLUMNS = ["source_id", "address", "published_at", "claim", "constellation", "satellite", "checked_on", "result",
                  "weight", "weight_reason", "evidence", "evidence_link"]
LAUNCH_DATE = re.compile(r"\bLaunched (\d{4}-\d{2}-\d{2})\b")
GRADE_ORDER = ("A", "B", "C", "D", "E", "F")
CLAIM_CATEGORIES = {"launch": "launch", "satellite status and outages": "status"}


class Score(NamedTuple):
    claims: int
    held: int
    score: float
    failed: int


def read_record(path=SOURCE_RECORD_FILE):
    """The source-record table as rows keyed by column name."""
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            return [{name: (value or "") for name, value in row.items() if name} for row in csv.DictReader(handle)]
    except FileNotFoundError:
        return []


def append_rows(rows, path=SOURCE_RECORD_FILE):
    """Append rows to the source-record table; returns how many rows were written."""
    rows = list(rows)
    if not rows:
        return 0
    file = Path(path)
    write_header = not file.exists() or file.stat().st_size == 0
    with open(file, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECORD_COLUMNS, lineterminator="\n")
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in RECORD_COLUMNS})
    return len(rows)


def claims_from(items):
    """Claims from latest-news items: one launch/status claim per constellation named by the item."""
    claims = []
    for item in items:
        claim = CLAIM_CATEGORIES.get(item.get("category", ""))
        if not claim:
            continue
        seen = set()
        for constellation in item.get("constellations", []):
            if not constellation or constellation in seen:
                continue
            seen.add(constellation)
            claims.append({
                "source_id": item.get("source_id", ""),
                "address": item.get("address", ""),
                "published_at": item.get("published_at", ""),
                "claim": claim,
                "constellation": constellation,
                "satellite": "",
                "title": item.get("title", ""),
            })
    return claims


def launches_from(satellites=None):
    """[(constellation, launch date)] from registry data, as far as local rows can say.

    # ponytail: if a future launch date is only available from a network source, pass launches in from that caller.
    """
    satellites = satellites if satellites is not None else read_table(REGISTRY_SATELLITES_FILE)
    launches = []
    for row in satellites:
        if not (constellation := row.get("constellation", "")):
            continue
        if launch_day := _launch_day(row):
            launches.append((constellation, launch_day))
    return sorted(set(launches), key=lambda row: (row[0], row[1]))


def check_launch(claim, launches, today):
    """A launch claim is held, failed or still waiting from the launch list and claim date."""
    if claim.get("claim") != "launch":
        return None
    if not (published := _day(claim.get("published_at", ""))):
        return {"result": "could not check", "evidence": "The article gives no publish date for this launch claim.",
                "evidence_link": ""}
    # Held when the item came before the launch (by up to LAUNCH_DAYS_BEFORE) or at most LAUNCH_DAYS_AFTER after it:
    # repeating a launch the records already show earns nothing.
    start = published - timedelta(days=LAUNCH_DAYS_AFTER)
    end = published + timedelta(days=LAUNCH_DAYS_BEFORE)
    for constellation, launch_text in launches:
        launch = _day(launch_text)
        if constellation == claim.get("constellation", "") and launch and start <= launch <= end:
            return {"result": "held", "evidence": f"{constellation} launch on {launch.isoformat()}.", "evidence_link": ""}
    # ponytail: no launch in the window is not yet a failure. A "launch" item can be about a launch still to come,
    # and the registry lists only satellites still in it; mark it failed once a model reads past from future (#152).
    return None


def check_corroboration(claim, items, grade_of, today):
    """A status claim is corroborated by a different A/B source with a different title in the time window."""
    if claim.get("claim") != "status":   # a launch claim is checked against the launch list instead
        return None
    published = _day(claim.get("published_at", ""))
    if not published:
        return None
    claim_key = _title_key(claim.get("title", ""))
    window_end = published + timedelta(days=CORROBORATION_DAYS)
    for item in items:
        if item.get("source_id", "") == claim.get("source_id", ""):
            continue
        if grade_of(item.get("source_id", "")) not in CORROBORATING_GRADES:
            continue
        if _title_key(item.get("title", "")) == claim_key:
            continue
        if claim.get("constellation", "") not in item.get("constellations", []):
            continue
        if CLAIM_CATEGORIES.get(item.get("category", "")) != claim.get("claim", ""):
            continue
        if not (other_day := _day(item.get("published_at", ""))):
            continue
        if published <= other_day <= window_end:
            return {"result": "corroborated",
                    "evidence": f"Corroborated by {item.get('source_id', '')} on {other_day.isoformat()}.",
                    "evidence_link": item.get("address", "")}
    # Status claims in this PR are corroborated-or-waiting only; they are never marked failed by this check.
    return None


def check(claim, launches, items, grade_of, today):
    """One checked source-record row for this claim, or None while the check window is still open."""
    if launch_check := check_launch(claim, launches, today):
        return _row(claim, today, **launch_check)
    if corroboration := check_corroboration(claim, items, grade_of, today):
        return _row(claim, today, **corroboration)
    published = _day(claim.get("published_at", ""))
    if not published:
        return _row(claim, today, result="could not check",
                    evidence="The article gives no publish date, so this claim cannot be checked.", evidence_link="")
    if today >= published + timedelta(days=CHECK_GIVE_UP_DAYS):
        return _row(claim, today, result="could not check",
                    evidence=f"No launch or corroboration found after {CHECK_GIVE_UP_DAYS} days.", evidence_link="")
    return None


def new_rows(items, record, launches, grade_of, today):
    """Checks for new claims only, keyed by source/address/claim/constellation."""
    seen = {_claim_key(row) for row in record}
    rows = []
    for claim in claims_from(items):
        key = _claim_key(claim)
        if key in seen:
            continue
        seen.add(key)
        if found := check(claim, launches, items, grade_of, today):
            rows.append(found)
    return rows


def score(rows, today):
    """Weighted score and claim counts in the recent window."""
    weighted_held, weighted_failed = 0.0, 0.0
    claims, held, failed = 0, 0, 0
    for row in _window_rows(rows, today):
        result = row.get("result", "")
        if result not in {"held", "failed", "corroborated"}:
            continue
        claims += 1
        weight = _weight(row)
        if result == "failed":
            failed += 1
            weighted_failed += weight
        elif result == "held":
            held += 1
            weighted_held += weight
        else:
            held += 1
            weighted_held += CORROBORATION_WEIGHT * weight
    value = (weighted_held + 1.0) / (weighted_held + weighted_failed + 2.0)
    return Score(claims=claims, held=held, score=value, failed=failed)


def record_grade(rows, current, today):
    """The grade this source record proposes after one-step movement and drop rules."""
    if current == "A":
        return "A"
    stats = score(rows, today)
    target = _target_grade(stats.claims, stats.score)
    now = current if current in GRADE_ORDER else "F"
    if now == target:
        return now
    if _grade_index(target) < _grade_index(now):
        step = GRADE_ORDER[_grade_index(now) - 1]
        return "D" if step == "E" and target != "E" else step   # a source on its way up never passes through "unreliable"
    if not _drop_allowed(now, stats):
        return now
    return GRADE_ORDER[_grade_index(now) + 1]


def record_line(rows, current, today):
    """A short line saying what the source record implies right now."""
    stats = score(rows, today)
    grade = record_grade(rows, current, today)
    if stats.claims < GRADE_E_MIN_CLAIMS:
        return f"{grade} · cannot be judged yet: {stats.claims} of {GRADE_E_MIN_CLAIMS} claims checked"
    return f"{grade} · {stats.held} of {stats.claims} checked claims held · from the record, waiting for approval"


def findings(record, grades, today):
    """Source-grade findings from the source record and current source grades."""
    by_source = defaultdict(list)
    for row in record:
        if row.get("source_id"):
            by_source[row["source_id"]].append(row)
    found = []
    for source_id, rows in sorted(by_source.items()):
        current, set_by_person = grades.get(source_id, ("", False))
        current = current if current in GRADE_ORDER else "F"
        stats = score(rows, today)
        proposed = record_grade(rows, current, today)
        signal = _target_grade(stats.claims, stats.score)
        if current == "B" and _shortlisted_for_a(rows, stats, today):
            found.append(_finding_shortlist_a(source_id, current, stats))
        if current == "A" and _below_b_bar(stats):
            found.append(_finding_drop_from_a(source_id, current, stats))
        if set_by_person:
            if stats.claims >= DISAGREEMENT_MIN_CLAIMS and _grade_distance(current, signal) >= DISAGREEMENT_STEPS:
                found.append(_finding_disagreement(source_id, current, signal, stats, rows, today))
            continue
        if proposed != current and proposed != "A":
            found.append(_finding_move(source_id, current, proposed, stats, rows, today))
    return found


def _window_rows(rows, today):
    start = today - timedelta(days=RECORD_WINDOW_DAYS)
    kept = []
    for row in rows:
        if (published := _day(row.get("published_at", ""))) and start <= published <= today:
            kept.append(row)
    return kept


def _target_grade(claims, value):
    for grade, (need_claims, need_score) in GRADE_BARS.items():
        if claims >= need_claims and value >= need_score:
            return grade
    if claims >= GRADE_E_MIN_CLAIMS:
        return "E"
    return "F"


def _drop_allowed(current, stats):
    if current in GRADE_BARS:
        need_claims, need_score = GRADE_BARS[current]
        if stats.claims < need_claims:
            return True
        return stats.score < need_score - GRADE_DROP_MARGIN
    if current == "E":
        return stats.claims < GRADE_E_MIN_CLAIMS
    return False


def _shortlisted_for_a(rows, stats, today):
    need_claims, need_score, days_without_failed = SHORTLIST_FOR_A
    return stats.claims >= need_claims and stats.score >= need_score and not _failed_since(rows, today, days_without_failed)


def _below_b_bar(stats):
    need_claims, need_score = GRADE_BARS["B"]
    return stats.claims < need_claims or stats.score < need_score


def _failed_since(rows, today, days):
    start = today - timedelta(days=days)
    for row in rows:
        when = _day(row.get("published_at", ""))
        if when and start <= when <= today and row.get("result") == "failed":
            return True
    return False


def _finding_move(source_id, current, proposed, stats, rows, today):
    action = "Raise" if _grade_index(proposed) < _grade_index(current) else "Drop"
    statement = (f"{action} {source_id} from {current} to {proposed}: {stats.held} of {stats.claims} checked claims held "
                 f"(score {stats.score:.2f}).")
    return {"id": f"source-grade-move-{_id_part(source_id)}", "category": "Source grade", "statement": statement,
            "detail": f"From the source record in the last {RECORD_WINDOW_DAYS} days; waiting for a person's approval.",
            "sources": [_source_row(source_id, rows, current, today)],
            "measured": _measured_rows(stats)}


def _finding_shortlist_a(source_id, current, stats):
    days_without_failed = SHORTLIST_FOR_A[2]
    statement = (f"Shortlisted for A: {source_id} has {stats.held} of {stats.claims} checked claims held "
                 f"(score {stats.score:.2f}) and no failed claim in {days_without_failed} days.")
    return {"id": f"source-grade-shortlist-a-{_id_part(source_id)}", "category": "Source grade", "statement": statement,
            "detail": "A person decides A after reviewing this shortlist finding.",
            "sources": [{"source": source_id, "line": f"Current grade {current}.", "grade": current}],
            "measured": _measured_rows(stats)}


def _finding_drop_from_a(source_id, current, stats):
    need_claims, need_score = GRADE_BARS["B"]
    statement = (f"Shortlisted to drop from A: {source_id} is below the B bar "
                 f"({stats.claims} claims, score {stats.score:.2f}; B needs {need_claims} and {need_score:.2f}).")
    return {"id": f"source-grade-drop-a-{_id_part(source_id)}", "category": "Source grade", "statement": statement,
            "detail": "A person reviews whether A should be kept.",
            "sources": [{"source": source_id, "line": "Current grade A.", "grade": current}],
            "measured": _measured_rows(stats)}


def _finding_disagreement(source_id, current, proposed, stats, rows, today):
    statement = (f"The record disagrees with the grade set by a person: {source_id} is {current}, "
                 f"while the record points to {proposed} ({stats.held} of {stats.claims} held, score {stats.score:.2f}).")
    return {"id": f"source-grade-disagree-{_id_part(source_id)}", "category": "Source grade", "statement": statement,
            "detail": "The person's grade stays unless the team chooses to change it.",
            "sources": [_source_row(source_id, rows, current, today)],
            "measured": _measured_rows(stats)}


def _source_row(source_id, rows, grade, today):
    return {"source": source_id, "line": record_line(rows, grade, today), "grade": grade}


def _measured_rows(stats):
    return [{"what": "Checked claims", "value": str(stats.claims)},
            {"what": "Held claims", "value": str(stats.held)},
            {"what": "Score", "value": f"{stats.score:.2f}"}]


def _row(claim, today, result, evidence, evidence_link):
    return {"source_id": claim.get("source_id", ""), "address": claim.get("address", ""),
            "published_at": claim.get("published_at", ""), "claim": claim.get("claim", ""),
            "constellation": claim.get("constellation", ""), "satellite": claim.get("satellite", ""),
            "checked_on": today.isoformat(), "result": result, "weight": "", "weight_reason": "",
            "evidence": evidence, "evidence_link": evidence_link}


def _claim_key(row):
    return "|".join(row.get(name, "") for name in ("source_id", "address", "claim", "constellation"))


def _title_key(title):
    return " ".join((title or "").split()).casefold()


def _weight(row):
    try:
        return int((row.get("weight") or "").strip() or "1")
    except ValueError:
        return 1


def _grade_index(grade):
    return GRADE_ORDER.index(grade if grade in GRADE_ORDER else "F")


def _grade_distance(one, two):
    return abs(_grade_index(one) - _grade_index(two))


def _id_part(source_id):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", source_id).strip("-") or "source"


def _launch_day(row):
    if found := LAUNCH_DATE.search(row.get("note", "")):
        return found.group(1)
    return ""


def _day(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
