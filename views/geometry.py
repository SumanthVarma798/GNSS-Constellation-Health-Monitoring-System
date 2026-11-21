"""Geometry: how well the satellites' layout serves places the reader knows (position quality), where they sit in the
sky and over the ground, how their orbits trend, and how evenly inclined orbits share a track.

Position quality: the reader picks "your place" and a place to compare from a list of world cities (ui/geometry_settings.py;
no location is asked of the browser); each gets its satellites in view and its position error in metres, on a map of
cities coloured by theirs, with DOP explained from first principles one step at a time. Sky and ground starts at your
place; when each satellite is in view is a timeline, a lane each. Orbit trends: a card per satellite, full width, each
opening with one computed line. Each picture has one line of what it shows and a section one step deeper (ui/reveal.py).
"""
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from skyfield.api import EarthSatellite

from analysis.raan_analysis import analyze_raan_spacing
from evidence.registry_tables import judged_by_plane
from ui import limits, data, next_step, next_step_data, reveal, shell, surfaces, tooltip
from ui import geometry_data as gd
from ui import geometry_settings as gs
from ui.components.ferris import ferris
from ui.components.sky_view import sky_view
from ui.figures import geometry as gf
from ui.picker import chosen_constellations

CSS = Path(__file__).resolve().parent.parent / "ui" / "geometry.css"
CHART = {"use_container_width": True, "config": {"displayModeBar": False}}
ALL_SATELLITES_NOTE = ("Position quality, the sky, when each satellite is in view and plane spacing count every "
                       "satellite of each constellation; the ground tracks only the picks.")
WHOLE_CONSTELLATION = ("Position quality", "Sky and ground")
# What each section shows, behind a pill above it.
SECTION_KEYS = {
    "Position quality": gf.dop_key(),
    "Sky and ground": tooltip.glance(gs.SKY_GROUND_LEAD, gs.SKY_GROUND_KEY, gs.SKY_GROUND_NOTE),
    "Orbit trends": gf.trends_key(),
}


def _heading(text):
    surfaces.show(f'<div class="geo-head">{text}</div>')


def _params(constellation):
    params = dict(st.session_state["params"])
    if constellation == "QZSS":
        params.setdefault("inclination_tolerance", limits.QZSS_INCLINATION_TOLERANCE)
    return params


def _remember_place(constellation, who):
    st.session_state[f"geo_places_{constellation}"][who] = st.session_state[f"geo_{who}_{constellation}"]


def _chosen_places(constellation):
    """The two cities the reader chose, (your place, the place to compare with), kept between sections."""
    kept = st.session_state.setdefault(f"geo_places_{constellation}", dict(zip(("you", "vs"), gs.default_places(constellation))))
    return kept["you"], kept["vs"]


def _place_pickers(constellation):
    """Your place and a second place to compare it with, from the list of world cities. No location is asked of the browser."""
    you, vs = _chosen_places(constellation)
    st.session_state.setdefault(f"geo_you_{constellation}", you)   # the pickers start at the places kept
    st.session_state.setdefault(f"geo_vs_{constellation}", vs)
    left, right = st.columns(2)
    for column, who, label in ((left, "you", gs.YOU_LABEL), (right, "vs", gs.COMPARE_LABEL)):
        with column:
            ferris(label, sorted(gs.CITIES), key=f"geo_{who}_{constellation}", on_change=_remember_place,
                   args=(constellation, who))
    return _chosen_places(constellation)


def _explained(key, title, line, deeper_html):
    """What a picture shows and how to read it: one line always, the rest one step deeper."""
    reveal.section(key, title, line, deeper_html)


# cache_resource, as the trend: the satellites count by their element set; the clock is on five-minute steps.
@st.cache_resource(show_spinner=False, max_entries=16,
                   hash_funcs={EarthSatellite: lambda sat: (sat.name, sat.model.satnum, sat.epoch.tt)})
def _city_rows(satellites, cities, when, mask):
    return gd.dop_rows(satellites, dict(cities), when, mask)


