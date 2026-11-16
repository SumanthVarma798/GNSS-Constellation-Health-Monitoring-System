"""System design, for the administration console: one picture of the whole system, each part explained when clicked,
and one item followed from a source to the change a person approves.

The page is ui/components/system_design.html (plain JavaScript, no network); the words are here. They are a summary of
docs/system-design.md, the settings files and the workflows, as of 20 Oct 2026: a pull request that changes how the
system works changes this file too, as it changes that page. Text reaches the page as JSON escaped by embed() and is
put in with textContent, so it is never read as markup.
"""
from pathlib import Path
import re

from evidence import jobs, source_overview, sources
from evidence.console_settings import ARCHIVE_WORKFLOW, REGISTRY_UPDATE_WORKFLOW, WORKFLOWS_DIR
from evidence.settings import (BACKOFF_FIRST, BACKOFF_LONGEST, DOWNLOAD_TRIES, MAX_COPY_BYTES, MIN_GAP_BETWEEN_DOWNLOADS,
                               WAIT_BETWEEN_TRIES_SECONDS)
from ui.components.master_map import embed

PAGE_FILE = Path(__file__).with_name("system_design.html")


def _workflow_text(name):
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def _schedule_word(workflow_text, group):
    crons = jobs.schedules(workflow_text).get(group, [])
    return jobs.schedule_words(crons[0]) if crons else ""


def _daily_times(words):
    found = re.fullmatch(r"daily (.+)", words or "")
    return [part.strip() for part in found.group(1).split(",")] if found else []


def _daily_time(words):
    times = _daily_times(words)
    return times[0] if times else words


def _hourly_words(words):
    found = re.fullmatch(r"every (\d+) hours from (\d{2}:\d{2})", words or "")
    return f"every {found.group(1)} hours" if found else words


def _duration_words(delta):
    seconds = int(delta.total_seconds())
    if seconds % 86400 == 0:
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''}"
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"{seconds} second{'s' if seconds != 1 else ''}"


def _schedule_label(group):
    return {"orbital": "orbits", "x": "X"}.get(group, group)


_ARCHIVE_WORKFLOW_TEXT = _workflow_text(ARCHIVE_WORKFLOW)
_REGISTRY_WORKFLOW_TEXT = _workflow_text(REGISTRY_UPDATE_WORKFLOW)
_SCHEDULES = jobs.schedules(_ARCHIVE_WORKFLOW_TEXT)
_ARCHIVE_GROUPS = list(_SCHEDULES)
_CATALOGUES_SCHEDULE = _schedule_word(_ARCHIVE_WORKFLOW_TEXT, "catalogues")
_ORBITAL_SCHEDULE = _schedule_word(_ARCHIVE_WORKFLOW_TEXT, "orbital")
_NEWS_SCHEDULE = _schedule_word(_ARCHIVE_WORKFLOW_TEXT, "news")
_SOCIAL_SCHEDULE = _schedule_word(_ARCHIVE_WORKFLOW_TEXT, "social")
_X_SCHEDULE = _schedule_word(_ARCHIVE_WORKFLOW_TEXT, "x")
_REGISTRY_SCHEDULE = _schedule_word(_REGISTRY_WORKFLOW_TEXT, "")
_OVERVIEW = source_overview.overview()
_CANDIDATE_COUNT = _OVERVIEW["candidates"]
_PROPOSED_COUNT = sum(n for grade, n in _OVERVIEW["proposed"].items() if grade)
_NEWS_SOURCE_COUNT = len(sources.ARCHIVED_SOURCES["news"])
_X_ACCOUNT_COUNT = len(sources.ARCHIVED_SOURCES["x"])
_ORBITAL_TIMES = _daily_times(_ORBITAL_SCHEDULE)
_ORBITAL_FIRST_TIME = _ORBITAL_TIMES[0] if _ORBITAL_TIMES else _ORBITAL_SCHEDULE
_X_ACCOUNT_WORD = "account" if _X_ACCOUNT_COUNT == 1 else "accounts"
_CELESTRAK_GAP_WORDS = _duration_words(MIN_GAP_BETWEEN_DOWNLOADS["celestrak.org"])
_REGISTRY_WEEKDAY_EACH = _REGISTRY_SCHEDULE.split()[0].removesuffix("s")   # "Sundays 01:00" gives "Sunday"

