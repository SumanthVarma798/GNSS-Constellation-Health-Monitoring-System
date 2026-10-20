"""System design, for the administration console: one picture of the whole system, each part explained when clicked,
and one item followed from a source to the change a person approves.

The page is ui/components/system_design.html (plain JavaScript, no network); the words are here. They are a summary of
docs/system-design.md, the settings files and the workflows, as of 20 Oct 2026: a pull request that changes how the
system works changes this file too, as it changes that page. Text reaches the page as JSON escaped by embed() and is
put in with textContent, so it is never read as markup.
"""
from pathlib import Path

from ui.components.master_map import embed

PAGE_FILE = Path(__file__).with_name("system_design.html")

# Each part: (name, built | planned | key (where a person decides), in simple terms, key technical details,
# limits and risks, where it lives). The keys are the boxes' ids in the page's picture.
PARTS = {
    "igs": ("IGS satellite file", "built",
            "The International GNSS Service's list of every navigation satellite: which spacecraft is which, its signal ID, its block.",
            ["Copied into the archive by the documents job", "The registry is rebuilt from the archived copy each Sunday",
             "Graded B: a scientific body"],
            ["One file with one maintainer (DLR, for IGS); if its layout changes, the rebuild stops and says so"],
            "evidence/igs_metadata.py · scripts/build_registry.py"),
    "gcat": ("GCAT catalogue", "built",
             "One expert's catalogue of every object launched, with owner, state and dates: a second opinion on each satellite, and the Library's counts.",
             ["Archived daily at 00:45 UTC, after its own daily rebuild", "Graded C: widely cited, not an institution"],
             ["Its author updates some dates patchily, so its status is read as his latest word, not a live one"],
             "evidence/gcat.py · evidence/catalogue_check.py"),
    "cel": ("CelesTrak orbit records", "built",
            "Where every satellite is: published orbit records (two-line elements) for the GNSS group. The dashboard's orbit maths starts here.",
            ["The dashboard asks at most once every 2 hours, CelesTrak's own limit",
             "Archived once a day at 01:15 UTC, so every day's records are kept", "Graded B"],
            ["If CelesTrak fails, the dashboard keeps its last copy and says since when it has been failing"],
            "data/celestrak.py · evidence/settings.py"),
    "news": ("News and official feeds", "built",
             "Operator pages, advisories, specialist press and newsletters: what people say about the satellites.",
             ["57 candidate sources, each with a proposed grade waiting for approval",
              "44 read every 3 hours; a copy is kept only when the page changed",
              "Read for evidence only: nothing they say changes anything yet"],
             ["Some fail in every run (6 of 44 on 20 Oct); the Jobs page shows which",
              "Two tracker sites are never fetched, by a rule in the settings"],
             "evidence/source_candidates.csv · evidence/news.py"),
    "social": ("Social feeds", "built",
               "Reddit groups about space agencies and navigation, kept for the links they carry, never as evidence on their own.",
               ["Read once a day at 01:40 UTC; Reddit refuses quick repeat requests", "Social posts never count as a second source"],
               ["Grade E at most"], "evidence/settings.py (SOCIAL_PLATFORM_HOSTS)"),
    "job": ("Archive job", "built",
            "The collector. On a timer it visits every source politely, keeps a copy of anything new, and writes one line per run saying how it went.",
            ["GitHub Actions, five schedules: documents, catalogues, orbits, news, social",
             "Up to 3 tries per download, 60 s apart; a site that refuses is left for 1 hour, doubling up to 7 days",
             "Copies over 50 MB are not kept"],
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
               ["Sundays 01:00 UTC, after that day's fetch",
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
              "Runs on this computer (localhost:48974); the team's hosted copy is separate"],
             ["The weekly job that refreshes its bundled orbit data is turned off on GitHub"], "dashboard.py · views/ · ui/"),
    "admin": ("Administration console", "key",
              "This console: what the system is doing, all in one place, and the place a person approves changes.",
              ["Google sign-in with an allow-list; one GitHub token kept on this computer",
               "Reads GitHub's record of jobs, issues and pull requests, and the archive's run logs",
               "Every change it makes goes out as a pull request"],
              ["Runs on one computer for now (localhost:48973); hosting is undecided"],
              "admin.py · console/ · evidence/decisions.py"),
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


def payload(facts):
    """What the page shows: the parts, the steps, and a few live figures as (figure, words) pairs."""
    return {"parts": {key: {"name": p[0], "kind": p[1], "simple": p[2], "tech": p[3], "limits": p[4], "where": p[5]}
                      for key, p in PARTS.items()},
            "steps": [{"words": words, "nodes": nodes, "edges": edges} for words, nodes, edges in STEPS],
            "facts": [{"figure": figure, "words": words} for figure, words in facts]}


def system_design_html(tokens_css, font, facts):
    """The finished page: the console's colours first, the data last so it is never searched for placeholders."""
    page = PAGE_FILE.read_text(encoding="utf-8").replace("__TOKENS__", tokens_css).replace("__FONT__", font)
    return page.replace("const DATA = __DATA__;", f"const DATA = {embed(payload(facts))};", 1)
