"""How the "what should happen next" lines are made, from first principles: one line always visible (the section's
summary), the picture and the reasoning one step deeper (ui/reveal.py). Used once, on Station-keeping.
"""
from html import escape

from ui import palette
from ui.figures.slot_belt import text

ONE_LINE = ("A satellite near its slot is pulled along the equator and drifts on a parabola; we read where it is, "
            "follow that curve forward, and say when a burn is due.")

POINTS = [
    ("The pull", "The Earth's equator is slightly oval, so a satellite in geostationary orbit is pulled along it towards "
                 "the nearer of two stable points, 75° E and 105° W. The pull is at most about 0.0017° of longitude "
                 "a day each day, and is nothing at the stable and the unstable points (Soop, Handbook of Geostationary Orbits)."),
    ("A parabola", "With a steady pull, position follows x = x₀ + vt + ½at². A satellite that has just burned drifts "
                   "out to the far side of its box, is stopped there by the pull, and falls back: one cycle, then it burns "
                   "again. A burn changes the drift by about 4√(a·h) for a box half-width h, so the box a satellite keeps "
                   "itself in can be read from the size of its routine burns."),
    ("Cheap fuel, costly time", "A routine burn is a fraction of a metre a second, small against a budget of tens of "
                                "metres a second a year. What does the damage is time off station: past the box edge "
                                "the correction grows quickly with both the drift and the distance. So the last chance "
                                "is the day the satellite leaves our box, less two days to plan."),
    ("What we read", "Where it is and how fast it drifts come from the mean longitudes of its newest element sets since "
                     "its last burn, with the pull taken out (never from the mean-motion formula, which carries the "
                     "Earth's flattening as a bias). Its own box comes from its routine east-west burns; with fewer "
                     "than three, 0.8 of ours is assumed and the line says so."),
    ("What we cannot know", "The operator's fuel budget (we show the yearly use and a band that is typical for this "
                            "class of satellite) and the operator's plans: a burn made early, a relocation or a "
                            "pause changes every date. Each line says when it was worked out and from what."),
    ("The numbers", "Every constant is named in analysis/forecast_settings.py and ui/next_step_settings.py, "
                    "for the team to confirm."),
]


def diagram():
    """The cycle drawn: three routine cycles inside its own box, then the path if no burn is made, out to our box edge."""
    width, top, bottom, own_t, own_b = 600, 34, 200, 106, 126   # the box it keeps is a fifth of ours, as NVS-01's is
    left, cycle, size = 20, 112, 20

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
    for y, label in ((top, "our box"), (bottom, "our box")):
        out.append(f'<line x1="{left}" x2="{width - 6}" y1="{y}" y2="{y}" stroke="{palette.WARN}" stroke-width="1.5" stroke-dasharray="6 5"/>')
        out.append(text(width - 6, y - 6, label, palette.WARN, size, anchor="end"))
    for y in (own_t, own_b):
        out.append(f'<line x1="{left}" x2="{width - 6}" y1="{y}" y2="{y}" stroke="{palette.TRACK}" stroke-width="1.5"/>')
    out.append(text(width - 6, own_t - 6, "its own box", palette.MUTED, size, anchor="end"))
    for start in range(3):
        out.append(f'<polyline points="{parabola(start)}" fill="none" stroke="{palette.ACCENT}" stroke-width="2.5"/>')
        out.append(f'<circle cx="{left + cycle * start:.1f}" cy="{own_b}" r="6" fill="none" stroke="{palette.INK}" stroke-width="2"/>')
    x_last = left + cycle * 3
    out.append(f'<circle cx="{x_last:.1f}" cy="{own_b}" r="6" fill="none" stroke="{palette.INK}" stroke-width="2"/>')
    # the way on with no burn: u beyond 1, the same parabola
    pts = " ".join(f"{left + cycle * (2 + u):.1f},{own_t + (own_b - own_t) * (2 * u - 1) ** 2:.1f}"
                   for u in [1 + k * 0.01 for k in range(0, int((edge_u - 1) * 100) + 1)] if own_t + (own_b - own_t) * (2 * u - 1) ** 2 <= bottom)
    out.append(f'<polyline points="{pts}" fill="none" stroke="{palette.MUTED}" stroke-width="2.5" stroke-dasharray="3 5"/>')
    out.append(text(left, (top + own_t) / 2 + 8, "routine cycle: burn, drift, fall back", palette.MUTED, size, anchor="start"))
    out.append(text(x_last - 8, own_b + 30, "ideal burn", palette.INK, size, anchor="middle"))
    out.append(text(width - 6, bottom + 22, "no burn: reaches our edge", palette.MUTED, size, anchor="end"))
    spoken = escape("A satellite's longitude over time: it cycles between the two edges of its own box, each cycle a "
                    "parabola started by a burn. With no burn it keeps going out to the edge of our box.", quote=True)
    return (f'<svg viewBox="0 0 {width} {bottom + 34}" role="img" aria-label="{spoken}" '
            f'font-family="{escape(palette.FONT, quote=True)}">' + "".join(out) + "</svg>")


def body():
    """The picture, then each point: its term, then its words."""
    from ui import surfaces

    points = "".join(f"<li><b>{escape(term)}</b> {escape(words)}</li>" for term, words in POINTS)
    return (surfaces.picture(diagram()) + f'<ul class="small meanings">{points}</ul>'
            '<p class="small">Sources: Soop, Handbook of Geostationary Orbits (the pull and the burn sizes); Wertz, '
            "Space Mission Analysis and Design (north-south station keeping).</p>")
