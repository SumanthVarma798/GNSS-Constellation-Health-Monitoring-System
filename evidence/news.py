"""News items read from the archived feeds (issue 13): one record per article a feed pointed to.

An item is a pointer to an article, with its title and dates. It is not a claim and decides
nothing; claims are taken from articles later (issue 15). Records are worked out afresh from
the archive's raw copies each time, like the query store, so they cannot drift from them.

Feed text is untrusted data: it is parsed, never followed. Python's XML parser fetches no
outside entities, and its expat (2.4.1 or later) refuses runaway entity expansion.
"""
import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree

from evidence.archive import object_path, read_runs, read_versions
from evidence.confidence import read_source_grades
from evidence import source_record
from evidence.news_settings import (NEWS_CATEGORIES, NEWS_ITEMS_PER_SYSTEM, NEWS_MAX_AGE_DAYS,
                                    NEWS_TEXT_MATCH_KINDS, SUMMARY_CHARACTERS)
from evidence.settings import (CANDIDATE_FEED_TYPE, CANDIDATE_SOCIAL_KIND, FEED_REPORT_COLUMNS, LABELLING_SHEET_SIZE,
                               NOT_AN_ARTICLE_HOSTS, SOCIAL_PLATFORM_HOSTS, SYSTEM_WORDS)
from evidence.sources import ARCHIVED_SOURCES, PROVISIONAL_GROUPS, candidate_rows, working_candidates

ATOM = "{http://www.w3.org/2005/Atom}"
LINK = re.compile(r"""href=["'](https?://[^"']+)["']""")
POST_LINK = re.compile(r"""href=["'](https?://[^"']+)["'][^>]*>\s*\[link\]""")  # a Reddit post's own link
TAGS = re.compile(r"<[^>]+>")
DASHBOARD_SYSTEMS = {"BeiDou": "BeiDou-3"}


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

    Each item is a dict: title, link, published_at, outlet (the <source> words, if any), outlet_url (its URL),
    and summary (the feed text, for finding links in a social post and for the dashboard). Raises ValueError for
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
                          "outlet": outlet_name, "outlet_url": source.get("url", "") if source is not None else "",
                          "summary": _text(entry, "description", "{http://purl.org/rss/1.0/modules/content/}encoded")})
        return items
    if root.tag == f"{ATOM}feed":
        items = []
        for entry in root.iter(f"{ATOM}entry"):
            links = [link for link in entry.findall(f"{ATOM}link") if link.get("rel", "alternate") == "alternate"]
            items.append({"title": _text(entry, f"{ATOM}title"), "link": links[0].get("href", "") if links else "",
                          "published_at": when(_text(entry, f"{ATOM}published", f"{ATOM}updated")),
                          "outlet": "", "outlet_url": "", "summary": _text(entry, f"{ATOM}content", f"{ATOM}summary")})
        return items
    raise ValueError(f"not a feed: its top element is <{root.tag}>")


def _on(host, hosts):
    return any(host == name or host.endswith("." + name) for name in hosts)


def outside_link(text):
    """The link a social post gives as its source, or "" when it gives none.

    That is the post's own "[link]" when it leads off the platform; otherwise the first link in the post that
    leads off the platform to something other than a clock, an image or a video (NOT_AN_ARTICLE_HOSTS).
    """
    text = text or ""
    own = POST_LINK.search(text)
    for address in ([own.group(1)] if own else []) + LINK.findall(text):
        address = html.unescape(address)
        host = (urlsplit(address).hostname or "").lower()
        if not _on(host, SOCIAL_PLATFORM_HOSTS + NOT_AN_ARTICLE_HOSTS):
            return address
    return ""


def items_from(candidate, body, fetched_at):
    """News item records from one archived copy of a candidate's feed.

    A direct feed's items belong to its own source. A news search's items belong to the outlet it names, and a
    social post's to the page it links to: the post counts only if it holds such a link (decision 5).
    """
    records = []
    social = candidate["kind"] == CANDIDATE_SOCIAL_KIND
    for item in parse_feed(body):
        address, source_id, outlet = item["link"], candidate["source_id"], ""
        if social:
            address = outside_link(item["summary"])
            if not address:
                continue  # a post with no link to its source is not collected
            source_id = host_id(address)
        elif item["outlet_url"]:
            source_id = host_id(item["outlet_url"])
            outlet = item["outlet"]
        else:
            outlet = candidate.get("name") or source_id
        if address and item["title"]:
            records.append({"source_id": source_id, "address": address, "title": " ".join(item["title"].split()),
                            "summary": "" if social else item["summary"], "outlet": outlet,
                            "published_at": item["published_at"], "fetched_at": fetched_at,
                            "via": candidate["address"], "social": social, "kind": candidate["kind"]})
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


