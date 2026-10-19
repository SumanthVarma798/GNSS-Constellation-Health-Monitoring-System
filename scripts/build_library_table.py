"""Build registry/library_counts.csv and registry/library_matching.csv: how many navigation satellites each system
has launched, lost at launch, lost early in orbit, retired and still operating, as the General Catalog of
Artificial Space Objects (GCAT) states them. Read by the dashboard's Library page.

Download the three GCAT files once into a folder OUTSIDE the repository, then build from them:

    curl -O https://planet4589.org/space/gcat/tsv/cat/satcat.tsv     # and psatcat.tsv, ftocat.tsv
    python scripts/build_library_table.py --objects satcat.tsv --payloads psatcat.tsv --failed ftocat.tsv

Like the other registry tables, the output has a fixed order and no build date (GCAT's own update date is a column),
so `git diff registry/` shows exactly what the catalogue changed. The ftocat.tsv address is
GCAT_FAILED_LAUNCHES_URL in evidence/sources.py; it is not fetched on a schedule.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.library import library_tables
from evidence.library_settings import (LIBRARY_COUNTS_COLUMNS, LIBRARY_COUNTS_FILE, LIBRARY_MATCHING_COLUMNS,
                                       LIBRARY_MATCHING_FILE)
from evidence.registry_tables import read_table, write_table
from evidence.settings import REGISTRY_SATELLITES_FILE


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("objects", "payloads", "failed"):
        parser.add_argument(f"--{name}", required=True, help=f"local copy of the {name} catalogue file")
    args = parser.parse_args()

    counts, matching = library_tables(read_table(REGISTRY_SATELLITES_FILE),
                                      *(Path(path).read_text(encoding="utf-8") for path in (args.objects, args.payloads, args.failed)))
    if not any(row[2] for row in counts):
        sys.exit("No navigation satellite was found in the catalogue: its layout may have changed. Nothing written.")
    write_table(LIBRARY_COUNTS_FILE, LIBRARY_COUNTS_COLUMNS, counts)
    write_table(LIBRARY_MATCHING_FILE, LIBRARY_MATCHING_COLUMNS, matching)
    print(f"{sum(row[2] for row in counts)} satellites counted; written to registry/{LIBRARY_COUNTS_FILE} and registry/{LIBRARY_MATCHING_FILE}")


if __name__ == "__main__":
    main()
