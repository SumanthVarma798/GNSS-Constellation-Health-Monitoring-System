"""Pure helpers for one-off X and Substack discovery grading."""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from evidence import news, source_record
from evidence.news_settings import (X_ACTIVE_DAYS, X_FAIL_SKIP_RECENT_DAYS, X_FAIL_WINDOW_DAYS, X_MIN_POSTS)

TWEET_TIME = "%a %b %d %H:%M:%S %z %Y"
DONE_WORDS = (
    r"\blaunched\b",
    r"\blifts off\b",
    r"\blifted off\b",
    r"\bliftoff\b",
    r"\bsuccessfully\b",
    r"\bhas launched\b",
    r"\breached orbit\b",
)
FUTURE_WORDS = (
    r"\bwill\b",
    r"\bscheduled\b",
    r"\bset to\b",
    r"\bupcoming\b",
    r"\btargeting\b",
    r"\bnet\b",
    r"\bno earlier than\b",
    r"\btomorrow\b",
    r"\bnext week\b",
)
STATUS_WORDS = (r"\boutage\b", r"\banomaly\b", r"\bnanu\b", r"\bnagu\b", r"\bout of service\b")
URL_WORD = re.compile(r"https?://[^\s<>\"]+")


def tweet_row(raw):
    """A normalised tweet row from one API tweet object."""
    author = raw.get("author") or {}
    return {
        "id": str(raw.get("id", "")),
        "url": raw.get("url", ""),
        "published_at": _tweet_time(raw.get("createdAt", "")),
        "text": raw.get("text", ""),
        "user": author.get("userName", ""),
        "name": author.get("name", ""),
        "followers": _as_int(author.get("followers", 0)),
        "verified": bool(author.get("isBlueVerified", False)),
    }


def launch_claim(text):
    """True when words say a launch has happened, not one still ahead."""
    words = " ".join((text or "").split()).casefold()
    if not any(re.search(pattern, words, re.I) for pattern in DONE_WORDS):
        return False
    if any(re.search(pattern, words, re.I) for pattern in FUTURE_WORDS):
        return False
    return True


def judge(row, launches, today):
    """[(constellation, held|failed, evidence)] from one post row."""
    text = row.get("text", "")
    if _status_post(text) or not launch_claim(text):
        return []
    if not (published := _day(row.get("published_at", ""))):
        return []
    checked = []
    recent_cutoff = today - timedelta(days=X_FAIL_SKIP_RECENT_DAYS)
    for constellation in _constellations_named(text):
        claim = {"claim": "launch", "constellation": constellation, "published_at": row.get("published_at", "")}
        if launch_check := source_record.check_launch(claim, launches, today):
            if launch_check.get("result", "") == "held":
                checked.append((constellation, "held", launch_check.get("evidence", "")))
                continue
        if published > recent_cutoff:
            continue
        if _launch_in_window(constellation, launches, published, X_FAIL_WINDOW_DAYS):
            continue
        start = (published - timedelta(days=X_FAIL_WINDOW_DAYS)).isoformat()
        end = (published + timedelta(days=1)).isoformat()
        checked.append((constellation, "failed", f"No {constellation} launch in the registry from {start} to {end}."))
    return checked


def account_table(rows, launches, today):
    """Per-account rollup rows with the same held/failed bars as source-record checks."""
    by_user = {}
    for row in rows:
        user = row.get("user", "")
        if user:
            by_user.setdefault(user, []).append(row)
    table = []
    for user in sorted(by_user):
        posts = by_user[user]
        if len(posts) < X_MIN_POSTS:
            continue
        active_posts = sum(1 for row in posts if _is_active(row.get("published_at", ""), today))
        checked_claims, held, failed = 0, 0, 0
        covered, held_url, failed_url = set(), "", ""
        for row in posts:
            judged = judge(row, launches, today)
            checked_claims += len(judged)
            for constellation, result, _evidence in judged:
                covered.add(constellation)
                if result == "held":
                    held += 1
                    held_url = held_url or row.get("url", "")
                if result == "failed":
                    failed += 1
                    failed_url = failed_url or row.get("url", "")
        score = (held + 1.0) / (held + failed + 2.0)
        table.append({
            "user": user,
            "name": _first(posts, "name"),
            "followers": _max_int(posts, "followers"),
            "verified": any(bool(row.get("verified", False)) for row in posts),
            "posts": len(posts),
            "active_posts": active_posts,
            "first_post": _first_day(posts),
            "last_post": _last_day(posts),
            "checked_claims": checked_claims,
            "held": held,
            "failed": failed,
            "score": score,
            "grade": _grade_never_a(source_record._target_grade(checked_claims, score)),
            "constellations": ", ".join(sorted(covered)),
            "example_held_url": held_url,
            "example_failed_url": failed_url,
        })
    return table