def _position_quality(constellation, satellites, now, mask, choice, more):
    surfaces.show(gf.too_few_line(constellation, list(satellites), choice, more))
    you, vs = _place_pickers(constellation)
    here, there = gs.CITIES[you], gs.CITIES[vs]
    x_range, y_range = gf.map_ranges(list(gs.PLACES[constellation].values()), [here, there])
    shown = {name: at for name, at in gs.CITIES.items() if name in (you, vs)
             or (x_range[0] <= at[1] <= x_range[1] and y_range[0] <= at[0] <= y_range[1])}
    when = now - timedelta(minutes=now.minute % gs.CITY_STEP_MINUTES)
    rows = _city_rows(satellites, tuple(shown.items()), when, mask)
    by_name = {row["place"]: row for row in rows}
    surfaces.show(gf.place_cards(by_name[you], by_name[vs]))
    surfaces.show(gf.quality_legend_html())
    with st.container(key="geo_qmap"):
        st.plotly_chart(gf.quality_map(rows, by_name[you], by_name[vs], (x_range, y_range)), **CHART)
    _explained(f"geo_map_say_{constellation}", "The map",
               "Each dot is a city: its colour and shape say how well the satellites pin its position down now.",
               gf.quality_map_deeper())
    spread, bunched = st.columns(2)
    for column, angles, words in ((spread, gs.SPREAD_ANGLES, "Spread across the sky"), (bunched, gs.BUNCHED_ANGLES, "Bunched together")):
        with column:
            surfaces.show(f'<div class="geo-head tight">{words}</div>')
            st.plotly_chart(gf.spread_sketch(angles), **CHART)
    surfaces.show(f'<p class="geo-say">{escape(gf.spread_words())}</p>')
    reveal.section(f"geo_dop_how_{constellation}", "What DOP means",
                   gs.DOP_LINE, gf.dop_steps_html())
    key_rows = gd.dop_rows(satellites, gs.PLACES[constellation], now, mask)
    unfixed = sum(row["GDOP"] is None for row in key_rows)
    reveal.section(f"geo_dop_{constellation}", "Every DOP value at the key places",
                   f"{reveal.count(len(key_rows), 'place')} · " + (f"{unfixed} without a position" if unfixed
                                                                    else "a position at every place"),
                   gf.dop_grid(key_rows))
    if all(row["GDOP"] is None for row in key_rows):
        surfaces.show(surfaces.notice("Fewer than 4 of these satellites are in view at every place, so no position "
                                      "can be worked out.", "bad"))
    _heading(f"Over the last 24 hours at {escape(you)}")
    end = now - timedelta(minutes=now.minute % gs.TREND_STEP_MINUTES)   # on the trend's own steps, so it can be kept
    summary, figure = _trend(satellites, *here, end, mask, you)
    if summary:
        surfaces.show(summary)
    st.plotly_chart(figure, **CHART)
    _explained(f"geo_trend_say_{constellation}", "The 24 hours", gs.DOP_TREND_LINE, f"<p>{escape(gs.DOP_TREND_DEEPER)}</p>")


# cache_resource, as Station-keeping's timeline: never changed after they are made. A satellite counts by its element set.
@st.cache_resource(show_spinner=False, max_entries=16,
                   hash_funcs={EarthSatellite: lambda sat: (sat.name, sat.model.satnum, sat.epoch.tt)})
def _trend(satellites, lat, lon, end, mask, place):
    """The trend's summary and chart, made once per step (15 minutes): on Render's share of a CPU about 3 seconds."""
    series = gd.dop_series(satellites, lat, lon, end, mask)
    return gf.gdop_summary(series), gf.dop_trend(series, place)


def _choices(constellation):
    """The places the sky can be shown for by name: the world cities, then the constellation's key places."""
    return {**gs.CITIES, **gs.PLACES[constellation]}


def _where(constellation):
    """The place the sky is shown for: (name, latitude, longitude). Your place until the reader picks another."""
    choices = _choices(constellation)
    you, _ = _chosen_places(constellation)
    name, lat, lon = st.session_state.setdefault(f"geo_where_{constellation}", (you, *choices[you]))
    # the two inputs show the place; Streamlit forgets them while another section is shown, so they are put back
    st.session_state.setdefault(f"geo_pick_{constellation}", name if name in choices else None)
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
        _go(constellation, name, *_choices(constellation)[name], key_place=name)


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
    key_place = next((p for p, at in _choices(constellation).items() if at == (lat, lon)), None)
    _go(constellation, key_place or gf.latlon_words(lat, lon), lat, lon, key_place)


