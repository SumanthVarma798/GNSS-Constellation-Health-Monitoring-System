"""What kind of burn each detected manoeuvre was: planned, routine, a response, off its pattern, or not a burn at all.

Pure analysis: no score reads this yet and no page shows it. Input is the detector's burns table
(analysis/bundled_run.burns_detailed) and the bundled history; every threshold is named in
analysis/burn_class_settings.py. Rules run in order and the first match wins; each result carries a confidence and the
tests it passed or failed.

    0 artefact            excluded    an implausible step (above the delta-v cap) or one that is undone
    1 relocation          planned     a pair of big opposite burns with a fast drift between (or one big burn that moved it)
    2 end of life         planned     a raise that ends in, or a burn made in, the graveyard
    3 routine east-west   counted     T1 interval, T2 size, T3 direction (reverses the drift, inside its box); 3 of 3 high;
                                      never one with a sign of response (cluster, off-limit state)
    4 routine north-south counted     moves the inclination towards its target, a normal size, apart from the last one, no big radial move
    5 response            irregular   it was off before the burn (outside its box or drift limit), a cluster, a quick reversal
    6 off pattern         irregular   an east-west burn that does not reverse the drift, or of a size far from its own norm
    6b off-cycle timing   not counted only the interval is off (T1 fails, T2 and T3 pass)
    7 unexplained         not counted too little history and no peers, or nothing above matched

A burn is judged against its own earlier burns once it has MIN_PRIORS of them, otherwise against its peers (other
satellites of the same constellation and orbit type); a verdict resting on peers is one level less confident.
"""
import numpy as np
import pandas as pd

from analysis import burn_class_settings as S
from analysis import burn_context, score_rules
from config.config import (
    BEIDOU3_SERVICE_REQUIREMENTS, GRAVEYARD_ORBIT_MIN, NAVIK_SERVICE_REQUIREMENTS, QZSS_SERVICE_REQUIREMENTS,
)

ARTEFACT, RELOCATION, DISPOSAL = "artefact", "relocation", "end of life"
ROUTINE_EW, ROUTINE_NS = "routine east-west", "routine north-south"
RESPONSE, OFF_PATTERN = "response", "off pattern"
OFF_CYCLE, UNEXPLAINED = "off-cycle timing", "unexplained"
CLASSES = (ROUTINE_EW, ROUTINE_NS, RESPONSE, OFF_PATTERN, OFF_CYCLE, RELOCATION, DISPOSAL, ARTEFACT, UNEXPLAINED)
DECIDED = (ROUTINE_EW, ROUTINE_NS, RESPONSE, OFF_PATTERN)   # the burns a share is worked out over
IRREGULAR = (RESPONSE, OFF_PATTERN)
LEVEL = {name: i for i, name in enumerate(S.CONFIDENCE_LEVELS)}
EW, NS = "east-west", "north-south"

COLUMNS = ["rule", "burn_class", "confidence", "counted", "basis", "tests", "note"]


def _lower(confidence):
    return S.CONFIDENCE_LEVELS[max(0, LEVEL[confidence] - 1)]


def _requirements(name):
    for table in (NAVIK_SERVICE_REQUIREMENTS, QZSS_SERVICE_REQUIREMENTS, BEIDOU3_SERVICE_REQUIREMENTS):
        if name in table:
            return table[name]
    return {}


def inclination_target(name, orbit_type):
    """The inclination a satellite is kept near, in degrees: its requirement, the middle of its range, or 0 for a GEO one."""
    wanted = _requirements(name)
    for key in ("inclination", "inclination_target_deg"):
        if key in wanted:
            return float(wanted[key])
    if "inclination_target_deg_range" in wanted:
        return float(np.mean(wanted["inclination_target_deg_range"]))
    return 0.0 if orbit_type == "GEO" else np.nan


def _inclination_beyond(name, orbit_type, inc, constellation):
    """Whether an inclination is outside what the satellite is allowed: outside its range, else further than the tolerance."""
    wanted = _requirements(name)
    if "inclination_target_deg_range" in wanted:
        low, high = wanted["inclination_target_deg_range"]
        return not low <= inc <= high
    target = inclination_target(name, orbit_type)
    return bool(abs(inc - target) > score_rules.default_inclination_tolerance(constellation))