def summary_from(text, title, outlet):
    """A plain summary from feed text, cut at SUMMARY_CHARACTERS; blank when it only repeats the title."""
    cleaned = " ".join(TAGS.sub(" ", html.unescape(text or "")).split())
    title = " ".join((title or "").split())
    outlet = " ".join((outlet or "").split())
    if not cleaned:
        return ""
    if title and cleaned.casefold().startswith(title.casefold()):
        tail = cleaned[len(title):].strip(" -—|·")
        if not tail or (outlet and tail.casefold() == outlet.casefold()):
            return ""
    if len(cleaned) <= SUMMARY_CHARACTERS:
        return cleaned
    cut = cleaned[:SUMMARY_CHARACTERS + 1]
    if " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" ,.;:-") + "…"


def category_of(title, summary):
    """The first category whose words match the title, then the summary, else "other"."""
    title, summary = title or "", summary or ""
    for category, words in NEWS_CATEGORIES.items():
        if category == "other":
            continue
        for word in words:
            if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", title, re.I):
                return category
    for category, words in NEWS_CATEGORIES.items():
        if category == "other":
            continue
        for word in words:
            if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", summary, re.I):
                return category
    return "other"


def _dashboard_systems(title):
    named = systems_named(title)
    return [DASHBOARD_SYSTEMS.get(system, system) for system in named]


def _moment(text):
    stamp = when(text)
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else None


def _too_old(item, newest_fetched):
    if newest_fetched is None:
        return False
    published = _moment(item.get("published_at", ""))
    if published is None:
        return False
    return published < newest_fetched - timedelta(days=NEWS_MAX_AGE_DAYS)


def _item_systems(item):
    named = _dashboard_systems(item.get("title", ""))
    if named or item.get("kind", "") not in NEWS_TEXT_MATCH_KINDS:
        return named
    # Feed text may hold markup: match on its words only.
    return _dashboard_systems(re.sub(r"<[^>]+>", " ", html.unescape(item.get("summary", ""))))


def claim_items(items):
    """Archived items in the latest-news shape source-record checking reads."""
    rows = []
    for item in items:
        constellations = []
        for system in _item_systems(item):
            if system and system not in constellations:
                constellations.append(system)
        summary = summary_from(item.get("summary", ""), item.get("title", ""), item.get("outlet", ""))
        rows.append({
            "source_id": item.get("source_id", ""),
            "address": item.get("address", ""),
            "published_at": item.get("published_at", ""),
            "title": item.get("title", ""),
            "category": category_of(item.get("title", ""), summary),
            "constellations": constellations,
        })
    return rows


def _grade_tables():
    confirmed = {row["source_id"]: row for row in read_source_grades()}
    provisional = {}
    for row in candidate_rows():
        provisional.setdefault(row["source_id"], row)
    return confirmed, provisional


def _source_grade(source_id, confirmed, provisional, record_rows, today):
    if source_id in confirmed:
        row = confirmed[source_id]
        return row["reliability"], "confirmed", row["reason"], row["graded_by"], ""
    row = provisional.get(source_id, {})
    if row.get("proposed_grade"):
        return row["proposed_grade"], "provisional", row.get("grade_reason", ""), "", ""
    if record_rows:
        grade = source_record.record_grade(record_rows, "", today)
        return grade, "provisional", "From the checked-claims record, waiting for approval.", "", "record"
    return "", "not graded", "", "", ""


def _title_key(title):
    return " ".join((title or "").split()).casefold()


