"""Geometry: how well the satellites' layout serves the places they cover (position quality), where they sit in the
sky and over the ground, how their orbits trend, and how evenly inclined orbits share a track.

What app.py showed in its DOP Analysis, Visualizations and RAAN Spacing tabs, worked out with the same functions.
"Sky and ground" is for one place: a key place, a latitude and longitude typed in, or a point clicked on the map;
the sky above it now and over the next day, and when each satellite is next in view there (issue 98).
What each section shows is behind a pill ("What this shows"); the tables are in sections (ui/reveal.py): position
quality by place and when each satellite is in view open, each plane spacing group's satellites closed.
"""
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from analysis.raan_analysis import analyze_raan_spacing
from ui import data, reveal, shell, surfaces, tooltip
from ui import geometry_data as gd
from ui import geometry_settings as gs
from ui.components.sky_view import sky_view
from ui.figures import geometry as gf

CSS = Path(__file__).resolve().parent.parent / "ui" / "geometry.css"
CHART = {"use_container_width": True, "config": {"displayModeBar": False}}
ALL_SATELLITES_NOTE = ("Position quality, the sky, when each satellite is in view and plane spacing count every "
                       "satellite of each constellation; the ground tracks only the picks.")
WHOLE_CONSTELLATION = ("Position quality", "Sky and ground")
# What each section shows, behind a pill above it.
SECTION_KEYS = {
    "Position quality": gf.dop_key(),
    "Sky and ground": ('<p>The map: where each satellite passes over the ground, and where it is now; the crosses are '
                       'the key places. Click anywhere on it, pick a key place or type a latitude and longitude to see '
                       'the sky above that place.</p>'
                       '<p>The sky: overhead in the middle, the horizon at the edge; the dotted ring is the elevation '
                       'mask. Play or drag through the next 24 hours.</p>'
                       f'<p>Plane spacing: {gs.SPACING_INTRO}</p>'),
    "Orbit trends": gf.trends_key(),
}


def _chosen():
    """{constellation: [satellite, ...] or None for all} for the top bar's choice, as Station-keeping reads it."""
    if not st.session_state["compare"]:
        return {st.session_state["scope"]: None}
    picks = st.session_state.get("compare_picks", {})
    return {name: picks[name] for name in shell.CONSTELLATIONS if picks.get(name)}


def _heading(text):
    surfaces.show(f'<div class="geo-head">{text}</div>')


def _params(constellation):
    params = dict(st.session_state["params"])
    if constellation == "QZSS":
        params.setdefault("inclination_tolerance", shell.QZSS_INCLINATION_TOLERANCE)
    return params


def _place(constellation, key):
    places = list(gs.PLACES[constellation])
    capital = next((i for i, p in enumerate(places) if p.startswith("Capital")), 0)
    return st.selectbox("Place", places, index=capital, key=f"geo_place_{key}_{constellation}")


def _position_quality(constellation, satellites, now, mask):
    rows = gd.dop_rows(satellites, gs.PLACES[constellation], now, mask)
    unfixed = sum(row["GDOP"] is None for row in rows)
    reveal.section(f"geo_dop_{constellation}", "Position quality by place",
                   f"{reveal.count(len(rows), 'place')} · " + (f"{unfixed} without a position" if unfixed
                                                               else "a position at every place"),
                   gf.dop_grid(rows), open=True)
    if all(row["GDOP"] is None for row in rows):
        surfaces.show(surfaces.notice("Fewer than 4 of these satellites are in view at every place, so no position "
                                      "can be worked out.", "bad"))
    _heading("Over the last 24 hours")
    place = _place(constellation, "trend")
    series = gd.dop_series(satellites, *gs.PLACES[constellation][place], now, mask)
    summary = gf.gdop_summary(series)
    if summary:
        surfaces.show(summary)
    st.plotly_chart(gf.dop_trend(series, place), **CHART)


def _where(constellation):
    """The place the sky is shown for: (name, latitude, longitude). The capital until the reader picks another."""
    places = gs.PLACES[constellation]
    capital = next((p for p in places if p.startswith("Capital")), next(iter(places)))
    name, lat, lon = st.session_state.setdefault(f"geo_where_{constellation}", (capital, *places[capital]))
    # the two inputs show the place; Streamlit forgets them while another section is shown, so they are put back
    st.session_state.setdefault(f"geo_pick_{constellation}", name if name in places else None)
    st.session_state.setdefault(f"geo_coords_{constellation}", f"{lat:g}, {lon:g}")
    return name, lat, lon