# Each part: (name, built | planned | key (where a person decides), in simple terms, key technical details,
# limits and risks, where it lives). The keys are the boxes' ids in the page's picture.
PARTS = {
    "igs": ("IGS satellite file", "built",
            "The International GNSS Service's list of every navigation satellite: which spacecraft is which, its signal ID, its block.",
            ["Copied into the archive by the documents job",
             f"The registry is rebuilt from the archived copy each {_REGISTRY_WEEKDAY_EACH}",
             "Graded B: a scientific body"],
            ["One file with one maintainer (DLR, for IGS); if its layout changes, the rebuild stops and says so"],
            "evidence/igs_metadata.py · scripts/build_registry.py"),
    "gcat": ("GCAT catalogue", "built",
             "One expert's catalogue of every object launched, with owner, state and dates: a second opinion on each satellite, and the Library's counts.",
             [f"Archived daily at {_daily_time(_CATALOGUES_SCHEDULE)} UTC, after its own daily rebuild",
              "Graded C: widely cited, not an institution"],
             ["Its author updates some dates patchily, so its status is read as his latest word, not a live one"],
             "evidence/gcat.py · evidence/catalogue_check.py"),
    "cel": ("CelesTrak orbit records", "built",
            "Where every satellite is: published orbit records (two-line elements) for the GNSS group. The dashboard's orbit maths starts here.",
            [f"The dashboard asks at most once every {_CELESTRAK_GAP_WORDS}, CelesTrak's own limit",
             f"Archived {len(_ORBITAL_TIMES)} times a day from {_ORBITAL_FIRST_TIME} UTC, so every day's records are kept",
             "Graded B"],
            ["If CelesTrak fails, the dashboard keeps its last copy and says since when it has been failing"],
            "data/celestrak.py · evidence/settings.py"),
    "news": ("News and official feeds", "built",
             "Operator pages, advisories, specialist press and newsletters: what people say about the satellites.",
             [f"{_CANDIDATE_COUNT} candidate sources, {_PROPOSED_COUNT} with a proposed grade waiting for approval",
              f"{_NEWS_SOURCE_COUNT} read {_hourly_words(_NEWS_SCHEDULE)}; a copy is kept only when the page changed",
              f"{_X_ACCOUNT_COUNT} X {_X_ACCOUNT_WORD} are read through twitterapi.io {_hourly_words(_X_SCHEDULE)}",
              "Substack newsletters arrive by email and are read as feeds from feeds.opengnss.org (Substack refuses GitHub's servers)",
              "Read for evidence only: nothing they say changes anything yet"],
             ["Some fail in every run; the Jobs page shows which",
              "Two tracker sites are never fetched, by a rule in the settings"],
             "evidence/source_candidates.csv · evidence/news.py"),
    "social": ("Social feeds", "built",
               "Reddit groups about space agencies and navigation, kept for the links they carry, never as evidence on their own.",
               [f"Read once a day at {_daily_time(_SOCIAL_SCHEDULE)} UTC; Reddit refuses quick repeat requests",
                "Social posts never count as a second source"],
               ["Grade E at most"], "evidence/settings.py (SOCIAL_PLATFORM_HOSTS)"),
    "job": ("Archive job", "built",
            "The collector. On a timer it visits every source politely, keeps a copy of anything new, and writes one line per run saying how it went.",
            [f"GitHub Actions, {len(_ARCHIVE_GROUPS)} schedules: {', '.join(_schedule_label(group) for group in _ARCHIVE_GROUPS)}",
             f"Up to {DOWNLOAD_TRIES} tries per download, {WAIT_BETWEEN_TRIES_SECONDS} s apart; a site that refuses is left for {_duration_words(BACKOFF_FIRST)}, doubling up to {_duration_words(BACKOFF_LONGEST)}",
             f"Copies over {MAX_COPY_BYTES // (1024 * 1024)} MB are not kept"],
            ["GitHub starts scheduled runs late, sometimes by hours, and sometimes skips them"],
            ".github/workflows/archive.yml · evidence/archive.py"),
    "hc": ("Healthchecks.io", "built",
           "A watchdog outside GitHub: it emails when a scheduled run fails, or does not arrive at all.",
           ["Each run reports its result to Healthchecks.io at the end", "Nothing is sent until its key is set as a GitHub secret"],
           ["Only as good as its email being read; the account is personal for now"], ".github/workflows/*.yml"),
    "arc": ("Archive", "built",
            "The memory: every copy ever fetched, dated and never overwritten, so any claim can be traced back to exactly what a source said, and when.",
            ["A separate private repository", "Each copy is named by its fingerprint (a SHA-256 hash), so an unchanged page is never stored twice",
             "versions.csv lists every change; runs/ holds the run logs this console reads"],
            ["It grows for ever; moving it to object storage is parked (issue 45) until its size matters"],
            "the …-archive repository · evidence/archive.py"),
    "regjob": ("Registry job", "built",
               "Once a week it rebuilds the satellite tables from the archived IGS file and, if anything changed, proposes the change in plain words.",
               [f"{_REGISTRY_SCHEDULE} UTC, after that day's fetch",
                "Opens one pull request labelled 'decision: registry update' and starts the tests on it"],
               ["It never writes to the main copy itself"], ".github/workflows/registry-update.yml"),
    "store": ("Query store", "built",
              "A small database built from the archive, the registry and the source grades, so a question like 'what has been said about this satellite' is quick to answer.",
              ["SQLite, rebuilt from scratch on every run, never edited by hand",
               "Its tables follow the evidence model: source, document, claim, event, observation"],
              ["Disposable by design: losing it loses nothing"], "evidence/store.py · evidence/store_schema.sql"),
    "ext": ("Claim extraction", "planned",
            "Reading each new article and pulling out the statements it makes about a satellite, for example 'satellite X has been retired'.",
            ["Issue 15, about 20 hours (a guess)",
             "A language model will extract the statements; ordinary code, never the model, decides what happens next"],
            ["Waiting on a choice of model and a spending ceiling"], "issue 15"),
    "pr": ("Pull request", "key",
           "The one record of every change. A change is proposed, the tests run on it, a person approves it, and merging it is the moment it goes live.",
           ["GitHub pull requests in the private mirror", "The tests run on every pull request, on Python 3.11",
            "Approving in this console writes the decision on it, then merges it"],
           ["Nothing in the system changes reference data without one"], "GitHub · evidence/decisions.py"),
    "tab": ("Registry tables", "built",
            "The answer to 'which satellite is which': every identifier of a spacecraft tied to one master ID, and who held each signal ID when.",
            ["Plain-text tables: satellites, signal IDs, catalogue, the dashboard's tracked list", "Changed only through a pull request"],
            ["Which satellites are in service is still typed by hand, until operator status (issue 19) lands"],
            "registry/*.csv"),
    "bar": ("The bar and labels", "built",
            "How sure we are. Each item is labelled confirmed, probable or unconfirmed by written rules, not judgement.",
            ["A grade-A source clears the bar alone",
             "Grade B clears with a second independent source, or with our own orbit data agreeing", "Social posts never corroborate"],
            ["The rules are a starting proposal, to be confirmed with the team"], "evidence/confidence.py · evidence/settings.py"),
    "prop": ("Change proposals", "planned",
             "When a statement clears the bar and would change the registry (status, slot, signal ID or retirement), the system opens a pull request for a person.",
             ["Issue 16, about 12 hours", "One proposal per event; a second report of the same event joins it",
              "The rule is ordinary code with a test for each clause"],
             ["Specialist press and general news never trigger one on their own"], "issue 16"),
    "dash": ("Dashboard", "built",
             "The team's view of the satellites: where each one is, whether it is where it should be, and how good positioning is from any place.",
             ["Streamlit, with the orbit maths in SGP4 and Skyfield", "Reads its tracked satellites from the registry and its orbits from CelesTrak",
              "Public at dashboard.opengnss.org: Render's free plan, rebuilt from main on each commit (render.yaml)"],
             ["Sleeps after 15 minutes unvisited; the first visit after that takes about a minute",
              "The weekly job that refreshes its bundled orbit data is turned off on GitHub"], "dashboard.py · views/ · ui/"),
    "admin": ("Administration console", "key",
              "This console: what the system is doing, all in one place, and the place a person approves changes.",
              ["Google sign-in with an allow-list; one GitHub token, kept in the console's secrets",
               "Reads GitHub's record of jobs, issues and pull requests, and the archive's run logs",
               "Every change it makes goes out as a pull request"],
              ["Shared copy at console.opengnss.org on Render's free plan; it sleeps after 15 minutes unvisited and takes about a minute to wake",
               "The assistant answers only where Ollama runs, so not on the shared copy"],
              "admin.py · console/ · evidence/decisions.py"),
    "host": ("Hosting and the domain", "built",
             "Where each part runs, and the project's own name on the internet, opengnss.org, so addresses outlive any one person's account.",
             ["opengnss.org is held in the project's own Cloudflare account, which answers for every name under it",
              "dashboard.opengnss.org and console.opengnss.org: both apps on Render's free plan, rebuilt from main (render.yaml)",
              "feeds.opengnss.org: a Cloudflare Worker keeps only mail Substack signed and turns it into feeds",
              "Scheduled jobs run on GitHub Actions; code, tables and approvals live on GitHub"],
             ["Free plans sleep: the dashboard and the console each take about a minute to wake",
              "The domain does not renew by itself: renew it before 27 Oct 2027",
              "One Cloudflare admin so far; a second is still to be invited"],
             "render.yaml · cloudflare/newsletters/ · docs/infrastructure.md"),
}

