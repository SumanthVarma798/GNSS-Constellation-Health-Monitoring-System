"""The sources at a glance (evidence/source_overview.py)."""
import pytest

from datetime import datetime, timezone

from evidence.source_overview import ago_words, archive_read_times, overview, source_rows


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


def test_a_short_line_reads_as_empty_fields_and_not_fetched_is_held_only_when_held(tmp_path):
    grades, candidates = tables(tmp_path)
    candidates.write_text(CANDIDATES + "short.org,Short\n" + "odd.org,Odd,page,https://odd.org/,2026-10-19,not fetched,C,Why,provisional\n")

    rows = {r["name"]: r for r in source_rows(grades, candidates)}

    assert rows["Short"]["address"] == "" and rows["Short"]["group"] == "not answering"
    assert rows["Odd"]["answer"] == ("idle", "not fetched") and rows["Held centre"]["answer"][1] == "not fetched: held by rule"


NOW = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)


def test_archive_read_times_take_the_newest_group_run_and_all_runs():
    from evidence.sources import ARCHIVED_SOURCES, CELESTRAK_GNSS_URL

    news_addr = ARCHIVED_SOURCES["news"][0]
    log = [{"job": "archive news", "started": "2026-10-19T10:00:00Z", "ended": "2026-10-19T10:05:00Z"},
           {"job": "archive news", "started": "2026-10-20T12:00:00Z", "ended": "2026-10-20T12:10:00Z"},
           {"job": "archive all", "started": "2026-10-18T08:00:00Z", "ended": "2026-10-18T09:00:00Z"}]
    versions = [{"address": news_addr, "fetched_at": "2026-10-19T06:00:00Z"}]
    times = archive_read_times(versions, log)

    assert times[news_addr]["last_read"].isoformat() == "2026-10-20T12:10:00+00:00"
    assert times[CELESTRAK_GNSS_URL]["last_read"].isoformat() == "2026-10-18T09:00:00+00:00"
    assert times[news_addr]["last_changed"].isoformat() == "2026-10-19T06:00:00+00:00"


def test_archive_read_times_leave_an_unknown_address_out():
    times = archive_read_times([{"address": "https://not-archived.example/", "fetched_at": "2026-10-20T12:00:00Z"}], [])

    assert "https://not-archived.example/" not in times


def test_ago_words_read_in_plain_english():
    from datetime import timedelta

    assert ago_words(NOW, NOW + timedelta(hours=3)) == "3 h ago"
    assert ago_words(None, NOW) == "not known"
