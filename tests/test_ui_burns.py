"""The burn pictures: where each kind sits, the cadence numbers, and the conversion from detections."""
import re

import pandas as pd
import pytest

from analysis.maneuver_detection import detect_navik_maneuvers
from evidence import settings
from ui import palette
from ui.figures import burns as B

DAY = pd.Timedelta(days=1)
T0 = pd.Timestamp("2026-01-01")


def burn(sat, kind, day, half_days=1.0, sma=2.0, inc=0.0):
    """A burn whose window is centred on T0 + day."""
    mid = T0 + day * DAY
    return {"satellite": sat, "kind": kind, "window_start": mid - half_days * DAY,
            "window_end": mid + half_days * DAY, "d_sma_km": sma, "d_inc_deg": inc}


def frame(*rows):
    return pd.DataFrame(list(rows), columns=B.COLUMNS)


# A: east-west at days 0, 10, 40 (gaps 10, 30); north-south at 5, 25 (gap 20), interleaved on purpose.
SMALL = frame(burn("A", "east-west", 0), burn("A", "north-south", 5, sma=0, inc=0.2),
              burn("A", "east-west", 10), burn("A", "north-south", 25, sma=0, inc=-0.3),
              burn("A", "east-west", 40), burn("B", "east-west", 3))
SATS = ["A", "B", "C"]   # C has no burns
END = T0 + 100 * DAY


def steps(column, jump, n=30, at=15):
    epoch = pd.date_range("2026-01-01", periods=n, freq="D")
    df = pd.DataFrame({"EPOCH": epoch.astype(str), "SEMIMAJOR_AXIS": 42164.0, "INCLINATION": 28.0})
    df.loc[at:, column] += jump
    return detect_navik_maneuvers(df, z_thresh=3.5, sma_abs_thresh_km=1.5, inc_abs_thresh_deg=0.1, persist_window=2)


def test_conversion_gives_window_from_previous_element_set():
    ew, ns = steps("SEMIMAJOR_AXIS", 5.0), steps("INCLINATION", 0.5)
    out = B.burns_from_detections({"S1": ew, "S2": ns})
    assert list(out.columns) == B.COLUMNS
    assert out["kind"].tolist() == ["east-west", "north-south"]
    i = int(ew.index[ew["EW_MANEUVER"]][0])
    first = out.iloc[0]
    assert first["window_end"] == pd.Timestamp(ew["EPOCH"][i])
    assert first["window_start"] == pd.Timestamp(ew["EPOCH"][i - 1])
    assert first["d_sma_km"] > 0 and out.iloc[1]["d_inc_deg"] > 0


def test_windows_run_forwards_in_time():
    out = B.burns_from_detections({"S1": steps("SEMIMAJOR_AXIS", 5.0), "S2": steps("INCLINATION", 0.5)})
    assert (out["window_start"] < out["window_end"]).all()


def test_conversion_of_nothing_is_an_empty_table():
    quiet = steps("SEMIMAJOR_AXIS", 0.0)
    assert B.burns_from_detections({"S1": quiet}).empty


def bars(fig, kind):
    return next(t for t in fig.data if t.name == kind)


def test_kinds_sit_in_the_right_half_of_each_band():
    fig = B.burn_timeline(SMALL, SATS, T0, END)
    for band, sat in enumerate(SATS):
        centre = -band
        for kind, side in (("east-west", 1), ("north-south", -1)):
            t = bars(fig, kind)
            ys = [y for y, s in zip(t.y, [r for r in _sats_of(kind)]) if s == sat]
            assert all(side * (y - centre) > 0 for y in ys)
    assert len(bars(fig, "east-west").y) == 4 and len(bars(fig, "north-south").y) == 2


def _sats_of(kind):
    rows = SMALL[SMALL["kind"] == kind].sort_values("window_start")  # the timeline orders by time
    return rows["satellite"].tolist()


def test_bar_spans_the_window_and_never_vanishes():
    fig = B.burn_timeline(SMALL, SATS, T0, END)
    t = bars(fig, "east-west")
    first = next(i for i, b in enumerate(t.base) if pd.Timestamp(b) == T0 - DAY)
    assert t.x[first] == 2 * 86400 * 1000   # a two-day window
    tiny = frame(burn("A", "east-west", 5, half_days=0.001))
    width_ms = bars(B.burn_timeline(tiny, SATS, T0, END), "east-west").x[0]
    assert width_ms == pytest.approx((END - T0).total_seconds() * 1000 * B.MIN_WIDTH_SHARE)


def test_range_slider_and_opening_view():
    fig = B.burn_timeline(SMALL, SATS, T0, END)
    axis = fig.layout.xaxis
    assert axis.rangeslider.visible
    assert pd.Timestamp(axis.rangeslider.range[0]) == T0 and pd.Timestamp(axis.rangeslider.range[1]) == END
    assert pd.Timestamp(axis.range[1]) == END
    assert pd.Timestamp(axis.range[0]) == END - settings.BURN_TIMELINE_RECENT_DAYS * DAY
    short = B.burn_timeline(SMALL, SATS, T0, T0 + 30 * DAY)   # a span shorter than 90 days opens on all of it
    assert pd.Timestamp(short.layout.xaxis.range[0]) == T0


