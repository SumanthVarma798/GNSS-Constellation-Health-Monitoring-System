"""Build the satellite registry tables from the IGS satellite metadata file.

    python scripts/build_registry.py                      # download the IGS file
    python scripts/build_registry.py --metadata FILE.snx  # use a local copy

Writes registry/satellites.csv (one row per physical satellite) and
registry/signal_ids.csv (one row per satellite per signal-ID period).
The output has a fixed order and no build date, so `git diff registry/`
is the change report: no difference means nothing changed at the source.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.igs_metadata import OPEN_END, block_rows, read_metadata, sinex_time
from evidence.registry_tables import (CONSTELLATIONS, REGISTRY_DIR, SATELLITE_COLUMNS, SATELLITES,
                                      SIGNAL_ID_COLUMNS, SIGNAL_IDS, constellation_names, write_table)


def build_tables(text):
    """Return (satellites, signal_ids): lists of rows, sorted, without headers."""
    signal_ids = []
    for line in block_rows(text, "PRN"):
        svn, start, end, signal_id, *note = line.split(None, 4)
        signal_ids.append([svn, signal_id, sinex_time(start), sinex_time(end), note[0].strip() if note else ""])
    signal_ids.sort(key=lambda row: (row[0], row[2]))
    signal_id_now = {row[0]: row[1] for row in signal_ids if not row[3]}

    # PLANE is read by column position: the slot column can be blank.
    place_now = {line[1:5]: (line[36:37].strip(), line[38:44].strip())
                 for line in block_rows(text, "PLANE") if line[21:35] == OPEN_END}

    constellations = constellation_names()
    satellites = []
    for line in block_rows(text, "IDENTIFIER"):
        svn, cospar, catalogue_no, block, *note = line.split(None, 4)
        if svn[0] not in constellations:
            # A system we have not seen before is for a person to look at, not to guess.
            raise ValueError(f"{svn}: system letter {svn[0]!r} is not in registry/{CONSTELLATIONS}")
        plane, slot = place_now.get(svn, ("", ""))
        satellites.append([svn, constellations[svn[0]], block, cospar, catalogue_no,
                           signal_id_now.get(svn, ""), plane, slot, note[0].strip() if note else ""])
    satellites.sort()
    return satellites, signal_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--metadata", help="local copy of the IGS file (default: download it)")
    args = parser.parse_args()

    satellites, signal_ids = build_tables(read_metadata(args.metadata))
    if not satellites or not signal_ids:
        sys.exit("No satellites or no signal IDs found: the file layout may have changed. Nothing written.")
    write_table(SATELLITES, SATELLITE_COLUMNS, satellites)
    write_table(SIGNAL_IDS, SIGNAL_ID_COLUMNS, signal_ids)
    print(f"{len(satellites)} satellites, {len(signal_ids)} signal-ID periods written to {REGISTRY_DIR}")


if __name__ == "__main__":
    main()
