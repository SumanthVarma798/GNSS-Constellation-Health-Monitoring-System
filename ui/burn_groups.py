"""What part of the burn picture a classified burn belongs to (ui/burn_ledger.py, ui/figures/burns.py): the grouping and its
colours, in one place and without Streamlit."""
from analysis.burn_classes import ARTEFACT, DISPOSAL, OFF_PATTERN, RELOCATION, RESPONSE as RESPONSE_CLASS, ROUTINE_EW, ROUTINE_NS
from ui import palette

ROUTINE, PLANNED, RESPONSE, OFF, OPEN = "routine", "planned", "response", "off", "open"   # the picture's groups
ARTEFACT_GROUP = "artefact"
# (group, its words) in the order drawn, left to right. "open" is every burn not judged: only the interval is off, nothing
# explains it, or the verdict is a low-confidence one.
GROUPS = ((ROUTINE, "routine"), (PLANNED, "planned moves"), (RESPONSE, "response"), (OFF, "off pattern"),
          (OPEN, "not judged"))
# The shape variant each group takes in a Plotly figure, added to the kind's circle or diamond, so shape says it as well
# as colour: filled, open, crossed (x), plus (+), open with a dot.
GROUP_SYMBOL = {ROUTINE: "", PLANNED: "-open", RESPONSE: "-x", OFF: "-cross", OPEN: "-open-dot"}
# What each group counts as, said after the burn's kind in a tooltip.
VERDICT = {ROUTINE: "counted: routine", PLANNED: "planned: counted neither way", RESPONSE: "counted: irregular",
           OFF: "counted: irregular", OPEN: "not judged: counted neither way", ARTEFACT_GROUP: "a record error, left out"}
COUNT_KEYS = tuple(key for key, _ in GROUPS) + (ARTEFACT_GROUP,)
CONFIDENCE_WORDS = {"high": "high, every test agrees", "medium": "medium, probably right",
                    "low": "low, a guess: not counted"}


def group_of(burn_class, counted):
    """Which part of the picture one burn belongs to (a counted burn is a decided one at medium confidence or better)."""
    if burn_class == ARTEFACT:
        return ARTEFACT_GROUP
    if burn_class in (RELOCATION, DISPOSAL):
        return PLANNED
    if counted and burn_class in (ROUTINE_EW, ROUTINE_NS):
        return ROUTINE
    if counted and burn_class == RESPONSE_CLASS:
        return RESPONSE
    if counted and burn_class == OFF_PATTERN:
        return OFF
    return OPEN


# The colour of each group in a Plotly figure (palette constants, mapped to the theme); None is drawn outlined and empty.
COLOURS = {ROUTINE: palette.OK, PLANNED: palette.IDLE, RESPONSE: palette.BAD, OFF: palette.WARN}
