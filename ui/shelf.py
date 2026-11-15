"""The Library's shelves: a card per dataset (a picture, a label, how fresh, whose, and a download where allowed), the
newest stories, and the take-home bundle. What is on each shelf, and every licence and citation, is in
ui/shelf_settings.py. Every builder returns an HTML string; only the file bytes are not markup.
"""
import csv
import io
import json
import re
import zipfile
from datetime import date
from html import escape
from pathlib import Path

import streamlit as st

from evidence import jobs
from evidence.console_settings import JOBS, WORKFLOWS_DIR
from ui import icons, surfaces, tooltip
from ui.shelf_settings import DATASETS, FITTED, JOB_NAMES, LATEST_GNSS, LICENCES, NEWS, ORBIT_GAP, SHELVES

ROOT = Path(__file__).resolve().parent.parent
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

CSS = """<style>
/* the shop's map: one raised tile per shelf, a picture and a count */
.shop-map { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin: 8px 0 22px; }
.shop-tile { display: grid; justify-items: center; gap: 6px; text-align: center; padding: 16px 12px; border-radius: var(--r);
  background: var(--platform); border: 1px solid var(--edge); box-shadow: var(--raised); }
.shop-tile b { font-size: var(--fs-num); font-weight: var(--fw-num); line-height: 1; }
.shop-tile span.small { color: var(--fc-small); }
/* a picture: an icon resting on a pressed plinth */
.plinth { display: grid; place-items: center; width: 56px; height: 56px; flex: 0 0 56px; border-radius: 50%; background: var(--well);
  box-shadow: var(--pressed); color: var(--accent); }
.plinth .ic { width: 26px; height: 26px; }
.shelf-sign { display: flex; align-items: center; gap: 14px; margin: 30px 0 10px; }
.shelf-sign h2 { margin: 0; padding: 0; }
.shelf-sign p { margin: 2px 0 0; color: var(--fc-small); font-size: var(--fs-small); }
/* the objects on a shelf: cards in a grid that wraps to one column on a phone */
.st-key-shelf_tables, .st-key-shelf_published, .st-key-shelf_others, .st-key-shelf_stories {
  display: grid !important; grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr)); gap: 16px; }
[class*="st-key-item_"] { background: var(--platform); border: 1px solid var(--edge); border-radius: var(--r);
  box-shadow: var(--raised); padding: 16px 18px; gap: 10px; min-width: 0; height: 100%; }
/* the download sits at the foot of its card, so a row of cards lines up */
[class*="st-key-item_"] > [data-testid="stElementContainer"]:has([data-testid="stDownloadButton"]) { margin-top: auto; }
.obj { display: grid; grid-template-columns: auto 1fr; gap: 6px 14px; align-items: start; }
.obj .lbl { min-width: 0; }
.obj .lbl b { display: block; font-size: var(--fs-side); line-height: 1.25; }
.obj .lbl p { margin: 4px 0 0; font-size: var(--fs-body); }
.obj .facts { grid-column: 1 / -1; display: grid; gap: 4px; font-size: var(--fs-small); color: var(--fc-small); }
.obj .facts span { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 8px; align-items: baseline; }
.obj .facts i { font-style: normal; color: var(--muted); }
.obj .why { grid-column: 1 / -1; margin: 2px 0 0; padding: 8px 10px; border-radius: 12px; background: var(--well);
  box-shadow: var(--pressed); font-size: var(--fs-small); }
.obj a { color: var(--accent); overflow-wrap: anywhere; }
.story-obj .lbl b { font-size: var(--fs-body); }
/* a finger-sized target for each card's tooltip and download, without moving the words */
.obj .lbl .tt-trigger { display: inline; padding: 10px 0; margin: -10px 0; }
[class*="st-key-item_"] [data-testid="stDownloadButton"] button,
[class*="st-key-shelfbody_"] [data-testid="stPageLink-NavLink"] { min-height: 44px; }
/* a shelf drawn inside a section (ui/reveal.py hides only an HTML body or a frame): padded like one, and gone while
   the section is closed */
[class*="st-key-shelfbody_"] { padding: 0 20px 16px; }
[class*="st-key-shelfbody_"] [data-testid="stPageLink-NavLink"] { width: auto; max-width: 100%; }
[class*="st-key-shelfbody_"] [data-testid="stPageLink-NavLink"] p { white-space: normal; }
.st-key-shelfbody_cite pre, .st-key-shelfbody_cite code { white-space: pre-wrap; overflow-wrap: anywhere; }
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
    """'Registry update, Sundays 01:00 UTC' from the console's job list and the workflow's own schedule."""
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
    """{name: (payload, problem)} for the files the dashboard reads from the repository's branches, each read once an
    hour at most (the loaders cache them). A file that cannot be read has the problem in words."""
    from data import celestrak
    from ui import data, news

    gap, fitted = data.orbit_gap(), data.fitted_orbits()
    story_file, story_problem = news.load_news()
    copy_at = celestrak.state.get("copy_at")
    return {ORBIT_GAP: (gap, "" if gap else "it cannot be read right now"),
            FITTED: (fitted, "" if fitted else "it cannot be read right now"),
            NEWS: (story_file, story_problem),
            LATEST_GNSS: ({"copy_at": copy_at.isoformat()} if copy_at else {}, "")}


@st.cache_data(show_spinner=False, ttl=3600)
def _repo_file(path):
    try:
        return (ROOT / path).read_bytes()
    except OSError:
        return None


def _head(path, key):
    """A key's value near the top of a large JSON file, without loading the file."""
    try:
        with open(ROOT / path, encoding="utf-8") as handle:
            found = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]+)"', handle.read(600))
    except OSError:
        return ""
    return found.group(1) if found else ""


