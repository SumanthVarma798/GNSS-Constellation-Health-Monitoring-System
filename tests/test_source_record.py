"""Checked-claim record logic for source grades (evidence/source_record.py)."""
from datetime import date, timedelta

import pytest

from evidence import decisions, source_record
from evidence.news_settings import RECORD_GRADED_BY

TODAY = date(2026, 10, 20)


def claim(**changes):
    row = {
        "source_id": "alpha.example",
        "address": "https://alpha.example/one",
        "published_at": "2026-10-10T00:00:00Z",
        "claim": "launch",
        "constellation": "GPS",
        "satellite": "",
        "title": "GPS launch notice",
    }
    row.update(changes)
    return row


def record_row(source_id, at_days, result, weight=""):
    day = (TODAY - timedelta(days=at_days)).isoformat()
    return {"source_id": source_id, "address": f"https://{source_id}/{at_days}", "published_at": day, "claim": "status",
            "constellation": "GPS", "satellite": "", "checked_on": TODAY.isoformat(), "result": result, "weight": weight,
            "weight_reason": "", "evidence": "e", "evidence_link": ""}


def test_check_launch_holds_on_a_launch_and_never_fails_without_one():
    held = source_record.check_launch(claim(), [("GPS", "2026-10-09")], TODAY)
    failed = source_record.check_launch(claim(), [], TODAY)
    waiting = source_record.check_launch(claim(), [], date(2026, 10, 12))

    assert held["result"] == "held"
    assert failed is None   # may be a launch still to come: not a failure until a model reads past from future
    assert waiting is None


def test_a_claim_published_five_days_after_the_launch_is_not_held():
    checked = source_record.check_launch(
        claim(published_at="2026-10-15T00:00:00Z"),
        [("GPS", "2026-10-10")],
        TODAY,
    )

    assert checked is None   # not held: the claim came too long after the launch


def test_check_corroboration_needs_another_a_or_b_source_with_a_different_title():
    status = claim(claim="status", title="GPS outage notice")
    items = [
        {"source_id": "alpha.example", "category": "satellite status and outages", "title": "Independent report",
         "constellations": ["GPS"], "published_at": "2026-10-11T00:00:00Z", "address": "https://alpha.example/two"},
        {"source_id": "beta.example", "category": "satellite status and outages", "title": "Independent report",
         "constellations": ["GPS"], "published_at": "2026-10-11T00:00:00Z", "address": "https://beta.example/two"},
        {"source_id": "gamma.example", "category": "satellite status and outages", "title": "gps  outage  notice",
         "constellations": ["GPS"], "published_at": "2026-10-11T00:00:00Z", "address": "https://gamma.example/two"},
        {"source_id": "delta.example", "category": "satellite status and outages", "title": "GPS status update",
         "constellations": ["GPS"], "published_at": "2026-10-12T00:00:00Z", "address": "https://delta.example/two"},
    ]
    grades = {"beta.example": "C", "gamma.example": "A", "delta.example": "B"}

    checked = source_record.check_corroboration(status, items, lambda source_id: grades.get(source_id, ""), TODAY)

    assert checked["result"] == "corroborated"
    assert checked["evidence_link"] == "https://delta.example/two"


def test_check_marks_claim_could_not_check_after_the_give_up_window():
    checked = source_record.check(
        claim(claim="status", published_at="2026-09-10T00:00:00Z"),
        launches=[],
        items=[],
        grade_of=lambda _source_id: "",
        today=TODAY,
    )

    assert checked["result"] == "could not check"


def test_score_counts_blank_and_set_weights():
    rows = [
        record_row("held.example", 1, "held", ""),
        record_row("corr.example", 2, "corroborated", "2"),
        record_row("failed.example", 3, "failed", "3"),
        record_row("skip.example", 4, "could not check", "5"),
    ]

    scored = source_record.score(rows, TODAY)

    assert scored.claims == 3
    assert scored.held == 2
    assert scored.failed == 1
    assert scored.score == pytest.approx(3 / 7, rel=1e-6)


