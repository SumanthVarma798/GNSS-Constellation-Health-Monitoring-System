"""
The health assessment of one constellation from the bundled data, without app.py's screen.

app.py does this work inside its Streamlit script (load the bundled history, set aside
graveyard satellites, analyse the 365-day pattern, assess health, then work out each
satellite's longitude against its slot and rescore). Importing app.py would run that
script, so the steps are here as plain functions. The dashboard calls
`assess_constellation` and gets the same numbers app.py shows; `tests/test_bundled_run.py`
checks that against the scores recorded from app.py.

Nothing here reads the clock: the caller passes `now`.
"""

from collections import Counter
from datetime import timedelta, timezone

import numpy as np
import pandas as pd
from skyfield.api import EarthSatellite, load, wgs84

from analysis.dop_calculations import parse_tle_data
from analysis.drift_analysis import calculate_longitudinal_drift
from analysis.health_assessment import assess_satellite_health_with_drift
from analysis.maneuver_detection import detect_navik_maneuvers
from config.config import (
    BEIDOU3_SATS, BEIDOU3_SERVICE_REQUIREMENTS, DEFAULT_PARAMS, GRAVEYARD_ORBIT_MIN,
    NAVIK_SATS, QZSS_SATS, QZSS_SERVICE_REQUIREMENTS, R_EARTH,
)
from data.tle_cache import get_gp_history_metadata, load_bundled_gp_history, load_bundled_tles

# constellation -> (satellites it tracks, service requirements), as app.py picks them.
_CONSTELLATIONS = {
    "NavIC": (NAVIK_SATS, None),
    "QZSS": (QZSS_SATS, QZSS_SERVICE_REQUIREMENTS),
    "BeiDou-3": (BEIDOU3_SATS, BEIDOU3_SERVICE_REQUIREMENTS),
}

_ts = load.timescale()


def load_bundled_gp_as_dataframes(constellation_key: str, sat_dict: dict, fresh=None) -> list:
    """Copy of app.py's load_bundled_gp_as_dataframes (same behaviour); app.py cannot be
    imported without running its Streamlit script. `fresh` ({norad: [rows]}, from data.celestrak)
    is added to each satellite's bundled records, leaving out epochs already there."""
    bundled = load_bundled_gp_history(constellation_key)
    if not bundled or not bundled.get('satellites'):
        return []

    all_dfs = []
    sat_data = bundled.get('satellites', {})
    fresh = fresh or {}

    for sat_name, norad_id in sat_dict.items():
        records = sat_data.get(sat_name, [])
        held = {record.get('EPOCH') for record in records}
        records = records + list({row['EPOCH']: row for row in fresh.get(norad_id, []) if row['EPOCH'] not in held}.values())
        if not records:
            continue

        df = pd.DataFrame(records)

        # Standardize column names
        rename_map = {
            'epoch': 'EPOCH',
            'inclination': 'INCLINATION',
            'semimajor_axis': 'SEMIMAJOR_AXIS',
            'mean_motion': 'MEAN_MOTION',
            'ra_of_asc_node': 'RA_OF_ASC_NODE',
            'arg_of_pericenter': 'ARG_OF_PERICENTER',
            'mean_anomaly': 'MEAN_ANOMALY',
            'eccentricity': 'ECCENTRICITY',
            'tle_line1': 'TLE_LINE1',
            'tle_line2': 'TLE_LINE2',
            'object_name': 'OBJECT_NAME'
        }
        for old_col, new_col in rename_map.items():
            if old_col in df.columns and new_col not in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)

        df['EPOCH'] = pd.to_datetime(df['EPOCH'])
        df['INCLINATION'] = df['INCLINATION'].astype(float)

        # Calculate longitudinal drift
        if 'MEAN_MOTION' in df.columns:
            df['MEAN_MOTION'] = df['MEAN_MOTION'].astype(float)
            df['LonDrift_deg_per_day'] = calculate_longitudinal_drift(df['MEAN_MOTION'])

        # Classify satellite type
        df['type'] = df['INCLINATION'].apply(
            lambda x: 'GEO' if (x > 0.0 and x < 10.0) else ('IGSO' if x >= 10 else 'Unclassified')
        )

        mean_incl = df['INCLINATION'].mean()
        df['mean_inclination'] = mean_incl
        df['maintained'] = df['INCLINATION'].apply(lambda x: abs(x - mean_incl) <= 0.3)
        df['satellite'] = sat_name

        # Calculate altitude
        if 'SEMIMAJOR_AXIS' in df.columns:
            df['SEMIMAJOR_AXIS'] = df['SEMIMAJOR_AXIS'].astype(float)
            df['altitude_km'] = df['SEMIMAJOR_AXIS'] - R_EARTH
        else:
            df['SEMIMAJOR_AXIS'] = np.nan
            df['altitude_km'] = np.nan

        df = df.sort_values('EPOCH').reset_index(drop=True)
        all_dfs.append(df)

    return all_dfs


