"""The agreement strip: one small cell per spacecraft, lit by whether sources agree.

Cells are grouped by constellation, each group with its name and count. A
cell's colour comes from its service value, and its hover text says the same
in words, so colour is never the only signal.
"""

from html import escape
from string import Template

from ui import palette
from ui.figures._themed import themed_all

CELL_PX = 14
CELL_GAP_PX = 4

# (start of the service value, css class, colour, the reading in words). Anything else is drawn as idle.
_READINGS = (
    ("agree", "ok", palette.OK, "sources agree"),
    ("disagree", "warn", palette.WARN, "sources disagree"),
    ("not in the catalogue yet", "idle", palette.IDLE, "not in the catalogue yet"),
)
OTHER_CLASS = "idle"

_CSS = Template("""
.astrip { color:$ink; font-family:${font}; }
.astrip-group { margin-top:12px; }
.astrip-group:first-child { margin-top:0; }
.astrip-name { font-size:13px; color:$muted; margin-bottom:6px; }
.astrip-cells { display:flex; flex-wrap:wrap; gap:${gap}px; }
.astrip-cell { width:${cell}px; height:${cell}px; border-radius:4px; display:block; }
.astrip-ok { background:$ok; } .astrip-warn { background:$warn; } .astrip-idle { background:$idle; }
""").substitute(themed_all(), font=palette.FONT, cell=CELL_PX, gap=CELL_GAP_PX)


def _reading(service):
    """Return (css class, reading in words) for a service value."""
    lowered = service.strip().lower()
    for start, css, _, words in _READINGS:
        if lowered.startswith(start):
            return css, words
    return OTHER_CLASS, service or "no reading"


def agreement_legend():
    """Return (colour, text) pairs explaining the three colours."""
    return [(colour, words) for _, _, colour, words in _READINGS]


def _cell(row):
    """One spacecraft as a small square; hovering says its SVN and the reading in words."""
    css, words = _reading(row["service"])
    title = f"{row['svn']} ({row['constellation']}): {words}"
    if row.get("identity"):
        title += f". Identity: {row['identity']}"
    if row.get("remark"):
        title += f". {row['remark']}"
    return f'<span class="astrip-cell astrip-{css}" title="{escape(title)}"></span>'


def _group(name, rows):
    """One constellation: a label with its name and count, then its cells."""
    disagree = sum(1 for r in rows if _reading(r["service"])[0] == "warn")
    note = f", {disagree} disagree" if disagree else ""
    label = escape(f"{name}, {len(rows)}{note}")
    cells = "".join(_cell(r) for r in rows)
    return f'<div class="astrip-group"><div class="astrip-name">{label}</div><div class="astrip-cells">{cells}</div></div>'


def agreement_strip(rows):
    """Return HTML with one cell per row, grouped by constellation in order of first appearance."""
    groups = {}
    for row in rows:
        groups.setdefault(row["constellation"], []).append(row)
    counts = {}
    for row in rows:
        css = _reading(row["service"])[0]
        counts[css] = counts.get(css, 0) + 1
    summary = f"{len(rows)} spacecraft in {len(groups)} constellations: " + ", ".join(
        f"{counts[css]} {words}" for _, css, _, words in _READINGS if css in counts
    )
    body = "".join(_group(name, members) for name, members in groups.items())
    return f'<style>{_CSS}</style><div class="astrip" role="img" aria-label="{escape(summary)}">{body}</div>'