def _go(constellation, name, lat, lon, key_place=None):
    """Show the sky above another place; the key place list and the typed coordinates follow it."""
    st.session_state[f"geo_where_{constellation}"] = (name, lat, lon)
    st.session_state[f"geo_pick_{constellation}"] = key_place
    st.session_state[f"geo_coords_{constellation}"] = f"{lat:g}, {lon:g}"
    st.session_state.pop(f"geo_error_{constellation}", None)


def _picked(constellation):
    name = st.session_state[f"geo_pick_{constellation}"]
    if name:
        _go(constellation, name, *gs.PLACES[constellation][name], key_place=name)


def _typed(constellation):
    try:
        lat, lon = gd.parse_place(st.session_state[f"geo_coords_{constellation}"])
    except ValueError as error:
        st.session_state[f"geo_error_{constellation}"] = str(error)
        return
    _go(constellation, gf.latlon_words(lat, lon), lat, lon)


def _clicked(constellation):
    points = st.session_state[f"geo_map_{constellation}"]["selection"]["points"]
    if not points:
        return
    point = points[0]
    lat, lon = gd.clicked_place(point)
    key_place = next((p for p, at in gs.PLACES[constellation].items() if at == (lat, lon)), None)
    _go(constellation, key_place or gf.latlon_words(lat, lon), lat, lon, key_place)


def _place_controls(constellation):
    """A key place, or a latitude and longitude typed in. The map takes clicks as well."""
    pick, typed = st.columns([1, 1], vertical_alignment="bottom")
    with pick:
        st.selectbox("Key place", list(gs.PLACES[constellation]), key=f"geo_pick_{constellation}",
                     placeholder="Choose a key place", on_change=_picked, args=(constellation,))
    with typed:
        st.text_input("Or a latitude, longitude", key=f"geo_coords_{constellation}", placeholder=gs.PLACE_EXAMPLE,
                      help=gs.PLACE_HELP, on_change=_typed, args=(constellation,))
    error = st.session_state.get(f"geo_error_{constellation}")
    if error:
        surfaces.show(surfaces.notice(error, "bad"))


def _sky_and_ground(constellation, satellites, own, types, now, mask, window):
    """The map and the sky above the chosen place side by side (one under the other on a phone), when each satellite
    is next in view there, then plane spacing."""
    name, lat, lon = _where(constellation)
    _place_controls(constellation)
    zone = shell.viewer_zone()
    _heading(f"The sky above {escape(name)}")
    ground, sky = st.columns([3, 2])
    with ground:
        tracks, here = gd.ground_tracks({n: satellites[n] for n in own if n in satellites}, now, window)
        st.plotly_chart(gf.ground_map(tracks, here, types, gs.PLACES[constellation], (name, lat, lon)),
                        key=f"geo_map_{constellation}", on_select=lambda: _clicked(constellation),
                        selection_mode="points", **CHART)
    with sky:
        sky_view(gd.sky_frames(satellites, lat, lon, now, mask), gd.sky_paths(satellites, lat, lon, now), types, mask, zone)
    rows = gd.next_visible(satellites, lat, lon, now, mask)
    reveal.section(f"geo_next_{constellation}", "When each satellite is in view", gf.next_summary(rows, now, zone),
                   gf.next_table(rows, types, now, zone), open=True)
    _heading("Plane spacing")
    _spacing(constellation, satellites)


def _trends(constellation, result, names, types, now):
    window_days = st.session_state["window_days"]
    params = _params(constellation)
    since = pd.Timestamp((now - timedelta(days=window_days)).date())
    history = result["history"]
    history = history[history["satellite"].isin(names) & (history["EPOCH"] >= since)]
    series = {column: history[["satellite", "EPOCH", column]].dropna() for column, *_ in gs.TRENDS if column in history}
    series["central_lon"] = gd.central_longitudes(result["history"], names, since)
    end = pd.Timestamp(now).tz_localize(None)
    order = [n for _, group in gf.by_orbit(names, types) for n in group]
    columns = st.columns(2)
    for i, name in enumerate(order):   # two a row on wide screens, one under another on a phone
        with columns[i % 2]:
            bands = gd.targets(constellation, name, types.get(name), params)
            st.plotly_chart(gf.satellite_trends(series, name, types.get(name, gs.OTHER_ORBIT), bands, since, end), **CHART)


