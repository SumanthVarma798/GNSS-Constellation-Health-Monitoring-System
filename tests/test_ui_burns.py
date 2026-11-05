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


def marks(fig, kind):
    return next(t for t in fig.data if t.name == B.KIND_LABEL[kind])


def test_each_burn_is_a_mark_on_its_satellites_row_at_the_middle_of_its_window():
    fig = B.burn_timeline(SMALL, SATS, T0, END)
    ew, ns = marks(fig, "east-west"), marks(fig, "north-south")
    assert list(fig.layout.yaxis.ticktext) == SATS
    assert list(ew.y) == [0, -1, 0, 0] and list(ns.y) == [0, 0]     # in time order: A, B, A, A; A's row is 0
    assert [pd.Timestamp(x) for x in ns.x] == [T0 + 5 * DAY, T0 + 25 * DAY]
    assert (ew.marker.symbol, ns.marker.symbol) == ("circle", "diamond-open")


def test_hover_card_gives_the_title_then_when_how_much_and_the_gap():
    fig = B.burn_timeline(SMALL, SATS, T0, END)
    last = marks(fig, "east-west").hovertext[3]                      # A's east-west burn on day 40
    assert last.startswith("<b>A · east-west burn</b>")
    assert last.index("When") < last.index("Change") < last.index("Gap")
    assert "9 Feb 2026 00:00 – 11 Feb 00:00 UTC (2.0 days)" in last and "orbit height +2.00 km" in last
    assert "30 d after the one before, usually 20 d" in last
    assert "first in view" in marks(fig, "east-west").hovertext[0]
    assert "tilt +0.200°" in marks(fig, "north-south").hovertext[0]


def test_row_end_gives_the_days_since_the_last_east_west_burn_in_the_warning_colour_only_when_late():
    on_time, late = B.burn_timeline(SMALL, SATS, T0, T0 + 50 * DAY), B.burn_timeline(SMALL, SATS, T0, T0 + 70 * DAY)
    assert [a.text for a in on_time.layout.annotations] == ["10 d", "47 d", "–"]   # nothing else written on it
    assert {a.font.color for a in on_time.layout.annotations} == {palette.MUTED}
    first = late.layout.annotations[0]
    assert first.text == "30 d" and first.font.color == palette.WARN and "Late" in first.hovertext
    stretch = next(s for s in late.layout.shapes if s.line.width == 3)               # A's, from its last burn
    assert stretch.line.color == palette.WARN and pd.Timestamp(stretch.x0) == T0 + 40 * DAY


def test_satellite_names_are_escaped_for_plotly():
    fig = B.burn_timeline(frame(burn("<b>X", "east-west", 3)), ["<b>X"], T0, END)
    assert list(fig.layout.yaxis.ticktext) == ["&lt;b&gt;X"]
    assert marks(fig, "east-west").hovertext[0].startswith("<b>&lt;b&gt;X")


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
    drawn = B.burn_timeline(SMALL, SATS, T0, END).to_dict()
    drawn["layout"].pop("template")   # plotly's own default theme, whose colours the figure overrides
    used = set(re.findall(r"#[0-9a-fA-F]{6}", str(drawn)))
    assert {c.lower() for c in used} <= allowed


@pytest.mark.parametrize("burns", [pd.DataFrame(), pd.DataFrame(columns=B.COLUMNS)])
def test_empty_frame_still_draws(burns):
    assert len(B.burn_timeline(burns, SATS, T0, END).layout.annotations) == len(SATS)
    assert [r["count"] for r in B.cadence_summary(burns, SATS)] == [0] * 6


def test_timeline_accepts_timezone_aware_times():
    aware = SMALL.assign(window_start=SMALL["window_start"].dt.tz_localize("UTC"),
                         window_end=SMALL["window_end"].dt.tz_localize("UTC"))
    fig = B.burn_timeline(aware, SATS, T0.tz_localize("UTC"), END.tz_localize("UTC"))
    assert len(marks(fig, "east-west").y) == 4


def test_rhythm_by_hand():
    on_time, late = B.rhythm(SMALL, SATS, T0 + 50 * DAY), B.rhythm(SMALL, SATS, T0 + 70 * DAY)
    a = on_time[0]
    assert [r["satellite"] for r in on_time] == SATS
    assert (a["median_days"], a["q1_days"], a["q3_days"]) == (20, 15, 25)   # gaps 10 and 30
    assert a["since_days"] == 10 and a["due_in_days"] == 10 and a["late"] is False and a["ns_count"] == 2
    assert late[0]["due_in_days"] == -10 and late[0]["late"] is True         # 30 days on, past the upper quartile


def test_rhythm_without_an_interval():
    _, b, c = B.rhythm(SMALL, SATS, (T0 + 13 * DAY).tz_localize("UTC"))
    assert b["since_days"] == 10 and b["due_in_days"] is None and b["late"] is None   # one burn: no interval
    assert c["since_days"] is None and c["count"] == 0
