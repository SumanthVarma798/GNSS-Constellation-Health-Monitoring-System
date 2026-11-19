"""What should happen next, said plainly: the forecast (analysis/slot_forecast.py, analysis/fuel_use.py) turned into one
line per satellite, per constellation and per plane, so a reader sees what is due and not only what is wrong.

Pure: no Streamlit and no clock (the caller passes `now`). ui/next_step_data.py caches it for the pages.

Where the satellite is and how fast it drifts come from a fit to its newest element sets (their mean longitudes, from
the elements, as analysis/burn_context.py works them), after its last east-west burn, with the pull of the Earth's
oval equator taken out of the fit (analysis/slot_forecast.longitude_acceleration): never from the mean-motion
formula, which carries the Earth's flattening as a bias. Its own box (the width it keeps itself in) comes from the
size of its routine east-west burns (analysis/burn_classes.py); with fewer than MIN_ROUTINE_BURNS of them, a share of
ours is assumed and the line says so. The date is a range, as the model is a parabola and the operator may burn first.

Every line returns (text, tone, as_of): `as_of` is the date of the newest element set it was worked out from.
line_html draws it with the standing caveat. Words are exact and never imply fault: a satellite held off its slot
is "held", not "wrong".
"""
import csv
from functools import lru_cache
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import burn_classes, burn_context, score_rules
from analysis import burn_class_settings as S
from analysis.forecast_settings import (
    DASHBOARD_BOX_GEO_DEG, DASHBOARD_BOX_TILTED_DEG, DRIFT_PER_KM, NS_GROWTH_DEG_PER_YEAR,
)
from analysis.fuel_use import annual_rate, remaining_band
from analysis.slot_forecast import forecast, longitude_acceleration, ns_forecast, own_box_half_width, time_to_edge
from ui import next_step_settings as N

BUDGETS = Path(__file__).resolve().parent.parent / "registry" / "bus_budgets.csv"
EAST_WEST = "east-west"
CAVEAT = "from the latest element sets; it changes if the operator manoeuvres"


# ---- working it out ----------------------------------------------------------------------------------------------

def _box(orbit_type):
    return DASHBOARD_BOX_GEO_DEG if orbit_type == "GEO" else DASHBOARD_BOX_TILTED_DEG