def _spacing(constellation, satellites):
    groups = analyze_raan_spacing(satellites)
    if not groups:
        surfaces.show(surfaces.notice("No inclined orbits here share a ground track, so there is no spacing to check.", "idle"))
    for i, group in enumerate(groups):
        card, wheel = st.columns([3, 2], vertical_alignment="center")
        with card:
            surfaces.show(gf.spacing_card(group))
            reveal.section(f"geo_spacing_{constellation}_{i}", "Each satellite's node", gf.spacing_title(group),
                           gf.spacing_table(group))
        with wheel:
            st.plotly_chart(gf.spacing_wheel(group), **CHART)


def constellation(name, picks, section, choice, mask, window, now):
    """One constellation's part of the page. `picks` limits the satellite-by-satellite pictures (None: all)."""
    if name not in gs.PLACES:   # worked out for the regional systems' key places; GPS, GLONASS, Galileo have none yet
        regional = ", ".join(list(gs.PLACES)[:-1]) + " and " + list(gs.PLACES)[-1]
        surfaces.show(surfaces.notice(f"Geometry covers {regional} only, not yet {name}.", "idle"))
        return
    result = data.load(name, st.session_state["window_days"], st.session_state["params"])
    every = list(dict.fromkeys(result["history"]["satellite"]))
    counted = gd.chosen_satellites(every, result["set_aside"], choice)
    left_out = [n for n in every if n not in counted]
    if left_out:
        surfaces.show(surfaces.notice(f"Left out as not in service: {', '.join(left_out)}", "idle"))
    satellites = gd.satellites_from_history(result["history"], counted)
    types = gd.orbit_types(result["health"], result["history"])
    own = [n for n in counted if picks is None or n in picks]
    if section == "Position quality":
        _position_quality(name, satellites, now, mask)
    elif section == "Sky and ground":
        _sky_and_ground(name, satellites, own, types, now, mask, window)
    else:
        _trends(name, result, own, types, now)


st.html(f"<style>{CSS.read_text(encoding='utf-8')}</style>")
chosen = _chosen()
if not chosen:
    surfaces.show('<p class="small">Pick satellites on the Overview to compare.</p>')
    st.stop()

section = shell.segment("geo_section", gs.SECTIONS, label="Section")
now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
choice, mask, window = gs.SATELLITE_CHOICES[0], gs.ELEVATION_MASK_DEG, gs.TRACK_WINDOWS[0]
left, middle, right = st.columns([2, 2, 1], vertical_alignment="bottom")
if any(n in gs.NOT_IN_SERVICE for c in chosen for n in data.SATELLITES[c]):
    with left:
        choice = shell.segment("geo_satellites", gs.SATELLITE_CHOICES, label="Satellites")
if section == "Sky and ground":
    with middle:
        window = shell.segment("geo_track_window", gs.TRACK_WINDOWS, label="Window")
if section in ("Position quality", "Sky and ground"):
    with right:
        mask = st.number_input("Elevation mask (degrees)", *gs.ELEVATION_MASK_RANGE, gs.ELEVATION_MASK_DEG, 1,
                               key="geo_mask", help="A satellite lower in the sky than this is not counted")
if any(name in gs.PLACES for name in chosen):   # nothing to explain where the page says it does not cover them yet
    surfaces.show(f'<div class="facts">{tooltip.tip_html("What this shows", SECTION_KEYS[section], pill=True)}'
                  + (f"<span>{ALL_SATELLITES_NOTE}</span>" if st.session_state["compare"] and section in WHOLE_CONSTELLATION
                     else "") + "</div>")
try:
    for name, picks in chosen.items():
        if st.session_state["compare"]:
            _heading(name)
        constellation(name, picks, section, choice, mask, window, now)
except ValueError as error:
    surfaces.show(surfaces.notice(str(error), "warn"))
