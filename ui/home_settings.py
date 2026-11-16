"""The Home page's words and choices, in one place. Change a value here by pull request; nothing else needs editing.

The numbers marked "our choice" are not from a standard: they are named on the page, in "How to read this page".
"""
from datetime import timedelta

# Home's counts, made four times a day by the archive job (scripts/home_snapshot.py, .github/workflows/archive.yml).
SNAPSHOT_URL = ("https://raw.githubusercontent.com/SumanthVarma798/"
                "GNSS-Constellation-Health-Monitoring-System/orbit-data/home_snapshot.json")
# Older than this and Home counts again itself. Our choice: the job runs every 6 to 7 hours, so one late run is
# covered and two are not.
SNAPSHOT_MAX_AGE = timedelta(hours=14)

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
CAVEATS = {}

# "Worth a look": the rules, in the order their findings are listed. {rule: (name, what it compares)}.
RULES = {
    "silent": ("Tracked but silent", "the satellites we track against the IGS daily broadcast file"),
    "disagree": ("Two sources disagree", "the operator's own health flag against our orbit check"),
    "clock": ("Clock stepped", "each new clock message against what the one before it predicted"),
    "plane": ("Plane out of step", "one orbital plane against its sister planes"),
    "odd": ("Odd one out", "one satellite's score against the others in its constellation"),
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
# [(the term in bold, what to know about it)]). A plain string among the points starts a group under that small
# heading, so a long card reads in parts.
HOW = [
    ("radar", "What is measured", [
        "The score",
        ("Score", "One number out of 100, to compare constellations at a glance: orbit kept, station held and clock "
         "steady, each as the share of the satellites judged on it, added up with weights that suit the "
         "constellation's mission. A measure that could not be read that day is left out and the others count for "
         "its share. The ring round the score splits the constellation's satellites by state."),
        ("Weights", "Regional (NavIC, QZSS): clock 50%, station 30%, orbit 20%. Seven or eight satellites, none spare, "
         "every one in every user's sky: a bad clock corrupts every position fix in the service area with nothing to "
         "stand in, and a satellite off its station moves coverage off the region. Global (GPS, Galileo, GLONASS, "
         "BeiDou-3): clock 40%, orbit 35%, station 25%. Twenty-four to thirty-five satellites, eight to twelve in "
         "view: a receiver can leave out one bad clock, a neighbour covers one satellite out of step, and the orbital "
         "planes and spacing set the coverage everywhere."),
        "The states round the score",
        ("Healthy and in place", "The satellite's orbit, from public tracking records, scores 80 or more out of 100, "
         "and it sits in its slot or keeps step in its orbital plane. The constellation's own page shows every part of "
         "that score."),
        ("Needs a look", "Counted, but not healthy and in place: its orbit scores under 80, or it is out of its slot, "
         "out of step with its plane or off its plane. Its constellation's page says which."),
        ("Set aside", "Moved to a graveyard orbit, away from the working orbit, after its service ended. It is in the "
         "total but not judged."),
        "In the score",
        ("Orbit kept", "The satellite is on the orbit it should be on. For one held over a longitude that is its "
         "tilt; for one in a medium orbit, its plane, tilt, height and shape. Each must score 80 or more."),
        ("Station held", "It is being held there: it is in its slot and not drifting, or in step with the others in "
         "its plane. How often and how evenly it burns to stay there is on the constellation's own page."),
        ("Clock steady", "Through the day, each new clock message landed within 30 ns of what the one before it "
         "predicted. A clock that was reset or is failing steps by far more. 1 ns of clock is 0.3 m of range."),
        "Also on each card",
        ("Says healthy", "The health flag each satellite sends about itself. It is read once a day, with the clock "
         "messages, from the International GNSS Service's daily broadcast file, which holds the navigation "
         "messages its ground stations received."),
        ("Flag matches our check", "Where the operator's own flag says healthy exactly where our orbit check counts the "
         "satellite healthy and in place, and unhealthy where it does not. A flag that is often wrong is worth "
         "knowing before trusting it."),
        ("Burns", "The engine burns found in the last 90 days of public tracking records: how the operator keeps its "
         "satellites in place. Medium-orbit constellations rarely show any yet, because their records do not go back "
         "far enough to find them."),
    ]),
    ("calculator", "How", [
        ("Two sources, never mixed", "Orbit and station come from public tracking records; clock and flag from the "
         "satellites' own broadcast. Where the two disagree, the page says so under Worth a look."),
        ("Default limits", "The counts use the default limits. Limits you move on a constellation's page apply on that "
         "page only."),
        ("Findings by rule", "A finding is raised by a named rule, never picked by hand. The largest finding of "
         "each rule is listed first, then the rest by rule and by size."),
    ]),
    ("alert-triangle", "What is left out", [
        ("Measured accuracy", "How accurate each constellation's signal and clock actually are. That needs precise "
         "orbit and clock products we do not read yet. The flag and the clock messages are what the operator "
         "broadcasts, not a measurement against a reference."),
        ("Our choices", "The score's weights for each mission, the colours (green from 80 in 100, amber from "
         "60), the 30 ns line for a steady clock and "
         "the odd-one-out line (3 spreads under the median) are our choices, not a standard."),
        ("New satellites", "A satellite on its way to its slot, or at its slot for under 30 days, is not scored or "
         "counted yet. Its row names it."),
    ]),
    ("rocket", "What comes next", [
        ("More counts per constellation", "Stated accuracy per constellation, then measured signal error, each as its own count "
         "beside these two."),
    ]),
]

# The words on a row that "How to read this page" explains: {words on the row: the heading of the card that explains
# them}. On the row they are a link to that card, landing on the point itself when its term is the same words.
HOW_LINKS = {
    "score": "What is measured",
    "flag matches our check": "What is measured",
    "burns": "What is measured",
    "healthy and in place": "What is measured",
    "needs a look": "What is measured",
    "set aside": "What is measured",
    "new, not scored yet": "What is left out",
    "orbit kept": "What is measured",
    "station held": "What is measured",
    "clock steady": "What is measured",
    "says healthy": "What is measured",
    "not scored yet": "What is left out",
}
