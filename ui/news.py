"""News-page helpers: loading latest news, filtering items, and building markup."""
import json
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import requests
import streamlit as st

from evidence.news_settings import CATEGORY_RULE_WORDS, NEWS_CATEGORIES, NEWS_CYCLE_HOURS, NEWS_LATE_HOURS, NEWS_URL
from evidence.settings import RELIABILITY_GRADES
from ui import surfaces, tooltip

DATE_FILTERS = ["7 days", "30 days", "90 days", "1 year", "all"]
GRADE_STANDINGS = ["confirmed", "provisional", "not graded"]
GRADE_TONES = {"confirmed": "ok", "provisional": "warn", "not graded": "idle"}
CATEGORY_TONES = {"launch": "accent", "satellite status and outages": "warn", "signal and service": "ok",
                  "programme and policy": "idle", "other": "idle"}
CSS = """
.news-asof { margin: 6px 0 12px; font-size: 14px; color: var(--muted); }
.news-topline { margin: 6px 0 14px; font-size: 16px; color: var(--ink); }
.st-key-news_filters [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: 8px 10px; align-items: flex-end; }
.st-key-news_filters [data-testid="stColumn"] { min-width: 160px; flex: 1 1 220px !important; width: auto !important; }
.st-key-news_filters [data-testid="stButtonGroup"] [data-baseweb="button-group"] { flex-wrap: wrap; }
.st-key-news_filters [data-testid="stButtonGroup"] button { white-space: normal; }
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
    except Exception as error:
        return {}, f"it could not be read ({error})"
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


def item_html(item, source, is_new=False, zone=timezone.utc):
    """One item with details and source details, escaped."""
    summary = escape(item.get("summary") or "The feed gives no summary beyond the headline.")
    published = date_label(item, zone)
    standing = item.get("grade_standing", "not graded")
    grade = item.get("grade", "")
    meaning = RELIABILITY_GRADES.get(grade, "No grade yet in the team's source table.")
    chip = surfaces.chip(f"Grade {grade or 'none'} · {standing}", GRADE_TONES.get(standing, "idle"))
    chip = tooltip.tip_html(chip, escape(meaning), key=item.get("address", ""))
    source_grade = source.get("grade", "")
    source_meaning = RELIABILITY_GRADES.get(source_grade, "No grade yet in the team's source table.")
    source_lines = [
        f"<span><b>Name:</b> {escape(source.get('name', item.get('source_id', '')))}</span>",
        f"<span><b>Kind:</b> {escape(source.get('kind', '') or 'not stated')}</span>",
        f"<span><b>Grade:</b> {escape(source_grade or 'none')} ({escape(source_meaning)})</span>",
        f"<span><b>Standing:</b> {escape(source.get('grade_standing', 'not graded'))}</span>",
        f"<span><b>Reason:</b> {escape(source.get('reason', '') or 'not stated')}</span>",
        f"<span><b>Via:</b> {escape(item.get('via', '') or 'not stated')}</span>",
    ]
    if source.get("graded_by"):
        source_lines.append(f"<span><b>Graded by:</b> {escape(source['graded_by'])}</span>")
    if source.get("note"):
        source_lines.append(f"<span><b>Note:</b> {escape(source['note'])}</span>")
    address = _safe_link(item.get("address", ""))
    if address:
        source_lines.append(
            f'<a href="{escape(address, quote=True)}" target="_blank" rel="noopener noreferrer">Read the article</a>')
    new_words = '<span class="news-new">new</span>' if is_new else ""
    return (
        f'<details class="news-item{" new" if is_new else ""}"><summary><span class="news-mark"><i aria-hidden="true"></i></span>'
        f'<span><span class="news-head">{escape(item.get("title", ""))}</span>'
        f'<span class="news-meta">{escape(item.get("outlet", ""))} · {escape(published)}</span></span>{new_words}</summary>'
        f'<div class="news-body"><p>{summary}</p><p><b>Outlet:</b> {escape(item.get("outlet", "") or item.get("source_id", ""))}'
        f'</p><p><b>Published:</b> {escape(published)}</p><p>{chip}</p>'
        f'<details class="news-source"><summary>Source</summary><div class="news-source-body">'
        f'{"".join(source_lines)}</div></details></div></details>'
    )


def category_body_html(items, sources, zone=timezone.utc):
    """Markup for one category's list."""
    rows = [item_html(item, sources.get(item.get("source_id", ""), {}), is_new=item["_new"], zone=zone) for item in items]
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
        "<p>Grade standing: confirmed means the source is in the team's source table; provisional means a grade is "
        "proposed and waiting for the team's review; not graded means no grade is recorded yet.</p>"
    )


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
