"""Library: the shop at the end of the museum. Shelves to browse, in this order: the newest stories, the satellites and
their lives (counts per constellation, lifecycles, generations, money), every dataset the dashboard uses or scans, the files
a visitor may take home, and how to cite them.

What each shelf holds, and every licence and citation, is in ui/shelf_settings.py; the cards are built in ui/shelf.py.
Details sit in sections (ui/reveal.py); the shelf signs and the shop's map are always in view.
"""
from datetime import datetime, timezone
from html import escape

import streamlit as st

from evidence import news_stories
from evidence.library_settings import (LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE,
                                       LIFECYCLE_EVENTS_FILE)
from evidence.settings import (REGISTRY_CATALOGUE_FILE, REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_SATELLITES_FILE,
                               REGISTRY_SIGNAL_IDS_FILE)
from evidence.registry_tables import read_table
from ui import icons, library, reveal, shelf, surfaces
from ui.components.lifecycle import lifecycle_frame
from ui.shelf_settings import BUNDLE_NAME, CITATIONS, CODE_LINK, DATASET_GROUPS, DATASETS, NEWS, STORIES_SHOWN


@st.cache_data(show_spinner=False)
def load():
    return [read_table(name) for name in (LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE, LIFECYCLE_EVENTS_FILE,
                                          REGISTRY_SATELLITES_FILE, REGISTRY_SIGNAL_IDS_FILE, REGISTRY_CATALOGUE_FILE,
                                          REGISTRY_DASHBOARD_SATELLITES_FILE)]


counts, figures, matched, lifecycle_rows, satellites, signal_ids, catalogue, tracked = load()
registry = {"satellites": satellites, "signal_ids": signal_ids, "catalogue": catalogue, "tracked": tracked}
systems = library.system_rows(counts)
stated = sum(figure["value"] != library.NOT_KNOWN for figure in figures)

files = shelf.published()
states = {key: shelf.item_state(key, files) for key in DATASETS}   # (bytes, size, freshness, problem)
offered = {key: (state[0], state[2]) for key, state in states.items() if DATASETS[key]["offer"] and state[0] is not None}
news_file, news_problem = files[NEWS]
told = sorted(news_stories.stories(news_file.get("items", [])) if not news_problem else [],
              key=lambda story: max(item.get("published_at") or item.get("fetched_at") or "" for item in story["items"]),
              reverse=True)

surfaces.show(library.CSS)
surfaces.show(shelf.CSS)
surfaces.show('<p class="small">Everything the dashboard knows, laid out to browse and take home: the stories, the '
              'satellites and their lives, every dataset it reads, and the files you may keep, each with its licence '
              'and how to credit it.</p>')
surfaces.show(shelf.shop_map({
    "stories": (len(told), "from the news"), "satellites": (sum(r["launched"] for r in systems), "launched"),
    "datasets": (len(DATASETS), "used or scanned"), "takeaways": (len(offered), "files to take home"),
    "cite": (len(CITATIONS), "ways to credit")}))

# ---- Stories ----
surfaces.show(shelf.shelf_sign("stories"))
if news_problem:
    surfaces.show(surfaces.notice(f"The stories cannot be read right now: {news_problem}. The other shelves are all here.",
                                  "warn", inline=True))
else:
    def draw_stories():
        with st.container(key="shelfbody_stories"), st.container(key="shelf_stories"):
            for n, story in enumerate(told[:STORIES_SHOWN]):
                with st.container(key=f"item_story_{n}"):
                    st.html(shelf.story_html(story))
        with st.container(key="shelfbody_stories_link"):
            st.page_link("views/news.py", label="Every story, and who told it, on the News page",
                         icon=":material/arrow_forward:")

    reveal.section("library_stories", "Newest stories",
                   f"newest {min(len(told), STORIES_SHOWN)} of {len(told)} stories · {states[NEWS][2]}",
                   draw_stories, open=True)

