"""Read an X account's recent GNSS posts and keep them as an RSS copy, like any other news feed.

The archive keeps raw copies of feeds; X has none, so this asks twitterapi.io for the account's posts that name a
navigation system and writes them as RSS 2.0. From there the archive, the news file and the source record treat the
account like any other direct feed: each post belongs to the account (its source id is x.com/<handle>).
The key comes from the TWITTERAPI_IO_KEY environment variable and is never printed.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib import error, parse, request
from xml.sax.saxutils import escape

from evidence.archive import FetchFailed
from evidence.news_settings import X_API_URL, X_POST_WORDS, X_READ_DAYS, X_TITLE_CHARACTERS

KEY_VARIABLE = "TWITTERAPI_IO_KEY"
RSS_TYPE = "application/rss+xml"


def handle(address):
    """'planet4589' from 'https://x.com/planet4589'."""
    return parse.urlsplit(address).path.strip("/").split("/")[0]


def query(user, now):
    """The search that reads one account's recent posts naming a navigation system."""
    since = int((now - timedelta(days=X_READ_DAYS)).timestamp())
    return f"from:{user} {X_POST_WORDS} since_time:{since} -filter:retweets"


def _rfc822(created_at):
    """'Tue Dec 10 07:00:30 +0000 2024' as an RSS date, or '' when it cannot be read."""
    try:
        return format_datetime(datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y"))
    except (TypeError, ValueError):
        return ""


def _title(text):
    first = " ".join((text or "").split())
    return first if len(first) <= X_TITLE_CHARACTERS else first[:X_TITLE_CHARACTERS].rsplit(" ", 1)[0] + "…"


def rss_from(address, tweets):
    """RSS 2.0 bytes for one account's posts, newest first, as the API gave them."""
    items = []
    for tweet in tweets:
        link = tweet.get("url") or ""
        if not link.startswith("https://"):
            continue
        items.append(f"<item><title>{escape(_title(tweet.get('text', '')))}</title><link>{escape(link)}</link>"
                     f"<pubDate>{escape(_rfc822(tweet.get('createdAt', '')))}</pubDate>"
                     f"<description>{escape(tweet.get('text', ''))}</description></item>")
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>@{escape(handle(address))}'
            f"</title><link>{escape(address)}</link>{''.join(items)}</channel></rss>").encode("utf-8")


def fetch(address, now=None, opener=request.urlopen):
    """(status, body, content type) like evidence.archive.fetch, for one https://x.com/<handle> address."""
    key = os.environ.get(KEY_VARIABLE, "")
    if not key:
        raise FetchFailed(f"{address}: no {KEY_VARIABLE} set, so X cannot be read")
    now = now or datetime.now(timezone.utc)
    params = parse.urlencode({"query": query(handle(address), now), "queryType": "Latest", "cursor": ""})
    try:
        with opener(request.Request(f"{X_API_URL}?{params}", headers={"X-API-Key": key}), timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as failure:
        raise FetchFailed(f"{address}: the X reader answered {failure.code}") from failure
    except (error.URLError, TimeoutError, ValueError) as failure:
        raise FetchFailed(f"{address}: the X reader could not be read ({failure.__class__.__name__})") from failure
    # ponytail: one page (up to 20 posts) per read; an account posting more than that between reads loses the rest.
    return 200, rss_from(address, payload.get("tweets") or []), RSS_TYPE
