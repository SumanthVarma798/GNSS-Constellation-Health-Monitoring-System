"""The burn ledger pictures (ui/burn_ledger.py) and the timeline's marks coloured by what each burn was."""
import re

import pandas as pd

from ui import burn_groups, burn_ledger, burn_record, palette
from ui.figures import burns as figures

NOW = pd.Timestamp("2026-11-16")


def _table():
    def row(satellite, kind, days, burn_class, counted, confidence="high", tests="T1 interval: pass, 30 d; T2 size: pass"):
        end = NOW - pd.Timedelta(days=days)
        return {"satellite": satellite, "kind": kind, "window_start": end - pd.Timedelta(hours=10), "window_end": end,
                "when": end, "d_sma_km": 2.0, "d_inc_deg": 0.0, "burn_class": burn_class, "counted": counted,
                "confidence": confidence, "tests": tests, "note": ""}
    return pd.DataFrame([row("A", "east-west", 100, "routine east-west", True), row("A", "north-south", 80, "routine north-south", True),
                         row("A", "east-west", 60, "response", True, "medium"), row("A", "east-west", 40, "unexplained", False, "low"),
                         row("A", "east-west", 20, "relocation", False)])


def test_the_bar_is_one_100_percent_row_with_counts_and_words_and_nothing_for_no_burns():
    record = burn_record.record_of(_table(), NOW)
    bar = burn_ledger.bar(record)

    assert [int(n) for n in re.findall(r'class="lb-seg [a-z]+" style="flex:(\d+)"', bar)] == [2, 1, 1, 1]   # one share each, in order
    for words in ("routine", "planned moves", "response", "not judged"):
        assert words in bar
    assert "1 of 3 burns irregular" in bar and "too few to rate" in bar   # 3 judged burns: under 8
    assert 'role="img" aria-label="Burn record, last 365 days: 2 routine, 1 planned moves, 1 response, 1 not judged"' in bar
    assert burn_ledger.bar(None) == ""


def test_each_satellites_marks_are_in_time_order_with_shape_for_the_kind_and_a_tooltip_with_its_tests():
    html = burn_ledger.satellites(_table(), ["A", "B"], NOW)

    marks = re.findall(r'<i class="bm (ew|ns) (\w+)" role="img"', html)
    assert marks == [("ew", "routine"), ("ns", "routine"), ("ew", "response"), ("ew", "open"), ("ew", "planned")]
    assert "T1 interval: pass, 30 d" in html and "medium, probably right" in html and "low, a guess: not counted" in html
    assert "1 of 3 irregular" in html and "B" not in re.findall(r"<b>([^<]+)</b>", html)   # a satellite with no burns has no row


def test_the_timeline_fills_each_mark_by_what_the_burn_was_and_leaves_those_not_judged_empty():
    table = _table()
    burns = table[figures.COLUMNS]
    figure = figures.burn_timeline(burns, ["A"], NOW - pd.Timedelta(days=200), NOW, table[figures.KIND_COLUMNS])

    east_west = next(trace for trace in figure.data if trace.name == "East-west" and trace.showlegend is not True and trace.x[0] is not None)
    assert list(east_west.marker.color) == [palette.OK, palette.BAD, palette.INK, palette.IDLE]   # routine, response, not judged, planned
    # shape says it too: filled, crossed, open with a dot (not judged), open (planned)
    assert list(east_west.marker.symbol) == ["circle", "circle-x-open", "circle-open-dot", "circle-open"]
    legend = [trace.name for trace in figure.data if trace.showlegend is not False and trace.x[0] is None]
    assert legend == ["East-west", "North-south", "routine", "planned moves", "response", "off pattern", "not judged"]
    assert "response (counted: irregular)" in east_west.hovertext[1] and "Test" in east_west.hovertext[1]
    # without the classes the marks are drawn as before: ink, a dot and an open diamond
    plain = figures.burn_timeline(burns, ["A"], NOW - pd.Timedelta(days=200), NOW)
    assert [trace.marker.symbol for trace in plain.data] == ["circle", "diamond-open"]
    assert burn_groups.group_of("artefact", False) == "artefact"


def test_a_constellation_with_only_neutral_burns_has_nothing_judged_and_is_too_few_to_rate():
    rows = _table()[_table()["burn_class"].isin(["relocation", "unexplained"])]
    record = burn_record.record_of(rows, NOW)

    assert record["decided"] == 0 and record["low"] == 0.0 and record["high"] == 0.0   # no interval, no NaN
    assert burn_record.words(record) == "too few to rate (no judged burns)"
    assert not burn_record.rated(record)
