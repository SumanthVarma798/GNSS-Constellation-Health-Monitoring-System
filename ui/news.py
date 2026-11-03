"""News-page helpers: loading latest news, filtering items, and building markup."""
import json
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import requests
import streamlit as st

from evidence import news_stories
from evidence.news import host_id
from evidence.news_settings import (CATEGORY_RULE_WORDS, GRADE_BARS, GRADE_E_MIN_CLAIMS, NEWS_CATEGORIES, NEWS_CYCLE_HOURS,
                                    NEWS_LATE_HOURS, NEWS_URL, RECORD_WINDOW_DAYS, STORY_DAYS, STORY_SHARE,
                                    STORY_SHARED_WORDS)
from evidence.settings import RELIABILITY_GRADES
from ui import reveal, surfaces, tooltip

DATE_FILTERS = ["7 days", "30 days", "90 days", "1 year", "all"]
SHOW_FILTERS = ["all", "new only"]
GRADE_STANDINGS = ["confirmed", "provisional", "not graded"]
GRADE_TONES = {"confirmed": "ok", "provisional": "warn", "not graded": "idle"}
CATEGORY_TONES = {"launch": "accent", "satellite status and outages": "warn", "signal and service": "ok",
                  "programme and policy": "idle", "other": "idle"}
CSS = """
.news-asof { margin: 6px 0 12px; font-size: 14px; color: var(--muted); }
.news-topline { margin: 6px 0 14px; font-size: 16px; color: var(--ink); }
.st-key-news_filters { flex-direction: row !important; flex-wrap: wrap; align-items: center; gap: 10px 32px; margin: 4px 0 8px; }
.st-key-news_filters > [data-testid="stElementContainer"] { width: auto !important; flex: 0 1 auto; max-width: 100%; }
.st-key-news_filters [data-testid="stButtonGroup"] { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; overflow: visible; }
.st-key-news_filters [data-testid="stWidgetLabel"] { margin: 0; min-height: 0; }
.st-key-news_filters [data-testid="stWidgetLabel"] p { margin: 0; font-size: 14px; font-weight: 700; color: var(--ink); white-space: nowrap; }
.st-key-news_filters [data-testid="stButtonGroup"] [data-baseweb="button-group"] { flex-wrap: wrap; gap: 6px; padding: 2px;
  background: transparent; box-shadow: none; }
.st-key-news_filters [data-testid="stBaseButton-pillsActive"] { border-color: var(--accent); }
.st-key-news_filters > [data-testid="stElementContainer"]:has(.news-sr) {
  position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.st-key-news_filters [data-testid="stButtonGroup"] button { white-space: normal; padding: 4px 12px; }
.news-cat-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 10px 0 14px; }
.news-cat-tile { display: grid; place-items: center; gap: 4px; min-height: 104px; text-align: center; font-size: 14px;
  border-radius: var(--r); border: 1px solid var(--edge); background: var(--platform); box-shadow: var(--raised-sm); padding: 10px 12px; }
.news-cat-tile b { font-size: 24px; line-height: 1; }
.news-cat-dot { width: 10px; height: 10px; border-radius: 999px; background: var(--idle); box-shadow: var(--pressed); }
.news-cat-tile.ok .news-cat-dot { background: var(--ok); } .news-cat-tile.warn .news-cat-dot { background: var(--warn); }
.news-cat-tile.idle .news-cat-dot { background: var(--idle); } .news-cat-tile.accent .news-cat-dot { background: var(--accent); }
@media (max-width: 375px) { .news-cat-tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.news-list { display: grid; gap: 8px; width: 100%; max-width: 100%; }
.news-item { border-radius: 14px; border: 1px solid var(--edge); background: var(--well); box-shadow: var(--pressed); overflow: hidden; }
.news-item summary { list-style: none; cursor: pointer; padding: 10px 12px; display: grid; grid-template-columns: auto 1fr auto;
  gap: 8px; align-items: start; width: 100%; }
.news-item summary::-webkit-details-marker { display: none; }
.news-item .news-mark { width: 10px; margin-top: 6px; display: inline-flex; justify-content: center; }
.news-item .news-mark i { width: 8px; height: 8px; border-radius: 999px; background: var(--track); display: inline-block; }
.news-item.new .news-mark i { background: var(--accent); }
.news-item .news-head { min-width: 0; word-break: break-word; color: var(--ink); }
.news-item .news-meta { color: var(--muted); font-size: 13px; margin-top: 3px; display: block; }
.news-item .news-new { font-size: 12px; color: var(--accent); text-transform: lowercase; align-self: center; }
.news-item .news-body { padding: 0 12px 12px 30px; font-size: 14px; max-width: 100%; }
.news-item .news-body p { margin: 0 0 8px; max-width: none; }
.news-source { border: 1px solid var(--edge); border-radius: 12px; background: var(--platform); box-shadow: var(--raised-sm); }
.news-source > summary { list-style: none; cursor: pointer; padding: 8px 10px; font-weight: 600; color: var(--muted); }
.news-source > summary::-webkit-details-marker { display: none; }
.news-source-body { padding: 0 10px 10px; display: grid; gap: 4px; font-size: 13px; }
.news-story-sources { display: grid; gap: 6px; margin-top: 8px; }
.news-story-sources > b { font-size: 13px; color: var(--muted); }
.news-said, .news-took { margin: 0 0 8px; padding: 8px 10px; border-left: 3px solid var(--edge); font-size: 14px; }
.news-said mark { background: none; color: var(--accent); font-weight: 600; }
.news-took ul { margin: 4px 0 0; padding-left: 18px; }
.news-grade-legend { margin: 10px 0 0; border: 1px solid var(--edge); border-radius: var(--r); background: var(--platform);
  box-shadow: var(--raised-sm); padding: 8px 10px; }
.news-grade-legend > summary { cursor: pointer; font-weight: 600; color: var(--ink); }
.news-grade-legend > summary::-webkit-details-marker { margin-right: 6px; }
.news-grade-legend table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
.news-grade-legend th, .news-grade-legend td { border-top: 1px solid var(--edge); padding: 6px 4px; text-align: left; vertical-align: top; }
"""


