"""News items read from the archived feeds (issue 13): one record per article a feed pointed to.

An item is a pointer to an article, with its title and dates. It is not a claim and decides
nothing; claims are taken from articles later (issue 15). Records are worked out afresh from
the archive's raw copies each time, like the query store, so they cannot drift from them.

Feed text is untrusted data: it is parsed, never followed. Python's XML parser fetches no
outside entities, and its expat (2.4.1 or later) refuses runaway entity expansion.
"""
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree

from evidence.archive import object_path, read_versions
from evidence.settings import (CANDIDATE_FEED_TYPE, CANDIDATE_SOCIAL_KIND, LABELLING_SHEET_SIZE,
                               SOCIAL_PLATFORM_HOSTS, SYSTEM_WORDS)
from evidence.sources import working_candidates

ATOM = "{http://www.w3.org/2005/Atom}"
LINK = re.compile(r"""href=["'](https?://[^"']+)["']""")


def host_id(address):
    """A source ID from an address: its host name, without a leading "www.", as the candidate list writes it."""
    host = (urlsplit(address).hostname or "").lower()
    return host.removeprefix("www.")


def when(text):
    """A feed's date (RFC 822 in RSS, ISO 8601 in Atom) as UTC "YYYY-MM-DDTHH:MM:SSZ", or "" if unreadable."""
    text = (text or "").strip()
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)  # a feed that gives no zone: taken as UTC (guess)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(element, *tags):
    for tag in tags:
        found = element.find(tag)
        if found is not None and (found.text or "").strip():
            return found.text.strip()
    return ""


def parse_feed(body):
    """The items of one RSS 2.0 or Atom feed, in the order the feed lists them.

    Each item is a dict: title, link, published_at, outlet (the <source url> a news search names, or ""),
    and text (the summary or content, for finding links in a social post). Raises ValueError for
    anything that is not a feed, such as a web page.
    """
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as error:
        raise ValueError(f"not readable as a feed: {error}") from error
    if root.tag == "rss":
        items = []
        for entry in root.iter("item"):
            source = entry.find("source")
            outlet_name = (source.text or "").strip() if source is not None else ""
            title = _text(entry, "title")
            if outlet_name:
                title = title.removesuffix(f" - {outlet_name}")  # a news search adds the outlet's name to each title
            items.append({"title": title, "link": _text(entry, "link"),
                          "published_at": when(_text(entry, "pubDate", "{http://purl.org/dc/elements/1.1/}date")),
                          "outlet": source.get("url", "") if source is not None else "",
                          "text": _text(entry, "description", "{http://purl.org/rss/1.0/modules/content/}encoded")})
        return items
    if root.tag == f"{ATOM}feed":
        items = []
        for entry in root.iter(f"{ATOM}entry"):
            links = [link for link in entry.findall(f"{ATOM}link") if link.get("rel", "alternate") == "alternate"]
            items.append({"title": _text(entry, f"{ATOM}title"), "link": links[0].get("href", "") if links else "",
                          "published_at": when(_text(entry, f"{ATOM}published", f"{ATOM}updated")),
                          "outlet": "", "text": _text(entry, f"{ATOM}content", f"{ATOM}summary")})
        return items
    raise ValueError(f"not a feed: its top element is <{root.tag}>")


def outside_link(text):
    """The first link in a social post that leads off the platform, or "" when it holds none."""
    for address in LINK.findall(text or ""):
        address = html.unescape(address)
        host = (urlsplit(address).hostname or "").lower()
        if not any(host == own or host.endswith("." + own) for own in SOCIAL_PLATFORM_HOSTS):
            return address
    return ""


def items_from(candidate, body, fetched_at):
    """News item records from one archived copy of a candidate's feed.

    A direct feed's items belong to its own source. A news search's items belong to the outlet it names, and a
    social post's to the page it links to: the post counts only if it holds such a link (decision 5).
    """
    records = []
    for item in parse_feed(body):
        address, source_id = item["link"], candidate["source_id"]
        if candidate["kind"] == CANDIDATE_SOCIAL_KIND:
            address = outside_link(item["text"])
            if not address:
                continue  # a post with no link to its source is not collected
            source_id = host_id(address)
        elif item["outlet"]:
            source_id = host_id(item["outlet"])
        if address and item["title"]:
            records.append({"source_id": source_id, "address": address, "title": " ".join(item["title"].split()),
                            "published_at": item["published_at"], "fetched_at": fetched_at,
                            "via": candidate["address"]})
    return records


def collected_items(archive):
    """Every news item in the archive's copies of the candidate feeds, each once, as first fetched.

    Returns (items, unreadable): unreadable lists (address, fetched_at, reason) for copies of a feed that
    could not be read as one, so a feed that has turned into a page is noticed, not skipped quietly.
    """
    # ponytail: re-reads every archived copy each call; keep a running item list when that gets slow.
    feeds = {row["address"]: row for row in working_candidates() if row["check_type"].startswith(CANDIDATE_FEED_TYPE)}
    seen, items, unreadable = set(), [], []
    for version in read_versions(archive):
        candidate = feeds.get(version["address"])
        if candidate is None or not version["sha256"]:
            continue
        body = object_path(archive, version["sha256"]).read_bytes()
        try:
            found = items_from(candidate, body, version["fetched_at"])
        except ValueError as error:
            unreadable.append((version["address"], version["fetched_at"], str(error)))
            continue
        for item in found:
            if item["address"] not in seen:
                seen.add(item["address"])
                items.append(item)
    return items, unreadable


def systems_named(title):
    """The systems an item's title names, in SYSTEM_WORDS order."""
    return [system for system, words in SYSTEM_WORDS.items()
            if any(re.search(rf"\b{re.escape(word)}\b", title, re.I) for word in words)]


def labelling_sample(items, size=LABELLING_SHEET_SIZE):
    """About `size` recent items spread across the six systems, newest first within each.

    Takes one item per system in turn, so a system with few items gives what it has and the rest come from the
    others. An item that names no system is left out; one that names several counts for the first. The same
    title from two feeds is taken once.
    """
    newest_first = sorted(items, key=lambda item: item["published_at"] or item["fetched_at"], reverse=True)
    queues = {system: [] for system in SYSTEM_WORDS}
    titles = set()
    for item in newest_first:
        named = systems_named(item["title"])
        key = item["title"].lower()
        if named and key not in titles:
            titles.add(key)
            queues[named[0]].append(item)
    sample = []
    while len(sample) < size and any(queues.values()):
        for system, queue in queues.items():
            if queue and len(sample) < size:
                sample.append({"system": system, **queue.pop(0)})
    return sample
