"""Stories on the News page: items that say the same thing, grouped, with what the dashboard takes from each.

A story is built afresh from the shown items on every visit, so a source that reports it later joins it.
The rules and their numbers are in evidence/news_settings.py (STORY_*).
"""
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import cache

from evidence.news_settings import (CORROBORATING_GRADES, CORROBORATION_DAYS, IMPACT_CHECK_ORDER, IMPACT_OF_AN_ID,
                                    NEWS_CATEGORIES, NEWS_IMPACTS, STATE_AGENCIES, STORY_COMMON_SHARE, STORY_DAYS,
                                    STORY_HEADLINE_CHARACTERS, STORY_NEAR_SAME, STORY_SHARE, STORY_SHARED_WORDS,
                                    STORY_STOP_WORDS, STORY_TOLD_SHARE)
from evidence.registry_tables import read_table
from evidence.registry_settings import (
    REGISTRY_DASHBOARD_SATELLITES_FILE,
    REGISTRY_SATELLITES_FILE,
    REGISTRY_SIGHTINGS_FILE
)
from evidence.source_record import CLAIM_CATEGORIES

WORD = re.compile(r"[a-z0-9][a-z0-9\-]*")
# A mission or satellite ID (nvs-03, gslv-f18, qzs-7, sv10, irnss-1l) or a notice number (2026047); not a year, not
# L5 or E6.
ID = re.compile(r"(?=.{4,}$)(?:[a-z]{2,}-?(?:[a-z]?\d+|\d+[a-z])|\d{5,})$")
GRADE_ORDER = ("A", "B", "C", "D", "E", "F")


def stem(word):
    """launches, launched, launching -> launch; satellites, satellite -> satellit. IDs stay as they are."""
    if ID.match(word):
        return word
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return word[:-1] if len(word) > 4 and word.endswith("e") else word


def words(text, aliased=True):
    """The words of a headline that can tie it to another: lower case, stop words dropped, endings cut, and a satellite's
    other name (IRNSS-1L) read as the one the registry pairs it with (NVS-03)."""
    found = WORD.findall(unicodedata.normalize("NFKC", text or "").casefold().replace("’", "'"))   # 𝐍𝐚𝐯𝐈𝐂 reads as navic
    kept = {stem(word) for word in found if word not in STORY_STOP_WORDS and (len(word) > 2 or ID.match(word))}
    return {aliases().get(word, word) for word in kept} if aliased else kept


@cache
def aliases():
    """{ID: the one it stands for}: a satellite's other names, from the registry's notes and dashboard names, so a
    headline saying IRNSS-1L tells the same story as one saying NVS-03 ("NVS-03 (IRNSS-1L)"). An ID on more than one
    registry row (BeiDou-3, BeiDou-2) names a family, not a satellite, and stands for nothing."""
    per_row, rows_naming = _registry_ids()
    aliases = {}
    for ids in per_row:
        own = [word for word in ids if rows_naming[word] == 1]   # the dashboard's name first, then the note's order
        aliases.update({word: own[0] for word in own[1:]})
    return aliases


def _registry_ids():
    """([the IDs each registry row names, the dashboard's name first], Counter of how many rows name each ID)."""
    names = {row["svn"]: row["dashboard_name"] for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE)}
    per_row = [list(dict.fromkeys(_ids_in_order(f'{names.get(row["svn"], "")} {row["note"]}')))
               for row in read_table(REGISTRY_SATELLITES_FILE) + read_table(REGISTRY_SIGHTINGS_FILE)]
    return per_row, Counter(word for ids in per_row for word in ids)


@cache
def satellite_ids():
    """The IDs that name one satellite: on exactly one registry row (NVS-03, QZS-7), not a family (BeiDou-3)."""
    return {word for word, rows in _registry_ids()[1].items() if rows == 1}


def _ids_in_order(text):
    """The IDs a text names, in the order it names them."""
    found = WORD.findall(unicodedata.normalize("NFKC", text or "").casefold())
    return [stem(word) for word in found if ID.match(word)]


def _ids(word_set):
    return {word for word in word_set if ID.match(word)}


def same_story(a, b, common):
    """True when two headlines' words tell one story (see STORY_* in evidence/news_settings.py)."""
    ids_a, ids_b = _ids(a), _ids(b)
    if ids_a & ids_b:
        return True
    if ids_a and ids_b:   # both name an ID, and not the same one: two notices, two satellites
        return False
    if len(a & b) >= STORY_NEAR_SAME * len(a | b):   # the same headline, however common its words
        return True
    shared = (a - common) & (b - common)
    shorter = min(len(a - common), len(b - common)) or 1
    return len(shared) >= STORY_SHARED_WORDS and len(shared) / shorter >= STORY_SHARE


