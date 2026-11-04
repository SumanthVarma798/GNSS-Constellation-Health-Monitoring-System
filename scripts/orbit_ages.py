"""Measure how old each tracked satellite's newest orbit record is.

    python scripts/orbit_ages.py --archive FOLDER --outcome FILE
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402
from data import celestrak, spacetrack  # noqa: E402
from evidence.archive import log_run  # noqa: E402
from evidence.settings import ORBIT_AGE_COLUMNS, ORBIT_ALERT_DAYS, ORBIT_STALE_DAYS  # noqa: E402


def _tracked_satellites():
    """[(constellation, dashboard name, NORAD ID)] in dashboard order, skipping satellites with no NORAD ID."""
    rows = []
    for constellation, satellites in [("NavIC", config.NAVIK_SATS), ("QZSS", config.QZSS_SATS), ("BeiDou-3", config.BEIDOU3_SATS)]:
        rows += [(constellation, name, int(norad)) for name, norad in satellites.items() if norad is not None]
    for constellation, satellites in config.MEO_SATS.items():
        rows += [(constellation, name, int(norad)) for name, norad in satellites.items() if norad is not None]
    return rows


def _epoch(text):
    at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _age_days(now, row):
    return (now - _epoch(row["EPOCH"])).total_seconds() / 86400


def _short_reason(error, limit=60):
    text = str(error).replace("\n", " ").strip() or error.__class__.__name__
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _status(age_days):
    if age_days is None:
        return "missing"
    if age_days >= ORBIT_STALE_DAYS:
        return "stale"
    if age_days >= ORBIT_ALERT_DAYS:
        return "alert"
    return "ok"


def _pick_newer(celestrak_row, spacetrack_row):
    """(row, source) from CelesTrak and Space-Track, keeping the newer epoch."""
    if celestrak_row is None and spacetrack_row is None:
        return None, ""
    if celestrak_row is None:
        return spacetrack_row, "Space-Track"
    if spacetrack_row is None:
        return celestrak_row, "CelesTrak"
    if _epoch(spacetrack_row["EPOCH"]) > _epoch(celestrak_row["EPOCH"]):
        return spacetrack_row, "Space-Track"
    return celestrak_row, "CelesTrak"


def _write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, ORBIT_AGE_COLUMNS, lineterminator="\n")
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def _changed_sentence(rows, notes):
    total = len(rows)
    ok = sum(1 for row in rows if row["status"] == "ok")
    recorded = [row for row in rows if row["age_days_value"] is not None]
    if recorded:
        oldest = max(recorded, key=lambda row: row["age_days_value"])
        said = (f"{total} satellites: {ok} under {ORBIT_ALERT_DAYS} days, oldest "
                f"{oldest['age_days_value']:.1f} days ({oldest['satellite']}, {oldest['source']})")
    else:
        said = f"{total} satellites: {ok} under {ORBIT_ALERT_DAYS} days, no orbit records"
    from_spacetrack = sum(1 for row in rows if row["source"] == "Space-Track")
    extras = ([f"{from_spacetrack} from Space-Track"] if from_spacetrack else []) + notes
    for extra in extras:
        joined = f"{said}; {extra}"
        if len(joined) > 200:
            break
        said = joined
    return said if len(said) <= 200 else said[:199] + "…"


def _old_list(rows):
    old = [row for row in rows if row["status"] != "ok"]
    old.sort(key=lambda row: (row["age_days_value"] is None, -(row["age_days_value"] or 0), row["satellite"]))
    out = []
    for row in old:
        out.append(f"{row['satellite']} {row['age_days_value']:.1f} days" if row["age_days_value"] is not None
                   else f"{row['satellite']} missing")
    return out


def run(archive, outcome, now=None, env=None):
    """Write orbit ages to the archive, one line to the run log, and one JSON outcome file."""
    fixed_now = now
    now = fixed_now or datetime.now(timezone.utc)
    env = os.environ if env is None else env
    started = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    notes = []

    satellites = _tracked_satellites()
    norads = sorted({norad for _, _, norad in satellites})
    celestrak_rows = {}
    try:
        celestrak_rows, _ = celestrak.fetch(norads)
    except (requests.RequestException, ValueError, KeyError) as error:
        notes.append(f"CelesTrak failed: {_short_reason(error)}")

    stale_norads = []
    for _, _, norad in satellites:
        row = celestrak_rows.get(norad)
        if row is None or _age_days(now, row) >= ORBIT_ALERT_DAYS:
            stale_norads.append(norad)

    spacetrack_rows = {}
    if stale_norads:
        username, password = env.get("SPACETRACK_USERNAME"), env.get("SPACETRACK_PASSWORD")
        if not username or not password:
            notes.append("Space-Track: no login set")
        else:
            try:
                spacetrack_rows = spacetrack.fetch(username, password, sorted(set(stale_norads)))
            except spacetrack.LoginRefused:
                notes.append("Space-Track: login refused")
            except spacetrack.Busy:
                notes.append("Space-Track: busy, not retried")
            except spacetrack.SpaceTrackError:
                notes.append("Space-Track failed")

    checked = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    day = now.strftime("%Y-%m-%d")
    rows = []
    for constellation, satellite, norad in satellites:
        chosen, source = _pick_newer(celestrak_rows.get(norad), spacetrack_rows.get(norad))
        age = _age_days(now, chosen) if chosen else None
        rows.append({
            "day": day,
            "checked": checked,
            "constellation": constellation,
            "satellite": satellite,
            "norad": str(norad),
            "epoch": chosen["EPOCH"] if chosen else "",
            "source": source,
            "age_days": f"{age:.1f}" if age is not None else "",
            "status": _status(age),
            "age_days_value": age,
        })

    _write_rows(Path(archive) / "runs" / "orbit-age-by-satellite.csv", [{k: row[k] for k in ORBIT_AGE_COLUMNS} for row in rows])
    changed = _changed_sentence(rows, notes)
    ended = (fixed_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_run(archive, "orbit-ages", "orbit ages", started, ended, "success", changed)

    result = {"all_fresh": all(row["status"] == "ok" for row in rows), "line": changed, "old": _old_list(rows)}
    out_path = Path(outcome)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="the archive folder")
    parser.add_argument("--outcome", required=True, help="where to write the JSON outcome")
    args = parser.parse_args()
    run(args.archive, args.outcome)


if __name__ == "__main__":
    main()