def wilson(successes, total, z=S.WILSON_Z):
    """The Wilson score interval for a share, as (low, high); (nan, nan) when there is nothing to divide."""
    if total <= 0:
        return np.nan, np.nan
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0.0, centre - half), min(1.0, centre + half)


def _sign(x):
    return int(x > 0) - int(x < 0)


def _box(orbit_type):
    return S.BOX_GEO if orbit_type == "GEO" else S.BOX_TILTED


def _drift_limit(orbit_type):
    return S.DRIFT_TOLERANCE_GEO if orbit_type == "GEO" else score_rules.DRIFT_TOLERANCE_TILTED


def _longitude_accel(longitude):
    """Magnitude of the longitude acceleration at a longitude, degrees/day^2 (NaN when none or too weak to use)."""
    if longitude is None or not np.isfinite(longitude):
        return np.nan
    accel = abs(S.LON_ACCEL_K * np.sin(np.deg2rad(2 * (longitude - S.LON_ACCEL_STABLE))))
    return accel if accel >= S.LON_ACCEL_MIN else np.nan


def _stations(table, history, cuts):
    """Per burn, the satellite's own station in degrees from its designated slot: the median position of its records
    while it was kept (drift small), within the stretch between its relocations. NVS-01 is kept about 2 degrees from the
    slot the config names, so a box around the config slot would call every one of its burns off.
    `cuts` is {satellite: [times its longitude changed station]}."""
    station = pd.Series(np.nan, index=table.index)
    for name, group in table.groupby("satellite"):
        epoch, pos, drift = burn_context.position_records(history, name)
        if not len(epoch):
            continue
        boundaries = np.array([pd.Timestamp(c).value for c in sorted(cuts.get(name, []))], dtype="int64")
        kept = np.isfinite(pos) & np.isfinite(drift) & (np.abs(drift) < S.RELOCATION_MIN_DRIFT)
        stretch = np.searchsorted(boundaries, epoch, side="right")
        medians = {s: float(np.median(pos[kept & (stretch == s)])) for s in np.unique(stretch[kept])}
        for i in group.index:
            s = int(np.searchsorted(boundaries, pd.Timestamp(table.at[i, "window_start"]).value, side="right"))
            station[i] = medians.get(s, np.nan)
    return station


class _Verdict:
    """What the rules found for one burn."""
    __slots__ = ("rule", "burn_class", "confidence", "basis", "tests", "note")

    def __init__(self, rule, burn_class, confidence, basis="", tests="", note=""):
        self.rule, self.burn_class, self.confidence, self.basis, self.tests, self.note = (
            rule, burn_class, confidence, basis, tests, note)


def _find_relocations(t, done):
    """Rule 1. {index: (partner index or None)} for the burns of relocations; `done` holds rule 0's artefacts."""
    found = {}
    for name, group in t[(t["kind"] == EW) & ~t.index.isin(list(done))].groupby("satellite"):
        big = group[(group["delta_a_km"].abs() >= S.RELOCATION_MIN_KM)       # one that ends in the graveyard is rule 2's
                    & (group["alt_after_km"] < GRAVEYARD_ORBIT_MIN) & (group["alt_before_km"] < GRAVEYARD_ORBIT_MIN)].sort_values("when")
        rows = list(big.index)
        used = set()
        for a, b in zip(rows, rows[1:]):
            first, second = t.loc[a], t.loc[b]
            gap = (second["when"] - first["when"]).total_seconds() / 86400
            east = -_sign(first["delta_a_km"])        # a lower orbit drifts east
            if (_sign(second["delta_a_km"]) == -_sign(first["delta_a_km"]) and S.RELOCATION_MIN_DAYS <= gap <= S.RELOCATION_MAX_DAYS
                    and first["drift_after"] * east >= S.RELOCATION_MIN_DRIFT
                    and second["drift_before"] * east >= S.RELOCATION_MIN_DRIFT):
                found[a], found[b] = b, a
                used.update((a, b))
        for i in rows:
            if i in used:
                continue
            row = t.loc[i]
            moved = abs(row["pos_later"] - row["pos_before"]) if np.isfinite(row["pos_later"] + row["pos_before"]) else 0.0
            if moved >= S.RELOCATION_SHIFT_DEG:
                found[i] = None
    return found