def get_graveyard_satellites(df_all) -> set:
    """Copy of app.py's get_graveyard_satellites (same behaviour); same reason."""
    graveyard_sats = set()

    for sat_name in df_all['satellite'].unique():
        sat_df = df_all[df_all['satellite'] == sat_name]

        # Check if satellite has altitude data
        if 'altitude_km' not in sat_df.columns or sat_df['altitude_km'].isna().all():
            continue

        # Get current altitude (most recent data point)
        current_altitude = sat_df['altitude_km'].iloc[-1]

        # Check for graveyard orbit
        if current_altitude >= GRAVEYARD_ORBIT_MIN:
            graveyard_sats.add(sat_name)

    return graveyard_sats


def _detect(sat_df, p):
    return detect_navik_maneuvers(
        sat_df,
        sma_col='SEMIMAJOR_AXIS',
        inc_col='INCLINATION',
        z_thresh=p["z_threshold"],
        sma_abs_thresh_km=p["sma_threshold"],
        inc_abs_thresh_deg=p["inc_threshold"],
        persist_window=int(p["persist_window"]),
    )


def _longitude_score(abs_dev, sat_type):
    if sat_type == 'GEO':
        if abs_dev <= 0.5:
            return 100
        if abs_dev <= 1.0:
            return 90 - ((abs_dev - 0.5) / 0.5) * 20
        if abs_dev <= 2.0:
            return 70 - ((abs_dev - 1.0) / 1.0) * 30
        return max(0, 40 - ((abs_dev - 2.0) / 2.0) * 40)
    # IGSO
    if abs_dev <= 5.0:
        return 100
    if abs_dev <= 10.0:
        return 90 - ((abs_dev - 5.0) / 5.0) * 30
    return max(0, 60 - ((abs_dev - 10.0) / 10.0) * 60)


def _longitude_remark(abs_dev, deviation, sat_type, designated_lon):
    where = f"({deviation:+.2f}° from {designated_lon}°)"
    if sat_type == 'GEO':
        if abs_dev <= 0.5:
            return f"✅ Excellent longitude slot position {where}"
        if abs_dev <= 1.0:
            return f"✓ Good longitude position {where}"
        return f"⚠️ Longitude deviation from designated slot {where}"
    if abs_dev <= 5.0:
        return f"✅ Within central longitude tolerance {where}"
    return f"⚠️ Central longitude deviation {where}"