def test_record_grade_uses_bars_one_step_moves_and_drop_margin():
    b_rows = [record_row("bar.example", i, "held") for i in range(10)]
    c_border_rows = [record_row("bar.example", i, "held") for i in range(4)] + [record_row("bar.example", 10, "failed")]
    c_low_rows = [record_row("bar.example", i, "held") for i in range(3)] + [record_row("bar.example", 10 + i, "failed")
                                                                               for i in range(2)]

    assert source_record.record_grade(b_rows, "", TODAY) == "D"   # blank current counts as F; on the way up it skips E
    assert source_record.record_grade(b_rows, "E", TODAY) == "D"
    assert source_record.record_grade(b_rows, "D", TODAY) == "C"
    assert source_record.record_grade(b_rows, "C", TODAY) == "B"
    assert source_record.record_grade(b_rows, "B", TODAY) == "B"   # record never proposes A
    assert source_record.record_grade(c_border_rows, "C", TODAY) == "C"   # below C bar, but not past drop margin
    assert source_record.record_grade(c_low_rows, "C", TODAY) == "D"
    assert source_record.record_grade(c_low_rows[:2], "E", TODAY) == "F"
    assert source_record.record_grade(c_low_rows, "A", TODAY) == "A"


def test_record_line_words_for_judged_and_not_yet_judged():
    judged = source_record.record_line([record_row("line.example", i, "held") for i in range(3)], "F", TODAY)
    not_yet = source_record.record_line([record_row("line.example", 1, "held")], "F", TODAY)

    assert "from the record, waiting for approval" in judged
    assert not_yet == "F · cannot be judged yet: 1 of 3 claims checked"


def test_findings_cover_moves_shortlists_and_person_grade_disagreement():
    record = []
    record += [record_row("move.example", i, "held") for i in range(3)]         # F -> E move
    record += [record_row("short.example", i, "held") for i in range(20)]       # shortlisted for A
    record += [record_row("drop.example", i, "held") for i in range(4)]         # below B bar
    record += [record_row("person.example", i, "failed") for i in range(5)]     # disagrees with a person's B
    grades = {
        "move.example": ("F", False),
        "short.example": ("B", False),
        "drop.example": ("A", False),
        "person.example": ("B", True),
    }

    found = source_record.findings(record, grades, TODAY)
    by_id = {row["id"]: row for row in found}

    assert "source-grade-move-move-example" in by_id
    assert "source-grade-shortlist-a-short-example" in by_id
    assert "source-grade-drop-a-drop-example" in by_id
    assert "source-grade-disagree-person-example" in by_id
    assert "source-grade-move-person-example" not in by_id

    seen = set()
    for finding in found:
        assert decisions._clean_finding(finding, seen) == {k: v for k, v in finding.items() if k != "target_grade"}


def test_a_launch_claim_holds_before_the_launch_or_within_a_day_after_it():
    launches = [("GPS", "2026-10-10")]
    early = source_record.check_launch(claim(published_at="2026-10-08T00:00:00Z"), launches, TODAY)
    next_day = source_record.check_launch(claim(published_at="2026-10-11T00:00:00Z"), launches, TODAY)
    late = source_record.check_launch(claim(published_at="2026-10-12T00:00:00Z"), launches, TODAY)

    assert early["result"] == "held"
    assert next_day["result"] == "held"
    assert late is None   # two days after the launch: the records already showed it


def test_a_launch_claim_is_not_corroborated_by_news_alone():
    launch = claim(claim="launch", title="GPS launch")
    items = [{"source_id": "alpha.example", "category": "launch", "title": "Another GPS launch report",
              "constellations": ["GPS"], "published_at": "2026-10-11T00:00:00Z", "address": "https://alpha.example/3"}]

    assert source_record.check_corroboration(launch, items, lambda source_id: "A", TODAY) is None


def test_an_ungraded_source_with_a_poor_record_goes_to_e_not_d():
    poor = [record_row("poor.example", i, "failed") for i in range(3)]

    assert source_record.record_grade(poor, "", TODAY) == "E"


def test_grade_table_marks_only_the_records_own_rows_as_not_set_by_a_person():
    table = source_record.grade_table([
        {"source_id": "record.example", "reliability": "D", "graded_by": RECORD_GRADED_BY},
        {"source_id": "person.example", "reliability": "B", "graded_by": "Team review"},
    ])

    assert table == {"record.example": ("D", False), "person.example": ("B", True)}


