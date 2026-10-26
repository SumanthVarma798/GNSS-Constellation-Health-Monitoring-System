"""The sources at a glance (evidence/source_overview.py)."""
import pytest

from evidence.source_overview import overview, source_rows


def test_the_real_tables_add_up():
    seen = overview()

    assert seen["graded"] >= 3 and seen["candidates"] == sum(seen["proposed"].values())
    assert "not fetched" not in seen["not_answering"]   # held back by rule is not "not answering"


def test_answers_are_said_in_words_and_counted(tmp_path):
    grades, candidates = tmp_path / "g.csv", tmp_path / "c.csv"
    grades.write_text("source_id,name,reliability,graded_by,graded_on,reason\nx,X,B,someone,2026-10-09,why\n")
    candidates.write_text("source_id,check_status,proposed_grade\na,200,A\nb,403,A\nc,403,C\nd,timed out,\ne,not fetched,A\n")

    seen = overview(grades, candidates)

    assert seen["graded"] == 1 and seen["candidates"] == 5
    assert seen["proposed"] == {"A": 3, "C": 1, "": 1}
    assert seen["not_answering"] == {"refused (403)": 2, "timed out": 1}


GRADES = "source_id,name,reliability,graded_by,graded_on,reason\nsite.org,Site,B,someone,2026-10-09,A scientific body\nalone.org,Alone,C,someone,2026-10-09,One expert\n"
CANDIDATES = ("source_id,name,kind,address,checked_on,check_status,proposed_grade,grade_reason,standing\n"
              "site.org,Site news,press feed,https://site.org/feed,2026-10-19,200,B,A scientific body,graded\n"
              "site.org,Site page,official page,https://site.org/,2026-10-19,403,B,A scientific body,graded\n"
              "op.gov,Operator,official page,https://op.gov/,2026-10-19,200,A,The operator,provisional\n"
              "agg.com,Aggregator,discovery feed,https://agg.com/rss,2026-10-19,200,,,no grade: discovery or pointer\n"
              "held.ru,Held centre,official page,https://held.ru/,2026-10-19,not fetched,A,The operator,held: not fetched\n")


def tables(tmp_path):
    grades, candidates = tmp_path / "g.csv", tmp_path / "c.csv"
    grades.write_text(GRADES)
    candidates.write_text(CANDIDATES)
    return grades, candidates


def test_each_feed_is_a_row_and_a_graded_site_with_no_feed_is_one_too(tmp_path):
    rows = source_rows(*tables(tmp_path))

    assert [r["name"] for r in rows] == ["Site news", "Site page", "Operator", "Aggregator", "Held centre", "Alone"]


def test_a_sites_confirmed_grade_covers_all_its_feeds_and_a_proposal_says_so(tmp_path):
    rows = {r["name"]: r for r in source_rows(*tables(tmp_path))}

    assert (rows["Site page"]["grade"], rows["Site page"]["confirmed"]) == ("B", True)
    assert (rows["Operator"]["grade"], rows["Operator"]["confirmed"]) == ("A", False)
    assert rows["Aggregator"]["grade"] == "" and rows["Alone"]["confirmed"] and rows["Alone"]["reason"] == "One expert"


@pytest.mark.parametrize("name, shown", [("Site news", "graded"), ("Site page", "not answering"), ("Operator", "awaiting a grade"),
                                         ("Aggregator", "no grade"), ("Held centre", "held")])
def test_each_row_falls_in_one_filter_by_what_matters_most(tmp_path, name, shown):
    rows = {r["name"]: r for r in source_rows(*tables(tmp_path))}

    assert rows[name]["group"] == shown


def test_the_answer_at_the_last_check_is_said_in_words(tmp_path):
    rows = {r["name"]: r for r in source_rows(*tables(tmp_path))}

    assert rows["Site news"]["answer"] == ("ok", "answered") and rows["Site page"]["answer"] == ("warn", "refused (403)")
    assert rows["Held centre"]["answer"] == ("idle", "not fetched: held by rule") and rows["Alone"]["answer"] == ("idle", "not checked here")