def _artefacts(t):
    """Rule 0. {index: reason} for the steps that are not burns."""
    out = {}
    for i, row in t.iterrows():
        dv = abs(row["delta_a_km"]) * S.DV_PER_KM
        if row["kind"] == EW and dv > S.EW_MAX_DV:
            out[i] = f"east-west step of {row['delta_a_km']:+.1f} km would cost {dv:.0f} m/s, above {S.EW_MAX_DV:.0f}"
        elif row["kind"] == NS and abs(row["delta_i_deg"]) > S.NS_MAX_DEG:
            out[i] = (f"inclination step of {row['delta_i_deg']:+.2f} degrees would cost "
                      f"{abs(row['delta_i_deg']) * S.DV_PER_DEG_INCLINATION:.0f} m/s")
    wild = t[t["delta_i_deg"].abs() > S.NS_MAX_DEG]       # the records round a step like this are wrong for every kind
    for i, row in t.iterrows():
        near = wild["satellite"] == row["satellite"]
        if i not in out and (near & (wild["window_end"] == row["window_end"])).any():
            out[i] = "its records show an impossible inclination step in the same window"
        elif i not in out and (near & ((wild["window_end"] - row["window_start"]).abs() <= pd.Timedelta(days=S.CONTAMINATED_DAYS))).any():
            out[i] = "its before-record is the one that shows the impossible inclination step"
    return out


def _reversals(t, found, out):
    """Rule 0, second part: a step undone within REVERSAL_DAYS to within REVERSAL_NET of its size. Inclination steps count
    at any size (no one raises inclination to lower it again); east-west ones only when big and not a relocation, since a
    small east-west burn is routinely trimmed."""
    for name, group in t.groupby("satellite"):
        for kind, column, floor in ((NS, "delta_i_deg", 0.0), (EW, "delta_a_km", S.RELOCATION_MIN_KM)):
            rows = [i for i in group[group["kind"] == kind].sort_values("when").index
                    if i not in out and i not in found and abs(t.at[i, column]) >= floor]
            for a, b in zip(rows, rows[1:]):
                x, y = t.at[a, column], t.at[b, column]
                gap = (t.at[b, "when"] - t.at[a, "when"]).total_seconds() / 86400
                if _sign(x) == -_sign(y) and gap <= S.REVERSAL_DAYS and abs(x + y) <= S.REVERSAL_NET * max(abs(x), abs(y)):
                    why = f"a step of {x:+.2f} undone {gap:.0f} days later by {y:+.2f}"
                    out[a] = out[b] = why


def _disposals(t, graveyard, out):
    """Rule 2. {index: reason}."""
    result = {}
    for name, group in t[t["kind"] == EW].groupby("satellite"):
        group = group.sort_values("when")
        reach = group[(group["alt_after_km"] >= GRAVEYARD_ORBIT_MIN) | (group["alt_before_km"] >= GRAVEYARD_ORBIT_MIN)]
        reach = reach[~reach.index.isin(list(out))]
        if reach.empty:
            continue
        first = reach["when"].min()
        for i in reach.index:
            result[i] = f"altitude {t.at[i, 'alt_after_km']:.0f} km, at or above the graveyard {GRAVEYARD_ORBIT_MIN:.0f} km"
        sequence = group[(group["delta_a_km"] > 0) & (group["when"] < first)
                         & (group["when"] >= first - pd.Timedelta(days=S.DISPOSAL_SEQUENCE_DAYS))]
        for i in sequence.index:
            if i not in out:
                result[i] = "a raise in the sequence that ended in the graveyard"
    for name in graveyard:    # whatever it does once in the graveyard
        for i in t[(t["satellite"] == name) & (t["kind"] == EW)].index:
            if i not in out and i not in result and t.at[i, "alt_after_km"] >= GRAVEYARD_ORBIT_MIN:
                result[i] = "burn made in the graveyard"
    return result