def satellite_forecast(name, history, classes, now, tolerance=1.0, constellation=""):
    """One satellite's look ahead as a dict. `status` is "ok", "weak" (it sits where the pull is too weak for the
    parabola: only its drift is used), "settling" (burned too recently to read its drift), "stale", "no_data" or
    "no_slot". An "ok" or "weak" one carries as_of, station and pos (degrees from its slot, east positive), x0 and v0
    (from its own station: degrees and degrees a day), acc, box and own_half (own_known: from its burns), edge_days
    (days from as_of until it leaves our box, or None), rows ({ideal, last_chance, too_late} of slot_forecast.forecast;
    None when weak), ns (slot_forecast.ns_forecast, GEO only) and orbit_type.

    `classes` is analysis/burn_classes.classify's table; `history` the assessed constellation's.
    """
    out = {"name": name, "status": "ok"}
    slot = burn_context.designated_longitude(name)
    sat = history[history["satellite"] == name]
    if slot is None or sat.empty:
        return {**out, "status": "no_slot"}
    epoch, pos, drift = burn_context.position_records(history, name)
    found = np.isfinite(pos)
    epoch, pos, drift = epoch[found], pos[found], drift[found]
    if len(epoch) < N.FIT_MIN_RECORDS:
        return {**out, "status": "no_data"}
    as_of = pd.Timestamp(epoch[-1])
    out["as_of"] = as_of
    if (pd.Timestamp(now).tz_localize(None) - as_of).days > N.STALE_ORBIT_DAYS:
        return {**out, "status": "stale"}

    mine = classes[classes["satellite"] == name] if len(classes) else classes
    east_west = mine[mine["kind"] == EAST_WEST] if len(mine) else mine
    t = (epoch - epoch[-1]) / 86400e9                     # days before the newest element set
    use = t >= -N.FIT_DAYS
    if len(east_west):
        out["last_burn"] = pd.Timestamp(east_west["window_end"].max())
        use &= epoch >= out["last_burn"].value            # after its last burn: before it, the drift was another one
    if use.sum() < N.FIT_MIN_RECORDS or (t[use].max() - t[use].min()) < N.FIT_MIN_SPAN_DAYS:
        return {**out, "status": "settling"}

    relocated = (pd.Timestamp(east_west.loc[east_west["burn_class"] == burn_classes.RELOCATION, "window_end"].max())
                 if len(east_west) and (east_west["burn_class"] == burn_classes.RELOCATION).any() else None)
    kept = (np.isfinite(drift) & (np.abs(drift) < S.RELOCATION_MIN_DRIFT)
            & (t >= -N.STATION_DAYS) & ((epoch >= relocated.value) if relocated is not None else True))
    station = float(np.median(pos[kept])) if kept.sum() >= N.STATION_MIN_RECORDS else float(np.median(pos[use]))
    inclination = float(pd.to_numeric(sat.sort_values("EPOCH")["INCLINATION"], errors="coerce").dropna().iloc[-1])
    orbit_type = score_rules.orbit_type(inclination, constellation)
    box = _box(orbit_type)
    acc = longitude_acceleration(slot + station, inclination)
    # position = x0 + v0 t + acc t^2 / 2 about its station; the acc term is taken out, so a straight line fits the rest
    v0, x0 = np.polyfit(t[use], pos[use] - station - 0.5 * acc * t[use] ** 2, 1)

    # parked steadily (90 days, nearly all of it within a box of its station) more than a box from the slot in OUR table:
    # more likely the table is out of date than the satellite off its slot, so it is judged about its own station
    parked = kept & (t >= -N.STATION_DAYS)
    confirm = bool(abs(station) > box and parked.sum() >= N.STATION_MIN_RECORDS
                   and t[parked].min() <= -(N.STATION_DAYS - N.CONFIRM_SPAN_SLACK_DAYS)
                   and np.mean(np.abs(pos[parked] - station) < box) >= N.CONFIRM_SHARE_NEAR)
    out.update(confirm=confirm, slot=float(slot), station_lon=float((slot + station) % 360))
    weak = abs(acc) < S.LON_ACCEL_MIN
    routine = (east_west[(east_west["burn_class"] == burn_classes.ROUTINE_EW)
                         & (pd.to_datetime(east_west["when"]) > as_of - pd.Timedelta(days=365))]
               if len(east_west) else east_west)
    own_known = len(routine) >= N.MIN_ROUTINE_BURNS and not weak
    half = (own_box_half_width(float(np.median(np.abs(routine["delta_a_km"]))) * abs(DRIFT_PER_KM), acc)
            if own_known else N.OWN_BOX_FALLBACK_SHARE * box)
    out.update(status="weak" if weak else "ok", station=station, pos=float(x0) if confirm else station + float(x0),
               x0=float(x0), v0=float(v0),
               acc=float(acc), box=box, own_half=half, own_known=own_known, orbit_type=orbit_type,
               inclination=inclination,
               edge_days=time_to_edge(float(x0) if confirm else float(x0) + station, float(v0), 0.0 if weak else acc, box))
    out["rows"] = None if weak else {r["kind"]: r for r in forecast(
        float(x0), float(v0), acc, half, box, as_of.to_pydatetime(), dashboard_center=0.0 if confirm else -station)}
    if orbit_type == "GEO":
        target = burn_classes.inclination_target(name, orbit_type)
        if np.isfinite(target):
            out["ns"] = ns_forecast(inclination, target, tolerance, NS_GROWTH_DEG_PER_YEAR, as_of.to_pydatetime())
            out["tolerance"], out["target"] = tolerance, float(target)
    return out


@lru_cache(maxsize=1)
def _budgets():
    try:
        with open(BUDGETS, newline="", encoding="utf-8") as file:
            return {row["satellite"]: row for row in csv.DictReader(file)}
    except OSError:
        return {}


