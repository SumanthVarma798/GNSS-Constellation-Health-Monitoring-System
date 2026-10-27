#!/usr/bin/env python3
"""Check that bundled constellation data can be loaded and assessed."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.bundled_run import assess_constellation  # noqa: E402

CONSTELLATIONS = ("NavIC", "QZSS", "BeiDou-3")
BLOCKED_WARNING_TEXT = ("no bundled tles", "none of the tracked satellites")


def _blocked_warning(warning):
    text = warning.lower()
    return any(part in text for part in BLOCKED_WARNING_TEXT)


def _check_constellation(label, now):
    try:
        result = assess_constellation(label, now)
    except Exception as error:
        raise RuntimeError(f"{label}: assess_constellation failed: {error}") from error

    health = result.get("health")
    if health is None or health.empty:
        raise RuntimeError(f"{label}: health assessment returned no satellites")

    warnings = result.get("warnings") or []
    blocked = [warning for warning in warnings if _blocked_warning(warning)]
    if blocked:
        raise RuntimeError(f"{label}: {'; '.join(blocked)}")

    print(
        f"{label}: satellites assessed={len(health)}, "
        f"set aside={len(result.get('set_aside', []))}, "
        f"data_time={result.get('data_time')}"
    )


def main():
    now = datetime.now(timezone.utc)
    for label in CONSTELLATIONS:
        try:
            _check_constellation(label, now)
        except RuntimeError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
