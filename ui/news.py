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
from evidence.news_settings import (CORROBORATING_GRADES, CORROBORATION_DAYS, GRADE_BARS, GRADE_E_MIN_CLAIMS,
                                    IMPACT_CHECK_ORDER, IMPACT_OF_AN_ID, NEWS_CATEGORIES, NEWS_CYCLE_HOURS, NEWS_IMPACTS,
                                    NEWS_LATE_HOURS, NEWS_NEW_GRACE_HOURS, NEWS_URL, RECORD_WINDOW_DAYS, STORY_DAYS, STORY_SHARE,
                                    STORY_SHARED_WORDS)
from evidence.settings import RELIABILITY_GRADES
from ui import marks, reveal, surfaces, tooltip

DATE_FILTERS = ["7 days", "30 days", "90 days", "1 year", "all"]
SHOW_FILTERS = ["all", "new only"]
GRADE_STANDINGS = ["confirmed", "provisional", "not graded"]
GRADE_TONES = {"confirmed": "ok", "provisional": "warn", "not graded": "idle"}
IMPACT_TONES = {"affects service now": "warn", "changes the constellation": "accent", "plans and policy": "ok",
                "background": "idle"}
CSS = """
.news-asof { margin: 6px 0 12px; font-size: var(--fs-small); color: var(--fc-small); }
.news-topline { margin: 6px 0 14px; font-size: var(--fs-side); color: var(--ink); }
.st-key-news_filters { flex-direction: row !important; flex-wrap: wrap; align-items: center; gap: 10px 32px; margin: 4px 0 8px; }
.st-key-news_filters > [data-testid="stElementContainer"] { width: auto !important; flex: 0 1 auto; max-width: 100%; }
.st-key-news_filters [data-testid="stButtonGroup"] { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; overflow: visible; }
.st-key-news_filters [data-testid="stWidgetLabel"] { margin: 0; min-height: 0; }
.st-key-news_filters [data-testid="stWidgetLabel"] p { margin: 0; font-size: var(--fs-body); font-weight: 700; color: var(--ink); white-space: nowrap; }
.st-key-news_filters [data-testid="stButtonGroup"] [data-baseweb="button-group"] { flex-wrap: wrap; gap: 6px; padding: 2px;
  background: transparent; box-shadow: none; }
.st-key-news_filters [data-testid="stBaseButton-pillsActive"] { border-color: var(--accent); }
.st-key-news_filters > [data-testid="stElementContainer"]:has(.news-sr) {
  position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.st-key-news_filters [data-testid="stButtonGroup"] button { white-space: normal; padding: 4px 12px; }
.news-cat-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 10px 0 14px; }
.news-cat-tile { display: grid; place-items: center; gap: 4px; min-height: 104px; text-align: center; font-size: var(--fs-body);
  border-radius: var(--r); border: 1px solid var(--edge); background: var(--platform); box-shadow: var(--raised-sm); padding: 10px 12px; }
.news-cat-tile b { font-size: var(--fs-num); font-weight: var(--fw-num); line-height: 1; }
.news-cat-tile small { font-size: var(--fs-small); color: var(--fc-small); }
.news-ledger { display: grid; grid-template-columns: minmax(0, 1.4fr) auto minmax(0, 2fr); gap: 8px 14px; align-items: center;
  font-size: var(--fs-body); }
.news-ledger > .h { font-size: var(--fs-small); color: var(--fc-small); font-weight: 600; }
.news-ledger small { display: block; font-size: var(--fs-small); color: var(--fc-small); }
.news-ledger .n { text-align: right; font-size: var(--fs-side); }
.news-ledger .n.zero, .news-ledger .quiet { color: var(--fc-small); }
.news-ledger > .h.n { font-size: var(--fs-small); }
.news-ledger .share { display: grid; grid-template-columns: minmax(40px, 1fr) auto; gap: 8px; align-items: center; }
.news-ledger .bar { height: 8px; border-radius: 999px; background: var(--well); box-shadow: var(--pressed); overflow: hidden; }
.news-ledger .bar i { display: block; height: 100%; border-radius: 999px; background: var(--ok); }
.news-cat-dot { width: 10px; height: 10px; border-radius: 999px; background: var(--idle); box-shadow: var(--pressed); }
.news-cat-tile.ok .news-cat-dot { background: var(--ok); } .news-cat-tile.warn .news-cat-dot { background: var(--warn); }
.news-cat-tile.idle .news-cat-dot { background: var(--idle); } .news-cat-tile.accent .news-cat-dot { background: var(--accent); }
.news-cat-tile.ok b { color: var(--ok); } .news-cat-tile.warn b { color: var(--warn); } .news-cat-tile.accent b { color: var(--accent); }
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
.news-item .news-meta { color: var(--fc-small); font-size: var(--fs-small); margin-top: 3px; display: block; }
.news-about { display: inline-flex; flex-wrap: wrap; gap: 2px 12px; margin-right: 12px; color: var(--ink); }
.news-item .news-new { font-size: var(--fs-small); color: var(--accent); text-transform: lowercase; align-self: center; }
.news-item .news-body { padding: 0 12px 12px 30px; font-size: var(--fs-body); max-width: 100%; }
.news-item .news-body p { margin: 0 0 8px; max-width: none; }
.news-source { border: 1px solid var(--edge); border-radius: 12px; background: var(--platform); box-shadow: var(--raised-sm); }
.news-source > summary { list-style: none; cursor: pointer; padding: 8px 10px; font-weight: 600; color: var(--muted); }
.news-source > summary::-webkit-details-marker { display: none; }
.news-source-body { padding: 0 10px 10px; display: grid; gap: 4px; font-size: var(--fs-small); }
.news-story-sources { display: grid; gap: 6px; margin-top: 8px; }
.news-story-sources > b { font-size: var(--fs-small); color: var(--fc-small); }
.news-said, .news-took { margin: 0 0 8px; padding: 8px 10px; border-left: 3px solid var(--edge); font-size: var(--fs-body); }
.news-said mark { background: none; color: var(--accent); font-weight: 600; }
.news-took ul { margin: 4px 0 0; padding-left: 18px; }
.news-grade-legend { margin: 10px 0 0; border: 1px solid var(--edge); border-radius: var(--r); background: var(--platform);
  box-shadow: var(--raised-sm); padding: 8px 10px; }
.news-grade-legend > summary { cursor: pointer; font-weight: 600; color: var(--ink); }
.news-grade-legend > summary::-webkit-details-marker { margin-right: 6px; }
.news-grade-legend table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: var(--fs-small); }
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
    """True when this item is new for the visit: fetched after the last visit (or in the last 24 hours with no visit
    stored) and published then too, less NEWS_NEW_GRACE_HOURS. An article published days earlier and only found now
    (Google News re-lists old ones: the NVS-03 launch stories reappeared on 9 Nov) is not news to the reader."""
    fetched = _time(item.get("fetched_at"))
    if fetched is None:
        return False
    since = seen_at if seen_at is not None else now - timedelta(hours=24)
    published = _time(item.get("published_at")) or fetched
    return fetched > since and published > since - timedelta(hours=NEWS_NEW_GRACE_HOURS)


def filter_items(items, constellation, impacts, standings, date_window, only_new, seen_at, now):
    """Items for one constellation after impact, grade, date and new-only filters, each with its "_impact"."""
    days = {"7 days": 7, "30 days": 30, "90 days": 90, "1 year": 365, "all": None}[date_window]
    cutoff = now - timedelta(days=days) if days is not None else None
    kept = []
    for item in items:
        if constellation not in item.get("constellations", []):
            continue
        impact = news_stories.impact(item)[0]
        if impact not in impacts or item.get("grade_standing") not in standings:
            continue
        published = _time(item.get("published_at")) or _time(item.get("fetched_at"))
        if cutoff is not None and (published is None or published < cutoff):
            continue
        fresh = is_new(item, seen_at, now)
        if only_new and not fresh:
            continue
        kept.append({**item, "_new": fresh, "_published": published, "_impact": impact})
    kept.sort(key=lambda row: row["_published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return kept


def date_label(item, zone=timezone.utc):
    """A short published date, or fetched date when published is missing."""
    moment = _time(item.get("published_at")) or _time(item.get("fetched_at"))
    return f"{moment.astimezone(zone):%d %b %Y}" if moment else "date not given"


def impact_tiles_html(stories):
    """A raised tile per impact with its story count large and its item count small, coloured by impact."""
    tiles = []
    for impact in NEWS_IMPACTS:
        told = [story for story in stories if story["impact"] == impact]
        if told:
            items = sum(len(story["items"]) for story in told)
            tiles.append(f'<div class="news-cat-tile {IMPACT_TONES.get(impact, "idle")}"><span class="news-cat-dot"></span>'
                         f'<b class="num">{len(told)}</b><span>{escape(impact)}</span>'
                         f'<small>{"story" if len(told) == 1 else "stories"} · {reveal.count(items, "item")}</small></div>')
    return f'<div class="news-cat-tiles">{"".join(tiles)}</div>' if tiles else ""


def marked_html(text, words, rule_word=""):
    """text, escaped, with each word of the story (and the word that set its impact) marked."""
    parts, last = [], 0
    rule = (rule_word or "").casefold()
    for found in re.finditer(r"[A-Za-z0-9][A-Za-z0-9\-]*", text or ""):
        token = found.group(0)
        parts.append(escape(text[last:found.start()]))
        stem = news_stories.stem(token.casefold())
        hit = news_stories.aliases().get(stem, stem) in words or token.casefold() == rule   # IRNSS-1L marks as NVS-03
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
    rule = news_stories.impact(item)[1]
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
    about = list(dict.fromkeys(name for item in items for name in item.get("constellations", [])))   # which it names
    about_html = "".join(marks.named(name) for name in about)
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
        f'<span class="news-meta">{f"""<span class="news-about">{about_html}</span>""" if about else ""}'
        f'{escape(meta)}</span></span>{new_words}</summary>'
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
        "F": f"1 to {GRADE_E_MIN_CLAIMS - 1} checked claims; with none checked, not graded",
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


def impact_body_html(items, sources, zone=timezone.utc, stories=None):
    """Markup for one impact's list: its stories (or its items, grouped here), the newest story first."""
    rows = [story_html(story, sources, zone) for story in (news_stories.stories(items) if stories is None else stories)]
    return f'<div class="news-list">{"".join(rows)}</div>'


