"""The Library's shelves: the newest stories, a card for each dataset only this project makes (how to get it, use it
and cite it), the others' data we use and where to go for it, and the people already doing this work. What is on
each shelf is in ui/shelf_settings.py. Every builder returns an HTML string; only the file bytes are not markup.
"""
import csv
import io
import json
import re
from datetime import date
from html import escape
from pathlib import Path

import streamlit as st

from evidence import jobs
from evidence.console_settings import JOBS, WORKFLOWS_DIR
from ui import icons, marks, surfaces
from ui.shelf_settings import FITTED, JOB_NAMES, ORBIT_GAP, OUR_CREDIT, OUR_LICENCE, OURS, SHELVES

ROOT = Path(__file__).resolve().parent.parent
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

CSS = """<style>
/* the shelves at a glance: one raised tile per shelf, a button that opens the shelf and goes to it */
.st-key-shop_map { display: grid !important; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin: 4px 0 18px; }
.st-key-shop_map button { width: 100%; min-height: 112px; flex-direction: column; gap: 6px; padding: 14px 12px;
  border-radius: var(--r); box-shadow: var(--raised); }
.st-key-shop_map button::before { content: ""; width: 26px; height: 26px; background: var(--accent);
  -webkit-mask: var(--tile-ic) center / contain no-repeat; mask: var(--tile-ic) center / contain no-repeat; }
.st-key-shop_map button p { margin: 0; text-align: center; line-height: 1.3; }
.st-key-shop_map button strong { display: block; font-size: var(--fs-num); font-weight: var(--fw-num); line-height: 1.1; }
.st-key-tile_stories { --tile-ic: var(--ic-broadcast); } .st-key-tile_satellites { --tile-ic: var(--ic-rocket); }
.st-key-tile_datasets { --tile-ic: var(--ic-database); } .st-key-tile_cite { --tile-ic: var(--ic-quote); }
[class*="st-key-rv_library_"] { scroll-margin-top: 96px; }
/* a picture: an icon resting on a pressed plinth */
.plinth { display: grid; place-items: center; width: 56px; height: 56px; flex: 0 0 56px; border-radius: 50%; background: var(--well);
  box-shadow: var(--pressed); color: var(--accent); }
.plinth .ic { width: 26px; height: 26px; }
.shelf-sign { display: flex; align-items: center; gap: 14px; margin: 26px 0 10px; }
.shelf-sign h2 { margin: 0; padding: 0; }
/* the objects on a shelf: cards in a grid that wraps to one column on a phone */
.st-key-shelf_ours, .st-key-shelf_stories, .shelf-grid {
  display: grid !important; grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr)); gap: 16px; }
[class*="st-key-item_"], .shelf-grid > .obj { background: var(--platform); border: 1px solid var(--edge); border-radius: var(--r);
  box-shadow: var(--raised); padding: 16px 18px; gap: 10px; min-width: 0; height: 100%; }
/* the download sits at the foot of its card, so a row of cards lines up */
[class*="st-key-item_"] > [data-testid="stElementContainer"]:has([data-testid="stDownloadButton"]) { margin-top: auto; }
.obj { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px 14px; align-items: start; align-content: start; }
.obj .lbl { min-width: 0; }
.obj .lbl b { display: block; font-size: var(--fs-side); line-height: 1.25; }
.obj .lbl p { margin: 4px 0 0; font-size: var(--fs-body); }
.obj .facts { grid-column: 1 / -1; display: grid; gap: 4px; font-size: var(--fs-small); color: var(--fc-small); }
.obj .facts span { display: grid; grid-template-columns: 70px minmax(0, 1fr); gap: 8px; align-items: baseline; }
.obj .facts i { font-style: normal; color: var(--muted); }
.obj .facts code { font-size: var(--fs-small); overflow-wrap: anywhere; white-space: normal; }
.obj a { color: var(--accent); overflow-wrap: anywhere; }
/* how to use a dataset: closed until asked for */
.obj details { grid-column: 1 / -1; min-width: 0; overflow-wrap: anywhere; border-radius: 12px; background: var(--well); box-shadow: var(--pressed); }
.obj summary { cursor: pointer; min-height: 44px; display: flex; align-items: center; padding: 0 12px; font-weight: 600; }
.obj details > div { padding: 0 12px 12px; font-size: var(--fs-small); display: grid; gap: 6px; }
.obj details dl { margin: 0; display: grid; gap: 4px; } .obj details dt { font-family: var(--font-numbers, monospace); color: var(--accent); }
.obj details dd { margin: 0 0 4px; }
.obj details p { margin: 0; }
.story-obj .lbl b { font-size: var(--fs-body); }
.story-about { display: flex; flex-wrap: wrap; gap: 2px 12px; }
.people h4 { margin: 14px 0 6px; }
.people ul { margin: 0; padding-left: 18px; display: grid; gap: 6px; }
[class*="st-key-item_"] [data-testid="stDownloadButton"] button,
[class*="st-key-shelfbody_"] [data-testid="stPageLink-NavLink"] { min-height: 44px; }
/* a shelf drawn inside a section (ui/reveal.py hides only an HTML body or a frame): padded like one, and gone while
   the section is closed */
[class*="st-key-shelfbody_"] { padding: 0 20px 16px; }
[class*="st-key-shelfbody_"] [data-testid="stPageLink-NavLink"] { width: auto; max-width: 100%; }
[class*="st-key-shelfbody_"] [data-testid="stPageLink-NavLink"] p { white-space: normal; }
[class*="st-key-shelfbody_"] pre, [class*="st-key-shelfbody_"] pre code { white-space: pre-wrap; overflow-wrap: anywhere; }
[class*="st-key-rv_"]:not(:has([class*="st-key-rvx_"] input:checked)) [class*="st-key-shelfbody_"] { display: none; }
</style>"""