def _add_longitude(health_df, satellites_dop, now, warnings):
    """app.py's longitude step: 24-hour mean longitude per satellite, its deviation from
    the designated slot, the longitude score, and the overall score recalculated with it."""
    # "N/A" strings to NaN so float values can be assigned (as app.py does).
    for _col in ['Current Mean Lon (°)', 'Lon Slot Deviation (°)', 'Lon Deviation Score']:
        if _col in health_df.columns:
            health_df[_col] = pd.to_numeric(health_df[_col], errors='coerce')

    for idx, row in health_df.iterrows():
        sat_name = row['Satellite']
        designated_lon = row['Designated Lon (°)']
        if sat_name not in satellites_dop or designated_lon == "N/A":
            continue
        try:
            sat_obj = satellites_dop[sat_name]

            # 96 steps of 15 minutes over the 24 hours before `now`
            longitudes = []
            for i in range(96):
                dt = now - timedelta(hours=24) + timedelta(minutes=i * 15)
                geocentric = sat_obj.at(_ts.from_datetime(dt))
                longitudes.append(wgs84.subpoint(geocentric).longitude.degrees)

            # circular mean longitude
            lons_rad = np.deg2rad(longitudes)
            current_mean_lon = np.rad2deg(np.arctan2(np.mean(np.sin(lons_rad)), np.mean(np.cos(lons_rad))))

            diff = current_mean_lon - float(designated_lon)
            while diff > 180:
                diff -= 360
            while diff < -180:
                diff += 360
            longitude_deviation = diff

            health_df.at[idx, 'Current Mean Lon (°)'] = round(current_mean_lon, 2)
            health_df.at[idx, 'Lon Slot Deviation (°)'] = round(longitude_deviation, 2)

            abs_dev = abs(longitude_deviation)
            sat_type = row['Type']
            lon_score = _longitude_score(abs_dev, sat_type)
            health_df.at[idx, 'Lon Deviation Score'] = round(lon_score, 1)

            # Overall Score over all five parts. The health module's score used weights summing
            # to 0.85 (longitude left out); longitude (0.15) is folded back in here.
            _weights = {'inc': 0.30, 'maintenance': 0.25, 'uniformity': 0.10,
                        'drift': 0.20, 'longitude': 0.15}
            _components = {}
            for _k, _col in [('inc', '_inc_score'), ('maintenance', '_maintenance_score'),
                             ('uniformity', '_uniformity_score'), ('drift', '_drift_score')]:
                _v = row.get(_col)
                if _v is not None and not (isinstance(_v, float) and np.isnan(_v)):
                    _components[_k] = float(_v)

            _original_score = float(row['Overall Score'])
            if len(_components) >= 1:
                _components['longitude'] = float(lon_score)
                _total_w = sum(_weights[k] for k in _components)
                _new_score = sum(_components[k] * _weights[k] for k in _components) / _total_w
            else:
                _new_score = _original_score * 0.85 + float(lon_score) * 0.15

            health_df.at[idx, 'Overall Score'] = round(_new_score, 1)
            if _new_score >= 80:
                _hs, _sc = "Healthy", "🟢"
            elif _new_score >= 60:
                _hs, _sc = "Fair", "🟡"
            elif _new_score >= 40:
                _hs, _sc = "Degraded", "🟠"
            else:
                _hs, _sc = "Critical", "🔴"
            health_df.at[idx, 'Health Status'] = f"{_sc} {_hs}"

            new_remark = _longitude_remark(abs_dev, longitude_deviation, sat_type, designated_lon)
            current_remarks = health_df.at[idx, 'Remarks']
            health_df.at[idx, 'Remarks'] = f"{current_remarks} | {new_remark}" if current_remarks else new_remark
        except Exception as e:
            # app.py shows this on screen and carries on; here it is returned in `warnings`.
            warnings.append(f"Longitude calculation failed for {sat_name}: {e}")


def _burns(df_all_full, p):
    """One row per detected manoeuvre in each satellite's whole bundled history."""
    rows = []
    for sat_name in df_all_full['satellite'].unique():
        sat_df = df_all_full[df_all_full['satellite'] == sat_name].sort_values('EPOCH').reset_index(drop=True)
        det = _detect(sat_df, p)
        for i in det.index[det['MANEUVER']]:
            if i == 0:
                continue
            for flag, kind in (('EW_MANEUVER', 'east-west'), ('NS_MANEUVER', 'north-south')):
                if det.at[i, flag]:
                    rows.append({
                        'satellite': sat_name,
                        'kind': kind,
                        'window_start': det.at[i - 1, 'EPOCH'],
                        'window_end': det.at[i, 'EPOCH'],
                        'd_sma_km': float(det.at[i, 'dSMA']),
                        'd_inc_deg': float(det.at[i, 'dINC']),
                    })
    return pd.DataFrame(rows, columns=['satellite', 'kind', 'window_start', 'window_end',
                                       'd_sma_km', 'd_inc_deg'])


