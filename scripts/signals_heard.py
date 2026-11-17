"""Which signals each tracked satellite was heard sending on one UTC day, from IGS receivers' observation files.

Reads the day's 30-second RINEX 3 observation file of each station in ui/signal_settings.py from BKG's IGS data
centre (no login), notes every signal a receiver recorded from each satellite (analysis/observed_signals.py), and
writes one JSON file the dashboard reads. Run by the daily RINEX check, after the broadcast-orbit step.

    python scripts/signals_heard.py --day 2026-11-16 --json signals_heard.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import hatanaka
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.observed_signals import combine, read_observations  # noqa: E402
from scripts.orbit_record_gap import newest_day, tracked  # noqa: E402
from ui.signal_settings import FILES, FOLDER, SAMPLE_EVERY, STATIONS  # noqa: E402

SAVED = Path.home() / ".cache" / "gnss-health-monitor" / "observations"   # one copy per station and day, outside the repository


def observation_text(code, day):
    """(the station's file for `day` as RINEX text, its download size in bytes): the saved copy, or BKG's (then saved)."""
    url = FILES.format(year=day.year, doy=day.timetuple().tm_yday, code=code)
    saved = SAVED / url.rsplit("/", 1)[1]
    if not saved.exists():
        reply = requests.get(url, timeout=120)
        reply.raise_for_status()
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(reply.content)
    raw = saved.read_bytes()
    return hatanaka.decompress(raw).decode("ascii", "replace"), len(raw)


def measure(day, now=None):
    """The JSON payload for `day`. A station whose file cannot be read is listed with why and left out of the counts;
    it raises only when no station can be read."""
    stations, by_station = [], {}
    for code, (short, place, _) in STATIONS.items():
        entry = {"code": code, "name": short, "place": place}
        try:
            text, size = observation_text(code, day)
            by_station[short] = read_observations(text)
            entry |= {"read": True, "megabytes": round(size / 1e6, 1)}
        except (requests.RequestException, hatanaka.HatanakaException, OSError, ValueError) as error:
            entry |= {"read": False, "problem": str(error)[:120]}
        stations.append(entry)
    if not by_station:
        raise RuntimeError("no station's observation file could be read: " + "; ".join(s["problem"] for s in stations))
    satellites = [(name, signal_id) for _, name, _, signal_id in tracked(day)]
    return {"day": day.isoformat(), "checked": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "folder": FOLDER.format(year=day.year, doy=day.timetuple().tm_yday), "sample_every": SAMPLE_EVERY,
            "stations": stations, "satellites": combine(by_station, satellites)}


def summary(payload):
    """One line: how many satellites were heard, and how many stations were read."""
    rows = payload["satellites"]
    read = sum(s["read"] for s in payload["stations"])
    return f"{sum(bool(r['signals']) for r in rows)} of {len(rows)} satellites heard by {read} of {len(payload['stations'])} stations"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--day", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
                        help="the UTC day; default: the newest day BKG has the IGS broadcast file for")
    parser.add_argument("--json", required=True, help="where to write the JSON payload")
    arguments = parser.parse_args()
    payload = measure(arguments.day or newest_day(datetime.now(timezone.utc).date()))
    Path(arguments.json).write_text(json.dumps(payload), encoding="utf-8")
    print(summary(payload))
