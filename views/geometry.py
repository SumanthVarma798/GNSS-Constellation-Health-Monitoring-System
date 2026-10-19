"""Geometry: how well the satellites' layout serves the places they cover (position quality), where they sit in the
sky and over the ground, how their orbits trend, and how evenly inclined orbits share a track.

What app.py showed in its DOP Analysis, Visualizations and RAAN Spacing tabs, worked out with the same functions.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from analysis.raan_analysis import analyze_raan_spacing
from ui import data, shell, surfaces
from ui import geometry_data as gd
from ui import geometry_settings as gs
from ui.figures import geometry as gf

CSS = Path(__file__).resolve().parent.parent / "ui" / "geometry.css"
CHART = {"use_container_width": True, "config": {"displayModeBar": False}}
ALL_SATELLITES_NOTE = "Position quality, the sky view and plane spacing count every satellite of each constellation."
WHOLE_CONSTELLATION = ("Position quality", "Sky view", "Plane spacing")
# What each section shows, said once above it.
SECTION_KEYS = {
    "Position quality": gf.dop_key(),
    "Sky view": ('<p class="small">Overhead in the middle, the horizon at the edge; the dotted ring is the elevation '
                 'mask. Play or drag through the next 24 hours.</p>'),
    "Ground tracks": ('<p class="small">Where each satellite passes over the ground, and where it is now. '
                      'The marks are the places position quality is worked out for.</p>'),
    "Orbit trends": gf.trends_key(),
    "Plane spacing": f'<p class="small">{gs.SPACING_INTRO}</p>',
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
    surfaces.show(gf.dop_grid(rows))
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


def _sky(constellation, satellites, types, now, mask):
    place = _place(constellation, "sky")
    frames = gd.sky_frames(satellites, *gs.PLACES[constellation][place], now, mask)
    st.plotly_chart(gf.sky_view(frames, types, mask), **CHART)


def _tracks(constellation, satellites, types, now, window):
    tracks, here = gd.ground_tracks(satellites, now, window)
    st.plotly_chart(gf.ground_map(tracks, here, types, gs.PLACES[constellation]), **CHART)


def _trends(constellation, result, names, types, now):
    window_days = st.session_state["window_days"]
    params = _params(constellation)
    since = pd.Timestamp((now - timedelta(days=window_days)).date())
    history = result["history"]
    history = history[history["satellite"].isin(names) & (history["EPOCH"] >= since)]
    series = {column: history[["satellite", "EPOCH", column]].dropna() for column, *_ in gs.TRENDS if column in history}
    series["central_lon"] = gd.central_longitudes(result["history"], names, since)
    bands = {n: gd.targets(constellation, n, types.get(n), params) for n in names}
    st.plotly_chart(gf.orbit_trends(series, names, types, bands, since, pd.Timestamp(now).tz_localize(None)), **CHART)


def _spacing(satellites):
    groups = analyze_raan_spacing(satellites)
    if not groups:
        surfaces.show(surfaces.notice("No inclined orbits here share a ground track, so there is no spacing to check.", "idle"))
    for group in groups:
        card, wheel = st.columns([3, 2], vertical_alignment="center")
        with card:
            surfaces.show(gf.spacing_card(group))
        with wheel:
            st.plotly_chart(gf.spacing_wheel(group), **CHART)


def constellation(name, picks, section, choice, mask, window, now):
    """One constellation's part of the page. `picks` limits the satellite-by-satellite pictures (None: all)."""
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
    elif section == "Sky view":
        _sky(name, satellites, types, now, mask)
    elif section == "Ground tracks":
        _tracks(name, {n: satellites[n] for n in own if n in satellites}, types, now, window)
    elif section == "Orbit trends":
        _trends(name, result, own, types, now)
    else:
        _spacing(satellites)


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
if section == "Ground tracks":
    with middle:
        window = shell.segment("geo_track_window", gs.TRACK_WINDOWS, label="Window")
if section in ("Position quality", "Sky view"):
    with right:
        mask = st.number_input("Elevation mask (degrees)", *gs.ELEVATION_MASK_RANGE, gs.ELEVATION_MASK_DEG, 1,
                               key="geo_mask", help="A satellite lower in the sky than this is not counted")
surfaces.show(SECTION_KEYS[section] + (f'<p class="small">{ALL_SATELLITES_NOTE}</p>'
                                         if st.session_state["compare"] and section in WHOLE_CONSTELLATION else ""))
try:
    for name, picks in chosen.items():
        if st.session_state["compare"]:
            _heading(name)
        constellation(name, picks, section, choice, mask, window, now)
except ValueError as error:
    surfaces.show(surfaces.notice(str(error), "warn"))