def fuel_forecast(name, history, classes, now):
    """{rate, years (low, high) or None, from_budget} for one satellite, or None when too little history for a rate.

    The yearly rate is the delta-v of its station-keeping burns (not relocations, end of life or artefacts) in the last
    year over the days seen. The band takes a typical design life (registry/bus_budgets.csv when it names one) and
    assumes today's rate since launch for what is used: a guess, said so wherever it is shown.
    """
    sat = history[history["satellite"] == name].sort_values("EPOCH")
    if sat.empty or not len(classes):
        return None
    end = pd.Timestamp(sat["EPOCH"].iloc[-1])
    since = max(end - pd.Timedelta(days=365), pd.Timestamp(sat["EPOCH"].iloc[0]))
    days = (end - since).days
    if days < N.FUEL_MIN_DAYS:
        return None
    mine = classes[(classes["satellite"] == name) & (pd.to_datetime(classes["when"]) > since)]
    mine = mine[~mine["burn_class"].isin([burn_classes.RELOCATION, burn_classes.DISPOSAL, burn_classes.ARTEFACT])]
    burns = [({"type": "ew", "delta_a_km": float(b.delta_a_km)} if b.kind == EAST_WEST else
              {"type": "ns", "delta_i_deg": float(b.delta_i_deg)}) for b in mine.itertuples()
             if np.isfinite(b.delta_a_km if b.kind == EAST_WEST else b.delta_i_deg)]
    rate = annual_rate(burns, days)
    out = {"rate": rate, "years": None, "from_budget": False}
    launched = pd.to_datetime(sat["LAUNCH_DATE"], errors="coerce").dropna()
    if not len(launched) or rate <= 0:
        return out
    used = rate * (end - launched.iloc[0]).days / 365.25
    budget = _budgets().get(name) or {}
    try:
        if budget.get("budget_m_s"):
            left = (float(budget["budget_m_s"]) - used) / rate
            return {**out, "years": (max(left, 0.0), max(left, 0.0)), "from_budget": True}
        life = float(budget.get("design_life_years") or N.DESIGN_LIFE_YEARS)
    except ValueError:
        life = N.DESIGN_LIFE_YEARS
    low, high, _ = remaining_band(life, used, rate)
    return {**out, "years": (low, high)}


# ---- saying it ---------------------------------------------------------------------------------------------------

def _day(when):
    when = pd.Timestamp(when)
    return f"{when.day} {when:%b}"


def _range(centre, now):
    """'30 Nov – 3 Dec', or '30 Nov – 3 Dec' shortened to '28–30 Nov', centred on `centre` (a datetime)."""
    now = pd.Timestamp(now).tz_localize(None)
    centre = max(pd.Timestamp(centre), now)
    ahead = (centre - now).total_seconds() / 86400
    spread = pd.Timedelta(days=max(N.DATE_SPREAD_MIN_DAYS, round(N.DATE_SPREAD_SHARE * ahead)))
    first, last = max(centre - spread, now), centre + spread
    if first.date() == last.date():
        return _day(first)
    return f"{first.day}–{last.day} {last:%b}" if (first.month, first.year) == (last.month, last.year) \
        else f"{_day(first)} – {_day(last)}"


def _in_days(when, now):
    """Whole days from `now` to `when`, not below zero."""
    return max(0, round((pd.Timestamp(when) - pd.Timestamp(now).tz_localize(None)).total_seconds() / 86400))


def _side(degrees):
    return "east" if degrees > 0 else "west"


def _row_days(f, kind, now):
    row = (f.get("rows") or {}).get(kind)
    return None if not row or row["delta_lambda_dot_deg_per_day"] is None else _in_days(row["date"], now)


def _edge_days(f, now):
    """Days from now until it leaves our box, if not corrected (None: not on this path)."""
    if f.get("edge_days") is None:
        return None
    return max(0, round(f["edge_days"] - (pd.Timestamp(now).tz_localize(None) - f["as_of"]).total_seconds() / 86400))


