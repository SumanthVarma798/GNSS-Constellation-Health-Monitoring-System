"""Source-record weekly build script and workflow contract."""
import csv
import sys
from pathlib import Path

from evidence.archive import record
from evidence.news_settings import RECORD_GRADED_BY

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_source_record  # noqa: E402


def _write_rows(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_build_source_record_script_writes_record_grades_rejected_and_report(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    archive.mkdir()
    feed = "https://press.example/feed/"
    body = b"""<rss><channel><item><title>GPS launch notice</title><link>https://press.example/story</link>
               <pubDate>Fri, 10 Oct 2026 00:00:00 +0000</pubDate></item></channel></rss>"""
    record(archive, feed, "2026-10-20T00:10:00Z", 200, body)
    monkeypatch.setattr(build_source_record.news, "working_candidates",
                        lambda: [{"source_id": "press.example", "kind": "press feed", "address": feed,
                                  "check_type": "feed; application/rss+xml"}])
    monkeypatch.setattr(build_source_record.source_record, "launches_from", lambda satellites=None: [("GPS", "2026-10-10")])

    record_file = tmp_path / "source_record.csv"
    grade_file = tmp_path / "source_grades.csv"
    rejected_file = tmp_path / "source_record_rejected.csv"
    report_file = tmp_path / "report.md"
    _write_rows(record_file, build_source_record.source_record.RECORD_COLUMNS, [
        {"source_id": "press.example", "address": "https://press.example/a", "published_at": "2026-10-09",
         "claim": "status", "constellation": "GPS", "satellite": "", "checked_on": "2026-10-10", "result": "held",
         "weight": "", "weight_reason": "", "evidence": "e", "evidence_link": ""},
        {"source_id": "press.example", "address": "https://press.example/b", "published_at": "2026-10-08",
         "claim": "status", "constellation": "GPS", "satellite": "", "checked_on": "2026-10-10", "result": "held",
         "weight": "", "weight_reason": "", "evidence": "e", "evidence_link": ""},
    ])
    _write_rows(grade_file, build_source_record.SOURCE_GRADE_COLUMNS, [
        {"source_id": "press.example", "name": "Press", "reliability": "F", "graded_by": RECORD_GRADED_BY,
         "graded_on": "2026-10-01", "reason": "old"},
    ])
    _write_rows(rejected_file, build_source_record.SOURCE_RECORD_REJECTED_COLUMNS, [])

    monkeypatch.setattr(build_source_record, "SOURCE_RECORD_FILE", record_file)
    monkeypatch.setattr(build_source_record, "SOURCE_GRADES_FILE", grade_file)
    monkeypatch.setattr(build_source_record, "SOURCE_RECORD_REJECTED_FILE", rejected_file)
    monkeypatch.setattr(build_source_record, "REGISTRY_SATELLITES_FILE", "unused.csv")
    monkeypatch.setattr(build_source_record, "read_table", lambda _path: [])
    monkeypatch.setattr(sys, "argv", ["build_source_record.py", "--archive", str(archive), "--report", str(report_file),
                                      "--today", "2026-10-20"])

    build_source_record.main()

    with open(record_file, newline="", encoding="utf-8") as handle:
        record_rows = list(csv.DictReader(handle))
    with open(grade_file, newline="", encoding="utf-8") as handle:
        grade_rows = list(csv.DictReader(handle))
    with open(rejected_file, newline="", encoding="utf-8") as handle:
        rejected_rows = list(csv.DictReader(handle))
    report = report_file.read_text(encoding="utf-8")

    assert len(record_rows) == 3
    assert next(row for row in grade_rows if row["source_id"] == "press.example")["reliability"] == "D"
    assert rejected_rows == []
    assert "Source-grade findings this week" in report and "<!-- findings" in report


def test_source_record_workflow_schedule_branch_label_and_added_files():
    workflow = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "source-record.yml").read_text()

    assert "name: Source record" in workflow
    assert "- cron: '0 2 * * 0'" in workflow
    assert "git switch -C source-record" in workflow
    assert '--label "decision: source grade"' in workflow
    assert "git add evidence/source_record.csv evidence/source_grades.csv evidence/source_record_rejected.csv" in workflow
    assert "git diff --quiet -- evidence/source_record.csv evidence/source_grades.csv evidence/source_record_rejected.csv" in workflow


def test_a_rejection_is_traced_to_its_source_through_the_open_proposals_own_findings():
    from datetime import date
    from evidence import decisions
    from evidence.decision_settings import REJECT

    body = decisions.findings_block([{"id": "source-grade-move-new-example", "category": "Source grade",
                                      "statement": "Raise new.example from F to D.", "detail": "",
                                      "sources": [{"source": "new.example", "line": "line", "grade": "F"}],
                                      "measured": []}])
    rows = build_source_record.add_rejections([], {"source-grade-move-new-example": REJECT},
                                              decisions.findings(body), [{"source_id": "new.example"}] * 4,
                                              date(2026, 10, 27))

    assert rows == [{"source_id": "new.example", "finding_id": "source-grade-move-new-example",
                     "claims_at_rejection": "4", "decided_on": "2026-10-27"}]


def test_rejections_are_read_from_every_version_and_keep_their_first_claim_count():
    from datetime import date
    from evidence.decision_settings import APPROVE, REJECT

    def marker(choice, finding_id, sha):
        return {"body": f"<!-- admin-finding-decision: {choice}; finding: {finding_id}; sha: {sha} -->\nDecision."}

    comments = [marker(REJECT, "source-grade-move-a-example", "old"), marker(APPROVE, "source-grade-move-b-example", "new")]
    assert build_source_record.latest_decisions(comments) == {"source-grade-move-a-example": REJECT,
                                                              "source-grade-move-b-example": APPROVE}

    first = [{"source_id": "a.example", "finding_id": "source-grade-move-a-example", "claims_at_rejection": "4",
              "decided_on": "2026-10-20"}]
    again = build_source_record.add_rejections(first, {"source-grade-move-a-example": REJECT}, [],
                                               [{"source_id": "a.example"}] * 9, date(2026, 10, 27))
    assert again == first