def assess_constellation(constellation, now, window_days=90, params=None, fresh=None):
    """Health of every tracked satellite of `constellation` as app.py shows it.

    `now` is a timezone-aware datetime. `params` overrides DEFAULT_PARAMS (app.py's
    sidebar defaults; QZSS's inclination tolerance defaults to 4.0 as in the sidebar).
    Dates follow app.py's, taken in UTC: the display range is the `window_days` days up to
    today, and pattern analysis uses the 365 days up to `now`.

    `fresh` ({norad: [history rows]}, from data.celestrak) is merged onto the bundled history, and
    the newest of those rows places the satellite for the longitude step.

    Returns {'health', 'set_aside', 'history', 'burns', 'data_time', 'warnings'}.
    Raises ValueError for an unknown constellation, no bundled data, or no records in the window.
    """
    if constellation not in _CONSTELLATIONS:
        raise ValueError(f"Unknown constellation {constellation!r}; expected one of {list(_CONSTELLATIONS)}")
    if now.tzinfo is None:
        raise ValueError("`now` must be timezone-aware")
    sat_dict, service_reqs = _CONSTELLATIONS[constellation]
    p = {**DEFAULT_PARAMS, **(params or {})}
    if constellation == "QZSS" and "inclination_tolerance" not in (params or {}):
        p["inclination_tolerance"] = 4.0
    warnings = []

    key = constellation.lower().replace('-', '')
    gp_meta = get_gp_history_metadata(key)
    if not gp_meta['available']:
        raise ValueError(f"No bundled data for {constellation}")
    all_dfs = load_bundled_gp_as_dataframes(key, sat_dict, fresh)
    if not all_dfs:
        raise ValueError(f"Bundled data for {constellation} could not be loaded")
    df_all_full = pd.concat(all_dfs, ignore_index=True, sort=False)

    # Display range and satellites set aside (graveyard orbit), as app.py does
    now = now.astimezone(timezone.utc)
    end_date = now.date()
    start_date = end_date - timedelta(days=window_days)
    user_start = pd.Timestamp(start_date.strftime("%Y-%m-%d"))
    user_end = pd.Timestamp(end_date.strftime("%Y-%m-%d"))
    df_all = df_all_full[(df_all_full['EPOCH'] >= user_start) &
                         (df_all_full['EPOCH'] <= user_end + pd.Timedelta(days=1))]
    if df_all.empty:
        raise ValueError(f"No bundled {constellation} data between {start_date} and {end_date}")
    graveyard_sats = get_graveyard_satellites(df_all)
    df_all = df_all[~df_all['satellite'].isin(graveyard_sats)]

    # Pattern analysis over the 365 days up to `now`, from the unfiltered bundled history
    pattern_start_ts = pd.Timestamp((now - timedelta(days=365)).strftime("%Y-%m-%d"))
    pattern_end_ts = pd.Timestamp(now.strftime("%Y-%m-%d"))
    pattern_data = {}
    for sat_name in [s for s, n in sat_dict.items() if n is not None]:
        try:
            sat_df = df_all_full[df_all_full['satellite'] == sat_name].copy()
            if sat_df.empty:
                pattern_data[sat_name] = None
                continue
            pattern_df = sat_df[(sat_df['EPOCH'] >= pattern_start_ts) &
                                (sat_df['EPOCH'] <= pattern_end_ts + pd.Timedelta(days=1))].copy()
            if pattern_df.empty:
                pattern_df = sat_df.copy()  # all available bundled data for this satellite
            pattern_df = pattern_df.sort_values('EPOCH').reset_index(drop=True)
            detected = _detect(pattern_df, p)
            pattern_data[sat_name] = {'df': pattern_df, 'maneuvers': detected[detected['MANEUVER']].copy()}
        except Exception:
            pattern_data[sat_name] = None

    # Days when at least 75% of the expected satellites have observations count as "deployed"
    date_counter = Counter()
    for pdata in pattern_data.values():
        if pdata is None:
            continue
        try:
            for d in pd.to_datetime(pdata['df']['EPOCH']).dt.date.unique().tolist():
                date_counter[d] += 1
        except Exception:
            continue
    min_required = max(1, int(0.75 * len(sat_dict)))
    deployed_dates = {d for d, cnt in date_counter.items() if cnt >= min_required} or None

    health_assessments = []
    for sat_name in sorted(df_all['satellite'].unique()):
        sat_df = df_all[df_all['satellite'] == sat_name].copy()

        if pattern_data.get(sat_name) is not None:
            health_sat_df = pattern_data[sat_name]['df'].copy()
            health_maneuvers = pattern_data[sat_name]['maneuvers'].copy()
        else:
            health_sat_df = sat_df.copy()
            detected = _detect(sat_df, p)
            health_maneuvers = detected[detected['MANEUVER']].copy()

        # Leave out days when the constellation was not fully deployed
        if deployed_dates is not None and not health_sat_df.empty:
            try:
                health_sat_df['EPOCH_date'] = pd.to_datetime(health_sat_df['EPOCH']).dt.date
                filtered_df = health_sat_df[health_sat_df['EPOCH_date'].isin(deployed_dates)].drop(columns=['EPOCH_date'])
                if not filtered_df.empty:
                    health_sat_df = filtered_df.reset_index(drop=True)
                if not health_maneuvers.empty:
                    health_maneuvers['EPOCH_date'] = pd.to_datetime(health_maneuvers['EPOCH']).dt.date
                    fm = health_maneuvers[health_maneuvers['EPOCH_date'].isin(deployed_dates)].drop(columns=['EPOCH_date'])
                    if not fm.empty:
                        health_maneuvers = fm.reset_index(drop=True)
            except Exception:
                pass  # as app.py: fall back to the unfiltered data

        health_assessments.append(assess_satellite_health_with_drift(
            sat_name, health_sat_df, health_maneuvers,
            p["inclination_tolerance"], p["min_maneuvers_per_month"],
            p["max_maneuvers_per_month"], p["maneuver_uniformity_threshold"],
            p["drift_tolerance_gso"], service_requirements=service_reqs,
            constellation_name=constellation,
            pattern_maneuvers=health_maneuvers,
            pattern_df=health_sat_df,
        ))
    health_df = pd.DataFrame(health_assessments)

    bundled_tles = load_bundled_tles(key)
    satellites_dop = parse_tle_data(bundled_tles['tle_data'], sat_dict) if bundled_tles.get('tle_data') else {}
    for sat_name, norad_id in sat_dict.items():
        if (fresh or {}).get(norad_id):
            newest = max(fresh[norad_id], key=lambda row: row['EPOCH'])
            satellites_dop[sat_name] = EarthSatellite(newest['TLE_LINE1'], newest['TLE_LINE2'], sat_name, _ts)
    if satellites_dop:
        _add_longitude(health_df, satellites_dop, now, warnings)
    elif bundled_tles.get('tle_data'):
        warnings.append("Bundled TLEs hold none of the tracked satellites; longitude not calculated")
    else:
        warnings.append("No bundled TLEs; longitude not calculated")

    return {
        'health': health_df,
        'set_aside': sorted(graveyard_sats),
        'history': df_all_full,
        'burns': _burns(df_all_full, p),
        'data_time': gp_meta['timestamp'],
        'warnings': warnings,
    }
