"""Count Home's rows once, on GitHub, so the dashboard does not count them on every cold start.

    python scripts/home_snapshot.py --out orbit-data/home_snapshot.json

The dashboard sleeps when no one visits (Render Free), and waking it loses every count it kept, so the first visitor
waited for every constellation to be assessed. This runs the dashboard's own counting (ui.data.refresh, then
ui.system_summary.summary per part, at the default time range and limits) and writes it as one small file beside the
orbit copy on branch orbit-data. Home reads that file while it is fresh (ui/home_data.py, published) and counts live
otherwise. Space-Track is asked when SPACETRACK_USERNAME and SPACETRACK_PASSWORD are set, as on the server.
"""
import argparse
import json
import logging
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

warnings.filterwarnings("ignore")      # Streamlit warns that it runs without a page; the counting does not need one
logging.disable(logging.WARNING)

from ui import data, next_step_data, systems, system_summary, time_range  # noqa: E402


def _plain(value):
    """numpy numbers as plain ones, for json."""
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"{type(value).__name__} is not JSON")


def snapshot(now):
    """{"made", "window_days", "parts": {part: summary}, "next_steps": {part: [text, tone, as_of]},
    "next_figures": {part: html}} for every part of every constellation that could be counted."""
    data.refresh()
    gap = data.orbit_gap()
    parts, steps, figures = {}, {}, {}
    for names in systems.SYSTEMS.values():
        for name in names:
            try:
                result = data.load(name, time_range.DEFAULT_DAYS)
                parts[name] = system_summary.summary(name, result, gap)
            except Exception as error:   # one that fails is counted live by Home, as before; the others are kept
                print(f"{name} not counted: {type(error).__name__}: {error}", file=sys.stderr)
                continue
            try:   # "what should happen next": left out when it fails, and Home works it out itself
                steps[name] = list(next_step_data.constellation_line(name, result))
                figures[name] = next_step_data.outlook_html(name, result, compact=True)
            except Exception as error:
                print(f"{name} next step not worked out: {type(error).__name__}: {error}", file=sys.stderr)
    return {"made": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "window_days": time_range.DEFAULT_DAYS, "parts": parts,
            "next_steps": steps, "next_figures": figures}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    payload = snapshot(datetime.now(timezone.utc))
    if not payload["parts"]:
        sys.exit("No constellation could be counted; nothing written.")
    args.out.write_text(json.dumps(payload, default=_plain, separators=(",", ":")))
    print(f"Counted {len(payload['parts'])} parts at {payload['made']}.")


if __name__ == "__main__":
    main()
