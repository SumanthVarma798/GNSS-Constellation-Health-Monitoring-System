"""Build the satellite registry tables from the IGS satellite metadata file.

    python scripts/build_registry.py                      # download the IGS file
    python scripts/build_registry.py --metadata FILE.snx  # use a local copy

Writes registry/satellites.csv (one row per physical satellite) and
registry/signal_ids.csv (one row per satellite per signal-ID period).
The output has a fixed order and no build date, so `git diff registry/`
is the change report: no difference means nothing changed at the source.
"""
import argparse
import csv
import datetime
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_satellite_ids import IGS_URL, OPEN_END, _rows

REGISTRY = Path(__file__).resolve().parent.parent / "registry"
# First letter of the SVN. An unknown letter stops the build on purpose:
# a new system in the file is something a person should look at.
CONSTELLATIONS = {"G": "GPS", "R": "GLONASS", "E": "Galileo", "C": "BeiDou", "J": "QZSS", "I": "NavIC"}
SATELLITE_COLUMNS = ["svn", "constellation", "block", "cospar_id", "catalogue_no",
                     "signal_id_now", "plane", "slot", "note"]
SIGNAL_ID_COLUMNS = ["svn", "signal_id", "valid_from", "valid_to", "note"]


def sinex_time(stamp):
    """'2026:090:46920' -> '2026-03-31T13:02:00Z'; the open-ended marker -> ''."""
    if stamp == OPEN_END:
        return ""
    year, day, seconds = map(int, stamp.split(":"))
    moment = datetime.datetime(year, 1, 1) + datetime.timedelta(days=day - 1, seconds=seconds)
    return moment.isoformat() + "Z"


def build_tables(text):
    """Return (satellites, signal_ids): lists of rows, sorted, without headers."""
    signal_ids = []
    for line in _rows(text, "PRN"):
        svn, start, end, prn, *note = line.split(None, 4)
        signal_ids.append([svn, prn, sinex_time(start), sinex_time(end), note[0].strip() if note else ""])
    signal_ids.sort(key=lambda row: (row[0], row[2]))
    signal_id_now = {row[0]: row[1] for row in signal_ids if not row[3]}

    # PLANE is read by column position: the slot column can be blank.
    place_now = {line[1:5]: (line[36:37].strip(), line[38:44].strip())
                 for line in _rows(text, "PLANE") if line[21:35] == OPEN_END}

    satellites = []
    for line in _rows(text, "IDENTIFIER"):
        svn, cospar, norad, block, *note = line.split(None, 4)
        plane, slot = place_now.get(svn, ("", ""))
        satellites.append([svn, CONSTELLATIONS[svn[0]], block, cospar, norad,
                           signal_id_now.get(svn, ""), plane, slot, note[0].strip() if note else ""])
    satellites.sort()
    return satellites, signal_ids


def write_table(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--metadata", help="local copy of the IGS file (default: download it)")
    args = parser.parse_args()

    if args.metadata:
        text = Path(args.metadata).read_text()
    else:
        response = requests.get(IGS_URL, timeout=60)
        response.raise_for_status()
        text = response.text
    satellites, signal_ids = build_tables(text)
    if not satellites or not signal_ids:
        sys.exit("No satellites or no signal IDs found: the file layout may have changed. Nothing written.")
    REGISTRY.mkdir(exist_ok=True)
    write_table(REGISTRY / "satellites.csv", SATELLITE_COLUMNS, satellites)
    write_table(REGISTRY / "signal_ids.csv", SIGNAL_ID_COLUMNS, signal_ids)
    print(f"{len(satellites)} satellites, {len(signal_ids)} signal-ID periods written to {REGISTRY}")


if __name__ == "__main__":
    main()