def latest_news(items):
    """A latest-news dict for the dashboard file, capped per constellation."""
    confirmed, provisional = _grade_tables()
    record = source_record.read_record()
    by_source = {}
    for row in record:
        if row.get("source_id"):
            by_source.setdefault(row["source_id"], []).append(row)
    counts = {DASHBOARD_SYSTEMS.get(system, system): 0 for system in SYSTEM_WORDS}
    picked, used_sources = [], set()
    fetched = [_moment(item.get("fetched_at", "")) for item in items]
    newest_fetched = max((moment for moment in fetched if moment), default=None)
    today = newest_fetched.date() if newest_fetched else datetime(1970, 1, 1, tzinfo=timezone.utc).date()
    # Old items go before the duplicate check, so an old copy never takes a recent one's place.
    recent = [item for item in items if not _too_old(item, newest_fetched)]
    newest_first = sorted(recent, key=lambda item: item["published_at"] or item["fetched_at"], reverse=True)
    deduped, seen_titles = [], {}
    for item in newest_first:
        key = _title_key(item.get("title", ""))
        at = seen_titles.get(key)
        if at is None:
            seen_titles[key] = len(deduped)
            deduped.append(item)
            continue
        if deduped[at].get("social") and not item.get("social"):
            deduped[at] = item
    for item in deduped:
        address = item.get("address", "")
        if not (address.startswith("http://") or address.startswith("https://")):
            continue
        constellations, open_slots = [], []
        for system in _item_systems(item):
            if system not in constellations:
                constellations.append(system)
            if counts[system] < NEWS_ITEMS_PER_SYSTEM:
                open_slots.append(system)
        if not open_slots:
            continue
        source_id = item.get("source_id", "")
        record_rows = by_source.get(source_id, [])
        grade, standing, _, _, grade_from = _source_grade(source_id, confirmed, provisional, record_rows, today)
        summary = summary_from(item.get("summary", ""), item.get("title", ""), item.get("outlet", ""))
        row = {
            "constellations": open_slots,
            "category": category_of(item.get("title", ""), summary),
            "title": item.get("title", ""),
            "summary": summary,
            "outlet": item.get("outlet") or source_id,
            "source_id": source_id,
            "address": address,
            "published_at": item.get("published_at", ""),
            "fetched_at": item.get("fetched_at", ""),
            "via": item.get("via", ""),
            "grade": grade,
            "grade_standing": standing,
        }
        if grade_from:
            row["grade_from"] = grade_from
        picked.append(row)
        for system in open_slots:
            counts[system] += 1
        used_sources.add(source_id)
    sources = {}
    for source_id in sorted(used_sources):
        record_rows = by_source.get(source_id, [])
        grade, standing, reason, graded_by, grade_from = _source_grade(source_id, confirmed, provisional, record_rows, today)
        confirmed_row = confirmed.get(source_id, {})
        provisional_row = provisional.get(source_id, {})
        row = {
            "name": confirmed_row.get("name") or provisional_row.get("name") or source_id,
            "kind": provisional_row.get("kind", ""),
            "grade": grade,
            "grade_standing": standing,
            "reason": reason,
            "graded_by": graded_by if standing == "confirmed" else "",
            "note": provisional_row.get("note", ""),
        }
        if record_rows and grade_from == "record":
            current = confirmed_row.get("reliability") or provisional_row.get("proposed_grade", "")
            row["record_line"] = source_record.record_line(record_rows, current, today)
        if grade_from:
            row["grade_from"] = grade_from
        sources[source_id] = row
    seen = [item["fetched_at"] for item in items if item.get("fetched_at")]
    return {
        # The archive last saw news at this fetch time. It stays unchanged when nothing else changed.
        "generated_at": max(seen) if seen else "",
        "items": picked,
        "sources": sources,
        "rules": {category: list(words) for category, words in NEWS_CATEGORIES.items()},
    }


def feed_report(archive, run_log="archive"):
    """FEED_REPORT_COLUMNS for every feed of the news, social and X groups, from the archive and its run log.

    runs counts the runs of the feed's group (or of every group) in the run log; copies counts the copies kept,
    each one a change. An item names a system when its title holds one of SYSTEM_WORDS.
    """
    items, _ = collected_items(archive)
    versions = read_versions(archive)
    jobs = [line["job"] for line in read_runs(archive, run_log)]
    feeds = {row["address"] for row in working_candidates() if row["check_type"].startswith(CANDIDATE_FEED_TYPE)}
    rows = []
    for group in PROVISIONAL_GROUPS:
        runs = sum(job in (f"archive {group}", "archive all") for job in jobs)
        for address in (address for address in ARCHIVED_SOURCES.get(group, ()) if address in feeds):
            copies = sum(row["address"] == address and bool(row["sha256"]) for row in versions)
            found = [item for item in items if item["via"] == address]
            naming = sum(bool(systems_named(item["title"])) for item in found)
            rows.append(dict(zip(FEED_REPORT_COLUMNS, [
                address, group, runs, copies, f"{copies / runs:.2f}" if runs else "", len(found), naming,
                f"{naming / len(found):.2f}" if found else ""])))
    return rows


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
