"""The health of one medium Earth orbit (MEO) system: GPS, GLONASS or Galileo.

The same shape of result as analysis/bundled_run.assess_constellation, so the pages read both alike.
The orbits are the CelesTrak rows held (data/celestrak.py) on top of any bundled history file
(data/<system>_gp_history.json, written by scripts/update_bundled_data.py from Space-Track; there is
none yet). Health comes from each satellite's newest elements (analysis/meo_geometry.py);
manoeuvres are looked for in whatever history there is, with the detector the other systems use.

Nothing here reads the clock: the caller passes `now`.
"""
import pandas as pd

from analysis.bundled_run import _burns, load_bundled_gp_as_dataframes
from analysis.meo_geometry import assess
from config.config import DEFAULT_PARAMS, MEO_SATS
from data.tle_cache import get_gp_history_metadata
from evidence.registry_tables import dashboard_registry_rows

STALE_DAYS = 7          # elements this much older than the newest are named in a warning
PART_COLUMNS = {"plane": "_plane_score", "spacing": "_spacing_score", "inclination": "_inc_score",
                "height": "_height_score", "eccentricity": "_ecc_score"}


def history_words(history, bundled):
    """How much orbit history there is, in one plain line."""
    where = "bundled history and CelesTrak" if bundled else "CelesTrak since this server started, no bundled history"
    per_satellite = history.groupby("satellite")["EPOCH"]
    if per_satellite.size().max() < 2:
        return f"Orbit history: only the newest element set of each satellite ({where})."
    days = (per_satellite.max() - per_satellite.min()).max().total_seconds() / 86400
    span = f"{days:.0f} days" if days >= 2 else f"{days * 24:.0f} hours"
    return f"Orbit history: {span}, up to {per_satellite.size().max()} element sets a satellite ({where})."


def assess_meo(constellation, now, window_days=90, params=None, fresh=None):
    """Health of every tracked satellite of a MEO system. `now` is timezone-aware; window_days is accepted
    for the same call as assess_constellation and not used: health is from the newest elements.

    Returns {'health', 'set_aside', 'history', 'burns', 'data_time', 'warnings', 'rows', 'history_note'};
    'rows' are analysis.meo_geometry's, in tracked order. Raises ValueError with no orbit data at all.
    """
    if now.tzinfo is None:
        raise ValueError("`now` must be timezone-aware")
    sats = MEO_SATS[constellation]
    key = constellation.lower()
    frames = load_bundled_gp_as_dataframes(key, sats, fresh)
    if not frames:
        raise ValueError(f"No orbit data for {constellation} yet: it comes with the next CelesTrak refresh")
    history = pd.concat(frames, ignore_index=True, sort=False)
    newest = history.sort_values("EPOCH").groupby("satellite").tail(1).set_index("satellite")
    elements = {name: {**newest.loc[name].to_dict(), "EPOCH": newest.loc[name, "EPOCH"].to_pydatetime()}
                for name in sats if name in newest.index}
    rows = assess(constellation, elements, dashboard_registry_rows(constellation))

    health = pd.DataFrame([{"Satellite": row["name"], "Type": f"MEO · plane {row['plane']}",
                            "Signal ID": row["signal_id"], "Overall Score": round(row["score"], 1),
                            "Health Status": row["status"],
                            **{PART_COLUMNS[m]: round(s, 1) for m, s in row["parts"].items()}} for row in rows])
    latest = max(element["EPOCH"] for element in elements.values())
    stale = [name for name, element in elements.items() if (latest - element["EPOCH"]).days > STALE_DAYS]
    disagree = [f"{row['name']} (orbit plane {row['plane']}, registry plane {row['registry_plane']})"
                for row in rows if not row["plane_agrees"]]
    warnings = ([f"Orbit data over {STALE_DAYS} days older than the rest: {', '.join(stale)}"] if stale else []) + \
               ([f"Plane differs from the registry: {', '.join(disagree)}"] if disagree else [])
    bundled = get_gp_history_metadata(key)
    return {
        "health": health,
        "set_aside": [],
        "history": history,
        "burns": _burns(history, {**DEFAULT_PARAMS, **(params or {})}),
        "data_time": bundled["timestamp"] if bundled["available"] else latest.isoformat(),
        "warnings": warnings,
        "rows": rows,
        "history_note": history_words(history, bundled["available"]),
    }