def test_halves_are_named_once_and_there_is_no_legend():
    fig = B.burn_timeline(SMALL, SATS, T0, END)
    texts = [a.text for a in fig.layout.annotations]
    assert texts.count("E-W") == 1 and texts.count("N-S") == 1
    assert not fig.layout.showlegend


def test_hover_says_kind_window_and_size_in_words():
    fig = B.burn_timeline(SMALL, SATS, T0, END)
    text = " ".join(bars(fig, "east-west").hovertext)
    assert "east-west burn" in text and "sometime between" in text and "orbit height changed by +2.00 km" in text
    assert "degrees" in " ".join(bars(fig, "north-south").hovertext)


def cadence_points(fig, sat_index, kind):
    t = [t for t in fig.data if t.name == B.KIND_LABEL[kind] and t.xaxis == f"x{sat_index + 1 if sat_index else ''}"]
    return t[0]


def test_cadence_y_values_are_the_gaps_between_burns_of_the_same_kind():
    fig = B.burn_cadence(SMALL, SATS)
    ew, ns = cadence_points(fig, 0, "east-west"), cadence_points(fig, 0, "north-south")
    assert list(ew.y) == [10, 30]
    assert list(ns.y) == [20]
    assert [pd.Timestamp(x) for x in ew.x] == [T0 + 10 * DAY, T0 + 40 * DAY]   # dated at the burn, not the one before
    assert len(cadence_points(fig, 1, "east-west").y) == 0                    # one burn has no gap


def test_cadence_has_one_cell_per_satellite_and_a_median_line():
    fig = B.burn_cadence(SMALL, SATS)
    assert [a.text for a in fig.layout.annotations] == SATS
    medians = sorted(s.y0 for s in fig.layout.shapes)
    assert medians == [20, 20]     # east-west (10, 30) and north-south (20) both have median 20


def regular(n, step):
    return frame(*[burn("A", "east-west", i * step) for i in range(n)])


def test_summary_numbers_by_hand():
    rows = {(r["satellite"], r["kind"]): r for r in B.cadence_summary(SMALL, SATS)}
    ew = rows[("A", "east-west")]
    assert ew["count"] == 3 and ew["median_days"] == 20 and ew["longest_gap_days"] == 30
    assert ew["iqr_days"] == pytest.approx(10)     # percentiles of [10, 30]: 15 and 25
    assert rows[("A", "north-south")]["longest_gap_days"] == 20
    assert len(rows) == 6                          # two kinds for each of three satellites


def test_summary_pattern_rule():
    steady = B.cadence_summary(regular(6, 30), ["A"])[0]
    assert steady["pattern"] == "regular" and steady["iqr_days"] == 0
    scatter = frame(*[burn("A", "east-west", d) for d in (0, 10, 50, 60, 130, 140)])   # gaps 10, 40, 10, 70, 10
    assert B.cadence_summary(scatter, ["A"])[0]["pattern"] == "irregular"
    assert B.cadence_summary(regular(2, 30), ["A"])[0]["pattern"] == "too few"


def test_pattern_follows_the_stated_thresholds(monkeypatch):
    monkeypatch.setattr(settings, "BURN_REGULAR_MAX_IQR_SHARE", 100)
    scatter = frame(*[burn("A", "east-west", d) for d in (0, 10, 50, 60, 130, 140)])
    assert B.cadence_summary(scatter, ["A"])[0]["pattern"] == "regular"
    monkeypatch.setattr(settings, "BURN_MIN_FOR_PATTERN", 99)
    assert B.cadence_summary(scatter, ["A"])[0]["pattern"] == "too few"


def test_summary_of_a_satellite_without_burns():
    row = next(r for r in B.cadence_summary(SMALL, SATS) if r["satellite"] == "C")
    assert row["count"] == 0 and row["median_days"] is None and row["pattern"] == "too few"


def test_every_colour_comes_from_the_palette():
    allowed = {v.lower() for v in vars(palette).values() if isinstance(v, str) and re.fullmatch(r"#[0-9a-f]{6}", v)}
    for fig in (B.burn_timeline(SMALL, SATS, T0, END), B.burn_cadence(SMALL, SATS)):
        drawn = fig.to_dict()
        drawn["layout"].pop("template")   # plotly's own default theme, whose colours the figure overrides
        used = set(re.findall(r"#[0-9a-fA-F]{6}", str(drawn)))
        assert {c.lower() for c in used} <= allowed


@pytest.mark.parametrize("burns", [pd.DataFrame(), pd.DataFrame(columns=B.COLUMNS)])
def test_empty_frame_still_draws(burns):
    assert B.burn_timeline(burns, SATS, T0, END).layout.xaxis.rangeslider.visible
    assert len(B.burn_cadence(burns, SATS).layout.annotations) == len(SATS)
    assert [r["count"] for r in B.cadence_summary(burns, SATS)] == [0] * 6


def test_timeline_accepts_timezone_aware_times():
    aware = SMALL.assign(window_start=SMALL["window_start"].dt.tz_localize("UTC"),
                         window_end=SMALL["window_end"].dt.tz_localize("UTC"))
    fig = B.burn_timeline(aware, SATS, T0.tz_localize("UTC"), END.tz_localize("UTC"))
    assert len(bars(fig, "east-west").y) == 4