def item_state(key, files):
    """(bytes or None, size in bytes or None, freshness words, problem) for one dataset. files: published()."""
    item = DATASETS[key]
    kind, where = item["file"] or (None, None)
    content, size, problem = None, None, ""
    if kind == "repo" and item["offer"]:
        content = _repo_file(where)
    elif kind == "repo":   # a large file not offered here: its size only, never loaded
        size = (ROOT / where).stat().st_size if (ROOT / where).is_file() else None
        problem = "" if size is not None else "the file cannot be read right now"
    elif kind == "published":
        payload, problem = files[where]
        content = json.dumps(payload, indent=1).encode("utf-8") if payload and where != LATEST_GNSS else None
    if kind == "repo" and item["offer"] and content is None:
        problem = "the file cannot be read right now"
    if content is not None:
        size = len(content)
    day = ""
    if item["date"] and not problem:
        how, name = item["date"]
        if how == "column" and content is not None:
            values = [row.get(name, "") for row in csv.DictReader(io.StringIO(content.decode("utf-8")))]
            day = _day_words(max((v for v in values if _DAY.match(v or "")), default=""))
            day = day and f"newest entry {day}"
        elif how == "json":
            day = _day_words(str(files[where][0].get(name, "")))
            day = day and f"made {day}"
        elif how == "head":
            day = _day_words(_head(where, name))
            day = day and f"made {day}"
    if where == LATEST_GNSS:
        copy_at = files[LATEST_GNSS][0].get("copy_at", "")
        day = f"copy in use taken {_day_words(copy_at)}" if copy_at else "not in use here just now"
    if kind is None:   # an outside source: its owner keeps it; one of our jobs reads it, or a copy comes with the code
        fresh = "kept by its owner · " + ("a copy comes with the code" if item["job"] == "hand" else "read by " + job_words(item["job"]))
    else:
        fresh = (day or "the file carries no date") + " · " + job_words(item["job"])
    return content, size, fresh, problem


def size_words(size):
    if size is None:
        return "size not known"
    return f"{size / 1e6:.1f} MB" if size >= 1e6 else f"{max(1, round(size / 1e3))} kB"


def licence_html(key):
    name, link, _ = LICENCES[key]
    return (f'<a href="{escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(name)}</a>'
            if link else escape(name))


def _more(item):
    """The card's tooltip: what it means, what is measured and how, what is left out (the page's story order)."""
    return tooltip.glance(item["what"], [("calculator", "How", item["how"]), ("alert-triangle", "Left out", item["left_out"])])


