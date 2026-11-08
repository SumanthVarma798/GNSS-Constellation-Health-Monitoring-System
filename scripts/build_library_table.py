"""Build registry/library_counts.csv and registry/library_matching.csv: how many navigation satellites each system
has launched, lost at launch, lost early in orbit, retired and still operating, as the General Catalog of
Artificial Space Objects (GCAT) states them. Read by the dashboard's Library page.

    python scripts/build_library_table.py --archive FOLDER      # newest archived copies (the weekly registry job)
    python scripts/build_library_table.py --objects satcat.tsv --payloads psatcat.tsv --failed ftocat.tsv   # local copies

Like the other registry tables, the output has a fixed order and no build date (GCAT's own update date is a column),
so `git diff registry/` shows exactly what the catalogue changed. The archive job fetches all three GCAT files daily
(the "catalogues" group in evidence/sources.py).
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
from evidence.sources import GCAT_FAILED_LAUNCHES_URL, GCAT_OBJECTS_URL, GCAT_PAYLOADS_URL
from build_catalogue_table import archived_copy


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", help="archive folder: build from its newest copies of the three GCAT files")
    for name in ("objects", "payloads", "failed"):
        parser.add_argument(f"--{name}", help=f"local copy of the {name} catalogue file")
    args = parser.parse_args()
    if args.archive:
        args.objects, args.payloads, args.failed = (archived_copy(args.archive, address)[0] for address in
                                                    (GCAT_OBJECTS_URL, GCAT_PAYLOADS_URL, GCAT_FAILED_LAUNCHES_URL))
    if not (args.objects and args.payloads and args.failed):
        parser.error("give --archive, or all of --objects, --payloads and --failed")

    counts, matching = library_tables(read_table(REGISTRY_SATELLITES_FILE),
                                      *(Path(path).read_text(encoding="utf-8") for path in (args.objects, args.payloads, args.failed)))
    if not any(row[2] for row in counts):
        sys.exit("No navigation satellite was found in the catalogue: its layout may have changed. Nothing written.")
    write_table(LIBRARY_COUNTS_FILE, LIBRARY_COUNTS_COLUMNS, counts)
    write_table(LIBRARY_MATCHING_FILE, LIBRARY_MATCHING_COLUMNS, matching)
    print(f"{sum(row[2] for row in counts)} satellites counted; written to registry/{LIBRARY_COUNTS_FILE} and registry/{LIBRARY_MATCHING_FILE}")


if __name__ == "__main__":
    main()
