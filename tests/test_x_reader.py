"""The X reader: an account's posts kept as RSS, then read by the news pipeline like any direct feed."""
import io
import json
from datetime import datetime, timezone

import pytest

from evidence import news, x_reader
from evidence.archive import FetchFailed
from evidence.settings import CANDIDATE_X_KIND
from evidence.sources import ARCHIVED_SOURCES, working_candidates

ADDRESS = "https://x.com/planet4589"
CANDIDATE = {"source_id": "x.com/planet4589", "name": "Jonathan McDowell (@planet4589)", "kind": CANDIDATE_X_KIND,
             "address": ADDRESS}
TWEET = {"url": "https://x.com/planet4589/status/1", "createdAt": "Wed Jan 28 23:53:00 +0000 2026",
         "text": "Falcon 9 launched GPS III-9 tonight & it reached orbit <ok>"}
NOW = datetime(2026, 1, 29, tzinfo=timezone.utc)


def test_posts_become_an_rss_copy_that_the_news_pipeline_reads_as_the_accounts_own():
    body = x_reader.rss_from(ADDRESS, [TWEET, {"url": "", "text": "no link"}])
    items = news.items_from(CANDIDATE, body, "2026-01-29T00:00:00Z")

    assert len(items) == 1
    item = items[0]
    assert item["source_id"] == "x.com/planet4589"
    assert item["address"] == TWEET["url"]
    assert item["summary"] == TWEET["text"]   # escaped on the way in, read back exactly
    assert item["published_at"] == "2026-01-28T23:53:00Z"
    assert item["kind"] == CANDIDATE_X_KIND


def test_a_post_naming_its_system_only_after_the_title_cut_still_reaches_the_news_file():
    long_text = "A very long post " * 10 + "about the BeiDou launch today"
    body = x_reader.rss_from(ADDRESS, [{**TWEET, "text": long_text}])
    items = news.items_from(CANDIDATE, body, "2026-01-29T00:00:00Z")

    assert "BeiDou" not in items[0]["title"]
    assert news._item_systems(items[0]) == ["BeiDou-3"]


def test_the_query_reads_recent_posts_that_name_a_system_and_skips_reposts():
    words = x_reader.query("planet4589", NOW)

    assert words.startswith("from:planet4589 (GPS OR BeiDou")
    assert f"since_time:{int(datetime(2026, 1, 27, tzinfo=timezone.utc).timestamp())}" in words
    assert words.endswith("-filter:retweets")


def test_fetch_needs_the_key_and_never_reaches_the_network_without_it(monkeypatch):
    monkeypatch.delenv(x_reader.KEY_VARIABLE, raising=False)

    with pytest.raises(FetchFailed, match="no TWITTERAPI_IO_KEY"):
        x_reader.fetch(ADDRESS, NOW, opener=lambda *a, **k: pytest.fail("no key: nothing may be sent"))


def test_fetch_sends_the_key_as_a_header_and_returns_an_rss_copy(monkeypatch):
    monkeypatch.setenv(x_reader.KEY_VARIABLE, "test-key")
    sent = {}

    def opener(req, timeout):
        sent["key"], sent["url"] = req.get_header("X-api-key"), req.full_url
        return io.BytesIO(json.dumps({"tweets": [TWEET]}).encode())

    status, body, content_type = x_reader.fetch(ADDRESS, NOW, opener=opener)

    assert (status, content_type) == (200, x_reader.RSS_TYPE)
    assert sent["key"] == "test-key" and "test-key" not in sent["url"]
    assert b"GPS III-9" in body


def test_x_accounts_are_read_by_the_x_group_not_fetched_with_the_news():
    x_accounts = {row["address"] for row in working_candidates() if row["kind"] == CANDIDATE_X_KIND}

    assert x_accounts and set(ARCHIVED_SOURCES["x"]) == x_accounts
    assert not x_accounts & set(ARCHIVED_SOURCES["news"])