# Following one item: (what happens, the parts it lights, the arrows it lights).
STEPS = [
    ("A source publishes or changes something", ["news"], []),
    ("The archive job fetches it on its schedule, within the source's limits", ["job"], ["src-job"]),
    ("A copy is kept, named by its fingerprint, only if it changed", ["arc"], ["job-arc"]),
    ("Planned: statements about satellites are pulled out of it", ["ext"], ["arc-ext"]),
    ("Each statement is judged against the bar: confirmed, probable or unconfirmed", ["bar"], ["ext-bar", "store-bar"]),
    ("Planned: if it clears the bar and changes the registry, a pull request is opened", ["prop", "pr"], ["bar-prop", "prop-pr"]),
    ("A person approves it here; merging updates the registry, and the dashboard follows", ["admin", "pr", "tab", "dash"],
     ["admin-pr", "pr-tab", "tab-dash"]),
]


def payload():
    """What the picture shows: the parts and the follow-one-item steps (no live figures; those sit outside the iframe)."""
    return {"parts": {key: {"name": p[0], "kind": p[1], "simple": p[2], "tech": p[3], "limits": p[4], "where": p[5]}
                      for key, p in PARTS.items()},
            "steps": [{"words": words, "nodes": nodes, "edges": edges} for words, nodes, edges in STEPS]}


