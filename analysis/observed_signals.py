"""Which signals a receiver recorded from each satellite: read from a RINEX 3 observation file's text.

A receiver writes a code range (C) or a carrier phase (L) for a signal only while it tracks that signal, so a
non-empty one means a satellite was sending it, in view of that receiver. Nothing here downloads or decompresses.
"""
from collections import deque
from itertools import islice

from ui.signal_settings import SAMPLE_EVERY, signal_name

FIELD = 16   # each observation: 14 characters of value, then a loss-of-lock flag and a signal-strength flag


def _header_types(lines):
    """{constellation letter: [observation codes]} from the header's "SYS / # / OBS TYPES" lines (read to END OF HEADER)."""
    types, system = {}, None
    for line in lines:
        label = line[60:]
        if "END OF HEADER" in label:
            break
        if "SYS / # / OBS TYPES" in label:
            if line[0] != " ":
                system = line[0]
                types[system] = []
            types[system] += line[7:60].split()
    return types


def _recorded(field):
    try:
        return bool(field.strip()) and float(field) != 0.0   # 0.000 is how some receivers write "lost"
    except ValueError:
        return False


def read_observations(text, every=SAMPLE_EVERY):
    """{satellite signal ID ("G05"): {signal names}} for the satellites with a recorded code range or carrier phase.

    Reads one epoch in `every` (1 reads them all); the others are skipped line by line, unread.
    """
    lines = iter(text.splitlines())
    types = _header_types(lines)
    heard, epoch = {}, 0
    for line in lines:
        if not line.startswith(">"):
            continue
        parts = line[1:].split()
        flag, count = int(parts[6]), int(parts[7])
        block = islice(lines, count)
        if flag > 1 or epoch % every:   # a power failure or other event, or an epoch not sampled: skip its lines
            deque(block, maxlen=0)
            epoch += flag <= 1
            continue
        epoch += 1
        for row in block:
            codes = types.get(row[:1])
            if not codes:
                continue
            for at, code in enumerate(codes):
                if code[0] in "CL" and _recorded(row[3 + FIELD * at:3 + FIELD * at + 14]):
                    heard.setdefault(row[:3], set()).add(signal_name(row[0], code[1:]))
    return heard


def combine(by_station, satellites):
    """One row per (name, signal ID): {"satellite", "signal_id", "signals": {signal name: [stations that heard it]}}.

    by_station: {station name: read_observations' result}. satellites: [(dashboard name, signal ID)]. The
    signals and the stations are sorted, so the same day gives the same file.
    """
    rows = []
    for name, signal_id in satellites:
        signals = {}
        for station in sorted(by_station):
            for signal in by_station[station].get(signal_id, ()):
                signals.setdefault(signal, []).append(station)
        rows.append({"satellite": name, "signal_id": signal_id, "signals": dict(sorted(signals.items()))})
    return rows