def sorting_rules_html():
    """The rules section at the end of the page: impact words, story grouping, grade standing, the grade legend."""
    rules = "".join(
        f"<li><b>{escape(impact)}:</b> "
        f"{escape(', '.join(rule['words'] + tuple(word for category in rule['categories'] for word in NEWS_CATEGORIES[category])))}"
        f"</li>" for impact, rule in NEWS_IMPACTS.items() if impact in IMPACT_CHECK_ORDER)
    return (
        f"<p>Impact, checked in this order on the headline, then on the feed text; the first whole word that matches "
        f"decides: {escape(' → '.join(IMPACT_CHECK_ORDER))}.</p><ul>{rules}</ul>"
        f"<p>No word matched: a headline naming one satellite in the registry (NVS-03, QZS-7) is "
        f"{escape(IMPACT_OF_AN_ID)}; anything else is background. Word rules only, no model; an item appears under "
        "every constellation its headline names.</p>"
        f"<p>One story: reports with the same impact whose headlines name the same mission or satellite (NVS-03, "
        f"GSLV-F18), or share at least {STORY_SHARED_WORDS} uncommon words making up {STORY_SHARE:.0%} of the shorter "
        f"headline, each within {STORY_DAYS} days of another in it. Rebuilt on every visit.</p>"
        "<p>Grade standing: confirmed, in the team's source table; provisional, proposed and waiting for the team's "
        "review; not graded, no grade recorded and no checked claim yet.</p>"
        f"{grade_legend_html()}"
    )