def _clusters(t, rows):
    """Indexes in `rows` that lie in some run of CLUSTER_BURNS or more burns within CLUSTER_DAYS."""
    ordered = sorted(rows, key=lambda i: t.at[i, "when"])
    hit = set()
    for k, i in enumerate(ordered):
        end = t.at[i, "when"] + pd.Timedelta(days=S.CLUSTER_DAYS)
        run = [j for j in ordered[k:] if t.at[j, "when"] <= end]
        if len(run) >= S.CLUSTER_BURNS:
            hit.update(run)
    return hit


def _gaps(t, rows):
    """Days since the previous burn in `rows` for the same satellite and kind (NaN for the first)."""
    sub = t.loc[rows].sort_values("when")
    return sub.groupby(["satellite", "kind"])["when"].diff().dt.total_seconds().div(86400)


def classify(burns, history, constellation):
    """The burns table with each burn's context and its class.

    `burns` is analysis/bundled_run.burns_detailed's table, `history` the frame it came from, `constellation` the name the
    dashboard uses ("NavIC", "QZSS", "BeiDou-3"). One row per burn, ordered by satellite, time, kind. Added to the
    context columns of analysis/burn_context.add_context: station (degrees from the slot where the satellite is kept),
    pos_from_station, rule, burn_class, confidence, counted (a decided burn at COUNTED_CONFIDENCE or better), basis
    ("own", "peers" or ""), tests (what T1..T3 or N1..N4 found) and note (why, in words).
    """
    t = burn_context.add_context(burns, history, constellation)
    t = t.sort_values(["satellite", "when", "kind"]).reset_index(drop=True)
    if t.empty:
        return t.reindex(columns=list(t.columns) + ["station", "pos_from_station"] + COLUMNS)
    verdict = {}

    out = _artefacts(t)                       # rule 0 (caps) before 1, so a step too big for a burn is never a relocation
    last = history.sort_values("EPOCH").groupby("satellite")["SEMIMAJOR_AXIS"].last()
    graveyard = {n for n, a in last.items() if a - burn_context.R_EARTH >= GRAVEYARD_ORBIT_MIN}
    ends = _disposals(t, graveyard, out)      # found before relocations: a raise that ends in the graveyard moves the longitude too
    found = _find_relocations(t, list(out) + list(ends))
    _reversals(t, found, out)
    found = {i: p for i, p in found.items() if i not in out}
    cuts = {}
    for i, partner in found.items():
        if partner is None or t.at[partner, "when"] < t.at[i, "when"]:    # the burn that ends the move
            cuts.setdefault(t.at[i, "satellite"], []).append(t.at[i, "window_end"])
    t["station"] = _stations(t, history, cuts)
    t["pos_from_station"] = t["pos_before"] - t["station"]

    for i, why in out.items():
        verdict[i] = _Verdict("0", ARTEFACT, "high" if "cost" in why or "impossible" in why or "before-record" in why else "medium", note=why)
    for i, partner in found.items():
        row = t.loc[i]
        if partner is not None:
            verdict[i] = _Verdict("1", RELOCATION, "high", tests="opposite pair, drift between",
                                  note=f"{row['delta_a_km']:+.1f} km with the pair's other burn at "
                                       f"{t.at[partner, 'when']:%d %b %Y}; drift between {row['drift_after']:+.2f} degrees/day")
        else:
            verdict[i] = _Verdict("1", RELOCATION, "medium", tests="one big burn, longitude moved",
                                  note=f"{row['delta_a_km']:+.1f} km and its longitude moved {row['pos_later'] - row['pos_before']:+.1f} "
                                       "degrees; the burn that stopped it was not detected")
    for i, why in ends.items():
        verdict[i] = _Verdict("2", DISPOSAL, "high", note=why)

    _rules_3_to_7(t, constellation, verdict)

    for column in COLUMNS:
        t[column] = None
    for i, v in verdict.items():
        t.at[i, "rule"], t.at[i, "burn_class"], t.at[i, "confidence"] = v.rule, v.burn_class, v.confidence
        t.at[i, "basis"], t.at[i, "tests"], t.at[i, "note"] = v.basis, v.tests, v.note
    t["counted"] = t["burn_class"].isin(DECIDED) & (t["confidence"].map(LEVEL) >= LEVEL[S.COUNTED_CONFIDENCE])
    return t


