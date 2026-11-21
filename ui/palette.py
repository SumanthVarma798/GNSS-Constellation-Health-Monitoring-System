"""Every colour in the dashboard, named once.

The look is neumorphic, after CRED's Synth: one platform colour, with a lighter
shadow up and to the left and a darker one down and to the right. There is no
official web version of Synth, so this is an approximation written by hand.

ui/theme.css carries the same values for surfaces. Pictures drawn in Python
(charts, diagrams) take theirs from here. tests/test_ui_palette.py checks that
text and status colours stay readable on the platform.
"""

PLATFORM = "#20242b"   # the surface everything sits on
LIFT = "#2b3039"       # the lighter shadow, up and to the left
SINK = "#14171b"       # the darker shadow, down and to the right
WELL = "#1a1d23"       # a pressed-in area
TRACK = "#3a404b"      # axes, rails and quiet lines in pictures
FILL = "#4a5361"       # a neutral bar or shape in pictures

INK = "#e8ebf1"        # text
MUTED = "#a6afbd"      # secondary text
ACCENT = "#7fb0ff"     # the one accent: a blue lifted from the old navy

# A status is always said in words as well. Colour is never the only signal.
OK = "#74d6a0"
WARN = "#f0c36a"
BAD = "#ff9a94"
IDLE = "#8d96a5"

# The light look (Settings, Theme): the same parts on a pale platform, with the statuses darkened to stay readable.
# Pictures drawn in Python keep the dark values above; ui/theme.py puts these in their place in the browser.
LIGHT = {"platform": "#e4e8ee", "lift": "#ffffff", "sink": "#b8c0cc", "well": "#dbe0e7", "track": "#b3bbc7",
         "fill": "#98a2b1", "ink": "#1d222b", "muted": "#4f5866", "accent": "#2a5cba", "ok": "#17704a",
         "warn": "#7f5100", "bad": "#b1261f", "idle": "#59626f"}

# How a satellite stands against ITS OWN slot, and how each state is drawn.
# Never judge a satellite against the nearest slot: one that drifts onto
# another satellite's slot would then look fine.
SLOT_IN = "in slot"
SLOT_OFF = "off its slot"
SLOT_LEFT = "left its slot"
SLOT_UNKNOWN = "position not known"
SLOT_COLOURS = {SLOT_IN: OK, SLOT_OFF: WARN, SLOT_LEFT: BAD, SLOT_UNKNOWN: IDLE}
SLOT_EMPTY = BAD       # a slot whose own satellite is not on it

# One quiet colour per navigation system, for the master map's cards. Never text, and
# never a status: a card that needs a look also carries a marked sign.
# Each lifecycle step's colour in the Library's lifecycles, the one thing colour means there (step bar, card edge,
# icon, pin): getting there blue, raising the orbit amber, on station violet, working green, before launch and after
# service grey; red is kept for failure. A step's state is said in words too (its tooltip).
LIFECYCLE_STEP_COLOURS = {"built": IDLE, "launch": ACCENT, "separation": ACCENT, "burn": WARN, "gso": "#c9a2ff",
                          "slot": "#c9a2ff", "payload": OK, "service": OK, "end": IDLE, "disposal": IDLE, "note": MUTED}
CONSTELLATION_COLOURS = {"GPS": "#8f9cf0", "Galileo": "#6fc3cf", "GLONASS": "#d98f7a", "BeiDou": "#d3b56b",
                         "NavIC": "#8fcf8a", "QZSS": "#d58fc6"}

# The same hues darker for the light theme: at least 3 to 1 against its platform and well, as a mark must be.
LIGHT_CONSTELLATION_COLOURS = {"GPS": "#4a5bc7", "Galileo": "#1d7a87", "GLONASS": "#a4513a", "BeiDou": "#7f6212",
                               "NavIC": "#3a7f35", "QZSS": "#94457f"}

# Every colour that follows the theme, by its CSS variable's name (ui/theme.py defines both sets on :root).
DARK = {"platform": PLATFORM, "lift": LIFT, "sink": SINK, "well": WELL, "track": TRACK, "fill": FILL, "ink": INK,
        "muted": MUTED, "accent": ACCENT, "ok": OK, "warn": WARN, "bad": BAD, "idle": IDLE}
THEMED_DARK = {**DARK, **{f"sys-{key.lower()}": colour for key, colour in CONSTELLATION_COLOURS.items()}}
THEMED_LIGHT = {**LIGHT, **{f"sys-{key.lower()}": colour for key, colour in LIGHT_CONSTELLATION_COLOURS.items()}}
_AS_VARIABLE = {colour: f"var(--{name})" for name, colour in THEMED_DARK.items()}


def css(colour):
    """A colour for a page or a frame: one that follows the theme becomes its variable (var(--ok)), any other stays.
    A canvas resolves the variable when it draws (the frames' themed())."""
    return _AS_VARIABLE.get(colour, colour)


FONT = '"Avenir Next", "Segoe UI", system-ui, -apple-system, sans-serif'
FONT_NUMBERS = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace'
RADIUS_PX = 20         # surfaces; chips and buttons are fully rounded