def test_grade_changes_cover_move_shortlist_drop_and_disagreement_and_apply_changes_updates_rows():
    found = [
        {"id": "source-grade-move-move-example", "statement": "Raise move.example from F to D.", "detail": "",
         "sources": [{"source": "move.example", "line": "line", "grade": "F"}], "measured": [], "category": "Source grade",
         "target_grade": "D"},
        {"id": "source-grade-shortlist-a-short-example", "statement": "Shortlisted for A: short.example ...",
         "detail": "", "sources": [{"source": "short.example", "line": "line", "grade": "B"}], "measured": [],
         "category": "Source grade", "target_grade": "A"},
        {"id": "source-grade-drop-a-drop-example", "statement": "Shortlisted to drop from A: drop.example ...",
         "detail": "", "sources": [{"source": "drop.example", "line": "line", "grade": "A"}], "measured": [],
         "category": "Source grade", "target_grade": "B"},
        {"id": "source-grade-disagree-disagree-example", "statement": "The record disagrees with ...",
         "detail": "", "sources": [{"source": "disagree.example", "line": "line", "grade": "B"}], "measured": [],
         "category": "Source grade", "target_grade": "D"},
    ]

    changes = source_record.grade_changes(found, TODAY, {"move.example": "Move Source"})
    by_source = {row["source_id"]: row for row in changes}

    assert by_source["move.example"]["reliability"] == "D"
    assert by_source["short.example"]["reliability"] == "A"
    assert by_source["drop.example"]["reliability"] == "B"
    assert by_source["disagree.example"]["reliability"] == "D"
    assert by_source["move.example"]["graded_by"] == RECORD_GRADED_BY
    assert by_source["move.example"]["name"] == "Move Source"
    assert by_source["short.example"]["name"] == "short.example"

    rows = [{"source_id": "keep.example", "name": "Keep", "reliability": "C", "graded_by": "Team", "graded_on": "2026-10-01",
             "reason": "keep"},
            {"source_id": "move.example", "name": "Old move", "reliability": "F", "graded_by": "Team",
             "graded_on": "2026-10-01", "reason": "old"}]
    updated = source_record.apply_changes(rows, changes[:2])

    assert [row["source_id"] for row in updated] == ["keep.example", "move.example", "short.example"]
    assert next(row for row in updated if row["source_id"] == "move.example")["reliability"] == "D"
    assert next(row for row in updated if row["source_id"] == "short.example")["reliability"] == "A"


def test_still_rejected_waits_for_three_more_checked_claims():
    found = [{"id": "source-grade-move-alpha-example", "category": "Source grade", "statement": "Raise alpha.example ...",
              "detail": "", "sources": [{"source": "alpha.example", "line": "line", "grade": "F"}], "measured": []}]
    rejected = [{"source_id": "alpha.example", "finding_id": "source-grade-move-alpha-example",
                 "claims_at_rejection": "4", "decided_on": "2026-10-20"}]
    six_claims = [record_row("alpha.example", i, "held") for i in range(6)]
    seven_claims = [record_row("alpha.example", i, "held") for i in range(7)]

    assert source_record.still_rejected(found, rejected, six_claims) == []
    assert [row["id"] for row in source_record.still_rejected(found, rejected, seven_claims)] == [
        "source-grade-move-alpha-example"]


def test_propose_builds_new_rows_finds_a_move_and_returns_the_source_grade_row():
    items = [{"source_id": "alpha.example", "address": "https://alpha.example/story", "published_at": "2026-10-10",
              "title": "GPS launch notice", "category": "launch", "constellations": ["GPS"]}]
    record = [record_row("alpha.example", 2, "held"), record_row("alpha.example", 1, "held")]
    grades = [{"source_id": "alpha.example", "name": "Alpha", "reliability": "F", "graded_by": RECORD_GRADED_BY,
               "graded_on": "2026-10-01", "reason": "old"}]

    new_rows, found, grade_rows = source_record.propose(
        items=items,
        record=record,
        grade_rows=grades,
        rejected_rows=[],
        launches=[("GPS", "2026-10-10")],
        today=TODAY,
        names={"alpha.example": "Alpha"},
    )

    assert len(new_rows) == 1 and new_rows[0]["result"] == "held"
    assert [row["id"] for row in found] == ["source-grade-move-alpha-example"]
    assert next(row for row in grade_rows if row["source_id"] == "alpha.example")["reliability"] == "D"


def test_report_carries_findings_block_with_the_same_finding_ids():
    found = [{"id": "source-grade-move-alpha-example", "category": "Source grade", "statement": "Raise alpha.example ...",
              "detail": "detail", "sources": [{"source": "alpha.example", "line": "line", "grade": "F"}], "measured": []}]

    body = source_record.report([record_row("alpha.example", 1, "held")], found)
    parsed = decisions.findings(body)

    assert [row["id"] for row in parsed] == ["source-grade-move-alpha-example"]


def test_a_persons_a_below_the_b_bar_gets_only_the_drop_finding():
    rows = [record_row("person-a.example", i, "failed") for i in range(6)]

    found = source_record.findings(rows, {"person-a.example": ("A", True)}, TODAY)

    assert [finding["id"] for finding in found] == ["source-grade-drop-a-person-a-example"]
    assert found[0]["target_grade"] == "B"
