"""How steadily each satellite's clock ran over one day, as its own broadcast messages tell it.

Every broadcast record gives the satellite clock's offset from its system's time and how fast that offset is
changing. From one record, the offset at the time of the next can be predicted. How far the next record lands from
that prediction is a step. A clock running steadily, with a model that fits it, steps by a nanosecond or so; a clock
that was reset, switched to its spare or is failing steps by far more.

This reads what the operator broadcasts. It is not a measurement of the clock against a reference: that needs the
IGS's precise clock products, which the dashboard does not read (issue 77). One nanosecond of clock is 0.3 m of range.

Galileo sends two clock models, one per signal pair; only the I/NAV one (E1, E5b) is read, as mixing them shows steps
that are not there. GLONASS records give the offset and the relative frequency on their first line.
"""
import statistics
from datetime import timedelta

from analysis.broadcast_orbit import known, toc, read_navigation

MAX_GAP = timedelta(hours=4)   # a prediction is not asked to hold for longer than this
GALILEO_INAV_CLOCK = 512       # RINEX 3.04 "data sources", bit 9: the clock terms are for E5b and E1
NS = 1e9


def _glonass_terms(text):
    """{signal ID: {toc: (offset s, relative frequency, 0.0)}} from the GLONASS records' first lines."""
    lines = text.splitlines()
    body = lines[next(i for i, line in enumerate(lines) if "END OF HEADER" in line) + 1:]
    terms = {}
    for line in body:
        if line[:1] != "R":
            continue
        offset, frequency = known(line[23:42]), known(line[42:61])
        if offset is not None and frequency is not None:
            terms.setdefault(line[:3], {})[toc(line)] = (offset, frequency, 0.0)
    return terms


def _terms(text):
    """{signal ID: {toc: (offset s, drift s/s, drift rate s/s²)}} for every system; a later record at one toc wins."""
    terms = _glonass_terms(text)
    for signal_id, records in read_navigation(text).items():
        for record in records:
            if signal_id[0] == "E" and not int(record["codes"]) & GALILEO_INAV_CLOCK:
                continue
            terms.setdefault(signal_id, {})[record["toc"]] = (record["af0"], record["af1"], record["af2"])
    return terms


def steps_ns(terms):
    """How far each record's clock offset lands from what the record before it predicted, in nanoseconds, for the
    records no more than MAX_GAP apart. terms: {toc: (offset, drift, drift rate)}."""
    moments = sorted(terms)
    steps = []
    for earlier, later in zip(moments, moments[1:]):
        if later - earlier > MAX_GAP:
            continue
        seconds = (later - earlier).total_seconds()
        offset, drift, rate = terms[earlier]
        steps.append((terms[later][0] - (offset + drift * seconds + rate * seconds * seconds)) * NS)
    return steps


def clocks(text):
    """{signal ID: {"records", "drift_ns_per_day", "typical_step_ns", "largest_step_ns"}} from a RINEX 3 navigation
    file's text. The two steps are None for a satellite with no two records close enough to compare."""
    if "END OF HEADER" not in text:   # not a navigation file: nothing to read
        return {}
    out = {}
    for signal_id, terms in _terms(text).items():
        steps = [abs(step) for step in steps_ns(terms)]
        out[signal_id] = {
            "records": len(terms),
            "drift_ns_per_day": round(terms[max(terms)][1] * 86400 * NS, 3),
            "typical_step_ns": round(statistics.median(steps), 3) if steps else None,
            "largest_step_ns": round(max(steps), 3) if steps else None,
        }
    return out
