"""Build this week's checked-claims record and source-grade proposal.

    python scripts/build_source_record.py --archive archive --report source-record.md
    python scripts/build_source_record.py --archive archive --report source-record.md \
        --rejected-comments comments.json --open-body body.md --carried-rejected rejected.csv
"""
import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence import decisions, news, source_record
from evidence.decision_settings import REJECT
from evidence.registry_tables import read_table
from evidence.settings import (REGISTRY_SATELLITES_FILE, SOURCE_GRADE_COLUMNS, SOURCE_GRADES_FILE, SOURCE_RECORD_FILE,
                               SOURCE_RECORD_REJECTED_COLUMNS, SOURCE_RECORD_REJECTED_FILE)
from evidence.sources import candidate_rows


def read_rows(path):
    """CSV rows from a file, or [] when it does not exist yet."""
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            return [{name: (value or "") for name, value in row.items() if name} for row in csv.DictReader(handle)]
    except FileNotFoundError:
        return []


def write_rows(path, columns, rows):
    """Write rows with a header to one CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in columns})


def read_comments(path):
    """Issue comments from gh api output, or [] if the file is empty."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return []
    loaded = json.loads(text)
    return loaded if isinstance(loaded, list) else []


def names_table(grade_rows, claim_rows):
    """{source id: display name} from known grades, candidates and this week's claims."""
    names = {}
    for row in grade_rows:
        source_id = row.get("source_id", "")
        if source_id and row.get("name", ""):
            names[source_id] = row["name"]
    for row in candidate_rows():
        source_id = row.get("source_id", "")
        if source_id and row.get("name", ""):
            names.setdefault(source_id, row["name"])
    for row in claim_rows:
        source_id = row.get("source_id", "")
        if source_id:
            names.setdefault(source_id, source_id)
    return names


def latest_decisions(comments):
    """{finding id: choice} from every decision comment, whichever version it was made on; the latest wins."""
    found = {}
    for comment in comments:
        if parsed := decisions._finding_marker(comment.get("body", "")):
            found[parsed["id"]] = parsed["choice"]
    return found


def add_rejections(rejected_rows, decisions_by_id, findings, record, today):
    """Rejected-finding rows upserted by finding id."""
    if not decisions_by_id:
        return rejected_rows
    source_by_finding = {}
    for row in findings:
        source_by_finding.setdefault(row.get("id", ""), source_record._finding_source_id(row))
    claims_now = {}
    for row in record:
        source_id = row.get("source_id", "")
        if source_id:
            claims_now[source_id] = claims_now.get(source_id, 0) + 1
    existing = {row.get("finding_id", ""): row for row in rejected_rows if row.get("finding_id", "")}
    order = [row.get("finding_id", "") for row in rejected_rows if row.get("finding_id", "")]
    for finding_id, choice in decisions_by_id.items():
        if choice != REJECT or finding_id in existing:   # a rejection keeps the claim count it was made at
            continue
        source_id = source_by_finding.get(finding_id, existing.get(finding_id, {}).get("source_id", ""))
        if not source_id:
            continue
        existing[finding_id] = {"source_id": source_id, "finding_id": finding_id,
                                "claims_at_rejection": str(claims_now.get(source_id, 0)),
                                "decided_on": today.isoformat()}
        if finding_id not in order:
            order.append(finding_id)
    return [existing[finding_id] for finding_id in order if finding_id in existing]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="archive folder with objects/ and versions.csv")
    parser.add_argument("--report", required=True, help="write the pull-request body markdown here")
    parser.add_argument("--rejected-comments", help="JSON from gh api issues/<n>/comments for the open source-record PR")
    parser.add_argument("--carried-rejected", help="source_record_rejected.csv from the last proposal's own branch")
    parser.add_argument("--open-body", help="the open source-record PR's body, which names the source of each finding")
    parser.add_argument("--today", help="day to use as YYYY-MM-DD (default: today UTC)")
    args = parser.parse_args()

    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else datetime.now(timezone.utc).date()
    archived, _ = news.collected_items(args.archive)
    claim_rows = news.claim_items(archived)
    record = source_record.read_record(SOURCE_RECORD_FILE)
    grade_rows = read_rows(SOURCE_GRADES_FILE)
    rejected_rows = read_rows(SOURCE_RECORD_REJECTED_FILE)
    launches = source_record.launches_from(read_table(REGISTRY_SATELLITES_FILE))
    names = names_table(grade_rows, claim_rows)

    if args.carried_rejected:   # the last proposal's branch is rebuilt from main each week: carry its rejections over
        known = {row.get("finding_id", "") for row in rejected_rows}
        rejected_rows += [row for row in read_rows(args.carried_rejected) if row.get("finding_id", "") not in known]
    if args.rejected_comments:
        finding_choices = latest_decisions(read_comments(args.rejected_comments))
        grades = source_record.grade_table(grade_rows)
        # Claims as the proposal counted them: main's record plus the rows it added and has not merged.
        checked = record + source_record.new_rows(claim_rows, record, launches,
                                                  lambda source_id: grades.get(source_id, ("", False))[0], today)
        base_findings = source_record.findings(checked, grades, today)
        if args.open_body:   # the open PR's own findings first: they include moves this week's rows made possible
            base_findings = decisions.findings(Path(args.open_body).read_text(encoding="utf-8")) + base_findings
        rejected_rows = add_rejections(rejected_rows, finding_choices, base_findings, checked, today)

    new_rows, found, new_grades = source_record.propose(claim_rows, record, grade_rows, rejected_rows, launches, today, names)
    source_record.append_rows(new_rows, SOURCE_RECORD_FILE)
    write_rows(SOURCE_GRADES_FILE, SOURCE_GRADE_COLUMNS, new_grades)
    write_rows(SOURCE_RECORD_REJECTED_FILE, SOURCE_RECORD_REJECTED_COLUMNS, rejected_rows)
    Path(args.report).write_text(source_record.report(new_rows, found), encoding="utf-8")
    print(f"{len(new_rows)} claims checked; {len(found)} findings proposed.")


if __name__ == "__main__":
    main()