def system_design_html(tokens_css, font):
    """The finished page: the console's colours first, the data last so it is never searched for placeholders."""
    page = PAGE_FILE.read_text(encoding="utf-8").replace("__TOKENS__", tokens_css).replace("__FONT__", font)
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(payload())};", 1)


def facts_strip_html(tokens_css, font, facts):
    """Live figures read from GitHub, shown under the picture so the diagram never waits on the network."""
    facts_json = embed([{"figure": figure, "words": words} for figure, words in facts])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
__TOKENS__
*, *::before, *::after {{ box-sizing: border-box; }}
html, body {{ margin: 0; background: var(--pane); color: var(--ink); font: 13px/1.45 __FONT__; }}
.facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); border: 2px solid var(--outline); box-shadow: var(--hard); }}
.facts div {{ padding: 8px 12px; border-right: 1px solid var(--edge); border-top: 4px solid var(--c-info); min-width: 0; }}
.facts b {{ display: block; font-size: 22px; font-weight: 800; line-height: 1.2; }}
.facts span {{ color: var(--muted); }}
</style></head><body><div class="facts" id="facts"></div><script>
const FACTS = {facts_json};
function el(tag, text) {{ const e = document.createElement(tag); if (text !== undefined) e.textContent = text; return e; }}
for (const f of FACTS) {{ const d = el("div"); d.append(el("b", f.figure), el("span", f.words)); document.getElementById("facts").append(d); }}
// The frame takes the page's own height, so the console scrolls as one page and nothing scrolls inside the frame.
// Streamlit 1.45 ignores "streamlit:setFrameHeight" from these frames, but they share the page's origin (as live_pipeline).
function fitFrame() {{
  if (!window.frameElement) return;
  const parts = [...document.body.children].filter((e) => e.tagName !== "SCRIPT");
  const bottom = Math.max(0, ...parts.map((e) => e.getBoundingClientRect().bottom + window.scrollY));
  window.frameElement.style.height = Math.ceil(bottom) + 12 + "px";   // room for the hard shadow
}}
if ("ResizeObserver" in window) {{ const fitter = new ResizeObserver(fitFrame); [document.body, ...document.body.children].forEach((e) => fitter.observe(e)); }}
fitFrame();
</script></body></html>""".replace("__TOKENS__", tokens_css, 1).replace("__FONT__", font, 1)