def _confirm_words(f):
    """For a satellite kept steadily off the slot in our table: where it is kept and what the table says ('' otherwise)."""
    if not f.get("confirm"):
        return ""
    return (f"{f['name']} is kept at {f['station_lon']:.1f}° E, {abs(f['station']):.1f}° {_side(f['station'])} of the "
            f"{f['slot']:g}° E in our slot table; the table may be out of date (to confirm).")


def satellite_line(f, now):
    """(text, tone, as_of) for one satellite_forecast. Tones: ok nothing due, accent a burn soon or in the plan,
    warn a last chance or an edge close, idle a slot to confirm or not worked out."""
    name = f["name"]
    status = f["status"]
    as_of = _day(f["as_of"]) if f.get("as_of") is not None else ""
    if status == "no_slot":
        return f"{name} has no listed slot, so no next step is worked out.", "idle", as_of
    if status in ("no_data", "stale"):
        return f"{name}: too little recent orbit data to look ahead.", "idle", as_of
    if status == "settling":
        since = f"{name} manoeuvred on {_day(f['last_burn'])}; its" if f.get("last_burn") is not None else f"{name}:"
        return (f"{since} next step follows once about {N.FIT_MIN_SPAN_DAYS:g} days of orbit data have come in.",
                "accent", as_of)
    box = f"±{f['box']:g}°"
    where = f"{abs(f['pos']):.1f}° {_side(f['pos'])} of {'its station' if f['confirm'] else 'its slot'}"
    to_confirm = _confirm_words(f)
    assumed = "" if f["own_known"] else " Its own deadband is not yet known from its manoeuvres, so 0.8 of ours is assumed."
    edge = _edge_days(f, now)
    if status == "weak":
        text = (f"{name} sits where the longitude acceleration (J₂₂) is weak, so it drifts slowly ({f['v0']:+.3f}° a day); "
                + (f"it reaches the {box} deadband edge in {edge} days uncorrected." if edge is not None
                   else f"it stays inside the {box} deadband on this drift."))
        return text, "warn" if edge is not None and edge <= N.SOON_DAYS else "ok", as_of
    ideal, last = f["rows"]["ideal"], f["rows"]["last_chance"]
    when = _range(ideal["date"], now)
    if ideal["delta_v_m_s"] is None:
        return f"No manoeuvre is due for {name} on its present drift: it stays inside the {box} deadband." + assumed, "ok", as_of
    dv = f"about {ideal['delta_v_m_s']:.2f} m/s"
    if to_confirm:   # judged about its own station: its next burn only, no last chance against a box it is not centred on
        return f"{to_confirm} Its next east-west manoeuvre is expected {when} ({dv})." + assumed, "idle", as_of
    if abs(f["pos"]) > f["box"]:
        back = last["delta_v_m_s"]
        return (f"{name} is {where}, outside the {box} deadband"
                + (f"; a correction of about {back:.2f} m/s turns it back." if back is not None
                   else "; no single manoeuvre brings it back.") + assumed, "warn", as_of)
    ideal_days, last_days = _row_days(f, "ideal", now), _row_days(f, "last_chance", now)
    if edge is not None and last_days is not None and last_days <= N.NEAR_DAYS:
        text = (f"{name} reaches the {box} deadband edge in {edge} days uncorrected. Ideal manoeuvre {when} ({dv}); "
                f"last chance {_day(last['date'])}.")
        tone = "warn" if last_days <= N.SOON_DAYS else "accent"
    elif ideal_days is not None and ideal_days <= N.NEAR_DAYS:
        text = f"{name}'s next east-west manoeuvre is expected {when} ({dv}). Nothing else due in {N.NEAR_DAYS} days."
        tone = "accent" if ideal_days <= N.SOON_DAYS else "ok"
    else:
        text = f"Nothing due for {name} in {N.NEAR_DAYS} days; its next east-west manoeuvre is expected {when} ({dv})."
        tone = "ok"
    return text + assumed, tone, as_of