def _norms(t, rest, clean):
    """Per burn in `rest`: what to judge it against. Own and peer norms come from the `clean` burns only (those with no
    sign of a response), so a cluster of big burns does not become the norm.
    Returns {index: dict(priors, own_sizes, own_gaps, peer_sizes, peer_gaps, gap, previous)}: gap is days since the
    previous burn of the same satellite and kind (any), previous that burn's index."""
    column = {EW: "delta_a_km", NS: "delta_i_deg"}
    every = t.loc[rest].sort_values("when")
    gap_all = _gaps(t, rest)
    kept = t.loc[clean].sort_values("when")
    gap_kept = _gaps(t, clean)
    info = {}
    for (name, kind), group in every.groupby(["satellite", "kind"]):
        mine = kept[(kept["satellite"] == name) & (kept["kind"] == kind)]
        peers = kept[(kept["kind"] == kind) & (kept["satellite"] != name) & (kept["orbit_type"] == group["orbit_type"].iloc[-1])]
        idx = list(group.index)
        for k, i in enumerate(idx):
            before = mine[mine["when"] < t.at[i, "when"]]
            info[i] = {"priors": len(before), "own_sizes": before[column[kind]].abs().to_numpy(),
                       "own_gaps": gap_kept.reindex(before.index).dropna().to_numpy(),
                       "peer_sizes": peers[column[kind]].abs().to_numpy(),
                       "peer_gaps": gap_kept.reindex(peers.index).dropna().to_numpy(),
                       "gap": gap_all.get(i, np.nan), "previous": idx[k - 1] if k else None}
    return info


def _norm_size(n, kind):
    """(norm size, basis): the median of its own earlier burns if there are enough; else of those and its peers' together
    ("peers") if that makes enough; else (nan, '')."""
    if n["priors"] >= S.MIN_PRIORS:
        return float(np.median(n["own_sizes"])), "own"
    pool = np.concatenate([n["own_sizes"], n["peer_sizes"]])
    if len(pool) >= (S.MIN_PEERS if kind == EW else S.MIN_PEERS_NS):
        return float(np.median(pool)), "peers"
    return np.nan, ""


def _test_interval(t, i, n, basis):
    """T1 -> (True/False/None, words)."""
    gap = n["gap"]
    if not np.isfinite(gap):
        return None, "T1 interval: no earlier burn"
    ranges = []
    if basis == "own" and len(n["own_gaps"]) >= 2:
        ranges.append(("own", n["own_gaps"]))
    elif basis == "peers" and len(np.concatenate([n["own_gaps"], n["peer_gaps"]])) >= S.MIN_PEERS:
        ranges.append(("peers", np.concatenate([n["own_gaps"], n["peer_gaps"]])))
    said = []
    for label, gaps in ranges:
        q1, q3 = np.percentile(gaps, [25, 75])
        low, high = q1 * (1 - S.INTERVAL_MARGIN), q3 * (1 + S.INTERVAL_MARGIN)
        if low <= gap <= high:
            return True, f"T1 interval: pass, {gap:.0f} d inside {label} range {low:.0f}-{high:.0f} d"
        said.append(f"{gap:.0f} d outside {label} range {low:.0f}-{high:.0f} d")
    if t.at[i, "orbit_type"] == "GEO" and n["previous"] is not None:
        accel = _longitude_accel(t.at[i, "slot_lon"] + t.at[i, "station"]) if np.isfinite(t.at[i, "station"]) else np.nan
        if np.isfinite(accel):
            model = abs(S.DRIFT_PER_KM * t.at[n["previous"], "delta_a_km"]) / accel
            if abs(gap - model) <= S.INTERVAL_MARGIN * model:
                return True, f"T1 interval: pass, {gap:.0f} d within {S.INTERVAL_MARGIN:.0%} of the model {model:.0f} d"
            said.append(f"{gap:.0f} d against the model {model:.0f} d")
    return (False, "T1 interval: fail, " + "; ".join(said)) if said else (None, "T1 interval: no norm to compare with")


