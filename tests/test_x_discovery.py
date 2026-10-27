"""X discovery helpers: launch wording, claim checks, account scoring and Substack links."""
from datetime import date

from evidence import x_discovery


def tweet(user, text, published_at, url):
    return {
        "id": url.rsplit("/", 1)[-1],
        "url": url,
        "published_at": published_at,
        "text": text,
        "user": user,
        "name": user.title(),
        "followers": 100,
        "verified": False,
    }


def test_launch_claim_accepts_past_wording_and_rejects_future_wording():
    assert x_discovery.launch_claim("GPS III lifted off and reached orbit successfully.")
    assert not x_discovery.launch_claim("GPS III liftoff scheduled for tomorrow.")
    assert not x_discovery.launch_claim("Galileo has launched successfully and will launch another next week.")


def test_judge_marks_held_failed_and_skips_unmeasured_posts():
    launches = [("GPS", "2026-01-09"), ("Galileo", "2026-01-09")]
    today = date(2026, 2, 20)

    held = x_discovery.judge(
        tweet("a", "GPS III launched successfully.", "2026-01-10T00:00:00Z", "https://x.com/a/1"),
        launches,
        today,
    )
    failed = x_discovery.judge(
        tweet("a", "GPS III has launched.", "2026-01-20T00:00:00Z", "https://x.com/a/2"),
        launches,
        today,
    )
    recent = x_discovery.judge(
        tweet("a", "Galileo satellite launched.", "2026-02-18T00:00:00Z", "https://x.com/a/3"),
        launches,
        today,
    )
    status = x_discovery.judge(
        tweet("a", "GPS outage alert: NANU update.", "2026-01-20T00:00:00Z", "https://x.com/a/4"),
        launches,
        today,
    )
    unnamed = x_discovery.judge(
        tweet("a", "A satellite launched successfully.", "2026-01-20T00:00:00Z", "https://x.com/a/5"),
        launches,
        today,
    )

    assert held and held[0][0] == "GPS" and held[0][1] == "held"
    assert failed == [("GPS", "failed", "No GPS launch in the registry from 2026-01-13 to 2026-01-21.")]
    assert recent == []
    assert status == []
    assert unnamed == []


def test_account_table_applies_min_posts_and_grade_from_checked_claims():
    launches = [("GPS", "2026-01-09"), ("Galileo", "2026-01-15")]
    today = date(2026, 2, 20)
    rows = [
        tweet("alpha", "GPS III launched successfully.", "2026-01-10T00:00:00Z", "https://x.com/alpha/1"),
        tweet("alpha", "Galileo satellite launched.", "2026-01-16T00:00:00Z", "https://x.com/alpha/2"),
        tweet("alpha", "GPS III has launched.", "2026-01-30T00:00:00Z", "https://x.com/alpha/3"),
        tweet("beta", "GPS III launched successfully.", "2026-01-10T00:00:00Z", "https://x.com/beta/1"),
        tweet("beta", "GPS III launched successfully.", "2026-01-11T00:00:00Z", "https://x.com/beta/2"),
    ]

    table = x_discovery.account_table(rows, launches, today)

    assert [row["user"] for row in table] == ["alpha"]   # beta has fewer than X_MIN_POSTS
    assert table[0]["checked_claims"] == 3
    assert table[0]["held"] == 2
    assert table[0]["failed"] == 1
    assert table[0]["grade"] == "D"   # 3 checked claims at score 0.60


def test_substack_links_counts_substack_and_custom_p_hosts_and_tracks_users():
    rows = [
        {
            "user": "alpha",
            "text": "Read this https://spaceletter.substack.com/p/week-1",
            "entities": None,
        },
        {
            "user": "beta",
            "text": "Issue link",
            "entities": {"urls": [{"expanded_url": "https://gnssdigest.example/p/issue-4"}]},
        },
        {
            "user": "alpha",
            "text": "Another one https://spaceletter.substack.com/p/week-2 and https://spaceletter.substack.com/p/week-3",
            "entities": None,
        },
    ]

    hosts = x_discovery.substack_links(rows)

    assert hosts["spaceletter.substack.com"]["count"] == 2
    assert hosts["spaceletter.substack.com"]["users"] == ["alpha"]
    assert hosts["gnssdigest.example"]["count"] == 1
    assert hosts["gnssdigest.example"]["users"] == ["beta"]