def card_html(key, size, fresh, problem):
    """One dataset on its shelf: a picture, its label, how fresh, size, licence, how to credit it, and for one not
    offered here, why and where to get it. The state is said in words; colour only backs it up."""
    item = DATASETS[key]
    state = (surfaces.chip("cannot be read right now", "warn") + f" {escape(problem)}" if problem
             else escape(fresh))
    rows = [("Fresh", state), ("Size", escape(size_words(size)) if item["file"] else "&ndash;"),
            ("Licence", licence_html(item["licence"])), ("Credit", escape(LICENCES[item["licence"]][2]))]
    facts = "".join(f"<span><i>{label}</i>{value}</span>" for label, value in rows)
    why = ""
    if not item["offer"]:
        link = (f' <a href="{escape(item["link"], quote=True)}" target="_blank" rel="noopener noreferrer">Go to the source</a>'
                if item["link"] else "")
        why = f'<p class="why">{icons.mask("info-circle")} Not offered here. {escape(item["why_not"])}{link}</p>'
    return (f'<div class="obj"><span class="plinth">{icons.mask(item["icon"])}</span>'
            f'<span class="lbl"><b>{tooltip.tip_html(escape(item["name"]), _more(item), key=key)}</b>'
            f'<p>{escape(item["what"])}</p></span><span class="facts">{facts}</span>{why}</div>')


def shelf_sign(key, count_html=""):
    title, icon, line = SHELVES[key]
    return (f'<div class="shelf-sign"><span class="plinth">{icons.mask(icon)}</span>'
            f'<div><h2>{escape(title)} {count_html}</h2><p>{escape(line)}</p></div></div>')


def shop_map(counts):
    """The shelves at a glance, a tile each. counts: {shelf key: (number, words)}."""
    tiles = "".join(f'<div class="shop-tile"><span class="plinth">{icons.mask(SHELVES[key][1])}</span>'
                    f'<b class="num">{number}</b><span>{escape(SHELVES[key][0])}</span>'
                    f'<span class="small">{escape(words)}</span></div>' for key, (number, words) in counts.items())
    return f'<div class="shop-map">{tiles}</div>'


def story_html(story):
    """One story on the shelf: its headline, category, how many sources told it, when, and the newest link."""
    items = story["items"]
    newest = max((item.get("published_at") or item.get("fetched_at") or "" for item in items), default="")
    systems = sorted({name for item in items for name in item.get("constellations", [])})
    link = next((item["address"] for item in items if item["address"].startswith(("http://", "https://"))), "")
    head = (f'<a href="{escape(link, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(story["headline"])}</a>'
            if link else escape(story["headline"]))
    told = f'{len(items)} source{"" if len(items) == 1 else "s"}'
    return (f'<div class="obj story-obj"><span class="plinth">{icons.mask("broadcast")}</span>'
            f'<span class="lbl"><b>{head}</b><p class="small">{escape(" · ".join(systems))}</p></span>'
            f'<span class="facts"><span><i>Kind</i>{escape(story["category"])}</span><span><i>Told by</i>{told}</span>'
            f'<span><i>Latest</i>{escape(_day_words(newest) or "date not given")}</span></span></div>')


@st.cache_data(show_spinner=False, ttl=3600)
def bundle(files):
    """Every file offered here, in one zip with a README saying each one's licence, credit and freshness, and the
    project's NOTICE and LICENSE-DATA. files: {key: (bytes, fresh)} for the datasets that could be read."""
    buffer = io.BytesIO()
    lines = ["OpenGNSS Library: files to take home", "",
             "Each file keeps the licence named below. Credit it with the words given.", ""]
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for key, (content, fresh) in files.items():
            item = DATASETS[key]
            name = file_name(key)
            archive.writestr(name, content)
            licence, link, credit = LICENCES[item["licence"]]
            lines += [f"{name}: {item['name']}", f"  {item['what']}", f"  Fresh: {fresh}",
                      f"  Licence: {licence} {link}".rstrip(), f"  Credit: {credit}", ""]
        for extra in ("NOTICE", "LICENSE-DATA"):
            if (content := _repo_file(extra)) is not None:
                archive.writestr(extra + ".txt", content)
        archive.writestr("README.txt", "\n".join(lines))
    return buffer.getvalue()


def file_name(key):
    kind, where = DATASETS[key]["file"]
    return Path(where).name if kind == "repo" else {ORBIT_GAP: "orbit_gap.json", FITTED: "fitted_orbits.json"}[where]