def _test_direction(t, i):
    """T3 -> (True/False/None, words)."""
    row = t.loc[i]
    drift = row["drift_before"]
    if not np.isfinite(drift) or abs(drift) < S.DRIFT_NOISE:
        return None, "T3 direction: drift before too small to give a direction"
    reverses = _sign(row["delta_a_km"]) == _sign(drift)       # a lower orbit drifts east: it reverses a westward drift
    if not np.isfinite(row["pos_from_station"]):
        return None, "T3 direction: no position to put it in its box"
    inside = bool(abs(row["pos_from_station"]) <= _box(row["orbit_type"]))
    words = (f"T3 direction: {'pass' if reverses and inside else 'fail'}, drift before {drift:+.3f} degrees/day, "
             f"{'reverses it' if reverses else 'does not reverse it'}, "
             f"{'inside' if inside else 'outside'} its box")
    return bool(reverses and inside), words


def _rules_3_to_7(t, constellation, verdict):
    rest = [i for i in t.index if i not in verdict]
    if not rest:
        return
    ew = [i for i in rest if t.at[i, "kind"] == EW]
    cluster = set()
    for name in t.loc[ew, "satellite"].unique():
        cluster |= _clusters(t, [i for i in ew if t.at[i, "satellite"] == name])
    reasons = {}
    for i in rest:                       # the signs that a burn answers a state that was already off
        row, found = t.loc[i], []
        if row["kind"] == EW:
            if i in cluster:
                found.append(f"{S.CLUSTER_BURNS} or more burns within {S.CLUSTER_DAYS} days")
            if any(j != i and t.at[j, "satellite"] == row["satellite"] and _sign(t.at[j, "delta_a_km"]) == -_sign(row["delta_a_km"])
                   and abs((t.at[j, "when"] - row["when"]).total_seconds()) / 86400 <= S.QUICK_REVERSAL_DAYS for j in ew):
                found.append(f"an opposite burn within {S.QUICK_REVERSAL_DAYS} days")
            if np.isfinite(row["pos_from_station"]) and abs(row["pos_from_station"]) > _box(row["orbit_type"]):
                found.append(f"{row['pos_from_station']:+.2f} degrees from its station before the burn")
            if np.isfinite(row["drift_before"]) and abs(row["drift_before"]) > _drift_limit(row["orbit_type"]):
                found.append(f"drift {row['drift_before']:+.3f} degrees/day before the burn")
        else:
            toward = inclination_target(row["satellite"], row["orbit_type"]) - row["inc_before"]
            if (np.isfinite(toward) and _sign(row["delta_i_deg"]) == _sign(toward)
                    and _inclination_beyond(row["satellite"], row["orbit_type"], row["inc_before"], constellation)):
                found.append("inclination was beyond its limit before the burn")
        reasons[i] = found
    info = _norms(t, rest, [i for i in rest if not reasons[i]])
    for i in rest:
        row, n = t.loc[i], info[i]
        accompanied = ((t["satellite"] == row["satellite"]) & (t["kind"] == EW)
                       & ((t["when"] - row["when"]).abs() <= pd.Timedelta(days=S.ACCOMPANIED_DAYS))).any()
        norm, basis = _norm_size(n, row["kind"])
        size = abs(row["delta_a_km"] if row["kind"] == EW else row["delta_i_deg"])
        ratio = size / norm if np.isfinite(norm) and norm > 0 else np.nan
        low, high = S.SIZE_BAND
        t2 = None if not np.isfinite(ratio) else bool(low <= ratio <= high)
        t2_words = (f"{'T2' if row['kind'] == EW else 'N2'} size: no norm" if t2 is None else
                    f"{'T2' if row['kind'] == EW else 'N2'} size: {'pass' if t2 else 'fail'}, {size:.2f} is {ratio:.1f}x the "
                    f"{basis} median {norm:.2f}")
        drop = (lambda c: _lower(c)) if basis == "peers" else (lambda c: c)

        if row["kind"] == NS:
            toward = inclination_target(row["satellite"], row["orbit_type"]) - row["inc_before"]
            n1 = bool(_sign(row["delta_i_deg"]) == _sign(toward)) if np.isfinite(toward) else None
            gap = n["gap"]
            n3 = True if not np.isfinite(gap) else bool(gap >= S.NS_MIN_GAP_DAYS)
            n4 = True if accompanied else bool(abs(row["delta_a_km"]) < S.NS_MAX_DELTA_A)
            words = "; ".join([f"N1 moves the inclination towards its target: {n1}", t2_words, f"N3 gap {gap:.0f} d" if np.isfinite(gap)
                               else "N3 gap: first", f"N4 radial move {'small' if n4 else 'large'}"])
            if n1 and n4 and t2 is not None and (t2 or n3):
                good = int(bool(t2)) + int(n3)
                if good:
                    verdict[i] = _Verdict("4", ROUTINE_NS, drop("high" if good == 2 else "medium"), basis, words)
                    continue
            beyond = _inclination_beyond(row["satellite"], row["orbit_type"], row["inc_before"], constellation)
            if n1 and beyond:
                verdict[i] = _Verdict("5", RESPONSE, "medium", basis, words, "inclination was beyond its limit before the burn")
            else:
                verdict[i] = _Verdict("7", UNEXPLAINED, "low", basis, words)
            continue

        t1, t1_words = _test_interval(t, i, n, basis)
        t3, t3_words = _test_direction(t, i)
        words = "; ".join([t1_words, t2_words, t3_words])
        why = reasons[i]

        if basis and t3 is True and t2 is not None and (t2 or t1):
            if t1 and t2 and not why:
                verdict[i] = _Verdict("3", ROUTINE_EW, drop("high"), basis, words)
                continue
            if not why and t1 is not False:               # T1 not failing: it passed with T2 failing, or has no earlier burn
                verdict[i] = _Verdict("3", ROUTINE_EW, drop("medium"), basis, words)
                continue
        if why:
            confident = "high" if len(why) > 1 or i in cluster else "medium"
            verdict[i] = _Verdict("5", RESPONSE, confident, basis, words, "; ".join(why))
            continue
        if basis and (t3 is False or t2 is False):
            failed = sum(x is False for x in (t1, t2, t3))
            verdict[i] = _Verdict("6", OFF_PATTERN, drop("high" if failed >= 2 else "medium"), basis, words,
                                  "does not reverse the drift" if t3 is False else "size far from its norm")
        elif basis and t1 is False and t2 and t3:
            verdict[i] = _Verdict("6b", OFF_CYCLE, drop("medium"), basis, words, "only the interval is off")
        else:
            verdict[i] = _Verdict("7", UNEXPLAINED, "low", basis, words,
                                  "too little history and no peers" if not basis else "no rule matched")