def substack_links(rows):
    """{host: {count, users}} from Substack-like links in post text or entities."""
    hosts = {}
    for row in rows:
        shared_hosts = {_substack_host(link) for link in _links_from_row(row)}
        user = row.get("user", "")
        for host in shared_hosts:
            if not host:
                continue
            slot = hosts.setdefault(host, {"count": 0, "users": set()})
            slot["count"] += 1
            if user:
                slot["users"].add(user)
    return {host: {"count": row["count"], "users": sorted(row["users"])} for host, row in sorted(hosts.items())}


def substack_table(hosts, feed_bodies, launches, today):
    """Per-host Substack feed scores with launch claim checks."""
    table = []
    for host in sorted(hosts):
        shared_count, shared_users = _host_share(hosts[host])
        row = {
            "host": host,
            "shared_posts": shared_count,
            "shared_by": ", ".join(shared_users),
            "feed_posts": 0,
            "active_posts": 0,
            "checked_claims": 0,
            "held": 0,
            "failed": 0,
            "score": 0.5,
            "grade": "F",
            "constellations": "",
            "example_held_url": "",
            "example_failed_url": "",
            "note": "",
        }
        body = feed_bodies.get(host)
        if body is None:
            row["note"] = "feed not fetched"
            table.append(row)
            continue
        try:
            items = news.parse_feed(body)
        except ValueError as error:
            row["note"] = str(error)
            table.append(row)
            continue
        covered = set()
        for item in items:
            text = " ".join(part for part in [item.get("title", ""), item.get("summary", "")] if part).strip()
            post = {"text": text, "published_at": item.get("published_at", ""), "url": item.get("link", "")}
            row["feed_posts"] += 1
            if _is_active(post.get("published_at", ""), today):
                row["active_posts"] += 1
            judged = judge(post, launches, today)
            row["checked_claims"] += len(judged)
            for constellation, result, _evidence in judged:
                covered.add(constellation)
                if result == "held":
                    row["held"] += 1
                    row["example_held_url"] = row["example_held_url"] or post.get("url", "")
                if result == "failed":
                    row["failed"] += 1
                    row["example_failed_url"] = row["example_failed_url"] or post.get("url", "")
        row["score"] = (row["held"] + 1.0) / (row["held"] + row["failed"] + 2.0)
        row["grade"] = _grade_never_a(source_record._target_grade(row["checked_claims"], row["score"]))
        row["constellations"] = ", ".join(sorted(covered))
        table.append(row)
    return table


def _tweet_time(text):
    try:
        when = datetime.strptime((text or "").strip(), TWEET_TIME)
    except ValueError:
        return ""
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _status_post(text):
    words = " ".join((text or "").split())
    return any(re.search(pattern, words, re.I) for pattern in STATUS_WORDS)


def _constellations_named(text):
    named = []
    for system in news.systems_named(text or ""):
        mapped = news.DASHBOARD_SYSTEMS.get(system, system)
        if mapped and mapped not in named:
            named.append(mapped)
    return named


def _day(text):
    try:
        return datetime.fromisoformat((text or "").replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _launch_in_window(constellation, launches, published, before_days):
    start = published - timedelta(days=before_days)
    end = published + timedelta(days=1)
    for launch_constellation, launch_day in launches:
        if launch_constellation != constellation:
            continue
        if not (launch := _day(launch_day)):
            continue
        if start <= launch <= end:
            return True
    return False


def _is_active(published_at, today):
    if not (day := _day(published_at)):
        return False
    return today - timedelta(days=X_ACTIVE_DAYS) <= day <= today


def _first(rows, field):
    for row in rows:
        if row.get(field, ""):
            return row[field]
    return ""


def _max_int(rows, field):
    values = [_as_int(row.get(field, 0)) for row in rows]
    return max(values) if values else 0


def _first_day(rows):
    days = [row.get("published_at", "") for row in rows if row.get("published_at", "")]
    return min(days) if days else ""


def _last_day(rows):
    days = [row.get("published_at", "") for row in rows if row.get("published_at", "")]
    return max(days) if days else ""


def _grade_never_a(grade):
    return "B" if grade == "A" else grade


def _links_from_row(row):
    links = set(_links_from_text(row.get("text", "")))
    _collect_entity_links(row.get("entities"), links)
    return links


def _links_from_text(text):
    for found in URL_WORD.findall(text or ""):
        yield found.rstrip(").,;!?\"'")


def _collect_entity_links(value, links):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower().endswith("url") and isinstance(item, str) and item.startswith(("http://", "https://")):
                links.add(item)
            else:
                _collect_entity_links(item, links)
    elif isinstance(value, list):
        for item in value:
            _collect_entity_links(item, links)


def _substack_host(address):
    host = (urlsplit(address).hostname or "").casefold().removeprefix("www.")
    path = (urlsplit(address).path or "").casefold()
    if not host:
        return ""
    if host == "substack.com" or host.endswith(".substack.com"):
        return host
    if "/p/" in path:
        return host
    return ""


def _host_share(value):
    if isinstance(value, dict):
        count = _as_int(value.get("count", 0))
        users = value.get("users", [])
        if isinstance(users, list):
            return count, sorted(set(users))
        return count, []
    return _as_int(value), []
