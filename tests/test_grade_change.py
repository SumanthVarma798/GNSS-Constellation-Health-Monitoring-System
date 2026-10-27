"""Change a source grade from the console (evidence/grade_change.py)."""
import base64
from datetime import date, datetime, timezone

import pytest

from evidence import decisions, grade_change
from evidence.decision_settings import LABEL_PREFIX

NOW = datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)
TODAY = date(2026, 10, 20)
CSV = ("source_id,name,reliability,graded_by,graded_on,reason\n"
       "site.org,Site,B,someone,2026-10-09,why\n")


class FakeGitHub:
    def __init__(self):
        self.calls = []
        self.file_sha = "filesha"
        self.main_sha = "mainsha"

    def __call__(self, method, path, token, repository=None, **request):
        self.calls.append((method, path, repository, request.get("json"), request.get("params")))
        if method == "GET" and path == "/git/ref/heads/main":
            return {"object": {"sha": self.main_sha}}
        if method == "GET" and path.endswith("source_grades.csv"):
            return {"content": base64.b64encode(CSV.encode()).decode(), "sha": self.file_sha}
        if method == "POST" and path == "/git/refs":
            return {}
        if method == "PUT" and path.endswith("source_grades.csv"):
            return {}
        if method == "POST" and path == "/pulls":
            return {"number": 42, "html_url": "https://github.com/x/pull/42"}
        if method == "POST" and path == "/issues/42/labels":
            return {}
        raise AssertionError((method, path))


def test_new_grades_csv_replaces_a_row():
    text = grade_change.new_grades_csv(CSV, "site.org", "Site", "A", "More trusted now", "Ada", TODAY)

    assert "site.org,Site,A,Ada (from the console),2026-10-20,More trusted now" in text
    assert text.count("site.org") == 1


def test_new_grades_csv_adds_a_new_row():
    text = grade_change.new_grades_csv(CSV, "new.org", "New", "C", "A careful source", "Ada", TODAY)

    assert "new.org,New,C,Ada (from the console)" in text
    assert "site.org,Site,B" in text


def test_validation_stops_before_any_github_call():
    github = FakeGitHub()
    names = {"site.org": "Site"}

    assert grade_change.validate("missing", "A", "three word reason", names, "B")
    assert grade_change.validate("site.org", "Z", "three word reason", names, "B")
    assert grade_change.validate("site.org", "A", "too short", names, "B")
    assert grade_change.validate("site.org", "B", "same grade as before", names, "B") is not None
    assert grade_change.validate("site.org", "A", "good reason here", names, "B") is None
    assert github.calls == []


def test_submit_opens_a_branch_pull_request_label_and_findings_block():
    github = FakeGitHub()
    tone, words = grade_change.submit("t", "site.org", "Site", "B", "A", "Trusted after review", "Ada", TODAY,
                                      now=NOW, ask=github)

    assert tone == "ok" and "42" in words
    methods = [(m, p) for m, p, *_ in github.calls]
    assert methods[0] == ("GET", "/git/ref/heads/main")
    assert methods[1] == ("GET", "/contents/evidence/source_grades.csv")
    assert methods[2] == ("POST", "/git/refs")
    assert methods[2][0] == "POST"
    branch_ref = github.calls[2][3]["ref"]
    assert branch_ref.startswith("refs/heads/grade-change/site-org-202610201530")
    put = github.calls[3][3]
    assert put["branch"] == branch_ref.removeprefix("refs/heads/")
    pr_body = github.calls[4][3]["body"]
    pr_title = github.calls[4][3]["title"]
    assert pr_title == "Source grade: Site to A (from the console)"
    assert github.calls[5][3]["labels"] == [f"{LABEL_PREFIX}source grade"]
    found = decisions.findings(pr_body)
    assert found[0]["id"] == "grade-change-site-org"
    assert found[0]["category"] == "Source grade"
    assert decisions.findings(pr_body) == decisions.findings(pr_body)
