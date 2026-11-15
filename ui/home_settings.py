"""The Home page's words and choices, in one place. Change a value here by pull request; nothing else needs editing.

The numbers marked "our choice" are not from a standard: they are named on the page, in "How to read this page".
"""

# Who runs each system and where it serves, for a reader new to them: {system (ui/systems.py): (who, where)}.
SYSTEMS = {
    "NavIC": ("India", "regional: India and 1,500 km around"),
    "QZSS": ("Japan", "regional: Japan and Asia-Oceania"),
    "BeiDou-3": ("China", "global"),
    "GPS": ("United States", "global"),
    "GLONASS": ("Russia", "global"),
    "Galileo": ("European Union", "global"),
}

# What the page does not yet take into account for one system, said in its row: {name: one plain sentence}.
CAVEATS = {
    "GPS": "GPS flies more satellites than its 24 listed slots; the extra ones can read as out of step (issue 226).",
}

# "Worth a look": the rules, in the order their findings are listed. {rule: (name, what it compares)}.
RULES = {
    "silent": ("Tracked but silent", "the satellites we track against the IGS daily broadcast file"),
    "disagree": ("Two sources disagree", "the operator's own health flag against our orbit check"),
    "plane": ("Plane out of step", "one orbital plane against its sister planes"),
    "odd": ("Odd one out", "one satellite's score against the others in its system"),
}
ODD_SPREADS = 3.0        # a score this many spreads under its system's median is the odd one out. Our choice.
ODD_SPREAD_FLOOR = 5.0   # the spread is never taken as less than this many points, so a system of all 100s does
                         # not raise a 99. Our choice.
ODD_NEEDS = 5            # fewer scored satellites than this is too few to call one odd
FINDINGS_SHOWN = 5       # the rest sit in the expandable section

# Findings that are known and expected, so they are counted but not listed first: {(rule, system, satellite or plane):
# why}. Add or remove one by pull request, which is its approval record.
EXPLAINED = {
    ("disagree", "Galileo", "GSAT0201"): "launched into a wrong, eccentric orbit in 2014; flagged by Galileo itself",
    ("disagree", "Galileo", "GSAT0202"): "launched into a wrong, eccentric orbit in 2014; flagged by Galileo itself",
}

# "How to read this page": the same order the whole dashboard follows. (icon in ui/icons.py MASKED, heading,
# [(the term in bold, what to know about it)]).
HOW = [
    ("radar", "What is measured", [
        ("Healthy and in place", "The satellite's orbit, from public tracking records, scores 80 or more out of 100, "
         "and it sits in its slot or keeps step in its orbital plane. The system's own page shows every part of "
         "that score."),
        ("Broadcasting healthy", "The health flag each satellite sends about itself. It is read once a day from the "
         "International GNSS Service's daily broadcast file, which holds the navigation messages its ground "
         "stations received."),
    ]),
    ("calculator", "How", [
        ("Two counts, never mixed", "They come from different sources. Where they disagree, the page says so under "
         "Worth a look."),
        ("Default limits", "The counts use the default limits. Limits you move on a system's page apply on that "
         "page only."),
        ("Findings by rule", "A finding is raised by a named rule, never picked by hand. The largest finding of "
         "each rule is listed first, then the rest by rule and by size."),
    ]),
    ("alert-triangle", "What is left out", [
        ("Measured accuracy", "How accurate each system's signal actually is. That needs precise orbit and clock "
         "products we do not read yet. The broadcast flag is what the operator states, not a measurement."),
        ("Our choices", "The colours (green from 80 in 100, amber from 60) and the odd-one-out line (3 spreads "
         "under the median) are our choices, not a standard."),
        ("Settling in", "A satellite still moving to its slot is not counted until it arrives."),
    ]),
    ("rocket", "What comes next", [
        ("More counts per system", "Stated accuracy per system, then measured signal error, each as its own count "
         "beside these two."),
    ]),
]
