"""The Overview for a medium Earth orbit (MEO) system: GPS, GLONASS or Galileo, one row per orbital plane.

Each plane: a strip of its slots and satellites along the orbit, then a tile per satellite in orbit
order. Under the planes, every measure as should be / is, and the 3D view. The numbers come from
analysis/meo_run.py; the nominal values and their sources from config/meo_nominal.py.
"""
from html import escape

import streamlit as st

from analysis.meo_geometry import EXTENDED
from config.config import TRACKED_NOT_IN_REGISTRY
from config.meo_nominal import MEANINGS, NOMINAL
from ui import orbit_section, palette, surfaces
from ui.data import SATELLITES
from ui.figures.plane_strip import plane_strip

HEALTHY_FROM = 80
LABELS = {"plane": "Plane", "spacing": "Spacing", "inclination": "Inclination", "height": "Height",
          "eccentricity": "Eccentricity"}
# For Compare: the parts the other systems do not have, (label, column of the health table).
PARTS = [("Plane", "_plane_score"), ("Spacing", "_spacing_score"), ("Height", "_height_score"),
         ("Eccentricity", "_ecc_score")]


def state_of(row):
    """(palette.SLOT_* state, chip words, degrees off or None) for one satellite: is it where it should be
    along its plane?"""
    checks = {check[0]: check for check in row["checks"]}
    if not row["plane_agrees"]:
        return palette.SLOT_OFF, f"registry says plane {row['registry_plane']}", None
    if "plane" in checks and checks["plane"][4] < 100:
        return palette.SLOT_OFF, f"off its plane, {abs(checks['plane'][3]):.1f}°", abs(checks["plane"][3])
    if "spacing" in checks:
        off = abs(checks["spacing"][3])
        return (palette.SLOT_IN, "in step", None) if checks["spacing"][4] == 100 else \
            (palette.SLOT_OFF, f"out of step, {off:.1f}°", off)
    if row["plane"] == EXTENDED:
        return palette.SLOT_UNKNOWN, "own eccentric orbit", None
    # left out of the gaps (analysis/meo_geometry.py): passing through at another height, or alone in its plane
    if "height" in checks and checks["height"][4] < 100:
        return palette.SLOT_UNKNOWN, "away from its working height", None
    if row["slot_at"] is not None:
        return palette.SLOT_UNKNOWN, "no neighbour to space against", None
    return palette.SLOT_UNKNOWN, f"slot {row['slot']} not listed" if row["slot"] else "no slot given", None


def tiles(result):
    """{name: (tile html, counts as healthy, health row)}, in the order of result["rows"]."""
    health = {h["Satellite"]: h for h in result["health"].to_dict("records")}
    out = {}
    for row in result["rows"]:
        state, words, _ = state_of(row)
        weakest = min(((LABELS[m], s) for m, s in row["parts"].items()), key=lambda part: part[1], default=None)
        html = surfaces.tile(row["name"], row["signal_id"], row["score"], row["status"].split(" ", 1)[-1], words,
                             orbit_section.CHIP_STATUS[state], weakest if weakest and weakest[1] < 100 else None)
        out[row["name"]] = (html, row["score"] >= HEALTHY_FROM and state != palette.SLOT_OFF, health[row["name"]])
    return out


def _value(measure, value):
    if measure == "height":
        return f"{value:,.0f} km"
    if measure == "eccentricity":
        return f"{value:.3f}"
    return f"{value:+.1f}°" if measure == "plane" else f"{value:.1f}°"


def _should_be_table(rows):
    """Every measure of every satellite as 'is / should be', each coloured by its part's band."""
    head = "".join(f"<th>{LABELS[m]}</th>" for m in LABELS)
    lines = []
    for row in rows:
        checks = {check[0]: check for check in row["checks"]}
        cells = "".join(
            '<td class="idle">&ndash;</td>' if m not in checks else
            f'<td class="{surfaces.band(checks[m][4])}">{_value(m, checks[m][2])}'
            f'<span class="muted"> / {"≤ " if m == "eccentricity" and row["plane"] != EXTENDED else ""}'
            f'{_value(m, checks[m][1])}</span></td>' for m in LABELS)
        name = f'{escape(row["name"])} <span class="muted">{escape(row["signal_id"])}</span>'
        lines.append(f"<tr><th>{name}</th>{cells}</tr>")
    meanings = "".join(f"<li>{escape(text)}</li>" for text in MEANINGS.values())
    return (f'<ul class="small meanings">{meanings}<li>Each cell: is / should be.</li></ul>'
            f'<div class="sb-wrap"><table class="sb"><tr><th></th>{head}</tr>{"".join(lines)}</table></div>')


def _sources(system):
    """The documents the nominal values come from, one line each, with how sure we are of them."""
    seen = {}
    for value in NOMINAL[system].values():
        seen.setdefault(value.source.split(", http")[0] if value.label != "our choice" else "Our own tolerances",
                        value.label)
    return "".join(f'<li>{escape(source)} <span class="muted">({label})</span></li>' for source, label in seen.items())


def _gaps(name, result):
    shown = set(result["health"]["Satellite"])
    missing = [s for s in SATELLITES[name] if s not in shown]
    for text in (*result["warnings"], *([f"No orbit data: {', '.join(missing)}"] if missing else []),
                 *([f"Awaiting a registry update: {', '.join(TRACKED_NOT_IN_REGISTRY[name])}"]
                   if TRACKED_NOT_IN_REGISTRY[name] else [])):
        surfaces.show(surfaces.notice(text, "warn"))


def _planes(rows):
    """{plane name: rows in orbit order}, the nominal planes by name and the eccentric pair last."""
    planes = {}
    for row in sorted(rows, key=lambda r: r["u"]):
        planes.setdefault(row["plane"], []).append(row)
    return dict(sorted(planes.items(), key=lambda item: (item[0] == EXTENDED, item[0])))


def _strip(members):
    sats = []
    for row in members:
        state, words, _ = state_of(row)
        sats.append({"label": row["signal_id"], "u": row["u"], "slot_at": row["slot_at"], "state": state,
                     "title": f"{row['name']} ({row['signal_id']}), slot {row['slot'] or 'none'}: {words}"})
    return surfaces.picture(plane_strip(sats))


def page(name, result):
    """The count, the history line, one row per plane, should be / is, the 3D view."""
    shown = tiles(result)
    healthy = sum(ok for _, ok, _ in shown.values())
    surfaces.show(f'<div class="head"><span class="big num">{healthy} of {len(shown)}</span>'
                  '<span class="muted">healthy and in step</span></div>')
    surfaces.show(surfaces.notice(result["history_note"], "idle"))
    _gaps(name, result)
    planes = _planes(result["rows"])
    for plane, members in planes.items():
        tiles_html = f'<div class="tiles meo">{"".join(shown[row["name"]][0] for row in members)}</div>'
        if plane == EXTENDED:   # not a plane of slots: no strip
            surfaces.show(f'<div class="part-title">Eccentric orbit · {len(members)}</div>' + tiles_html)
        else:
            surfaces.show(surfaces.raised(_strip(members), title=f"Plane {plane} · {len(members)}") + tiles_html)
    in_order = [row for members in planes.values() for row in members]
    with st.expander("Should be and is, for every satellite"):
        surfaces.show(_should_be_table(in_order) + f'<ul class="small meanings">{_sources(name)}</ul>')
    rows = [{"name": row["name"], "slot_lon": None, "actual_lon": None, "note": "", "state": state,
             "deviation_deg": off} for row in in_order for state, _, off in [state_of(row)]]
    orbit_section.render_belt(rows, "3D", result["history"], result["health"], name)
