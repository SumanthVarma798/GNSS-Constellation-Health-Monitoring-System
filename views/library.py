"""Library: how many navigation satellites each system has launched, lost and kept, what public sources say it cost,
and each satellite's life from build to end of service.

Each part is in a section (ui/reveal.py): the count per system and the lifecycles open, the rest closed.
"""
from datetime import datetime, timezone

import streamlit as st

from evidence.library_settings import (LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE,
                                       LIFECYCLE_EVENTS_FILE)
from evidence.settings import (REGISTRY_CATALOGUE_FILE, REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_SATELLITES_FILE,
                               REGISTRY_SIGNAL_IDS_FILE)
from evidence.registry_tables import read_table
from ui import library, reveal, surfaces
from ui.components.lifecycle import lifecycle_frame


@st.cache_data(show_spinner=False)
def load():
    return [read_table(name) for name in (LIBRARY_COUNTS_FILE, LIBRARY_FIGURES_FILE, LIBRARY_MATCHING_FILE, LIFECYCLE_EVENTS_FILE,
                                          REGISTRY_SATELLITES_FILE, REGISTRY_SIGNAL_IDS_FILE, REGISTRY_CATALOGUE_FILE,
                                          REGISTRY_DASHBOARD_SATELLITES_FILE)]


counts, figures, matched, lifecycle_rows, satellites, signal_ids, catalogue, tracked = load()
registry = {"satellites": satellites, "signal_ids": signal_ids, "catalogue": catalogue, "tracked": tracked}
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
detailed = sorted({row["satellite"] for row in lifecycle_rows})
reveal.section("library_lifecycles", "Lifecycles",
               f"every satellite in the registry, from launch to end of service · {' · '.join(detailed)} step by step",
               lambda: lifecycle_frame(lifecycle_rows, datetime.now(timezone.utc), registry), open=True)
reveal.section("library_generations", "By design generation", reveal.count(len(counts), "generation"),
               library.generations(counts))
reveal.section("library_money", "Money stated by public sources",
               f"{reveal.count(stated, 'figure')} stated · {len(figures) - stated} not known", library.costs(figures))
reveal.section("library_notes", "Notes", "what each count means, and where it comes from", library.notes(counts))
surfaces.show(surfaces.notice(library.matching(matched), "idle"))
lag = library.registry_lag_note(matched, satellites)
if lag:
    surfaces.show(surfaces.notice(lag, "warn"))