def _day_words(text):
    """'15 Nov 2026' from any text that starts with an ISO date; "" when it does not."""
    found = _DAY.match(text or "")
    if not found:
        return ""
    day = date.fromisoformat(found.group(0))
    return f"{day.day} {day:%b %Y}"


@st.cache_data(show_spinner=False)
def job_words(job):
    """'the Registry update job, Sundays 01:00 UTC' from the console's job list and the workflow's own schedule."""
    if job == "hand":
        return "kept by hand; each change is a reviewed pull request"
    workflow, group = job
    name = next((row[2] for row in JOBS if row[0] == workflow and row[1] == group), JOB_NAMES.get(workflow, workflow))
    try:
        crons = jobs.schedules((WORKFLOWS_DIR / workflow).read_text(encoding="utf-8")).get(group, [])
    except OSError:
        crons = []
    when = ", ".join(jobs.schedule_words(cron) for cron in crons)
    return f"the {name} job" + (f", {when} UTC" if when else "")


def published():
    """{name: (payload, problem)} for the project's files on the orbit-checks branch, and the news file, each read
    once an hour at most (the loaders cache them). A file that cannot be read has the problem in words."""
    from ui import data, news

    gap, fitted = data.orbit_gap(), data.fitted_orbits()
    return {ORBIT_GAP: (gap, "" if gap else "it cannot be read right now"),
            FITTED: (fitted, "" if fitted else "it cannot be read right now"),
            "news": news.load_news()}


@st.cache_data(show_spinner=False, ttl=3600)
def _repo_file(path):
    try:
        return (ROOT / path).read_bytes()
    except OSError:
        return None


def item_state(key, files):
    """(bytes or None, freshness words, problem) for one of OURS. files: published()."""
    item = OURS[key]
    kind, where = item["file"]
    if kind == "repo":
        content = _repo_file(where)
        problem = "" if content is not None else "it cannot be read right now"
    else:
        payload, problem = files[where]
        content = json.dumps(payload, indent=1).encode("utf-8") if payload else None
    day = ""
    if item["date"] and content is not None:
        how, name = item["date"]
        if how == "column":
            values = [row.get(name, "") for row in csv.DictReader(io.StringIO(content.decode("utf-8")))]
            day = _day_words(max((v for v in values if _DAY.match(v or "")), default=""))
            day = day and f"newest entry {day}"
        else:
            day = _day_words(str(files[where][0].get(name, "")))
            day = day and f"made {day}"
    return content, (day or "the file carries no date") + " · " + job_words(item["job"]), problem


def size_words(size):
    return f"{size / 1e6:.1f} MB" if size >= 1e6 else f"{max(1, round(size / 1e3))} kB"


def file_name(key):
    kind, where = OURS[key]["file"]
    return Path(where).name if kind == "repo" else {ORBIT_GAP: "orbit_gap.json", FITTED: "fitted_orbits.json"}[where]