def _when(item):
    for key in ("published_at", "fetched_at"):
        try:
            moment = datetime.fromisoformat((item.get(key) or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)   # a time without a zone is UTC
    return datetime.min.replace(tzinfo=timezone.utc)


def _grade_rank(item):
    grade = item.get("grade", "")
    return GRADE_ORDER.index(grade) if grade in GRADE_ORDER else len(GRADE_ORDER)


def _story_words(item):
    """The headline's words, and, when the headline names no mission or satellite, the IDs its text names: a social post
    cut short ("𝐍𝐚𝐯𝐈𝐂 𝐈𝐒 𝐁𝐀𝐂𝐊 8 months ago...") names NVS-03 only further on."""
    found = words(item.get("title", ""))
    return found if _ids(found) else found | _ids(words(item.get("summary", "")))


def stories(items):
    """[{"headline", "summary", "impact", "items" (best grade first, then newest), "words" (the story's own, marked on the page)}],
    the story with the newest item first. items are one constellation's shown items."""
    keyed = [(item, _story_words(item)) for item in sorted(items, key=_when, reverse=True)]
    counts = Counter(word for _, word_set in keyed for word in word_set)
    common = {word for word, n in counts.items() if n > max(3, STORY_COMMON_SHARE * len(keyed))}
    groups = []
    for item, word_set in keyed:
        impact_of = impact(item)[0]
        for group in groups:
            if (group["impact"] == impact_of
                    and any(same_story(word_set, other, common) and abs(_when(item) - _when(member)) <= timedelta(days=STORY_DAYS)
                            for member, other in group["members"])):
                group["members"].append((item, word_set))
                break
        else:
            groups.append({"impact": impact_of, "members": [(item, word_set)]})
    return [_story(group["impact"], group["members"]) for group in groups]


def _story(impact_of, members):
    shared = Counter(word for _, word_set in members for word in word_set)
    told = {word for word, n in shared.items() if n >= max(2, STORY_TOLD_SHARE * len(members))}
    # The headline: the one whose words the others use most, by share, so a long post does not win by length
    # (a very short one counts as 5 words); then the best grade, then the newest. One longer than
    # STORY_HEADLINE_CHARACTERS only when all are.
    short = [pair for pair in members if len(pair[0].get("title", "")) <= STORY_HEADLINE_CHARACTERS] or members
    best, _ = max(short, key=lambda pair: (len(pair[1] & told) / max(len(pair[1]), 5), -_grade_rank(pair[0]),
                                           _when(pair[0])))
    ordered = sorted((item for item, _ in members), key=lambda item: (_grade_rank(item), -_when(item).timestamp()))
    summaries = [item["summary"] for item in [best, *ordered] if item.get("summary")]
    return {"headline": best.get("title", ""), "summary": summaries[0] if summaries else "", "impact": impact_of,
            "items": ordered, "words": told}


@cache
def _impact_words():
    """{impact: one pattern for all its whole words, its own and its categories'}."""
    found = {}
    for name in IMPACT_CHECK_ORDER:
        rule = NEWS_IMPACTS[name]
        every = list(rule["words"]) + [word for category in rule["categories"] for word in NEWS_CATEGORIES.get(category, ())]
        found[name] = _whole_words(sorted(every, key=len, reverse=True))
    return found


def impact(item):
    """(impact, the word or ID that decided it, as the item says it; "" for background). The rules are NEWS_IMPACTS in
    evidence/news_settings.py: impact words on the headline, then on the feed text; then a satellite or mission ID."""
    for field in ("title", "summary"):
        text = item.get(field) or ""
        for name, pattern in _impact_words().items():
            if found := pattern.search(text):
                return name, found.group(0)
    for found in re.finditer(r"[^\W_][\w\-]*", unicodedata.normalize("NFKC", item.get("title") or "")):
        token = found.group(0)
        if stem(token.casefold()) in satellite_ids() or token.casefold() in aliases():   # NVS-03, IRNSS-1L; not BeiDou-3
            return IMPACT_OF_AN_ID, token
    return "background", ""


def _whole_words(words):
    return re.compile(rf"(?<!\w)(?:{'|'.join(map(re.escape, words))})(?!\w)", re.I)


def _quotes(item, agency):
    """True when this report comes from the agency's own host or names it in its headline, feed text or outlet."""
    _, words, hosts = STATE_AGENCIES[agency]
    host = item.get("source_id", "")
    return (any(host == name or host.endswith("." + name) for name in hosts)
            or bool(_whole_words(words).search(" | ".join(item.get(key) or "" for key in ("title", "summary", "outlet")))))


def agency_ledger(items):
    """[{"agency", "country", "stories", "confirmed"}] in STATE_AGENCIES order, from the stories the items tell. A story
    quoting an agency is confirmed when a report in it that quotes no state agency, from a source confirmed at grade A
    or B (an operator, an official body), came out at or after the first quoting report, within CORROBORATION_DAYS. Nothing is fetched: only the reports already in the news file count."""
    told = stories(items)
    rows = []
    for agency, (country, _, _) in STATE_AGENCIES.items():
        quoting = confirmed = 0
        for story in told:
            quotes = [item for item in story["items"] if _quotes(item, agency)]
            if not quotes:
                continue
            quoting += 1
            first = min(_when(item) for item in quotes)
            confirmed += any(item.get("grade") in CORROBORATING_GRADES and item.get("grade_standing") == "confirmed"
                             and not any(_quotes(item, other) for other in STATE_AGENCIES)
                             and first <= _when(item) <= first + timedelta(days=CORROBORATION_DAYS)
                             for item in story["items"])
        rows.append({"agency": agency, "country": country, "stories": quoting, "confirmed": confirmed})
    return rows


def taken_from(item, source_name):
    """Plain lines saying what the dashboard took from this item."""
    category, systems = item.get("category", "other"), item.get("constellations", [])
    impact_of, word = impact(item)
    lines = [f'Under {impact_of}: it says "{word}".' if word else f"Under {impact_of}: no impact word matched."]
    if systems:
        lines.append(f"Listed under {', '.join(systems)}: the headline names {'it' if len(systems) == 1 else 'them'}.")
    claim = CLAIM_CATEGORIES.get(category)
    named = ", ".join(systems) or "its constellation"
    if claim == "launch":
        lines.append(f"Taken as a launch claim for {named}. The weekly source record checks it against the "
                     f"registry's launch dates, and the result counts toward {source_name}'s grade.")
    elif claim == "status":
        lines.append(f"Taken as a status claim for {named}. It holds when a different source graded A or B reports "
                     f"it within {CORROBORATION_DAYS} days, and the result counts toward {source_name}'s grade.")
    else:
        lines.append("No claim is taken from it: only launch and status items are checked for the source record.")
    return lines
