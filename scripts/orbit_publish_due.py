"""Say whether the orbit files on branch orbit-data are due, so a run that finds nothing new costs one short job.

    python scripts/orbit_publish_due.py --archive FOLDER >> "$GITHUB_OUTPUT"

Prints orbits_changed=true|false: the archive's newest GNSS copy differs from the one published as latest_gnss.json
(its element sets are compared, not the time it was fetched). And home_due=true|false: the copy changed, or Home's
counts (home_snapshot.json) are older than HOME_COUNT_EVERY. Anything unreadable on the published side says true.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.settings import HOME_COUNT_EVERY, ORBIT_DATA_URL  # noqa: E402
from latest_orbits import latest_copy  # noqa: E402


def fingerprint(rows):
    """One hash of a list of element sets, the same whichever way it was written out."""
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def published(name, get=requests.get):
    """The published JSON file `name`, or None when it is missing or unreadable."""
    try:
        reply = get(ORBIT_DATA_URL + name, timeout=30)
        reply.raise_for_status()
        return reply.json()
    except (requests.RequestException, ValueError):
        return None


def due(archive, now, get=requests.get):
    """(orbits_changed, home_due)."""
    try:
        newest = fingerprint(latest_copy(archive)["rows"])
    except (OSError, ValueError):
        return False, False   # no usable copy: nothing to publish (publish-orbits would write nothing either)
    copy = published("latest_gnss.json", get)
    changed = not (isinstance(copy, dict) and isinstance(copy.get("rows"), list) and fingerprint(copy["rows"]) == newest)
    snapshot = published("home_snapshot.json", get)
    try:
        made = datetime.fromisoformat(snapshot["made"].replace("Z", "+00:00"))
        old = now - made >= HOME_COUNT_EVERY
    except (TypeError, KeyError, ValueError, AttributeError):
        old = True
    return changed, changed or old


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--archive", required=True)
    changed, home = due(parser.parse_args().archive, datetime.now(timezone.utc))
    print(f"orbits_changed={str(changed).lower()}\nhome_due={str(home).lower()}")


if __name__ == "__main__":
    main()
