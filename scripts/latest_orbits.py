"""Write the archive's newest copy of CelesTrak's GNSS group as latest_gnss.json, for the public dashboard.

    python scripts/latest_orbits.py --archive FOLDER --out orbit-data/latest_gnss.json

CelesTrak refuses the hosted dashboard but still answers GitHub, so the archive job publishes its copy on branch
orbit-data and the dashboard reads it when its own fetch fails (data/celestrak.py, COPY_URL). Writes nothing and
exits non-zero when the archive holds no usable copy.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.archive import object_path, read_versions
from evidence.sources import CELESTRAK_GNSS_URL


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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="folder holding objects/ and versions.csv")
    parser.add_argument("--out", required=True, help="the JSON file to write")
    args = parser.parse_args()
    try:
        copy = latest_copy(args.archive)
    except (OSError, ValueError) as problem:
        sys.exit(f"No orbit copy written: {problem}")
    Path(args.out).write_text(json.dumps(copy, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(copy['rows'])} orbit records fetched {copy['fetched_at']} to {args.out}")


if __name__ == "__main__":
    main()
