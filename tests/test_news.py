"""News items are read from saved feeds correctly, social posts count only with a link, and sites keep their gaps.

Every feed here is a saved sample in tests/samples/news; no test touches the network.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
import time_machine

from evidence import archive, news
from evidence.archive import FetchFailed, pacer, record
from evidence.news import collected_items, items_from, labelling_sample, parse_feed, when
from evidence.settings import BACKOFF_FIRST, BACKOFF_LONGEST, DEFAULT_MIN_GAP, MIN_GAP_BETWEEN_DOWNLOADS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
SAMPLES = Path(__file__).resolve().parent / "samples" / "news"
DIRECT = {"source_id": "press.example", "kind": "press feed", "address": "https://press.example/feed/",
          "check_type": "feed; application/rss+xml"}
SEARCH = {"source_id": "news.google.com", "kind": "discovery feed",
          "address": "https://news.google.com/rss/search?q=GLONASS", "check_type": "feed; application/xml"}
SOCIAL = {"source_id": "reddit.com", "kind": "social feed", "address": "https://www.reddit.com/r/ISRO/.rss",
          "check_type": "feed; application/atom+xml"}
PAGE = {"source_id": "operator.example", "kind": "official page", "address": "https://operator.example/news",
        "check_type": "text/html"}
FETCHED = "2026-10-19T13:00:00Z"


def sample(name):
    return (SAMPLES / name).read_bytes()


# ------------------------------------------------------------------ Reading a feed

def test_a_direct_feed_gives_one_record_per_titled_item_owned_by_its_own_source():
    records = items_from(DIRECT, sample("direct.rss"), FETCHED)

    assert records[0] == {"source_id": "press.example", "address": "https://press.example/2026/10/gps-iii-sv09/",
                          "title": "GPS III SV09 joins the constellation", "published_at": "2026-10-19T10:00:00Z",
                          "fetched_at": FETCHED, "via": DIRECT["address"]}
    assert records[1]["title"] == "Galileo notice to users issued"   # spaces and line breaks tidied
    assert records[1]["published_at"] == "2026-10-18T08:00:00Z"      # from <dc:date> when there is no <pubDate>
    assert [record["published_at"] for record in records][2] == ""   # an unreadable date is left empty, not guessed
    assert len(records) == 3                                         # the item with no title is not a record


def test_a_news_search_item_belongs_to_the_outlet_it_names_never_to_the_search():
    records = items_from(SEARCH, sample("google_news.rss"), FETCHED)

    assert [record["source_id"] for record in records] == ["russianspaceweb.com", "exampledaily.example"]
    assert records[0]["title"] == "Soyuz rocket delivers fresh GLONASS navsat"   # the outlet's name is taken off
    assert records[1]["title"] == "GLONASS - the system, explained"              # only the outlet's own suffix
    assert all(record["via"] == SEARCH["address"] for record in records)


def test_a_social_post_counts_only_with_a_link_off_the_platform_and_belongs_to_that_page():
    records = items_from(SOCIAL, sample("reddit.atom"), FETCHED)

    # The second post links only to Reddit itself and its own image host, so it is not collected.
    assert records == [{"source_id": "isro.gov.in", "address": "https://www.isro.gov.in/NVS03.html?a=1&b=2",
                        "title": "NVS-03 launch date announced", "published_at": "2026-10-16T13:16:58Z",
                        "fetched_at": FETCHED, "via": SOCIAL["address"]}]


@pytest.mark.parametrize("body", [b"<!DOCTYPE html><html><body><p>News</p></body></html>",
                                  b"<html><body>News</body></html>", b"<rss><channel><item>", b""])
def test_a_page_or_a_broken_feed_is_not_taken_for_a_feed(body):
    with pytest.raises(ValueError):
        parse_feed(body)


@pytest.mark.parametrize("text, expected", [
    ("Mon, 19 Oct 2026 15:30:00 +0530", "2026-10-19T10:00:00Z"),
    ("Mon, 19 Oct 2026 10:00:00 GMT", "2026-10-19T10:00:00Z"),
    ("2026-10-16T13:16:58+00:00", "2026-10-16T13:16:58Z"),
    ("2026-10-18T08:00:00Z", "2026-10-18T08:00:00Z"),
    ("2026-10-18T08:00:00", "2026-10-18T08:00:00Z"),   # no zone given: taken as UTC
    ("sometime last week", ""),
    ("", ""),
])
def test_dates_are_written_in_utc(text, expected):
    assert when(text) == expected


# ------------------------------------------------------------------ Items from the archive

def test_each_item_is_listed_once_as_first_fetched_and_a_feed_turned_page_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "working_candidates", lambda: [DIRECT, SEARCH, PAGE])
    record(tmp_path, DIRECT["address"], "2026-10-19T00:50:00Z", 200, sample("direct.rss"))
    record(tmp_path, PAGE["address"], "2026-10-19T00:50:05Z", 200, b"<html><body>a page</body></html>")
    record(tmp_path, DIRECT["address"], "2026-10-19T03:50:00Z", 200, sample("direct.rss") + b"\n")  # changed copy
    record(tmp_path, SEARCH["address"], "2026-10-19T03:50:10Z", 200, b"<html>refused</html>")

    items, unreadable = collected_items(tmp_path)

    assert len(items) == 3 and {item["fetched_at"] for item in items} == {"2026-10-19T00:50:00Z"}
    assert unreadable == [(SEARCH["address"], "2026-10-19T03:50:10Z", "not a feed: its top element is <html>")]


# ------------------------------------------------------------------ The labelling sheet

def item(title, published_at):
    return {"source_id": "x.example", "address": f"https://x.example/{title}", "title": title,
            "published_at": published_at, "fetched_at": FETCHED, "via": ""}


def test_the_sheet_takes_the_newest_items_in_turn_from_every_system():
    items = [item("GPS old", "2026-10-01T00:00:00Z"), item("GPS new", "2026-10-10T00:00:00Z"),
             item("GPS newer", "2026-10-11T00:00:00Z"), item("Michibiki launch", "2026-08-11T00:00:00Z"),
             item("GLONASS-K2 news", "2025-09-13T00:00:00Z"), item("ISRO budget", "2026-10-12T00:00:00Z"),
             item("gps newer", "2026-10-11T00:00:00Z")]

    sample = labelling_sample(items, size=4)

    assert [(row["system"], row["title"]) for row in sample] == [
        ("GPS", "GPS newer"), ("GLONASS", "GLONASS-K2 news"), ("QZSS", "Michibiki launch"), ("GPS", "GPS new")]
    # "ISRO budget" names no system; "gps newer" repeats a title already taken.


def test_the_sheet_on_record_has_the_agreed_columns_and_every_system():
    import csv

    from evidence.settings import LABELLING_SHEET_COLUMNS, LABELLING_SHEET_FILE, LABELLING_SHEET_SIZE, SYSTEM_WORDS
    with open(LABELLING_SHEET_FILE, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == LABELLING_SHEET_COLUMNS and len(rows) == LABELLING_SHEET_SIZE
    assert {row["system"] for row in rows} == set(SYSTEM_WORDS)
    assert all(row["address"].startswith("https://") and row["title"] for row in rows)


# ------------------------------------------------------------------ Minimum gap between requests to one site

class Clock:
    """A clock that moves only when the code sleeps, or a fetch takes time."""

    def __init__(self):
        self.now, self.slept, self.asked = 1000.0, [], []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def fetch(self, address, takes=1.0):
        self.asked.append(address)
        self.now += takes
        return 200, b"", ""


def gap(site):
    return MIN_GAP_BETWEEN_DOWNLOADS[site].total_seconds()


def test_a_second_request_to_the_same_site_waits_out_its_gap_from_the_end_of_the_last():
    clock = Clock()
    paced = pacer(clock.fetch, clock, clock.sleep)

    paced("https://news.google.com/rss/search?q=NavIC")   # takes 1 s
    clock.now += 3
    paced("https://news.google.com/rss/search?q=QZSS")    # 3 s after the last one ended
    paced("https://insidegnss.com/feed/")                  # another site: no wait
    paced("https://news.google.com/rss/search?q=BeiDou")   # 1 s after the last Google one ended

    assert clock.slept == [gap("news.google.com") - 3, gap("news.google.com") - 1]
    assert len(clock.asked) == 4


def test_hosts_under_a_listed_site_share_its_gap_and_others_get_the_default():
    clock = Clock()
    paced = pacer(lambda address: clock.fetch(address, takes=0), clock, clock.sleep)

    paced("https://www.reddit.com/r/ISRO/.rss")
    paced("https://old.reddit.com/r/gnss/.rss")
    paced("https://spacenews.com/feed/")
    paced("https://spacenews.com/other/")

    assert clock.slept == [gap("reddit.com"), DEFAULT_MIN_GAP.total_seconds()]
    assert archive.site("https://notreddit.com/") == "notreddit.com"   # a look-alike name is not the listed site


def test_no_wait_when_the_gap_has_already_passed_and_a_failed_fetch_still_counts():
    clock = Clock()

    def refused(address):
        clock.now += 1
        raise FetchFailed("403")

    paced = pacer(refused, clock, clock.sleep)
    with pytest.raises(FetchFailed):
        paced("https://spacenews.com/feed/")
    with pytest.raises(FetchFailed):
        paced("https://spacenews.com/feed/")              # a refusal is still a request: the gap holds
    clock.now += DEFAULT_MIN_GAP.total_seconds() + 1
    with pytest.raises(FetchFailed):
        paced("https://spacenews.com/feed/")

    assert clock.slept == [DEFAULT_MIN_GAP.total_seconds(), 0.0]


# ------------------------------------------------------------------ Sites never fetched

@pytest.mark.parametrize("address", ["https://vimpel.ru/catalogue", "http://www.spacemapper.cn/", "https://SPACEMAPPER.example/"])
def test_a_tracker_site_is_refused_before_any_request(address, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: pytest.fail("a request was made"))
    with pytest.raises(FetchFailed, match="never fetched"):
        archive.fetch(address)


def test_a_redirect_to_a_tracker_site_is_not_followed():
    class Redirect:
        is_redirect = True
        url = "https://feeds.example/rss"
        headers = {"Location": "https://vimpel.ru/elements"}

    with pytest.raises(FetchFailed, match="never fetched"):
        archive._no_redirect_to_never_fetched(Redirect())


# ------------------------------------------------------------------ Which link is a social post's source

def test_a_posts_own_link_is_its_source_even_when_another_link_comes_first():
    text = ('<a href="https://www.reddit.com/user/someone">/u/someone</a> <a href="https://example.org/first">x</a> '
            '<span><a href="https://www.isro.gov.in/NVS03.html">[link]</a></span>')
    assert news.outside_link(text) == "https://www.isro.gov.in/NVS03.html"


def test_clocks_images_videos_and_other_social_posts_are_not_a_source():
    text = ('<a href="https://www.reddit.com/r/ISRO/comments/x/">[link]</a> '
            '<a href="https://free.timeanddate.com/countdown/i743">Launch Countdown</a> '
            '<a href="https://i.imgur.com/gUM4Dv8.png">Flight profile</a> <a href="https://www.youtube.com/watch?v=1">Stream</a> '
            '<a href="https://x.com/roscosmos/status/1">post</a> <a href="https://www.isro.gov.in/Mission.html">Mission page</a>')
    assert news.outside_link(text) == "https://www.isro.gov.in/Mission.html"
    assert news.outside_link('<a href="https://x.com/a/status/1">[link]</a>') == ""


# ------------------------------------------------------------------ Backing off a site that refuses us

NOW = datetime(2026, 10, 19, 6, 0, tzinfo=timezone.utc)


def test_each_refusal_in_a_row_doubles_the_wait_up_to_the_longest_and_one_answer_clears_it():
    limits, address = {}, "https://www.reddit.com/r/ISRO/.rss"

    archive.note_answer(limits, address, 429, NOW)
    assert archive.waiting_until(limits, "https://old.reddit.com/r/gnss/.rss", NOW) == NOW + BACKOFF_FIRST  # whole site
    assert archive.waiting_until(limits, address, NOW + BACKOFF_FIRST) is None                             # wait over

    archive.note_answer(limits, address, "no answer", NOW + BACKOFF_FIRST)
    assert archive.waiting_until(limits, address, NOW) == NOW + 3 * BACKOFF_FIRST                          # 1 h, then 2 h
    for _ in range(40):                                  # a site refused for most of a year: no overflow
        archive.note_answer(limits, address, 403, NOW)
    assert archive.waiting_until(limits, address, NOW) == NOW + BACKOFF_LONGEST

    archive.note_answer(limits, address, 200, NOW)
    assert limits == {}


def test_a_404_is_an_answer_not_a_refusal():
    limits = {}
    archive.note_answer(limits, "https://gone.example/page", 404, NOW)
    assert limits == {}


def test_a_refusing_site_fails_one_run_then_waits_without_failing_and_is_asked_again_later(monkeypatch, tmp_path):
    import archive_sources

    asked = []

    def refusing(address, timeout, headers, **_):
        asked.append(address)
        return SimpleNamespace(status_code=429, content=b"", headers={})

    monkeypatch.setattr(archive.requests, "get", refusing)
    monkeypatch.setattr(archive.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(archive_sources, "archived_addresses", lambda group: ["https://www.reddit.com/r/ISRO/.rss",
                                                                              "https://www.reddit.com/r/gnss/.rss"])

    def run(at):
        monkeypatch.setattr(sys, "argv", ["archive_sources.py", "--archive", str(tmp_path), "--group", "social"])
        with time_machine.travel(at, tick=False):
            archive_sources.main()

    with pytest.raises(SystemExit):
        run(NOW)                                          # refused: the run fails, and r/gnss is not asked at all
    run(NOW + timedelta(minutes=30))                      # still in its back-off: nothing asked, the run does not fail
    with pytest.raises(SystemExit):
        run(NOW + BACKOFF_FIRST)                          # asked again once the wait is over

    assert asked == ["https://www.reddit.com/r/ISRO/.rss"] * 2
    assert [line["result"] for line in archive.read_runs(tmp_path, "archive")] == [
        "failed: 1 of 2 sources; 1 waiting out a refusal", "ok; 2 waiting out a refusal",
        "failed: 1 of 2 sources; 1 waiting out a refusal"]
    assert archive.read_limits(tmp_path)["reddit.com"]["refusals"] == "2"


# ------------------------------------------------------------------ Measuring each feed

def test_the_report_gives_each_feeds_changes_per_run_and_share_of_items_naming_a_system(tmp_path, monkeypatch):
    monkeypatch.setattr(news, "working_candidates", lambda: [DIRECT, SOCIAL])
    monkeypatch.setattr(news, "ARCHIVED_SOURCES", {"news": [DIRECT["address"]], "social": [SOCIAL["address"]]})
    for started in ("2026-10-19T00:50:00Z", "2026-10-19T03:50:00Z"):
        archive.log_run(tmp_path, "archive", "archive news", started, started, "ok", "")
    archive.log_run(tmp_path, "archive", "archive all", "2026-10-19T05:00:00Z", "", "ok", "")
    record(tmp_path, DIRECT["address"], "2026-10-19T00:50:00Z", 200, sample("direct.rss"))
    record(tmp_path, SOCIAL["address"], "2026-10-19T05:00:00Z", 200, sample("reddit.atom"))

    rows = {row["via"]: row for row in news.feed_report(tmp_path)}

    assert rows[DIRECT["address"]] == {"via": DIRECT["address"], "group": "news", "runs": 3, "copies": 1,
                                       "copies_per_run": "0.33", "items": 3, "items_naming_a_system": 2,
                                       "share_naming_a_system": "0.67"}
    assert rows[SOCIAL["address"]]["runs"] == 1 and rows[SOCIAL["address"]]["share_naming_a_system"] == "1.00"   # "NVS-03" names NavIC