def _time(text):
    try:
        return datetime.fromisoformat((text or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _time_words(moment, zone):
    local = moment.astimezone(zone)
    return f"{local:%d %b %Y %H:%M} UTC" if zone == timezone.utc else f"{local:%d %b %Y %H:%M} {local:%Z}"


def _safe_link(address):
    return address if (address or "").startswith(("http://", "https://")) else ""


@st.cache_data(ttl=600, show_spinner=False)
def load_news(source=NEWS_URL):
    """Load latest-news JSON from a URL or local path. Returns (data, problem)."""
    try:
        if (source or "").startswith(("http://", "https://")):
            reply = requests.get(source, timeout=10)
            reply.raise_for_status()
            payload = reply.text
        else:
            payload = Path(source).read_text(encoding="utf-8")
    except requests.HTTPError as error:
        return {}, f"the news file could not be read (GitHub answered {error.response.status_code})"
    except Exception:  # no answer, no file, or anything else: the page must still draw
        return {}, "the news file could not be read"
    try:
        data = json.loads(payload)
    except ValueError:
        return {}, "it is not valid JSON"
    if not isinstance(data, dict):
        return {}, "it is not a JSON object"
    if not isinstance(data.get("items"), list):
        return {}, 'it is missing the "items" list'
    if not isinstance(data.get("sources"), dict):
        return {}, 'it is missing the "sources" map'
    if not isinstance(data.get("rules"), dict):
        return {}, 'it is missing the "rules" map'
    cleaned, skipped = [], 0
    for item in data["items"]:
        if (isinstance(item, dict)
                and all(isinstance(item.get(key), str) for key in ("title", "address", "source_id", "category"))
                and isinstance(item.get("constellations"), list)):
            cleaned.append(item)
        else:
            skipped += 1
    sources = {source_id: row if isinstance(row, dict) else {} for source_id, row in data["sources"].items()}
    return {**data, "items": cleaned, "sources": sources, "invalid_items": skipped}, ""


def cookie_seen():
    """The seen-cookie time for this session, or None."""
    value = (getattr(st.context, "cookies", {}) or {}).get("gnss_news_seen", "")
    return _time(value)


def is_new(item, seen_at, now):
    """True when this item is new for the visit."""
    fetched = _time(item.get("fetched_at"))
    if fetched is None:
        return False
    if seen_at is not None:
        return fetched > seen_at
    return fetched >= now - timedelta(hours=24)


def filter_items(items, constellation, categories, standings, date_window, only_new, seen_at, now):
    """Items for one constellation after category, grade, date and new-only filters."""
    days = {"7 days": 7, "30 days": 30, "90 days": 90, "1 year": 365, "all": None}[date_window]
    cutoff = now - timedelta(days=days) if days is not None else None
    kept = []
    for item in items:
        if constellation not in item.get("constellations", []):
            continue
        if item.get("category") not in categories or item.get("grade_standing") not in standings:
            continue
        published = _time(item.get("published_at")) or _time(item.get("fetched_at"))
        if cutoff is not None and (published is None or published < cutoff):
            continue
        fresh = is_new(item, seen_at, now)
        if only_new and not fresh:
            continue
        kept.append({**item, "_new": fresh, "_published": published})
    kept.sort(key=lambda row: row["_published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return kept


def date_label(item, zone=timezone.utc):
    """A short published date, or fetched date when published is missing."""
    moment = _time(item.get("published_at")) or _time(item.get("fetched_at"))
    return f"{moment.astimezone(zone):%d %b %Y}" if moment else "date not given"


def category_tiles_html(items):
    """Raised category tiles from filtered items."""
    counts = {category: 0 for category in NEWS_CATEGORIES}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    tiles = []
    for category in NEWS_CATEGORIES:
        count = counts.get(category, 0)
        if count:
            tone = CATEGORY_TONES.get(category, "idle")
            tiles.append(f'<div class="news-cat-tile {tone}"><span class="news-cat-dot"></span><b class="num">{count}</b>'
                         f"<span>{escape(category)}</span></div>")
    return f'<div class="news-cat-tiles">{"".join(tiles)}</div>' if tiles else ""


def marked_html(text, words, rule_word=""):
    """text, escaped, with each word of the story (and the category word) marked."""
    parts, last = [], 0
    rule = (rule_word or "").casefold()
    for found in re.finditer(r"[A-Za-z0-9][A-Za-z0-9\-]*", text or ""):
        token = found.group(0)
        parts.append(escape(text[last:found.start()]))
        hit = news_stories._stem(token.casefold()) in words or token.casefold() == rule
        parts.append(f"<mark>{escape(token)}</mark>" if hit else escape(token))
        last = found.end()
    parts.append(escape((text or "")[last:]))
    return "".join(parts)


def item_html(item, source, is_new=False, zone=timezone.utc, words=frozenset()):
    """One source's report within a story: outlet and date; opened, what it said (story words marked), what the
    dashboard took from it, its grade and the source's details. Escaped."""
    published = date_label(item, zone)
    chip = tooltip.tip_html(surfaces.chip(grade_words(item), GRADE_TONES.get(item.get("grade_standing"), "idle")),
                            escape(RELIABILITY_GRADES.get(item.get("grade", ""), "No grade yet in the team's source table.")),
                            key=item.get("address", ""))
    name, source_id = source.get("name") or item.get("source_id", ""), item.get("source_id", "")
    lines = [("Name", name if name == source_id else f"{name} ({source_id})"), ("What it is", source.get("kind", "")),
             ("Grade", grade_words(source, meaning=True)), ("Why this grade", source.get("reason", "")),
             ("Record", source.get("record_line", "")), ("Graded by", source.get("graded_by", "")),
             ("Note", source.get("note", "")),
             ("Found through", host_id(item.get("via", "")))]
    source_lines = [f"<span><b>{label}:</b> {escape(value)}</span>" for label, value in lines if value]
    address = _safe_link(item.get("address", ""))
    if address:
        source_lines.append(
            f'<a href="{escape(address, quote=True)}" target="_blank" rel="noopener noreferrer">Read the article</a>')
    rule = news_stories.rule_word(item)
    said = f"<b>{marked_html(item.get('title', ''), words, rule)}</b>"
    if item.get("summary"):
        said += f"<br>{marked_html(item['summary'], words, rule)}"
    took = "".join(f"<li>{escape(line)}</li>" for line in news_stories.taken_from(item, name))
    new_words = '<span class="news-new">new</span>' if is_new else ""
    return (
        f'<details class="news-item{" new" if is_new else ""}"><summary><span class="news-mark"><i aria-hidden="true"></i></span>'
        f'<span><span class="news-head">{escape(item.get("outlet", "") or name)}</span>'
        f'<span class="news-meta">{escape(published)} · {escape(grade_words(item))}</span></span>{new_words}</summary>'
        f'<div class="news-body"><p class="news-said">What it said: {said}</p>'
        f'<div class="news-took">What the dashboard took from it:<ul>{took}</ul></div><p>{chip}</p>'
        f'<details class="news-source"><summary>Source</summary><div class="news-source-body">'
        f'{"".join(source_lines)}</div></details></div></details>'
    )


def story_html(story, sources, zone=timezone.utc):
    """One story: its headline and summary; opened, every source that reported it, best grade first."""
    items = story["items"]
    fresh = sum(1 for item in items if item.get("_new"))
    outlets = list(dict.fromkeys(item.get("outlet") or item.get("source_id", "") for item in items))
    named = ", ".join(outlets[:3]) + (f" and {len(outlets) - 3} more" if len(outlets) > 3 else "")
    newest = max(items, key=news_stories._when)
    meta = f"{reveal.count(len(items), 'source')} · {named} · latest {date_label(newest, zone)}"
    if story["summary"]:
        summary = escape(story["summary"])
    else:
        oldest = min(items, key=news_stories._when)
        span = (date_label(oldest, zone) if date_label(oldest, zone) == date_label(newest, zone)
                else f"{date_label(oldest, zone)} to {date_label(newest, zone)}")
        summary = f"No feed gave a summary beyond the headline. Reported {span}."
    rows = "".join(item_html(item, sources.get(item.get("source_id", ""), {}), is_new=item.get("_new", False),
                             zone=zone, words=story["words"]) for item in items)
    new_words = f'<span class="news-new">{fresh} new</span>' if fresh else ""
    return (
        f'<details class="news-item{" new" if fresh else ""}"><summary><span class="news-mark"><i aria-hidden="true"></i></span>'
        f'<span><span class="news-head">{escape(story["headline"])}</span>'
        f'<span class="news-meta">{escape(meta)}</span></span>{new_words}</summary>'
        f'<div class="news-body"><p>{summary}</p><div class="news-story-sources"><b>Who reported it</b>{rows}</div>'
        f'</div></details>'
    )


def grade_words(row, meaning=False):
    """'Grade C · provisional', or 'Not graded yet'; with meaning, the grade's meaning follows the letter."""
    grade = row.get("grade", "")
    if not grade:
        return "Not graded yet"
    said = f", {RELIABILITY_GRADES[grade]}" if meaning and grade in RELIABILITY_GRADES else ""
    from_record = " · from the record" if row.get("grade_from") == "record" else ""
    return f"Grade {grade}{said} · {row.get('grade_standing', '')}{from_record}"


def grade_legend_html():
    """The grade legend for the rules section."""
    reached = {
        "A": "never by the record; a person decides, after a shortlist finding",
        "B": f"at least {GRADE_BARS['B'][0]} checked claims and score at least {GRADE_BARS['B'][1]:.2f}",
        "C": f"at least {GRADE_BARS['C'][0]} checked claims and score at least {GRADE_BARS['C'][1]:.2f}",
        "D": f"at least {GRADE_BARS['D'][0]} checked claims and score at least {GRADE_BARS['D'][1]:.2f}",
        "E": f"at least {GRADE_E_MIN_CLAIMS} checked claims, but below the D bar",
        "F": f"the start; fewer than {GRADE_E_MIN_CLAIMS} checked claims",
    }
    rows = "".join(
        f"<tr><th>{grade}</th><td>{escape(RELIABILITY_GRADES.get(grade, ''))}</td><td>{escape(reached[grade])}</td></tr>"
        for grade in ("A", "B", "C", "D", "E", "F")
    )
    return (
        '<details class="news-grade-legend"><summary>How grades work</summary>'
        "<table><thead><tr><th>Grade</th><th>Meaning</th><th>Reached by the record when</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"<p>Score = (held + 1) ÷ (held + failed + 2) over the last {RECORD_WINDOW_DAYS} days, "
        "so a few lucky claims are not enough.</p></details>"
    )


def category_body_html(items, sources, zone=timezone.utc):
    """Markup for one category's list: its items as stories, the newest story first."""
    rows = [story_html(story, sources, zone) for story in news_stories.stories(items)]
    return f'<div class="news-list">{"".join(rows)}</div>'


def sorting_rules_html():
    """The explanatory section shown at the end of the page."""
    rules = "".join(
        f"<li><b>{escape(category)}:</b> {escape(', '.join(words) if words else 'fallback when no earlier rule matches')}</li>"
        for category, words in NEWS_CATEGORIES.items()
    )
    return (
        f"<p>{escape(CATEGORY_RULE_WORDS)}</p><ul>{rules}</ul>"
        "<p>These are plain word rules on the headline and feed text; a model may sort them later.</p>"
        "<p>An item appears under every constellation its headline names.</p>"
        "<p>Items in one category that tell the same story are shown once: their headlines name the same mission or "
        f"satellite (NVS-03, GSLV-F18), or share at least {STORY_SHARED_WORDS} uncommon words making up "
        f"{STORY_SHARE:.0%} of the shorter headline, and each came out within {STORY_DAYS} days of another in it. "
        "Stories are rebuilt on every visit, so a source that reports later joins its story. Open a story for who "
        "reported it, and a source for what it said and what the dashboard took from it.</p>"
        "<p>Grade standing: confirmed means the source is in the team's source table; provisional means a grade is "
        "proposed and waiting for the team's review; not graded means no grade is recorded yet.</p>"
        f"{grade_legend_html()}"
    )


def screen_reader_heading(label):
    """A filter's name for screen readers: Streamlit hides the pills' own label from them (aria-hidden)."""
    st.html(f'<span class="news-sr" role="heading" aria-level="3">{escape(label)}</span>')


def seen_note(seen_at):
    """Help words for the new-only toggle."""
    if seen_at is None:
        return "No visit is stored yet, so 'new' means fetched in the last 24 hours."
    return f"New means fetched after your last visit on {_time_words(seen_at, timezone.utc)}."


def as_of_line(generated_at, now, zone=timezone.utc):
    """A notice when news is late, else a quiet as-of line."""
    generated = _time(generated_at)
    if generated is None:
        return surfaces.notice("News time is not in the file. Collection runs every 3 hours.", "warn")
    if now - generated > timedelta(hours=NEWS_LATE_HOURS):
        return surfaces.notice(f"News was last seen {_time_words(generated, timezone.utc)}. Collection runs every "
                               f"{NEWS_CYCLE_HOURS} hours.", "warn")
    return f'<p class="news-asof">News as of {escape(_time_words(generated, zone))}</p>'
