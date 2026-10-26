"""Library: how many navigation satellites each system has launched, lost and kept, and what public sources say it cost.

Each table is in a section (ui/reveal.py): the count per system open, the rest closed.
"""
import streamlit as st

from evidence.library_settings import LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE
from evidence.settings import REGISTRY_SATELLITES_FILE
from evidence.registry_tables import read_table
from ui import library, reveal, surfaces


@st.cache_data(show_spinner=False)
def load():
    return [read_table(name) for name in (LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE)]


counts, figures, matched = load()
systems = library.system_rows(counts)
stated = sum(figure["value"] != library.NOT_KNOWN for figure in figures)
surfaces.show(library.CSS)
surfaces.show('<p class="small">Satellites launched, lost and kept by each navigation system, counted from the General Catalog of '
              'Artificial Space Objects, and the money public sources say each programme cost. The ratios are plain counts '
              'with their definitions, not a ranking of agencies: the systems started in different decades, and their '
              'budgets cover different things.</p>')
reveal.section("library_systems", "Count per system",
               f"{reveal.count(len(systems), 'system')} · {sum(r['launched'] for r in systems)} launched · "
               f"{sum(r['operating'] for r in systems)} operating", library.scoreboard(counts, figures), open=True)
reveal.section("library_generations", "By design generation", reveal.count(len(counts), "generation"),
               library.generations(counts))
reveal.section("library_money", "Money stated by public sources",
               f"{reveal.count(stated, 'figure')} stated · {len(figures) - stated} not known", library.costs(figures))
reveal.section("library_notes", "Notes", "what each count means, and where it comes from", library.notes(counts))
surfaces.show(surfaces.notice(library.matching(matched), "idle"))
lag = library.registry_lag_note(matched, read_table(REGISTRY_SATELLITES_FILE))
if lag:
    surfaces.show(surfaces.notice(lag, "warn"))
