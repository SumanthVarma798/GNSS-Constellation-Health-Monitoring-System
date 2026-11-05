"""The dashboard's type scale, named once.

Six levels. Each is told apart by size, weight and colour together, never size alone. Accent is
kept for the key number, the one thing a page wants seen first. Sizes grow smoothly from a phone
(375px wide) to a desktop (1280px and wider) and stop there.

ui/theme.py turns these into CSS variables on :root: --fs-<level> (size), --fw-<level> (weight)
and --fc-<level> (colour). The canvases get the same :root, so they share the scale.
"""

PHONE_PX = 375
DESKTOP_PX = 1280

# level -> (size on a phone in px, size on a desktop in px, weight, colour variable)
LEVELS = {
    "title": (24, 30, 700, "ink"),      # the page's own title
    "section": (18, 22, 700, "ink"),    # a section of the page
    "side": (15, 17, 600, "ink"),       # a side heading inside a section
    "body": (14, 15, 400, "ink"),       # running text, table cells
    "small": (12, 13, 400, "muted"),    # captions, column heads, keys and chart labels
    "num": (24, 32, 700, "accent"),     # a key number, in the number typeface
}


def fluid(phone_px, desktop_px):
    """A CSS size that is phone_px on a phone, desktop_px on a desktop, and in proportion between.

    Written in rem so the reader's own browser text size still scales it."""
    slope = (desktop_px - phone_px) / (DESKTOP_PX - PHONE_PX)
    base = phone_px - slope * PHONE_PX
    return f"clamp({phone_px / 16:g}rem, {base / 16:.4g}rem + {slope * 100:.4g}vw, {desktop_px / 16:g}rem)"


def variables():
    """CSS variable name -> value, for every level."""
    out = {}
    for level, (phone, desktop, weight, colour) in LEVELS.items():
        out[f"fs-{level}"] = fluid(phone, desktop)
        out[f"fw-{level}"] = str(weight)
        out[f"fc-{level}"] = f"var(--{colour})"
    return out
