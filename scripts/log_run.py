"""Add one line to a run log in the archive, for a job whose result only its job file knows.

    python scripts/log_run.py --archive FOLDER --log registry-update --job "registry update" \
        --started 2026-10-19T05:13:12Z --result success --changed "nothing"

The line ends now. The archive job writes its own line (scripts/archive_sources.py).
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.archive import log_run


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", required=True, help="the archive folder")
    parser.add_argument("--log", required=True, help="which run log: runs/<log>.csv")
    parser.add_argument("--job", required=True)
    parser.add_argument("--started", required=True, help="UTC, as 2026-10-19T05:13:12Z")
    parser.add_argument("--result", required=True)
    parser.add_argument("--changed", required=True)
    args = parser.parse_args()
    ended = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_run(args.archive, args.log, args.job, args.started, ended, args.result, args.changed)


if __name__ == "__main__":
    main()
