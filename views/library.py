"""Library: the newest stories, the satellites and their lives (counts per constellation, lifecycles, generations,
money), the datasets (what only this project makes, what others make that we use, and who already does this work),
and how to cite. A tile per shelf opens that shelf and brings it into view.

What each shelf holds is in ui/shelf_settings.py; the cards are built in ui/shelf.py. Details sit in sections
(ui/reveal.py), all closed but the first shelf's, so the page opens on the tiles and the stories.

Another page can send the reader to a shelf: before this page runs it sets st.session_state["library_jump"] to
{"shelf": "stories" | "satellites" | "datasets" | "cite", "constellation": a key of ui.systems.SYSTEMS or None}.
This page takes it, opens that shelf (for "satellites" with a constellation, the lifecycles with it chosen; for
"stories", that constellation's stories) and scrolls to it.
"""
from datetime import datetime, timezone
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from evidence import news_stories
from evidence.library_settings import (LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE,
                                       LIFECYCLE_EVENTS_FILE)
from evidence.registry_settings import (
    REGISTRY_CATALOGUE_FILE,
    REGISTRY_DASHBOARD_SATELLITES_FILE,
    REGISTRY_SATELLITES_FILE,
    REGISTRY_SIGNAL_IDS_FILE
)
from evidence.registry_tables import read_table, registry_name
from ui import library, reveal, shelf, surfaces, systems
from ui.components.lifecycle import lifecycle_frame
from ui.session_keys import LIBRARY_JUMP
from ui.shelf_settings import (COLLEAGUES, OTHERS, OUR_CITATIONS, OURS, OUTSIDE_CITATIONS, SHELVES, STORIES_SHOWN)

JUMP = LIBRARY_JUMP


@st.cache_data(show_spinner=False)
def load():
    return [read_table(name) for name in (LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE, LIFECYCLE_EVENTS_FILE,
                                          REGISTRY_SATELLITES_FILE, REGISTRY_SIGNAL_IDS_FILE, REGISTRY_CATALOGUE_FILE,
                                          REGISTRY_DASHBOARD_SATELLITES_FILE)]


def jump_to(shelf_key):
    st.session_state[JUMP] = {"shelf": shelf_key, "constellation": None}


# ---- a jump, from a tile here or from another page: open its section, and scroll to it once the page is drawn ----
jump = st.session_state.pop(JUMP, None) or {}
jump_shelf = jump.get("shelf") if jump.get("shelf") in SHELVES else None
jump_constellation = jump.get("constellation") if jump.get("constellation") in systems.SYSTEMS else None
jump_section = None
if jump_shelf:
    jump_section = "library_lifecycles" if jump_shelf == "satellites" and jump_constellation else SHELVES[jump_shelf][2]
    st.session_state.setdefault(reveal.MEMORY, {})[jump_section] = True

counts, figures, matched, lifecycle_rows, satellites, signal_ids, catalogue, tracked = load()
registry = {"satellites": satellites, "signal_ids": signal_ids, "catalogue": catalogue, "tracked": tracked}
constellations = library.system_rows(counts)
stated = sum(figure["value"] != library.NOT_KNOWN for figure in figures)

files = shelf.published()
states = {key: shelf.item_state(key, files) for key in OURS}   # (bytes, freshness, problem)
news_file, news_problem = files["news"]
told = sorted(news_stories.stories(news_file.get("items", [])) if not news_problem else [],
              key=lambda story: max(item.get("published_at") or item.get("fetched_at") or "" for item in story["items"]),
              reverse=True)
story_parts = set(systems.SYSTEMS.get(jump_constellation, ())) if jump_shelf == "stories" else set()
if story_parts:
    told = [story for story in told if any(story_parts & set(item.get("constellations", [])) for item in story["items"])]

surfaces.show(library.CSS)
surfaces.show(shelf.CSS)

# ---- the shelves at a glance: each tile opens its shelf and goes to it ----
tiles = {"stories": (len(told), "Stories"), "satellites": (sum(r["launched"] for r in constellations), "Satellites launched"),
         "datasets": (len(OURS), "Datasets only here"), "cite": (len(OUR_CITATIONS) + len(OUTSIDE_CITATIONS), "How to cite")}