def _place_controls(constellation):
    """A city or key place, or a latitude and longitude typed in. The map takes clicks as well."""
    pick, typed = st.columns([1, 1])   # top: the wheel opens downward without moving the other input
    with pick:
        ferris("City or key place", list(_choices(constellation)), key=f"geo_pick_{constellation}",
               placeholder="Choose a city or key place", on_change=_picked, args=(constellation,))
    with typed:
        st.text_input("Or a latitude, longitude", key=f"geo_coords_{constellation}", placeholder=gs.PLACE_EXAMPLE,
                      help=gs.PLACE_HELP, on_change=_typed, args=(constellation,))
    error = st.session_state.get(f"geo_error_{constellation}")
    if error:
        surfaces.show(surfaces.notice(error, "bad", inline=True))


def _sky_and_ground(constellation, satellites, own, types, now, mask, window, result):
    """The map and the sky above the chosen place side by side (one under the other on a phone), when each satellite
    is next in view there as a timeline, then plane spacing. Each picture has its one line and a step deeper."""
    name, lat, lon = _where(constellation)
    you, vs = _chosen_places(constellation)
    _place_controls(constellation)
    zone = shell.viewer_zone()
    _heading(f"The sky above {escape(name)}")
    here = gd.dop_rows(satellites, {name: (lat, lon)}, now, mask)[0]
    surfaces.show(f'<p class="geo-say">{escape(gf.place_line(here))} {gf.latlon_words(lat, lon)}.</p>')
    ground, sky = st.columns([3, 2])
    with ground:
        tracks, now_at = gd.ground_tracks({n: satellites[n] for n in own if n in satellites}, now, window)
        marked = [(gs.city_short(city), *gs.CITIES[city]) for city in (you, vs)]
        st.plotly_chart(gf.ground_map(tracks, now_at, types, gs.PLACES[constellation], (name, lat, lon), marked),
                        key=f"geo_map_{constellation}", on_select=lambda: _clicked(constellation),
                        selection_mode="points", **CHART)
        _explained(f"geo_ground_{constellation}", "The ground map", gs.GROUND_LINE, f"<p>{escape(gs.GROUND_DEEPER)}</p>")
    with sky:
        sky_view(gd.sky_frames(satellites, lat, lon, now, mask), gd.sky_paths(satellites, lat, lon, now), types, mask, zone)
        _explained(f"geo_sky_{constellation}", "The sky", gs.SKY_LINE, f"<p>{escape(gs.SKY_DEEPER)}</p>")
    rows = gd.view_windows(satellites, lat, lon, now, mask)
    _heading(f"When each satellite is in view above {escape(name)}")
    surfaces.show(f'<p class="geo-say">{escape(gf.next_summary(rows, now, zone))}</p>')
    st.plotly_chart(gf.view_timeline(rows, types, now, zone), **CHART)
    _explained(f"geo_next_{constellation}", "The timeline", gs.TIMELINE_LINE, f"<p>{escape(gs.TIMELINE_DEEPER)}</p>")
    _heading("Plane spacing")
    _spacing(constellation, satellites, result)


def _trends(constellation, result, names, types, now, ahead=None):
    window_days = st.session_state["window_days"]
    params = _params(constellation)
    since = pd.Timestamp((now - timedelta(days=window_days)).date())
    history = result["history"]
    history = history[history["satellite"].isin(names) & (history["EPOCH"] >= since)]
    measures = gs.MEO_TRENDS if judged_by_plane(constellation) else gs.TRENDS
    series = {column: history[["satellite", "EPOCH", column]].dropna() for column, *_ in measures if column in history}
    if measures is gs.TRENDS:
        series["central_lon"] = gd.central_longitudes(result["history"], names, since)
    end = pd.Timestamp(now).tz_localize(None)
    order = [n for _, group in gf.by_orbit(names, types) for n in group]
    for name in order:   # every card full width and as tall as the next: the graph takes most of it
        orbit = types.get(name, gs.OTHER_ORBIT)
        bands = gd.targets(constellation, name, types.get(name), params)
        line = gf.trend_line(series, name, bands, window_days, measures) or "No orbit readings in this window."
        slug = re.sub(r"\W", "_", name)
        with st.container(key=f"geo_card_{constellation}_{slug}"):
            surfaces.show(f'<div class="geo-card-head"><b>{escape(name)}</b> <span class="muted">'
                          f'{escape(gs.ORBIT_WORDS.get(orbit, orbit))}</span>'
                          f'{tooltip.tip_html("What you are looking at", gf.trends_key(), pill=True, key=name)}</div>'
                          f'<p class="geo-say">{escape(line)}</p>'
                          + (next_step.line_html(ahead[name]) if ahead and name in ahead else ""))
            st.plotly_chart(gf.satellite_trends(series, name, bands, since, end, measures), **CHART)


