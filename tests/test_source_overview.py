"""The sources at a glance (evidence/source_overview.py)."""
from evidence.source_overview import overview


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
