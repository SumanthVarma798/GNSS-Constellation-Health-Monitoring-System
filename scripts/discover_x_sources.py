"""One-off discovery of GNSS-focused X accounts and Substacks."""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, time as day_start, timedelta, timezone
from pathlib import Path
from urllib import error, parse, request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence import source_record, x_discovery
from evidence.news_settings import (X_DISCOVERY_MONTHS, X_DISCOVERY_PAGES, X_DISCOVERY_QUERIES)

API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"
ACCOUNT_COLUMNS = [
    "user", "name", "followers", "verified", "posts", "active_posts", "first_post", "last_post", "checked_claims", "held",
    "failed", "score", "grade", "constellations", "example_held_url", "example_failed_url",
]
SUBSTACK_COLUMNS = [
    "host", "shared_posts", "shared_by", "feed_posts", "active_posts", "checked_claims", "held", "failed", "score", "grade",
    "constellations", "example_held_url", "example_failed_url", "note",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="directory for tweets.jsonl, x_accounts.csv and substacks.csv")
    parser.add_argument("--today", help="day to use as YYYY-MM-DD (default: today UTC)")
    args = parser.parse_args()

    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else datetime.now(timezone.utc).date()
    api_key = os.environ.get("TWITTERAPI_IO_KEY", "").strip()
    if not api_key:
        raise SystemExit("TWITTERAPI_IO_KEY is required.")

    since_time = int((datetime.combine(today, day_start(0, 0), tzinfo=timezone.utc)
                      - timedelta(days=30 * X_DISCOVERY_MONTHS)).timestamp())
    launches = source_record.launches_from()
    rows, pages_used = collect_tweets(api_key, since_time)
    accounts = x_discovery.account_table(rows, launches, today)
    accounts = sorted(accounts, key=lambda row: (_grade_index(row["grade"]), -row["checked_claims"], row["user"]))

    hosts = x_discovery.substack_links(rows)
    feed_bodies, feed_errors = read_substack_feeds(hosts)
    substacks = x_discovery.substack_table(hosts, feed_bodies, launches, today)
    for row in substacks:
        if row["host"] in feed_errors:
            row["note"] = feed_errors[row["host"]]
    substacks = sorted(substacks, key=lambda row: (_grade_index(row["grade"]), -row["checked_claims"], row["host"]))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "tweets.jsonl", rows)
    write_csv(out / "x_accounts.csv", ACCOUNT_COLUMNS, accounts)
    write_csv(out / "substacks.csv", SUBSTACK_COLUMNS, substacks)
    print(f"X discovery wrote {len(rows)} tweets, {len(accounts)} accounts, {len(substacks)} substacks; {pages_used} API pages used.")


def collect_tweets(api_key, since_time):
    """Rows from all configured queries, with tweet IDs de-duplicated."""
    seen, rows, pages_used = set(), [], 0
    for query in X_DISCOVERY_QUERIES:
        cursor = ""
        words = f"{query} since_time:{since_time} -filter:retweets"
        for _page in range(X_DISCOVERY_PAGES):
            payload = read_page(api_key, words, cursor)
            pages_used += 1
            for tweet in payload.get("tweets", []):
                row = x_discovery.tweet_row(tweet)
                if not row["id"] or row["id"] in seen:
                    continue
                seen.add(row["id"])
                row["entities"] = tweet.get("entities")
                rows.append(row)
            if not payload.get("has_next_page"):
                break
            cursor = payload.get("next_cursor", "")
            if not cursor:
                break
    return rows, pages_used


def read_page(api_key, query, cursor):
    """One advanced_search response page with 429 retries."""
    params = parse.urlencode({"query": query, "queryType": "Latest", "cursor": cursor or ""})
    address = f"{API_URL}?{params}"
    headers = {"X-API-Key": api_key}
    for attempt in range(4):
        try:
            response = request.urlopen(request.Request(address, headers=headers), timeout=30)
            with response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as err:
            if err.code == 429 and attempt < 3:
                time.sleep(5)
                continue
            raise RuntimeError(f"X API request failed with HTTP {err.code} for query page.") from err
        except (error.URLError, TimeoutError) as err:
            raise RuntimeError(f"X API request failed: {err}") from err
    raise RuntimeError("X API request failed after retries.")


def read_substack_feeds(hosts):
    """({host: body}, {host: failure note}) for host/feed lookups."""
    bodies, failures = {}, {}
    for host in sorted(hosts):
        address = f"https://{host}/feed"
        try:
            with request.urlopen(address, timeout=20) as response:
                bodies[host] = response.read()
        except Exception as err:   # nosec: one-off discovery script; broad catch records and skips host failures
            failures[host] = f"feed fetch failed: {err}"
    return bodies, failures


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            clean = {name: row.get(name, "") for name in columns}
            if isinstance(clean.get("score"), float):
                clean["score"] = f"{clean['score']:.3f}"
            writer.writerow(clean)


def _grade_index(grade):
    grades = source_record.GRADE_ORDER
    return grades.index(grade if grade in grades else "F")


if __name__ == "__main__":
    main()
