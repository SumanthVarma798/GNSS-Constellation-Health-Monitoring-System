"""Library: how many navigation satellites each system has launched, lost and kept, and what public sources say it cost."""
import streamlit as st

from evidence.library_settings import LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE
from evidence.registry_tables import read_table
from ui import library, surfaces


@st.cache_data(show_spinner=False)
def load():
    return [read_table(name) for name in (LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE)]


counts, figures, matched = load()
surfaces.show(library.CSS)
surfaces.show('<p class="small">Satellites launched, lost and kept by each navigation system, counted from the General Catalog of '
              'Artificial Space Objects, and the money public sources say each programme cost. The ratios are plain counts '
              'with their definitions, not a ranking of agencies: the systems started in different decades, and their '
              'budgets cover different things.</p>')
surfaces.show(library.scoreboard(counts, figures))
surfaces.show(library.generations(counts))
surfaces.show(library.costs(figures))
surfaces.show(surfaces.notice(library.matching(matched), "idle"))
