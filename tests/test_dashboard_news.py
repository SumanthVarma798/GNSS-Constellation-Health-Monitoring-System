"""The dashboard news helpers: loading, safe markup, and pure filtering."""
from datetime import datetime, timezone
import json
import re

from ui import news as news_ui


def _item(**changes):
    row = {
        "constellations": ["QZSS"],
        "category": "launch",
        "title": "Japan launches QZS satellite",
        "summary": "Mission update",
        "outlet": "Example outlet",
        "source_id": "example.com",
        "address": "https://example.com/story",
        "published_at": "2026-10-20T10:00:00Z",
        "fetched_at": "2026-10-20T10:15:00Z",
        "via": "https://feed.example/rss",
        "grade": "C",
        "grade_standing": "confirmed",
    }
    row.update(changes)
    return row


def test_load_news_from_a_missing_path_returns_a_problem_sentence():
    data, problem = news_ui.load_news("/this/path/does/not/exist.json")

    assert data == {} and "could not be read" in problem


def test_load_news_from_bad_json_returns_a_problem_sentence(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")

    data, problem = news_ui.load_news(str(bad))

    assert data == {} and "not valid JSON" in problem


def test_load_news_skips_items_not_in_the_expected_shape_and_normalises_sources(tmp_path):
    file = tmp_path / "latest_news.json"
    file.write_text(json.dumps({
        "generated_at": "2026-10-20T10:00:00Z",
        "items": [
            _item(),
            {"title": "Missing source id", "address": "https://x.example/1", "category": "launch",
             "constellations": ["QZSS"]},
            "not-a-dict",
        ],
        "sources": {"example.com": {"name": "Example"}, "bad": "words"},
        "rules": {"launch": ["launch"], "other": []},
    }), encoding="utf-8")

    data, problem = news_ui.load_news(str(file))

    assert problem == ""
    assert len(data["items"]) == 1
    assert data["sources"]["example.com"] == {"name": "Example"}
    assert data["sources"]["bad"] == {}
    assert data["invalid_items"] == 2


def test_item_html_escapes_text_and_only_draws_http_links():
    html = news_ui.item_html(
        _item(title='<script>alert("x")</script>', address="javascript:alert(1)"),
        {"name": "Source", "kind": "feed", "grade": "C", "grade_standing": "confirmed", "reason": "", "graded_by": "", "note": ""},
        is_new=True,
    )

    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "javascript:alert(1)" not in html and "Read the article" not in html


def test_item_html_uses_distinct_tooltip_ids_per_item_key():
    one = news_ui.item_html(_item(address="https://example.com/one"),
                            {"name": "Source", "kind": "feed", "grade": "C", "grade_standing": "confirmed",
                             "reason": "", "graded_by": "", "note": ""})
    two = news_ui.item_html(_item(address="https://example.com/two"),
                            {"name": "Source", "kind": "feed", "grade": "C", "grade_standing": "confirmed",
                             "reason": "", "graded_by": "", "note": ""})
    card_one = re.search(r'id="(tt-[^"]+)"', one).group(1)
    card_two = re.search(r'id="(tt-[^"]+)"', two).group(1)

    assert card_one != card_two


def test_category_body_html_uses_get_for_source_id():
    row = _item()
    row.pop("source_id")
    row["_new"] = False
    html = news_ui.category_body_html([row], {"example.com": {"name": "Example"}})

    assert "news-list" in html


def test_news_css_wraps_filter_pills_inside_news_filters():
    assert '.st-key-news_filters [data-testid="stButtonGroup"] [data-baseweb="button-group"] { flex-wrap: wrap; }' in news_ui.CSS
    assert '.st-key-news_filters [data-testid="stButtonGroup"] button { white-space: normal; }' in news_ui.CSS


def test_filter_items_applies_category_grade_date_and_new_only():
    now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    seen = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)
    rows = [
        _item(title="Launch one", category="launch", grade_standing="confirmed",
              published_at="2026-10-20T08:00:00Z", fetched_at="2026-10-20T08:05:00Z"),
        _item(title="Signal two", category="signal and service", grade_standing="provisional",
              published_at="2026-10-01T08:00:00Z", fetched_at="2026-10-01T08:05:00Z"),
        _item(title="Policy three", category="programme and policy", grade_standing="not graded",
              published_at="", fetched_at="2025-09-01T08:05:00Z"),
        _item(title="Old launch", category="launch", grade_standing="confirmed",
              published_at="2025-01-01T08:00:00Z", fetched_at="2025-01-01T08:05:00Z"),
    ]

    kept = news_ui.filter_items(rows, "QZSS", {"launch", "signal and service", "programme and policy"},
                                {"confirmed", "provisional", "not graded"}, "all", False, seen, now)
    assert len(kept) == 4

    kept = news_ui.filter_items(rows, "QZSS", {"launch"}, {"confirmed", "provisional", "not graded"},
                                "all", False, seen, now)
    assert [row["title"] for row in kept] == ["Launch one", "Old launch"]

    kept = news_ui.filter_items(rows, "QZSS", {"launch", "signal and service"}, {"confirmed"},
                                "all", False, seen, now)
    assert [row["title"] for row in kept] == ["Launch one", "Old launch"]

    kept = news_ui.filter_items(rows, "QZSS", {"launch", "signal and service", "programme and policy"},
                                {"confirmed", "provisional", "not graded"}, "30 days", False, seen, now)
    assert [row["title"] for row in kept] == ["Launch one", "Signal two"]

    kept = news_ui.filter_items(rows, "QZSS", {"launch", "signal and service", "programme and policy"},
                                {"confirmed", "provisional", "not graded"}, "all", True, seen, now)
    assert [row["title"] for row in kept] == []


def test_seen_note_takes_only_seen_time_and_as_of_line_returns_markup_only():
    now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)

    note = news_ui.seen_note(now)
    as_of = news_ui.as_of_line("2026-10-20T10:00:00Z", now)

    assert "last visit" in note
    assert isinstance(as_of, str) and "News as of" in as_of