def _link(address, words=""):
    return (f'<a href="{escape(address, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'{escape(words or address)}</a>')


def card_html(key, content, fresh, problem):
    """One dataset only this project makes: what it is, why it is ours, how fresh, size, its stable address, licence,
    and, opened on request, how to use it: each field, an example, what not to use it for, how to cite it."""
    item = OURS[key]
    state = surfaces.chip("cannot be read right now", "warn") + f" {escape(problem)}" if problem else escape(fresh)
    rows = [("Fresh", state), ("Size", escape(size_words(len(content))) if content is not None else "&ndash;"),
            ("Address", f"<code>{_link(item['address'])}</code>"),
            ("Licence", _link(OUR_LICENCE[1], OUR_LICENCE[0]))]
    facts = "".join(f"<span><i>{label}</i>{value}</span>" for label, value in rows)
    fields = "".join(f"<dt>{escape(name)}</dt><dd>{escape(meaning)}</dd>" for name, meaning in item["fields"])
    cite = f"OpenGNSS, {item['name']}, {OUR_CREDIT}, licensed CC BY 4.0, {item['address']}"
    use = (f'<details><summary>How to use it</summary><div><dl>{fields}</dl>'
           f'<p><b>Example</b> {escape(item["example"])}</p><p><b>Not for</b> {escape(item["not_for"])}</p>'
           f'<p><b>Cite</b> {escape(cite)}</p></div></details>')
    return (f'<div class="obj"><span class="plinth">{icons.mask(item["icon"])}</span>'
            f'<span class="lbl"><b>{escape(item["name"])}</b><p>{escape(item["what"])}</p>'
            f'<p class="small">{escape(item["why"])}</p></span><span class="facts">{facts}</span>{use}</div>')


def others_html(others):
    """The others' data we use: whose it is, what we use it for, how fresh our copy is, and a link to its owner."""
    cards = ""
    for name, icon, link, used_for, job in others:
        read = "a copy comes with the code" if job == "hand" else "read by " + job_words(job)
        go = _link(link, "Go to " + name) if link else "Read each on its publisher's site, linked from the News page."
        cards += (f'<div class="obj"><span class="plinth">{icons.mask(icon)}</span><span class="lbl"><b>{escape(name)}</b>'
                  f'<p>We use it for: {escape(used_for)}</p></span><span class="facts"><span><i>Fresh</i>kept by its '
                  f'owner · {escape(read)}</span><span><i>Get it</i>{go}</span></span></div>')
    return f'<div class="shelf-grid">{cards}</div>'


def colleagues_html(colleagues):
    """The people already doing this work, per constellation, each with a link."""
    groups = "".join(f'<h4>{marks.named(where)}</h4><ul>' + "".join(
        f'<li>{_link(link, who)}: {escape(what)}</li>' for who, what, link in people) + "</ul>"
        for where, people in colleagues)
    return f'<div class="people">{groups}</div>'


def shelf_sign(key):
    title, icon, _ = SHELVES[key]
    return f'<div class="shelf-sign"><span class="plinth">{icons.mask(icon)}</span><h2>{escape(title)}</h2></div>'


def story_html(story):
    """One story on the shelf: its headline, category, how many sources told it, when, and the newest link."""
    items = story["items"]
    newest = max((item.get("published_at") or item.get("fetched_at") or "" for item in items), default="")
    constellations = sorted({name for item in items for name in item.get("constellations", [])})
    link = next((item["address"] for item in items if item["address"].startswith(("http://", "https://"))), "")
    head = _link(link, story["headline"]) if link else escape(story["headline"])
    told = f'{len(items)} source{"" if len(items) == 1 else "s"}'
    return (f'<div class="obj story-obj"><span class="plinth">{icons.mask("broadcast")}</span>'
            f'<span class="lbl"><b>{head}</b><p class="small story-about">{"".join(marks.named(name) for name in constellations)}</p></span>'
            f'<span class="facts"><span><i>Kind</i>{escape(story["category"])}</span><span><i>Told by</i>{told}</span>'
            f'<span><i>Latest</i>{escape(_day_words(newest) or "date not given")}</span></span></div>')


def scroll_script(section, nonce):
    """A script for an empty component frame that brings a section into view in the page around it. Streamlit draws
    the page after the frame loads, so it looks again for a few seconds; nonce makes each jump a new frame."""
    target = json.dumps(f".st-key-rv_{section}")
    return (f"<script>/* {nonce} */ const doc = window.parent.document; let tries = 0;"
            f"(function go() {{ const el = doc.querySelector({target});"
            f" if (el) {{ el.scrollIntoView({{block: 'start'}}); if (tries++ < 3) setTimeout(go, 400); }}"
            f" else if (tries++ < 40) setTimeout(go, 150); }})();</script>")
