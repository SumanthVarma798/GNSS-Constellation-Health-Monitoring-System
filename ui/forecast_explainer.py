"""How the "what should happen next" lines are made, from first principles: one line always visible (the section's
summary), the picture and the reasoning one step deeper (ui/reveal.py). Used once, on Station-keeping.
"""
from html import escape

from ui import palette
from ui.figures.slot_belt import text

ONE_LINE = ("J₂₂ longitude acceleration bends each satellite's drift into a parabola; we fit where it is and how "
            "fast it drifts, carry the parabola forward, and date the next east-west manoeuvre.")

# (term, formula or rule): one short line each, drawn as tiles under the picture
POINTS = [
    ("Longitude acceleration", "λ̈ ≈ −0.0017 sin 2(λ − 75.1°) °/d²: J₂₂ has stable points at 75° E and 105° W (Soop)"),
    ("Drift parabola", "λ = λ₀ + λ̇t + ½λ̈t²; one manoeuvre per cycle, Δλ̇ ≈ 4√(|λ̈|·h) for half-width h"),
    ("Last chance", "deadband edge − 2 d planning; past the edge the correction Δv grows with drift and distance"),
    ("Inputs", "mean longitudes of element sets since the last manoeuvre, λ̈ removed; never the mean-motion formula (J₂ bias)"),
    ("Own deadband", "from its routine E-W manoeuvres (≥ 3 in a year); otherwise 0.8 × ours, and the row says so"),
    ("Not knowable", "the operator's Δv budget and plans: an early manoeuvre or a relocation moves every date"),
]
CONSTANTS = "Constants: analysis/forecast_settings.py and ui/next_step_settings.py, for the team to confirm."


def diagram():
    """The cycle drawn: three routine cycles inside its own box, then the path if no burn is made, out to our box edge."""
    width, top, bottom, own_t, own_b = 600, 30, 176, 92, 112   # the box it keeps is a fifth of ours, as NVS-01's is
    left, cycle, size = 20, 112, 13

    def parabola(start, steps=24, last=1.0):
        pts = []
        for i in range(steps + 1):
            u = last * i / steps
            pts.append((left + cycle * (start + u), own_t + (own_b - own_t) * (2 * u - 1) ** 2))
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    # past the last cycle's end the same curve carries on down: no burn, so it falls on to our box edge
    edge_u = (1 + ((bottom - own_t) / (own_b - own_t)) ** 0.5) / 2
    # the picture is an <img>, which cannot follow the theme: it carries its own dark ground, so its colours read on both
    out = [f'<rect width="{width}" height="{bottom + 34}" rx="14" fill="{palette.WELL}"/>']
    for y, label in ((top, "deadband +0.5°"), (bottom, "deadband −0.5°")):
        out.append(f'<line x1="{left}" x2="{width - 6}" y1="{y}" y2="{y}" stroke="{palette.WARN}" stroke-width="1.5" stroke-dasharray="6 5"/>')
        out.append(text(width - 6, y - 6, label, palette.WARN, size, anchor="end"))
    for y in (own_t, own_b):
        out.append(f'<line x1="{left}" x2="{width - 6}" y1="{y}" y2="{y}" stroke="{palette.TRACK}" stroke-width="1.5"/>')
    out.append(text(width - 6, own_t - 6, "own deadband", palette.MUTED, size, anchor="end"))
    for start in range(3):
        out.append(f'<polyline points="{parabola(start)}" fill="none" stroke="{palette.ACCENT}" stroke-width="2.5"/>')
        out.append(f'<circle cx="{left + cycle * start:.1f}" cy="{own_b}" r="6" fill="none" stroke="{palette.INK}" stroke-width="2"/>')
    x_last = left + cycle * 3
    out.append(f'<circle cx="{x_last:.1f}" cy="{own_b}" r="6" fill="none" stroke="{palette.INK}" stroke-width="2"/>')
    # the way on with no burn: u beyond 1, the same parabola
    pts = " ".join(f"{left + cycle * (2 + u):.1f},{own_t + (own_b - own_t) * (2 * u - 1) ** 2:.1f}"
                   for u in [1 + k * 0.01 for k in range(0, int((edge_u - 1) * 100) + 1)] if own_t + (own_b - own_t) * (2 * u - 1) ** 2 <= bottom)
    out.append(f'<polyline points="{pts}" fill="none" stroke="{palette.MUTED}" stroke-width="2.5" stroke-dasharray="3 5"/>')
    out.append(text(left, (top + own_t) / 2 + 5, "routine cycle: manoeuvre, drift, turn back", palette.MUTED, size, anchor="start"))
    out.append(text(x_last - 8, own_b + 22, "ideal manoeuvre", palette.INK, size, anchor="middle"))
    out.append(text(width - 6, bottom + 18, "uncorrected: reaches the deadband edge", palette.MUTED, size, anchor="end"))
    spoken = escape("A satellite's longitude over time: it cycles between the two edges of its own deadband, each cycle a "
                    "parabola started by an east-west manoeuvre. Uncorrected, it drifts out to the edge of our deadband.", quote=True)
    return (f'<svg viewBox="0 0 {width} {bottom + 34}" role="img" aria-label="{spoken}" '
            f'font-family="{escape(palette.FONT, quote=True)}">' + "".join(out) + "</svg>")


def body():
    """The picture, then one tile per point: its term, then its formula or rule; the sources under them."""
    from ui import surfaces

    tiles = "".join(f'<div class="fx-tile"><b>{escape(term)}</b><span>{escape(rule)}</span></div>' for term, rule in POINTS)
    return (f'<div class="fx-pic">{surfaces.picture(diagram())}</div><div class="fx-tiles">{tiles}</div>'
            f'<p class="fx-src">Sources: Soop, Handbook of Geostationary Orbits (longitude acceleration, manoeuvre sizes); '
            f'Wertz, Space Mission Analysis and Design (north-south station-keeping). {escape(CONSTANTS)}</p>')