# ---- Satellites and their lives ----
surfaces.show(shelf.shelf_sign("satellites"))
reveal.section("library_systems", "Count per constellation",
               f"{reveal.count(len(systems), 'constellation')} · {sum(r['launched'] for r in systems)} launched · "
               f"{sum(r['operating'] for r in systems)} operating", library.scoreboard(counts, figures), open=True)
detailed = sorted({row["satellite"] for row in lifecycle_rows})
reveal.section("library_lifecycles", "Lifecycles",
               f"every satellite in the registry, from launch to end of service · {' · '.join(detailed)} step by step",
               lambda: lifecycle_frame(lifecycle_rows, datetime.now(timezone.utc), registry), open=True)
reveal.section("library_generations", "By design generation", reveal.count(len(counts), "generation"),
               library.generations(counts))
reveal.section("library_money", "Money stated by public sources",
               f"{reveal.count(stated, 'figure')} stated · {len(figures) - stated} not known", library.costs(figures))
surfaces.show(surfaces.notice(library.matching(matched), "idle"))
lag = library.registry_lag_note(matched, satellites)
if lag:
    surfaces.show(surfaces.notice(lag, "warn"))

# ---- Datasets: one card each, a download on the card where its licence allows ----
surfaces.show(shelf.shelf_sign("datasets"))


def draw_group(group):
    with st.container(key=f"shelfbody_{group}"), st.container(key=f"shelf_{group}"):
        for key in (key for key, item in DATASETS.items() if item["shelf"] == group):
            content, size, fresh, problem = states[key]
            with st.container(key=f"item_{key}"):
                st.html(shelf.card_html(key, size, fresh, problem))
                if key in offered:
                    name = shelf.file_name(key)
                    st.download_button(f"Download {name}", content, file_name=name, key=f"dl_{key}", on_click="ignore",
                                       mime="text/csv" if name.endswith(".csv") else "application/json",
                                       icon=":material/download:")


for group, (title, line) in DATASET_GROUPS.items():
    keys = [key for key, item in DATASETS.items() if item["shelf"] == group]
    takeable = sum(key in offered for key in keys)
    reveal.section(f"library_{group}", title, f"{reveal.count(len(keys), 'dataset')} · {takeable} to take home · {line}",
                   lambda group=group: draw_group(group), open=group == "tables")

# ---- Take-aways ----
surfaces.show(shelf.shelf_sign("takeaways"))
with st.container(key="item_bundle"):
    surfaces.show(f'<div class="obj"><span class="plinth">{icons.mask("download")}</span><span class="lbl">'
                  f'<b>The whole shelf in one bag</b><p>All {len(offered)} files you may take home, with a note saying '
                  f'each one\'s licence, how to credit it and how fresh it is, and the project\'s licence files.</p>'
                  f'</span></div>')
    st.download_button(f"Download {BUNDLE_NAME}", shelf.bundle(offered), file_name=BUNDLE_NAME, mime="application/zip",
                       key="dl_bundle", on_click="ignore", icon=":material/download:")
with st.container(key="item_code"):
    surfaces.show(f'<div class="obj"><span class="plinth">{icons.mask("tool")}</span><span class="lbl">'
                  f'<b>The code</b><p>Everything that builds this dashboard, free to reuse under '
                  f'{shelf.licence_html("code")}. <a href="{CODE_LINK}" target="_blank" rel="noopener noreferrer">'
                  f'Get it from the repository</a>.</p></span></div>')

# ---- How to cite ----
surfaces.show(shelf.shelf_sign("cite"))


def draw_citations():
    with st.container(key="shelfbody_cite"):
        for who, words in CITATIONS:
            st.html(f'<p class="small">{escape(who)}</p>')
            st.code(words, language=None, wrap_lines=True)


reveal.section("library_cite", "Citations", f"{reveal.count(len(CITATIONS), 'citation')} to copy", draw_citations, open=True)
