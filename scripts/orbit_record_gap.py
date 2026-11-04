"""How far off each tracked satellite's orbit record is, measured against its own broadcast orbit,
and fresh orbit records fitted to the broadcast positions when the newest regular record is stale.

For one UTC day, every 15 minutes: where the orbit record nearest in time (TLE, rolled with SGP4)
puts each dashboard satellite, against where the satellite's broadcast orbit puts it (good to
metres). It can also fit an SGP4 record to those broadcast positions (GLONASS uses the positions
its own records give), so a day with no fresh regular record still leaves a usable one behind.
Prints a Markdown report. Read-only apart from the files it is told to write.

    python scripts/orbit_record_gap.py                   # the newest day BKG has, from its copy of the IGS file
    python scripts/orbit_record_gap.py --day 2026-10-17 --file BRDC00IGS_R_20262900000_01D_MN.rnx
    python scripts/orbit_record_gap.py --fitted fitted.json --previous-fitted-dir archive/orbits/fitted

Orbit records: the bundled history, plus CelesTrak's newest through data.celestrak (which keeps to
CelesTrak's 2 hours and its saved copy). Issue 77.
"""
import argparse
import csv
import gzip
import json
import math
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests
from skyfield.api import EarthSatellite, load
from skyfield.framelib import itrs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.broadcast_orbit import (FIT, nearest, position, read_glonass, read_navigation,  # noqa: E402
                                      read_status, seconds_from_toe, system_time, time_corrections)
from analysis.orbit_fit import fit as fit_orbit  # noqa: E402
from data import celestrak  # noqa: E402
from evidence.settings import ORBIT_FIT_MAX_KM, ORBIT_FIT_MIN_SAMPLES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# The IGS merged navigation file for one day, as BKG serves it without a login (checked 19 Oct 2026).
BKG = "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/{year}/{doy:03d}/BRDC00IGS_R_{year}{doy:03d}0000_01D_MN.rnx.gz"
SAVED = Path.home() / ".cache" / "gnss-health-monitor" / "broadcast"   # one copy per day, outside the repository
STEP = timedelta(minutes=15)
HISTORIES = ("navic", "qzss", "beidou3")
_ts = load.timescale()