def tile_line(f, now):
    """A few words for a satellite's tile, or None when nothing is due: (text, tone)."""
    if f["status"] != "ok":
        return None
    if f["confirm"]:
        ideal = _row_days(f, "ideal", now)
        return (f"Next E-W manoeuvre {_range(f['rows']['ideal']['date'], now)}", "accent") if ideal is not None and ideal <= N.SOON_DAYS else None
    if abs(f["pos"]) > f["box"]:
        return "Outside its deadband", "warn"
    edge, last = _edge_days(f, now), _row_days(f, "last_chance", now)
    if edge is not None and last is not None and last <= N.NEAR_DAYS:
        return f"Deadband edge in {edge} d · last chance {_day(f['rows']['last_chance']['date'])}", \
            "warn" if last <= N.SOON_DAYS else "accent"
    ideal = _row_days(f, "ideal", now)
    if ideal is not None and ideal <= N.SOON_DAYS:
        return f"Next E-W manoeuvre {_range(f['rows']['ideal']['date'], now)}", "accent"
    return None


def geometry_line(f, now):
    """What happens to a satellite's place in the layout, from satellite_forecast: '' when nothing is worked out."""
    if f["status"] not in ("ok", "weak"):
        return ""
    if f["confirm"]:
        return _confirm_words(f)
    name, box = f["name"], f"{f['box']:g}°"
    if abs(f["pos"]) > f["box"]:
        return f"{name} is {abs(f['pos']):.1f}° {_side(f['pos'])} of its slot, beyond {box}."
    edge = _edge_days(f, now)
    if edge is None:
        return f"{name} stays within {box} of its slot on its present path."
    last = (f.get("rows") or {}).get("last_chance")
    by = f" by {_day(last['date'])}" if last and last["delta_lambda_dot_deg_per_day"] is not None else ""
    return f"If {name} is not corrected{by}, it moves {box} off its slot, in about {edge} days."


def _list(names, limit=3):
    names = list(names)
    return ", ".join(names[:limit]) + (f" and {len(names) - limit} more" if len(names) > limit else "")


def constellation_line(forecasts, now):
    """(text, tone, as_of) for a constellation's satellites (satellite_forecast dicts, any order)."""
    worked = [f for f in forecasts if f["status"] in ("ok", "weak")]
    if not worked:
        return "No next step is worked out yet: too little recent orbit data.", "idle", ""
    as_of = _day(max(f["as_of"] for f in worked))
    boxes = {f["box"] for f in worked}
    box = f"±{boxes.pop():g}°" if len(boxes) == 1 else "longitude"
    confirm = [f["name"] for f in worked if f["confirm"]]
    out = [f["name"] for f in worked if not f["confirm"] and abs(f["pos"]) > f["box"]]
    free = [f for f in worked if f["name"] not in out and not f["confirm"]]   # judged against our box
    due = [f for f in worked if f["name"] not in out]                          # burns due, a slot to confirm included
    edge = sorted((e, f["name"]) for f in free if (e := _edge_days(f, now)) is not None
                  and ((e <= N.NEAR_DAYS) if f["status"] == "weak" else (_row_days(f, "last_chance", now) or 0) <= N.NEAR_DAYS))
    soon = sorted((d, f["name"]) for f in due if f["status"] == "ok" and (d := _row_days(f, "ideal", now)) is not None
                  and d <= N.NEAR_DAYS)
    parts, tone = [], "ok"
    if out:
        parts.append(f"{_list(out)} {'is' if len(out) == 1 else 'are'} outside the {box} deadband.")
        tone = "warn"
    if edge:
        # chosen by last chance (the edge less the lead), so an edge can fall a little past NEAR_DAYS
        one = len(edge) == 1
        parts.append(f"{len(edge)} of {len(worked)} satellites {'needs' if one else 'need'} an east-west manoeuvre within {N.NEAR_DAYS} days "
                     f"to stay inside the {box} deadband; uncorrected, {'it reaches' if one else 'they reach'} its edge: "
                     + _list(f"{n} in {e} days" for e, n in edge) + ".")
        tone = "warn" if edge[0][0] <= N.SOON_DAYS else "accent" if tone == "ok" else tone
    elif soon:
        parts.append("Next east-west manoeuvres expected: "
                     + _list(f"{n} {_range(f['rows']['ideal']['date'], now)}" for _, n in soon
                             for f in due if f["name"] == n) + f". Nothing reaches the {box} deadband edge within {N.NEAR_DAYS} days.")
        tone = "accent" if soon[0][0] <= N.SOON_DAYS and tone == "ok" else tone
    elif not out:
        later = sorted((f["rows"]["ideal"]["date"], f["name"]) for f in due if f["status"] == "ok" and f["rows"]["ideal"]["delta_v_m_s"] is not None)
        parts.append(f"Nothing due in {N.NEAR_DAYS} days across {reveal_count(len(worked), 'satellite')}."
                     + (f" Next: {later[0][1]} {_range(later[0][0], now)}." if later else ""))
    if confirm:
        parts.append(f"{_list(confirm)}: slot to confirm (kept steadily off the slot in our table).")
    return " ".join(parts), tone, as_of