def summarise(table, now, window_days=S.WINDOW_DAYS):
    """Counts by class and the irregular share over the `window_days` up to `now` (a timezone-aware or naive UTC time).

    Returns (by_satellite, overall): by_satellite has one row per satellite (columns: each class, decided, irregular, share,
    low, high, rating) and `overall` the same as a dict for the constellation. decided = routine east-west + routine
    north-south + response + off pattern, each at COUNTED_CONFIDENCE or better; irregular = response + off pattern;
    share = irregular/decided with its Wilson interval; rating is "too few to rate" below MIN_DECIDED decided burns.
    """
    now = pd.Timestamp(now)
    now = now.tz_convert("UTC").tz_localize(None) if now.tzinfo else now
    window = table[(table["when"] > now - pd.Timedelta(days=window_days)) & (table["when"] <= now)]

    def row(group):
        out = {c: int((group["burn_class"] == c).sum()) for c in CLASSES}
        counted = group[group["counted"].astype(bool)]
        decided = len(counted)
        irregular = int(counted["burn_class"].isin(IRREGULAR).sum())
        low, high = wilson(irregular, decided)
        out.update(decided=decided, irregular=irregular, share=irregular / decided if decided else np.nan, low=low, high=high,
                   rating="too few to rate" if decided < S.MIN_DECIDED else "rated")
        return out

    rows = {name: row(group) for name, group in window.groupby("satellite")}
    by_satellite = pd.DataFrame.from_dict(rows, orient="index")
    by_satellite.index.name = "satellite"
    return by_satellite, row(window)