def _iso_utc(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def navigation_text(day, file=None):
    """The day's navigation file as text: the given file, the saved copy, or BKG's (then saved)."""
    if file:
        return Path(file).read_text()
    doy = day.timetuple().tm_yday
    saved = SAVED / f"BRDC00IGS_R_{day.year}{doy:03d}0000_01D_MN.rnx.gz"
    if not saved.exists():
        reply = requests.get(BKG.format(year=day.year, doy=doy), timeout=60)
        reply.raise_for_status()
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(reply.content)
    return gzip.decompress(saved.read_bytes()).decode("ascii", "replace")


def newest_day(today):
    """The newest day BKG has the IGS file for: yesterday, else up to three days back. The file for a day appeared
    about 25 hours after the day ended (checked 26 Oct 2026: 24 Oct's at 00:56 on 26 Oct), so yesterday's is often
    not there yet. When none answers, yesterday, so the download says why."""
    for back in (1, 2, 3):
        day = today - timedelta(days=back)
        doy = day.timetuple().tm_yday
        if (SAVED / f"BRDC00IGS_R_{day.year}{doy:03d}0000_01D_MN.rnx.gz").exists():
            return day
        try:
            if requests.head(BKG.format(year=day.year, doy=doy), timeout=30).status_code == 200:
                return day
        except requests.RequestException:
            continue
    return today - timedelta(days=1)


def leap_seconds(text):
    """GPS time minus UTC, from the file header."""
    line = next(line for line in text.splitlines() if "LEAP SECONDS" in line)
    return int(line[:6])


def tracked(day):
    """[(svn, dashboard name, catalogue number, signal ID that day)] from the registry tables."""
    with open(ROOT / "registry" / "satellites.csv", newline="") as handle:
        catalogue = {row["svn"]: int(row["catalogue_no"]) for row in csv.DictReader(handle)}
    noon = f"{day.isoformat()}T12:00:00Z"
    with open(ROOT / "registry" / "signal_ids.csv", newline="") as handle:
        held = {row["svn"]: row["signal_id"] for row in csv.DictReader(handle)
                if row["valid_from"] <= noon and (not row["valid_to"] or row["valid_to"] > noon)}
    with open(ROOT / "registry" / "dashboard_satellites.csv", newline="") as handle:
        return [(row["svn"], row["dashboard_name"], catalogue[row["svn"]], held.get(row["svn"]))
                for row in csv.DictReader(handle)]


def cospar_ids():
    """{svn: COSPAR launch designator} from the registry."""
    with open(ROOT / "registry" / "satellites.csv", newline="") as handle:
        return {row["svn"]: row["cospar_id"] for row in csv.DictReader(handle)}


def orbit_records(catalogue_numbers, now):
    """{catalogue number: [(epoch, line1, line2), ...] oldest first}: bundled history plus CelesTrak's newest."""
    records = {}
    for name in HISTORIES:
        history = json.loads((ROOT / "data" / f"{name}_gp_history.json").read_text())["satellites"]
        for rows in history.values():
            for row in rows:
                records.setdefault(int(row["NORAD_CAT_ID"]), []).append(row)
    for norad, rows in celestrak.refresh(sorted(catalogue_numbers), now)["rows"].items():
        records.setdefault(norad, []).extend(rows)
    out = {}
    for norad, rows in records.items():
        unique = {row["EPOCH"]: row for row in rows}
        out[norad] = sorted((datetime.fromisoformat(epoch).replace(tzinfo=timezone.utc), row["TLE_LINE1"], row["TLE_LINE2"])
                            for epoch, row in unique.items())
    return out


def broadcast_samples(broadcast, signal_id, leap, day):
    """[(utc, Earth-fixed xyz km)] for one satellite and day, only moments a broadcast record covers."""
    samples = []
    for k in range(int(timedelta(days=1) / STEP)):
        utc = datetime.combine(day, datetime.min.time(), timezone.utc) + k * STEP
        own = system_time(utc.replace(tzinfo=None), signal_id, leap)
        record = nearest(broadcast, own)
        if abs(seconds_from_toe(record, own)) > FIT:
            continue
        samples.append((utc, np.array(position(record, own))))
    return samples


def previous_fitted(path, day):
    """{norad: fitted payload row} from the fitted file for the day before, or {}."""
    if not path:
        return {}
    previous = Path(path) / f"{(day - timedelta(days=1)).isoformat()}.json"
    if not previous.exists():
        return {}
    try:
        payload = json.loads(previous.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for satellite in payload.get("satellites", []):
        if satellite.get("row") is not None and satellite.get("norad") is not None:
            out[int(satellite["norad"])] = satellite
    return out


def compare(broadcast, records, signal_id, leap, day):
    """Per 15 minutes a broadcast record covers: (gap km, along km, cross km, radial km, broadcast longitude, UTC); and the last orbit record used."""
    samples, used = [], None
    if not records:
        return samples, used
    for utc, fixed in broadcast_samples(broadcast, signal_id, leap, day):
        epoch, line1, line2 = min(records, key=lambda record: abs(record[0] - utc))   # nearest in time, either side
        used = epoch
        t = _ts.from_datetime(utc)
        inertial = itrs.rotation_at(t).T @ fixed                       # Earth-fixed -> the frame SGP4's output uses
        at = EarthSatellite(line1, line2, ts=_ts).at(t)
        guess, speed = at.position.km, at.velocity.km_per_s
        radial = guess / np.linalg.norm(guess)
        cross = np.cross(guess, speed) / np.linalg.norm(np.cross(guess, speed))
        along = np.cross(cross, radial)
        gap = inertial - guess                                         # where it is, minus where the record says
        samples.append((float(np.linalg.norm(gap)), float(gap @ along), float(gap @ cross), float(gap @ radial),
                        math.degrees(math.atan2(fixed[1], fixed[0])), utc))
    return samples, used


def glonass_samples(glonass, signal_id, day):
    """[(utc, Earth-fixed xyz km)] for one GLONASS satellite: the positions its own records give on that day."""
    return sorted((utc, np.array(xyz)) for utc, xyz in glonass.get(signal_id, {}).items() if utc.date() == day)


def _fitted_gap(samples, row):
    """The median distance in km between a fitted record (rolled with SGP4) and broadcast positions, or None.
    Only the record's TLE lines are used, so its epoch text never needs reading."""
    try:
        satellite = EarthSatellite(row["TLE_LINE1"], row["TLE_LINE2"], ts=_ts)
    except (KeyError, TypeError, ValueError):
        return None
    gaps = []
    for utc, fixed in samples:
        t = _ts.from_datetime(utc)
        gaps.append(float(np.linalg.norm(itrs.rotation_at(t).T @ fixed - satellite.at(t).position.km)))
    return statistics.median(gaps) if gaps else None


def rows_for_day(day, file=None, now=None, previous_fitted_dir=None):
    """Rows for each tracked satellite, plus the leap-second value, check time and the header's time corrections.

    previous_fitted_dir, when given and holding the previous day's fitted file, adds how far that
    fitted record already is from today's broadcast positions (the proof it stayed good overnight).
    """
    now = now or datetime.now(timezone.utc)
    checked = _iso_utc(now)
    text = navigation_text(day, file)
    leap, broadcast = leap_seconds(text), read_navigation(text)
    statuses = read_status(text)
    glonass = read_glonass(text)
    corrections = time_corrections(text)
    satellites = tracked(day)
    records = orbit_records([norad for _, _, norad, _ in satellites], now)
    fitted = previous_fitted(previous_fitted_dir, day)
    rows = []
    for svn, name, norad, signal_id in satellites:
        row = {"satellite": name, "signal_id": signal_id, "record_epoch": None, "typical_km": None, "largest_km": None,
               "mostly": "", "note": "", "age_days": None, "mean_longitude_deg": None, "fitted_km": None,
               "health": None, "accuracy_m": None, "broadcast_newest": None}
        status = statuses.get(signal_id)
        if status is not None:
            row["health"] = status["health"]
            row["accuracy_m"] = status["accuracy_m"]
            row["broadcast_newest"] = status["newest"].strftime("%Y-%m-%dT%H:%M:%S")
        if signal_id not in statuses:
            row["note"] = "not in the day's broadcast file"
            rows.append(row)
            continue
        previous = fitted.get(norad)
        if previous and isinstance(previous.get("row"), dict):
            positions = (glonass_samples(glonass, signal_id, day) if signal_id[0] == "R"
                         else broadcast_samples(broadcast[signal_id], signal_id, leap, day))
            row["fitted_km"] = _fitted_gap(positions, previous["row"])
        if signal_id[0] == "R":
            row["note"] = "orbit not compared: GLONASS broadcasts position, not elements"
            rows.append(row)
            continue
        samples, used = compare(broadcast[signal_id], records.get(norad, []), signal_id, leap, day)
        if not samples:
            row["note"] = "no orbit record"
            rows.append(row)
            continue
        gaps = [s[0] for s in samples]
        parts = [statistics.mean(abs(s[i]) for s in samples) for i in (1, 2, 3)]
        biggest = max(range(3), key=lambda i: parts[i])
        sign = statistics.mean(s[biggest + 1] for s in samples)
        mostly = [("ahead" if sign > 0 else "behind") + " on its path", "off its orbit plane",
                  "higher" if sign > 0 else "lower"][biggest]
        longitude = math.degrees(math.atan2(statistics.mean(math.sin(math.radians(s[4])) for s in samples),
                                            statistics.mean(math.cos(math.radians(s[4])) for s in samples)))
        age = abs(samples[-1][5] - used).total_seconds() / 86400
        row |= {"record_epoch": _iso_utc(used), "typical_km": statistics.median(gaps), "largest_km": max(gaps), "mostly": mostly,
                "age_days": age, "mean_longitude_deg": longitude}
        rows.append(row)
    return rows, leap, checked, corrections


def markdown_report(day, leap, rows):
    """Markdown report for one day from precomputed satellite rows."""
    lines = [f"# How far off each orbit record is, {day.isoformat()}", "",
             "Gap = distance between where the orbit record nearest in time (rolled to the moment with SGP4) puts the satellite and "
             "where its own broadcast orbit puts it, every 15 minutes over the day (UTC) that a broadcast record covers. Along: + means the satellite "
             "is ahead of where the record says. Broadcast orbits are good to metres; a gap of kilometres is the record's.",
             "", "| Satellite | Signal ID | Record from | Days between record and last sample | Typical gap | Largest gap | Mostly | Mean longitude (broadcast) | Yesterday's fitted record |",
             "|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        satellite, signal = row["satellite"], row["signal_id"] or "none"
        fitted = f"{row['fitted_km']:.1f} km" if isinstance(row.get("fitted_km"), (int, float)) and not isinstance(row.get("fitted_km"), bool) else ""
        if row["note"] == "not in the day's broadcast file":
            lines.append(f"| {satellite} | {signal} | | | | | not in the day's broadcast file | | {fitted} |")
            continue
        if row["note"] == "no orbit record":
            lines.append(f"| {satellite} | {signal} | no orbit record | | | | | | {fitted} |")
            continue
        if row["note"] == "orbit not compared: GLONASS broadcasts position, not elements":
            lines.append(f"| {satellite} | {signal} | | | | | {row['note']} | | {fitted} |")
            continue
        when = datetime.fromisoformat(row["record_epoch"].replace("Z", "+00:00"))
        lines.append(f"| {satellite} | {signal} | {when:%d %b %H:%M} | {row['age_days']:.1f} days | "
                     f"{row['typical_km']:.1f} km | {row['largest_km']:.1f} km | {row['mostly']} | "
                     f"{row['mean_longitude_deg']:.2f}° | {fitted} |")
    lines += ["", f"Broadcast file: IGS merged navigation file for the day, GPS - UTC = {leap} s from its header. "
              "Orbit records: the bundled history plus CelesTrak's newest."]
    return "\n".join(lines)


def summary(rows):
    """One line for run logs from the row model."""
    total = len(rows)
    compared = [row for row in rows if row["typical_km"] is not None and row["largest_km"] is not None]
    if compared:
        typical = statistics.median([row["typical_km"] for row in compared])
        worst = max(compared, key=lambda row: row["largest_km"])
        said = (f"{total} satellites: orbit records off by {typical:.1f} km typical, worst {worst['largest_km']:.1f} km "
                f"({worst['satellite']})")
    else:
        said = f"{total} satellites: no orbit records to compare"
    not_in_broadcast = sum(1 for row in rows if row["note"] == "not in the day's broadcast file")
    if not_in_broadcast:
        said += f"; {not_in_broadcast} not in the broadcast file"
    no_record = sum(1 for row in rows if row["note"] == "no orbit record")
    if no_record:
        said += f"; {no_record} with no orbit record"
    fitted = [row["fitted_km"] for row in rows if isinstance(row.get("fitted_km"), (int, float))
              and not isinstance(row.get("fitted_km"), bool)]
    if fitted:
        said += f"; yesterday's fitted records off by {statistics.median(fitted):.1f} km typical"
    return said


def _row_payload(row):
    keys = ("satellite", "signal_id", "record_epoch", "typical_km", "largest_km", "mostly", "note", "fitted_km")
    payload = {key: row.get(key) for key in keys}
    for key in ("health", "accuracy_m", "broadcast_newest"):
        if key in row:
            payload[key] = row[key]
    return payload


def json_payload(day, checked, rows, leap=None, time_corrections=None):
    """Public JSON payload with the rows needed by the dashboard."""
    payload = {"day": day.isoformat(), "checked": checked,
               "satellites": [_row_payload(row) for row in rows]}
    if leap is not None:
        payload["leap_seconds"] = leap
    if time_corrections is not None:
        payload["time_corrections"] = {code: round(seconds * 1e9, 2)
                                       for code, seconds in time_corrections.items()}
    return payload


def write_json(path, day, checked, rows, leap=None, time_corrections=None):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(json_payload(day, checked, rows, leap, time_corrections)), encoding="utf-8")


def fitted_satellites(day, text, checked):
    """The `satellites` list for the fitted JSON payload, one row per tracked satellite."""
    leap, broadcast = leap_seconds(text), read_navigation(text)
    statuses = read_status(text)
    glonass = read_glonass(text)
    cospar = cospar_ids()
    satellites = []
    for svn, name, norad, signal_id in tracked(day):
        payload = {"satellite": name, "signal_id": signal_id, "norad": norad}
        if signal_id not in statuses:
            payload["note"] = "not in the day's broadcast file"
            satellites.append(payload)
            continue
        if signal_id[0] == "R":
            samples = glonass_samples(glonass, signal_id, day)
        else:
            samples = broadcast_samples(broadcast[signal_id], signal_id, leap, day)
        if len(samples) < ORBIT_FIT_MIN_SAMPLES:
            payload["note"] = "too few broadcast positions"
            satellites.append(payload)
            continue
        fitted = fit_orbit(samples, norad, cospar.get(svn, ""), name)
        if fitted is None:
            payload["note"] = f"did not fit within {ORBIT_FIT_MAX_KM:g} km"
        else:
            row, rms_km = fitted
            payload |= {"fit_km": round(rms_km, 2), "row": row}
        satellites.append(payload)
    return satellites


def fitted_json_payload(day, checked, satellites):
    return {"day": day.isoformat(), "checked": checked, "satellites": satellites}


def write_fitted_json(path, day, checked, satellites):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(fitted_json_payload(day, checked, satellites)), encoding="utf-8")


def fitted_rows_for_day(day, file=None, now=None):
    """Fitted-payload rows for one day; `now` fixes the same check time as the gap run."""
    now = now or datetime.now(timezone.utc)
    text = navigation_text(day, file)
    return fitted_satellites(day, text, _iso_utc(now))


def report(day, file=None, now=None):
    rows, leap, _, _ = rows_for_day(day, file, now)
    return markdown_report(day, leap, rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--day", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
                        help="the UTC day to check; default: the newest day BKG has the IGS file for")
    parser.add_argument("--file", help="a local RINEX 3 navigation file instead of BKG's copy")
    parser.add_argument("--json", help="where to write a JSON payload for this day")
    parser.add_argument("--summary-out", help="where to write one line that summarises the rows")
    parser.add_argument("--fitted", help="where to write the fitted orbit records for this day")
    parser.add_argument("--previous-fitted-dir", help="folder of previous days' fitted JSON, for the one-day-later proof")
    arguments = parser.parse_args()
    day = arguments.day or (arguments.file and (datetime.now(timezone.utc) - timedelta(days=1)).date()) \
        or newest_day(datetime.now(timezone.utc).date())
    rows, leap, checked_at, corrections = rows_for_day(day, arguments.file,
                                                       previous_fitted_dir=arguments.previous_fitted_dir)
    print(markdown_report(day, leap, rows))
    if arguments.json:
        write_json(arguments.json, day, checked_at, rows, leap, corrections)
    if arguments.fitted:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        satellites = fitted_rows_for_day(day, arguments.file, now=checked)
        write_fitted_json(arguments.fitted, day, checked_at, satellites)
    if arguments.summary_out:
        Path(arguments.summary_out).write_text(summary(rows) + "\n", encoding="utf-8")