def _spacing(constellation, satellites, result):
    if judged_by_plane(constellation):
        rows = gd.plane_rows(constellation, result["rows"])
        spacing = rows[0]["spacing_deg"] if rows else 0
        _explained(f"geo_plane_{constellation}", "How it is checked", gs.PLANE_WHY_MEO.format(spacing=spacing, planes=len(rows)),
                   f"<p>{escape(gs.PLANE_LINE_DEEPER)}</p>")
        for row in rows:
            surfaces.show(gf.plane_card(row))
        return
    _explained(f"geo_plane_{constellation}", "How it is checked", gs.PLANE_WHY_INCLINED, f"<p>{escape(gs.PLANE_LINE_DEEPER)}</p>")
    groups = analyze_raan_spacing(satellites)
    if not groups:
        surfaces.show(surfaces.notice("No inclined orbits here share a ground track, so there is no spacing to check.",
                                      "idle", inline=True))
    for i, group in enumerate(groups):
        card, wheel = st.columns([3, 2], vertical_alignment="center")
        with card:
            surfaces.show(gf.spacing_card(group))
            reveal.section(f"geo_spacing_{constellation}_{i}", "Each satellite's node", gf.spacing_title(group),
                           gf.spacing_table(group))
        with wheel:
            st.plotly_chart(gf.spacing_wheel(group), **CHART)


def _next_step(name, result):
    """{satellite: geometry line} for the trend cards (the constellation's outlook is drawn on Overview and
    Station-keeping, not repeated here). The look ahead is extra: when it fails the page stands without it."""
    try:
        return next_step_data.geometry_lines(name, result, st.session_state["params"])
    except Exception as error:
        surfaces.notice(f"Next steps could not be worked out: {type(error).__name__}: {error}", "warn")
        return {}


def constellation(name, picks, section, choice, mask, window, now):
    """One constellation's part of the page. `picks` limits the satellite-by-satellite pictures (None: all)."""
    if name not in gs.PLACES:   # every system on the chips has places (gs.GLOBAL_PLACES for the MEO ones); a new one may not
        regional = ", ".join(list(gs.PLACES)[:-1]) + " and " + list(gs.PLACES)[-1]
        surfaces.show(surfaces.notice(f"Geometry covers {regional} only, not yet {name}.", "idle", inline=True))
        return
    result = data.load(name, st.session_state["window_days"], st.session_state["params"])
    every = list(dict.fromkeys(result["history"]["satellite"]))
    counted = gd.chosen_satellites(every, [*result["set_aside"], *result.get("moving", {})], choice)
    left_out = [n for n in every if n not in counted]
    if left_out:
        surfaces.show(surfaces.notice(f"Left out as not in service: {', '.join(left_out)}", "idle"))
    if no_data := [n for n, norad in data.SATELLITES[name].items() if norad is not None and n not in every]:
        surfaces.show(surfaces.notice(f"No orbit data, so not drawn: {', '.join(no_data)}", "warn"))
    satellites = gd.satellites_from_history(result["history"], counted)
    types = gd.orbit_types(result["health"], result["history"])
    own = [n for n in counted if picks is None or n in picks]
    ahead = _next_step(name, result)   # under the heading: what should happen next to the layout
    if section == "Position quality":
        _position_quality(name, satellites, now, mask, choice, bool(left_out))
    elif section == "Sky and ground":
        _sky_and_ground(name, satellites, own, types, now, mask, window, result)
    else:
        _trends(name, result, own, types, now, ahead)


st.html(f"<style>{CSS.read_text(encoding='utf-8')}</style>")
chosen = chosen_constellations()
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
    surfaces.show(surfaces.notice(str(error), "warn", inline=True))