def reveal_count(n, word):
    """'1 satellite', '8 satellites'."""
    return f"{n} {word}{'' if n == 1 else 's'}"


def meo_line(system, drift, as_of, years_cap=N.MEO_YEARS_CAP):
    """(text, tone, as_of) for a medium-orbit system from analysis/meo_geometry.plane_drift: the plane that reaches
    its node limit first at today's rate. `as_of` is a date or text."""
    soonest = None
    for plane, d in sorted((drift or {}).items()):
        limit, offset, rate = d["offset_limit"], d["offset"], d["rate"]
        if abs(offset) > limit:
            soonest = (0.0, plane, limit)
            break
        if abs(rate) >= N.STEADY_DEG_PER_YEAR and (offset * rate > 0 or abs(offset) < 0.05):
            years = (limit - abs(offset)) / abs(rate)
            if years < years_cap and (soonest is None or years < soonest[0]):
                soonest = (years, plane, limit)
    as_of = _day(as_of)
    if soonest is None:
        return (f"No plane of {system} is moving towards its node limit at today's rates. No action needed.", "ok", as_of)
    years, plane, limit = soonest
    if years == 0.0:
        return f"{system} plane {plane} is past its {limit:g}° node limit; the operator would plan a correction.", "warn", as_of
    when = (f"about {years * 12:.0f} months" if years < 1 else f"about {years:.1f} years" if years < 3
            else f"about {years:.0f} years")
    action = "No action needed." if years >= 1 else "The operator would plan a correction."
    return (f"{system} plane {plane} reaches its {limit:g}° node limit in {when} at today's rate. {action}",
            "ok" if years >= 5 else "accent" if years >= 1 else "warn", as_of)


def expected_burns(forecast_by_satellite, now):
    """[(satellite, 'ideal' or 'last chance', date)] inside the ghost marks' horizon, for the burn timeline."""
    now = pd.Timestamp(now).tz_localize(None)
    out = []
    for name, f in forecast_by_satellite.items():
        if f["status"] != "ok" or abs(f["pos"]) > f["box"]:
            continue
        for kind, label in (("ideal", "ideal"), ("last_chance", "last chance")):
            if kind == "last_chance" and f.get("confirm"):   # no last chance against a deadband it is not centred on
                continue
            row = f["rows"][kind]
            if row["delta_lambda_dot_deg_per_day"] is None:
                continue
            date = max(pd.Timestamp(row["date"]), now)
            if (date - now).days <= N.GHOST_HORIZON_DAYS:
                out.append((name, label, date.to_pydatetime(), row["delta_v_m_s"]))
    return out


def line_html(line, short=False):
    """(text, tone, as_of) as a line on the page, with its standing caveat (short: only "as of <date>", for a card)."""
    text, tone, as_of = line
    tone = tone if tone in ("ok", "accent", "warn", "idle") else "idle"   # a published line's tone is only ever a class name
    caveat = (f"as of {as_of}" if short else f"as of {as_of}, {CAVEAT}") if as_of else "worked out from the latest element sets"
    return f'<div class="nx {tone}"><span>{escape(text)}</span> <span class="small">{escape(caveat)}</span></div>'
