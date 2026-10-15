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
CONSTELLATION_COLOURS = {"GPS": "#8f9cf0", "Galileo": "#6fc3cf", "GLONASS": "#d98f7a", "BeiDou": "#d3b56b",
                         "NavIC": "#8fcf8a", "QZSS": "#d58fc6"}

FONT = '"Avenir Next", "Segoe UI", system-ui, -apple-system, sans-serif'
FONT_NUMBERS = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace'
RADIUS_PX = 20         # surfaces; chips and buttons are fully rounded
