"""The "next step" lines for the pages: ui/next_step.py's look ahead, worked out once per constellation and per data time.

Looking ahead for a constellation classifies its burns and fits each satellite's newest element sets; on the free host's
small CPU that is worth keeping. The cache is keyed on the constellation, the data's time, its newest element set, the
inclination tolerance, the shape of the result and the UTC hour (the dates are measured from "now"), never on the result itself.
"""
from datetime import datetime, timezone
from html import escape

import streamlit as st

from analysis import score_rules
from analysis.bundled_run import burn_classes_of
from analysis.meo_geometry import plane_drift
from evidence.registry_tables import judged_by_plane
from ui import next_step, outlook


def _hour():
    return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None)


def _tolerance(constellation, params):
    return float((params or {}).get("inclination_tolerance", score_rules.default_inclination_tolerance(constellation)))


@st.cache_data(show_spinner=False, max_entries=16)
def _look_ahead(constellation, data_time, newest, shape, tolerance, hour, _result):
    """{"drift", "as_of"} for a medium-orbit constellation, else {"forecasts": {satellite: ...}, "fuel": {...}, "now"}."""
    if judged_by_plane(constellation):
        return {"drift": plane_drift(constellation, _result["rows"]), "as_of": str(data_time)[:10], "now": hour}
    history = _result["history"]
    classes = burn_classes_of(_result, constellation)
    names = [str(n) for n in _result["health"]["Satellite"]]
    return {"forecasts": {n: next_step.satellite_forecast(n, history, classes, hour, tolerance, constellation)
                          for n in names},
            "fuel": {n: next_step.fuel_forecast(n, history, classes, hour) for n in names}, "now": hour}


def look_ahead(constellation, result, params=None):
    """The cached look ahead for one constellation's assessed `result` (ui.data.load)."""
    # the shape (records, burns found, satellites judged) tells apart the same data read with another time range or limits
    shape = (len(result["history"]), len(result["burns"]), tuple(map(str, result["health"]["Satellite"])))
    return _look_ahead(constellation, str(result["data_time"]), str(result["history"]["EPOCH"].max()), shape,
                       _tolerance(constellation, params), _hour(), result)


def constellation_line(constellation, result, params=None):
    """(text, tone, as_of) for the whole constellation."""
    ahead = look_ahead(constellation, result, params)
    if "drift" in ahead:
        return next_step.meo_line(constellation, ahead["drift"], ahead["as_of"])
    return next_step.constellation_line(list(ahead["forecasts"].values()), ahead["now"])


def satellite_lines(constellation, result, params=None):
    """{satellite: (text, tone, as_of)} for a slot-keeping constellation; {} for one judged by plane."""
    ahead = look_ahead(constellation, result, params)
    return {n: next_step.satellite_line(f, ahead["now"]) for n, f in ahead.get("forecasts", {}).items()}


def tile_tags(constellation, result, params=None):
    """{satellite: html} for the tiles' tag rows: a short line for each satellite where something is due soon."""
    ahead = look_ahead(constellation, result, params)
    out = {}
    for name, f in ahead.get("forecasts", {}).items():
        if line := next_step.tile_line(f, ahead["now"]):
            out[name] = f'<div class="nx {line[1]}">{escape(line[0])}</div>'
    return out


def geometry_lines(constellation, result, params=None):
    """{satellite: (text, tone, as_of)} for the Geometry page: what happens to each satellite's place in the layout."""
    ahead = look_ahead(constellation, result, params)
    out = {}
    for name, f in ahead.get("forecasts", {}).items():
        if text := next_step.geometry_line(f, ahead["now"]):
            _, tone, as_of = next_step.satellite_line(f, ahead["now"])
            out[name] = (text, tone, as_of)
    return out


def outlook_html(constellation, result, params=None, compact=False):
    """The look ahead drawn (ui/outlook.py): a slot-keeping constellation's east-west outlook, or a medium-orbit one's
    planes; compact: the figures alone, for a card. '' when nothing is worked out."""
    ahead = look_ahead(constellation, result, params)
    if "drift" in ahead:
        return outlook.planes(constellation, ahead["drift"], ahead["as_of"], compact=compact)
    forecasts = list(ahead["forecasts"].values())
    if compact:
        return outlook.figures(forecasts, ahead["now"])
    dated = [f["as_of"] for f in forecasts if f.get("as_of") is not None]
    return outlook.outlook(forecasts, ahead["now"], f"as of {next_step._day(max(dated))}" if dated else "")
