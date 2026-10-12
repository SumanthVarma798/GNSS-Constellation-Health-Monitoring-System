"""Theme variables with a built-in fallback, so a picture looks right on its own.

The page theme defines CSS variables such as --accent and --raised. A picture
that uses one writes var(--accent, #7fb0ff): the theme wins when it is loaded,
and the palette value shows when it is not. Every fallback comes from
ui.palette, so a colour is still named in one place only.
"""

from ui import palette

RAISED = f"-6px -6px 14px {palette.LIFT}, 7px 7px 16px {palette.SINK}"
RAISED_SMALL = f"-3px -3px 8px {palette.LIFT}, 4px 4px 10px {palette.SINK}"
PRESSED = f"inset -3px -3px 7px {palette.LIFT}, inset 4px 4px 9px {palette.SINK}"

_FALLBACKS = {
    "platform": palette.PLATFORM,
    "lift": palette.LIFT,
    "sink": palette.SINK,
    "well": palette.WELL,
    "track": palette.TRACK,
    "fill": palette.FILL,
    "ink": palette.INK,
    "muted": palette.MUTED,
    "accent": palette.ACCENT,
    "ok": palette.OK,
    "warn": palette.WARN,
    "bad": palette.BAD,
    "idle": palette.IDLE,
    "edge": palette.LIFT,  # the theme's hairline is a faint white; the lift colour is its nearest palette match
    "raised": RAISED,
    "raised-sm": RAISED_SMALL,
    "pressed": PRESSED,
    "r": f"{palette.RADIUS_PX}px",
}


def themed(name):
    """Return var(--name, fallback) for one theme variable."""
    return f"var(--{name}, {_FALLBACKS[name]})"


def themed_all():
    """Return every variable as a dict for string.Template, with - turned into _ in the keys."""
    return {name.replace("-", "_"): themed(name) for name in _FALLBACKS}
