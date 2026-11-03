"""Stories on the News page: items that say the same thing, grouped, with what the dashboard takes from each.

A story is built afresh from the shown items on every visit, so a source that reports it later joins it.
The rules and their numbers are in evidence/news_settings.py (STORY_*).
"""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from evidence.news_settings import (CORROBORATION_DAYS, NEWS_CATEGORIES, STORY_COMMON_SHARE, STORY_DAYS,
                                    STORY_HEADLINE_CHARACTERS, STORY_NEAR_SAME, STORY_SHARE, STORY_SHARED_WORDS, STORY_STOP_WORDS,
                                    STORY_TOLD_SHARE)
from evidence.source_record import CLAIM_CATEGORIES

WORD = re.compile(r"[a-z0-9][a-z0-9\-]*")
# A mission or satellite ID (nvs-03, gslv-f18, qzs-7, sv10) or a notice number (2026047); not a year, not L5 or E6.
ID = re.compile(r"(?=.{4,}$)(?:[a-z]{2,}-?[a-z]?\d+|\d{5,})$")
GRADE_ORDER = ("A", "B", "C", "D", "E", "F")


def _stem(word):
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


def words(text):
    """The words of a headline that can tie it to another: lower case, stop words dropped, endings cut."""
    found = WORD.findall((text or "").casefold().replace("’", "'"))
    return {_stem(word) for word in found if word not in STORY_STOP_WORDS and (len(word) > 2 or ID.match(word))}


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


def stories(items):
    """[{"headline", "summary", "category", "items" (best grade first, then newest), "words" (the story's own, marked on the page)}],
    the story with the newest item first. items are one constellation's shown items."""
    keyed = [(item, words(item.get("title", ""))) for item in sorted(items, key=_when, reverse=True)]
    counts = Counter(word for _, word_set in keyed for word in word_set)
    common = {word for word, n in counts.items() if n > max(3, STORY_COMMON_SHARE * len(keyed))}
    groups = []
    for item, word_set in keyed:
        for group in groups:
            if (group["category"] == item.get("category")
                    and any(same_story(word_set, other, common) and abs(_when(item) - _when(member)) <= timedelta(days=STORY_DAYS)
                            for member, other in group["members"])):
                group["members"].append((item, word_set))
                break
        else:
            groups.append({"category": item.get("category"), "members": [(item, word_set)]})
    return [_story(group["category"], group["members"]) for group in groups]


def _story(category, members):
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
    return {"headline": best.get("title", ""), "summary": summaries[0] if summaries else "", "category": category,
            "items": ordered, "words": told}


def rule_word(item):
    """The category word that sorted this item, as the item says it, or "" for "other"."""
    for field in ("title", "summary"):
        text = item.get(field) or ""
        for word in NEWS_CATEGORIES.get(item.get("category"), ()):
            found = re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.I)
            if found:
                return found.group(0)
    return ""


def taken_from(item, source_name):
    """Plain lines saying what the dashboard took from this item."""
    category, systems = item.get("category", "other"), item.get("constellations", [])
    word = rule_word(item)
    lines = [f'Sorted under {category} because it says "{word}".' if word
             else 'Sorted under other: no category word matched.']
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
