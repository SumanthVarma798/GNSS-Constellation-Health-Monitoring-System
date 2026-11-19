"""Expected burns as ghost marks on the burn timeline (ui/figures/burns.py burn_timeline), added after it is made.

A downward triangle in the accent colour is the ideal manoeuvre, a thin cross in the warning colour the last chance:
shapes no past burn uses, so an expected mark is never read as one that happened. They
sit past the data's end, so the time axis is lengthened to hold the furthest. The base figure is copied, never changed
(the timeline is kept between runs).
"""
import pandas as pd
import plotly.graph_objects as go

from ui import palette
from ui.tooltip import PLOTLY_HOVER, plotly_card

SYMBOL = {"ideal": "triangle-down", "last chance": "x-thin-open"}
COLOUR = {"ideal": palette.ACCENT, "last chance": palette.WARN}
WORDS = {"ideal": "Expected: ideal manoeuvre", "last chance": "Expected: last chance"}
MEANS = {"ideal": "where its own drift cycle puts the next east-west manoeuvre",
         "last chance": "the last manoeuvre that keeps it inside our deadband: the edge less two days of planning"}


def add_expected(fig, expected, satellites, end):
    """A copy of `fig` with one ghost trace per kind. `end` is the data's last day. `expected` is next_step.expected_burns's
    [(satellite, kind, date, delta_v m/s)]; only the satellites drawn in the timeline's rows are marked."""
    rows = {name: -i for i, name in enumerate(satellites)}
    expected = [e for e in expected if e[0] in rows]
    if not expected:
        return fig
    out = go.Figure(fig)
    out.update_layout(hoverlabel=PLOTLY_HOVER)
    for kind, symbol in SYMBOL.items():
        mine = [e for e in expected if e[1] == kind]
        if not mine:
            continue
        out.add_trace(go.Scatter(
            x=[e[2] for e in mine], y=[rows[e[0]] for e in mine], mode="markers", name=WORDS[kind], cliponaxis=False,
            hoverinfo="text", hovertext=[plotly_card(f"{e[0]} · {WORDS[kind].lower()}", ("When", f"{e[2].day} {e[2]:%b %Y}"),
                                                     ("Δv", f"about {e[3]:.2f} m/s"), ("Means", MEANS[kind]),
                                                     ("Caveat", "it changes if the operator manoeuvres")) for e in mine],
            marker={"symbol": symbol, "size": 11, "color": COLOUR[kind], "line": {"color": COLOUR[kind], "width": 2}}))
    out.update_xaxes(range=[out.layout.xaxis.range[0], max(max(e[2] for e in expected), pd.Timestamp(end)) + pd.Timedelta(days=2)])
    return out
