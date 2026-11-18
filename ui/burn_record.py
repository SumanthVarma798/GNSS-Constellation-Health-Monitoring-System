"""The burn record: what kind each burn was (analysis/burn_classes.py), counted for the score's fourth measure ("care")
and for the pictures on Home, Overview and Station-keeping (ui/burn_ledger.py).

A satellite passes when it made no irregular burn in the last CARE_RECENT_DAYS days and its irregular share of the last
365 days is at most CARE_MAX_SHARE; it is not judged with fewer than CARE_MIN_JUDGED judged burns (ui/limits.py).
Relocations and end-of-life burns are planned and sit in neither count. Not read by the per-satellite Overall Score.
"""
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from analysis import burn_class_settings as S
from analysis.burn_classes import IRREGULAR, wilson
from analysis.bundled_run import burn_classes_of
from ui import limits
from ui.burn_groups import ARTEFACT_GROUP, COUNT_KEYS, OFF, RESPONSE, ROUTINE, group_of


@st.cache_data(show_spinner=False, max_entries=8)
def _classified(constellation, burns_key, _result):
    return burn_classes_of(_result, constellation)


def classified(constellation, result):
    """The classified burns table of an assessed `result` (analysis/burn_classes.classify), or None when the
    constellation has no burns found (the medium-orbit ones). Kept until the burns change: classifying takes a
    fraction of a second, and Home, Overview and Station-keeping all read it."""
    detailed = result.get("burns_detailed")
    if detailed is None or not len(detailed):
        return None
    key = (len(detailed), str(detailed["window_end"].max()), str(result["history"]["EPOCH"].max()))
    return _classified(constellation, key, result)


def _now(now):
    stamp = pd.Timestamp(now or datetime.now(timezone.utc))
    return stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo else stamp


def care_of(table, now=None):
    """{satellite: True (passes), False, or None (not judged)} for the satellites with counted burns in the last 365
    days; a satellite not in it has none, so is not judged."""
    now = _now(now)
    window = table[(table["when"] > now - pd.Timedelta(days=S.WINDOW_DAYS)) & (table["when"] <= now)]
    counted = window[window["counted"].astype(bool)]
    out = {}
    for name, own in counted.groupby("satellite"):
        if len(own) < limits.CARE_MIN_JUDGED:
            out[name] = None
            continue
        irregular = own[own["burn_class"].isin(IRREGULAR)]
        recent = (irregular["when"] > now - pd.Timedelta(days=limits.CARE_RECENT_DAYS)).any()
        out[name] = bool(not recent and len(irregular) / len(own) <= limits.CARE_MAX_SHARE)
    return out


def record_of(table, now=None):
    """The constellation's burn record over the last 365 days: {group: burns} for each of COUNT_KEYS, and decided
    (routine + response + off pattern), irregular (response + off pattern), low and high (their Wilson interval);
    None when there are no burns."""
    if table is None or not len(table):
        return None
    now = _now(now)
    window = table[(table["when"] > now - pd.Timedelta(days=S.WINDOW_DAYS)) & (table["when"] <= now)]
    counts = {key: 0 for key in COUNT_KEYS}
    for burn_class, counted in zip(window["burn_class"], window["counted"].astype(bool)):
        counts[group_of(burn_class, counted)] += 1
    return _with_share(counts)


def _with_share(counts):
    decided = counts[ROUTINE] + counts[RESPONSE] + counts[OFF]
    irregular = counts[RESPONSE] + counts[OFF]
    low, high = wilson(irregular, decided)
    return {**counts, "decided": decided, "irregular": irregular, "low": float(low), "high": float(high)}


def combine(records):
    """Several parts' records as one (the interval worked out again over the sum); None when none has one."""
    records = [record for record in records if record]
    return _with_share({key: sum(record[key] for record in records) for key in COUNT_KEYS}) if records else None


def _pct(value):
    return f"{round(100 * value)}%"


def rated(record):
    """Whether there are enough judged burns to rate the share (analysis/burn_class_settings.py MIN_DECIDED)."""
    return bool(record) and record["decided"] >= S.MIN_DECIDED


def words(record):
    """'3 of 41 burns irregular (7%, 2–20%)', or 'too few to rate' (with how many there were); '' with no record."""
    if not record or not record["decided"]:
        return ""
    count = f"{record['irregular']} of {record['decided']} burns irregular"
    if not rated(record):
        return f"too few to rate ({count})"
    share = record["irregular"] / record["decided"]
    return f"{count} ({_pct(share)}, {round(100 * record['low'])}–{_pct(record['high'])})"
