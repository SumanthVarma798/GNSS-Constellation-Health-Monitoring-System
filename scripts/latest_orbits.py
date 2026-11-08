"""Write the archive's newest copy of CelesTrak's GNSS group as latest_gnss.json, for the public dashboard.

    python scripts/latest_orbits.py --archive FOLDER --out orbit-data/latest_gnss.json [--outside-group]

CelesTrak refuses the hosted dashboard but still answers GitHub, so the archive job publishes its copy on branch
orbit-data, and the dashboard reads only this copy, never CelesTrak itself (data/celestrak.py, COPY_URL). Writes
nothing and exits non-zero when the archive holds no usable copy.

With --outside-group the copy also holds, under "outside_group", the orbit record of each tracked satellite the group
leaves out, asked for one by one as data.celestrak.fetch() does (QZS-7 was tracked before the group listed it).
Those rows are kept apart so "listed by CelesTrak" still means the group.
"""
import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.archive import object_path, read_versions
from evidence.registry_tables import read_table
from evidence.settings import REGISTRY_DASHBOARD_SATELLITES_FILE, REGISTRY_SATELLITES_FILE, REGISTRY_SIGHTINGS_FILE
from evidence.sources import CELESTRAK_GNSS_URL

GP_URL = CELESTRAK_GNSS_URL.split("?")[0]
TIMEOUT = 30   # seconds per request


def latest_copy(archive):
    """{'fetched_at', 'source', 'rows'} from the newest kept copy of the GNSS group. Raises ValueError without one."""
    kept = [row for row in read_versions(archive) if row["address"] == CELESTRAK_GNSS_URL and row["sha256"]]
    if not kept:
        raise ValueError(f"the archive holds no copy of {CELESTRAK_GNSS_URL}")
    newest = kept[-1]
    rows = json.loads(object_path(archive, newest["sha256"]).read_bytes())
    if not isinstance(rows, list) or not rows or not all(
            isinstance(row, dict) and "NORAD_CAT_ID" in row and "EPOCH" in row for row in rows):
        raise ValueError(f"the copy fetched {newest['fetched_at']} is not a list of orbit records")
    return {"fetched_at": newest["fetched_at"], "source": CELESTRAK_GNSS_URL, "rows": rows}


def tracked_catalogue_numbers():
    """The catalogue number of every satellite the dashboard tracks that the registry lists."""
    registry = {row["svn"]: row for row in read_table(REGISTRY_SATELLITES_FILE) + read_table(REGISTRY_SIGHTINGS_FILE)}
    return {int(registry[row["svn"]]["catalogue_no"])
            for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE) if row["svn"] in registry}


def outside_group(rows, tracked, get=requests.get):
    """Orbit records of the tracked satellites `rows` (the group) leaves out, one request each. One CelesTrak has
    nothing for, or a failed request, is named on stderr and left out: the group's copy is still worth writing."""
    listed = {int(row["NORAD_CAT_ID"]) for row in rows}
    found = []
    for norad in sorted(set(tracked) - listed):
        try:
            reply = get(GP_URL, params={"CATNR": norad, "FORMAT": "json"}, timeout=TIMEOUT)
            reply.raise_for_status()
            got = reply.json()   # CelesTrak answers "No GP data found" as text: a ValueError here
        except (requests.RequestException, ValueError) as problem:
            print(f"No orbit record for catalogue number {norad}: {problem}", file=sys.stderr)
            continue
        found += [row for row in got if isinstance(row, dict) and "NORAD_CAT_ID" in row and "EPOCH" in row] \
            if isinstance(got, list) else []
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="folder holding objects/ and versions.csv")
    parser.add_argument("--out", required=True, help="the JSON file to write")
    parser.add_argument("--outside-group", action="store_true",
                        help="also ask CelesTrak for each tracked satellite the group leaves out (the archive job does)")
    args = parser.parse_args()
    try:
        copy = latest_copy(args.archive)
    except (OSError, ValueError) as problem:
        sys.exit(f"No orbit copy written: {problem}")
    if args.outside_group:
        copy["outside_group"] = outside_group(copy["rows"], tracked_catalogue_numbers())
    Path(args.out).write_text(json.dumps(copy, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(copy['rows'])} orbit records fetched {copy['fetched_at']} to {args.out}")


if __name__ == "__main__":
    main()
