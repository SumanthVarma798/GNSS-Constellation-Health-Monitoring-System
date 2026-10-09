"""Build the query store afresh from the archive and the registry.

    python scripts/build_store.py --archive PATH_TO_ARCHIVE_FOLDER
    python scripts/build_store.py --archive FOLDER --out FILE.sqlite3

The store is a SQLite file. It is rebuilt whole every time and can be deleted
at any moment: everything in it comes from the archive and the registry.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.settings import STORE_FILE
from evidence.store import build_store


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="folder holding objects/ and versions.csv")
    parser.add_argument("--out", default=STORE_FILE, help=f"where to write the store (default: {STORE_FILE})")
    args = parser.parse_args()

    store = build_store(args.out, args.archive)
    counts = {table: store.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
              for table in ("constellation", "satellite", "signal_id_period", "source", "document")}
    print(", ".join(f"{count} {table.replace('_', ' ')} rows" for table, count in counts.items()))
    print(f"written to {args.out}")


if __name__ == "__main__":
    main()
