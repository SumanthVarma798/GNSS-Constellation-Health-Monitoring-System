"""Cross-check satellite identities against the IGS satellite metadata file.

The IGS file maps each physical satellite (SVN) to its catalogue number
(NORAD ID) and to every signal ID (PRN) it has broadcast, with dates.

    python scripts/check_satellite_ids.py             # config/config.py vs IGS
    python scripts/check_satellite_ids.py --signals   # + BeiDou: CelesTrak names
                                                      #   and galmon live signals
    python scripts/check_satellite_ids.py --metadata igs_satellite_metadata.snx

Read-only: prints a Markdown report, changes nothing.
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

IGS_URL = "https://files.igs.org/pub/station/general/igs_satellite_metadata.snx"
CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=beidou&FORMAT=json"
GALMON_URL = "https://galmon.eu/svs.json"
OPEN_END = "0000:000:00000"
# Satellite blocks the GEO/IGSO dashboard is meant to cover.
TRACKED_BLOCKS = ("IRS-", "QZS-", "BDS-3G", "BDS-3I")


def sinex_date(stamp):
    """'2026:111:43200' -> '2026-04-21'; the open-ended marker -> None."""
    if stamp == OPEN_END:
        return None
    year, day, _ = stamp.split(":")
    return (datetime.date(int(year), 1, 1) + datetime.timedelta(int(day) - 1)).isoformat()


def _rows(text, block):
    body = re.search(rf"^\+SATELLITE/{block}\s*$(.*?)^-SATELLITE/{block}", text, re.S | re.M)
    return [line for line in body.group(1).splitlines() if re.match(r" [A-Z]\d{3} ", line)]


def parse_metadata(text):
    """Return (by_norad, prn_history, slot) from the IGS metadata text."""
    by_norad, prn_history, slot = {}, {}, {}
    for line in _rows(text, "IDENTIFIER"):
        svn, cospar, norad, block, *comment = line.split(None, 4)
        by_norad[int(norad)] = {"svn": svn, "cospar": cospar, "block": block,
                                "comment": comment[0].strip() if comment else ""}
    for line in _rows(text, "PRN"):
        svn, start, end, prn = line.split()[:4]
        prn_history.setdefault(svn, []).append((sinex_date(start), sinex_date(end), prn))
    for line in _rows(text, "PLANE"):
        parts = line.split()
        if parts[2] == OPEN_END and len(parts) > 4 and not parts[4].startswith("["):
            slot[parts[0]] = parts[4]
    return by_norad, prn_history, slot


def current_prn(history):
    return next((prn for _, end, prn in history if end is None), None)


def config_report(by_norad, prn_history, slot):
    from config.config import BEIDOU3_SATS, NAVIK_SATS, QZSS_SATS

    tracked = {**NAVIK_SATS, **QZSS_SATS, **BEIDOU3_SATS}
    print("## Tracked satellites against the IGS file\n")
    print("| Dashboard name | Catalogue no. | SVN | Signal ID now | Earlier signal IDs | Slot |")
    print("|---|---|---|---|---|---|")
    for name, norad in tracked.items():
        sat = by_norad.get(norad)
        if not sat:
            print(f"| {name} | {norad} | **not in IGS file** | | | |")
            continue
        history = prn_history.get(sat["svn"], [])
        earlier = "; ".join(f"{prn} until {end}" for _, end, prn in history if end)
        print(f"| {name} | {norad} | {sat['svn']} | {current_prn(history) or 'none'} "
              f"| {earlier or '-'} | {slot.get(sat['svn'], '-')} |")

    print("\n## In the IGS file, same satellite families, not tracked\n")
    for norad, sat in by_norad.items():
        if sat["block"].startswith(TRACKED_BLOCKS) and norad not in tracked.values():
            prn = current_prn(prn_history.get(sat["svn"], []))
            print(f"- {sat['svn']} (catalogue no. {norad}, signal ID {prn or 'none'}): {sat['comment']}")


def signals_report(by_norad, prn_history):
    """BeiDou only: which physical satellite is behind each signal ID right now?"""
    import numpy as np
    from skyfield.api import EarthSatellite, load
    from skyfield.framelib import itrs

    ts = load.timescale()
    catalogue = requests.get(CELESTRAK_URL, timeout=60).json()
    signals = requests.get(GALMON_URL, timeout=60).json()
    now = ts.now()
    # Position of every catalogued BeiDou object, in the Earth-fixed frame galmon uses.
    objects = [(sat["OBJECT_NAME"], int(sat["NORAD_CAT_ID"]),
                EarthSatellite.from_omm(ts, sat).at(now).frame_xyz(itrs).km) for sat in catalogue]

    print("\n## BeiDou: who is broadcasting each signal ID right now\n")
    print("Each signal heard by galmon in the last hour is matched to the nearest "
          "catalogued object by position.\n")
    print("| Signal ID heard | Nearest object (CelesTrak name) | Miss (km) | Next nearest (km) "
          "| IGS agrees | Name agrees |")
    print("|---|---|---|---|---|---|")
    heard, igs_ok, name_ok = set(), 0, 0
    for key, sv in sorted(signals.items()):
        prn = key.split("@")[0]
        if not prn.startswith("C") or prn in heard or sv.get("x") is None or sv.get("last-seen-s", 1e9) > 3600:
            continue
        heard.add(prn)
        broadcast = np.array([sv["x"], sv["y"], sv["z"]]) / 1000.0
        ranked = sorted((float(np.linalg.norm(broadcast - xyz)), name, norad) for name, norad, xyz in objects)
        (miss, name, norad), runner_up = ranked[0], ranked[1][0]
        sat = by_norad.get(norad)
        igs = bool(sat) and current_prn(prn_history.get(sat["svn"], [])) == prn
        label = f"({prn})" in name
        igs_ok += igs
        name_ok += label
        print(f"| {prn} | {name} | {miss:.0f} | {runner_up:.0f} | {'yes' if igs else '**no**'} "
              f"| {'yes' if label else '**no**'} |")
    print(f"\n{len(heard)} signal IDs heard. IGS file agrees on {igs_ok}; "
          f"the signal ID in CelesTrak's object name agrees on {name_ok}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--metadata", help="local copy of the IGS file (default: download it)")
    parser.add_argument("--signals", action="store_true", help="also check BeiDou against CelesTrak and galmon")
    args = parser.parse_args()

    if args.metadata:
        text = Path(args.metadata).read_text()
    else:
        response = requests.get(IGS_URL, timeout=60)
        response.raise_for_status()
        text = response.text
    print(f"# Satellite identity check, {datetime.date.today().isoformat()}\n")
    print(f"Reference: {text.splitlines()[0].strip()}\n")
    meta = parse_metadata(text)
    config_report(*meta)
    if args.signals:
        signals_report(meta[0], meta[1])


if __name__ == "__main__":
    main()