with st.container(key="shop_map"):
    for key, (number, words) in tiles.items():
        st.button(f"**{number}**\n\n{words}", key=f"tile_{key}", on_click=jump_to, args=(key,), use_container_width=True)

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

    scope = f" about {jump_constellation}" if story_parts else ""
    reveal.section("library_stories", "Newest stories",
                   f"newest {min(len(told), STORIES_SHOWN)} of {len(told)} stories{scope} · {shelf.job_words(('archive.yml', 'news'))}",
                   draw_stories, open=True)

# ---- Satellites and their lives ----
surfaces.show(shelf.shelf_sign("satellites"))
reveal.section("library_systems", "Count per constellation",
               f"{reveal.count(len(constellations), 'constellation')} · {sum(r['launched'] for r in constellations)} launched · "
               f"{sum(r['operating'] for r in constellations)} operating", library.scoreboard(counts, figures))
detailed = sorted({row["satellite"] for row in lifecycle_rows})
lifecycle_constellation = registry_name(jump_constellation) if jump_section == "library_lifecycles" else None
reveal.section("library_lifecycles", "Lifecycles",
               f"every satellite in the IGS satellite metadata file, from launch to end of service · {' · '.join(detailed)} step by step",
               lambda: lifecycle_frame(lifecycle_rows, datetime.now(timezone.utc), registry, lifecycle_constellation))
reveal.section("library_generations", "By design generation", reveal.count(len(counts), "generation"),
               library.generations(counts))
reveal.section("library_money", "Money stated by public sources",
               f"{reveal.count(stated, 'figure')} stated · {len(figures) - stated} not known", library.costs(figures))
surfaces.show(surfaces.notice(library.matching(matched), "idle"))
lag = library.registry_lag_note(matched, satellites)
if lag:
    surfaces.show(surfaces.notice(lag, "warn"))

# ---- Datasets: ours first, with how to get, use and cite each; then others', and who already does this work ----
surfaces.show(shelf.shelf_sign("datasets"))


def draw_ours():
    with st.container(key="shelfbody_ours"), st.container(key="shelf_ours"):
        for key in OURS:
            content, fresh, problem = states[key]
            with st.container(key=f"item_{key}"):
                st.html(shelf.card_html(key, content, fresh, problem))
                if content is not None:
                    name = shelf.file_name(key)
                    st.download_button(f"Download {name}", content, file_name=name, key=f"dl_{key}", on_click="ignore",
                                       mime="text/csv" if name.endswith(".csv") else "application/json",
                                       icon=":material/download:")


reveal.section("library_ours", "Only here",
               f"{reveal.count(len(OURS), 'dataset')} this project makes, free to reuse under CC BY 4.0", draw_ours)
reveal.section("library_others", "Others' data we use",
               f"{reveal.count(len(OTHERS), 'source')}, each kept by its owner; go to them for it", shelf.others_html(OTHERS))
reveal.section("library_people", "Who already does this work",
               f"{reveal.count(sum(len(people) for _, people in COLLEAGUES), 'place')} to go, by constellation",
               shelf.colleagues_html(COLLEAGUES))

# ---- How to cite ----
surfaces.show(shelf.shelf_sign("cite"))


def draw_citations():
    with st.container(key="shelfbody_cite"):
        for who, words in OUR_CITATIONS:
            st.html(f'<p class="small">{escape(who)}</p>')
            st.code(words, language=None, wrap_lines=True)
        st.html('<p class="small">Each outside source, as its owner asks</p>')
        for who, words in OUTSIDE_CITATIONS:
            st.html(f'<p class="small"><b>{escape(who)}</b> {escape(words)}</p>')


reveal.section("library_cite", "Citations", f"our data and the dashboard · {reveal.count(len(OUTSIDE_CITATIONS), 'outside source')}",
               draw_citations)

if jump_section:
    st.session_state["_library_jumps"] = st.session_state.get("_library_jumps", 0) + 1
    components.html(shelf.scroll_script(jump_section, st.session_state["_library_jumps"]), height=0)