def ledger_html(rows):
    """State news agencies: stories quoting each, and the share of those a confirmed A or B source reported too."""
    tip = (f"A story quotes an agency when a report in it comes from the agency's site, as a feed pointed to it, or names "
           f"it. Confirmed: a report in the same story from a source confirmed at grade {' or '.join(CORROBORATING_GRADES)} "
           f"that quotes no state agency, published at or after the first report quoting it, within {CORROBORATION_DAYS} days. Only reports already in "
           "the news file count; the agencies' sites are never opened.")
    cells = ['<span class="h">Agency</span><span class="h n">Stories</span>',
             f'<span class="h">{tooltip.tip_html("Confirmed by an A or B source", escape(tip), key="ledger")}</span>']
    for row in rows:
        told, held = row["stories"], row["confirmed"]
        share = held / told if told else 0
        cells.append(f'<span>{escape(row["agency"])}<small>{escape(row["country"])}</small></span>'
                     f'<b class="n num{"" if told else " zero"}">{told}</b>')
        cells.append(f'<span class="share" role="img" aria-label="{held} of {told} confirmed"><span class="bar">'
                     f'<i style="width:{100 * share:.0f}%"></i></span>'
                     f'<span class="num{"" if told else " quiet"}">{f"{held} of {told}" if told else "not quoted"}</span></span>')
    return f'<div class="news-ledger">{"".join(cells)}</div>'


def screen_reader_heading(label):
    """A filter's name for screen readers: Streamlit hides the pills' own label from them (aria-hidden)."""
    st.html(f'<span class="news-sr" role="heading" aria-level="3">{escape(label)}</span>')


def seen_note(seen_at):
    """Help words for the new-only toggle."""
    if seen_at is None:
        return ("No visit is stored yet, so 'new' means fetched in the last 24 hours and published then, "
                f"allowing {NEWS_NEW_GRACE_HOURS} hours for slow feeds.")
    return (f"New means fetched after your last visit on {_time_words(seen_at, timezone.utc)} and published then, "
            f"allowing {NEWS_NEW_GRACE_HOURS} hours for slow feeds.")


def as_of_line(generated_at, now, zone=timezone.utc):
    """A notice when news is late, else a quiet as-of line."""
    generated = _time(generated_at)
    if generated is None:
        return surfaces.notice(f"The news file (latest_news.json) gives no collection time. We collect news every {NEWS_CYCLE_HOURS} hours.", "warn")
    if now - generated > timedelta(hours=NEWS_LATE_HOURS):
        return surfaces.notice(f"News was last seen {_time_words(generated, timezone.utc)}. We collect news every "
                               f"{NEWS_CYCLE_HOURS} hours.", "warn")
    return f'<p class="news-asof">News as of {escape(_time_words(generated, zone))}</p>'
