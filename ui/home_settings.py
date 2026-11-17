"""The Home page's words and choices, in one place. Change a value here by pull request; nothing else needs editing.

The numbers marked "our choice" are not from a standard: they are named on the page, in "Need help reading this page?".
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

# "Need help reading this page?": the same order the whole dashboard follows. (icon in ui/icons.py MASKED, heading,
# [(term, words, picture)]). A plain string among the points starts a group under that small heading. words is one
# short line or a list of short bullets. picture, drawn before the term, is an icon name (ui/icons.py MASKED), a
# state's mark ("mark:ok", "mark:warn", "mark:bad", "mark:accent"), "gauge" (a small score ring) or "weights" (the
# mission weights as bars, from ui/limits.py), or "" for none.
HOW = [
    ("radar", "What is measured", [
        "The score",
        ("Score", [("Means", "how healthy a constellation is today, from 0 to 100"),
                   ("Made of", "the three key health attributes: each adds its share of satellites that pass, times "
                               "its weight"),
                   ("The ring", "the constellation's satellites, coloured by state")], "gauge"),
        ("Weights", [("Means", "how much each attribute counts towards the 100; together they make 100%"),
                     ("Set by", "what a failure costs the constellation's users (our choice, open to change)"),
                     ("Regional", "7 or 8 satellites, all in every user's sky, none spare: one bad clock spoils "
                                  "every position fix"),
                     ("Global", "8 to 12 satellites in view: a receiver can leave out one bad clock")], "weights"),
        "The states round the score",
        ("Healthy and in place", [("Means", "its orbit scores 80 or more of 100, and it is where it should be: in its "
                                            "slot, or in step with its plane"),
                                  ("Colours", "our line: green from 80, amber from 60")], "mark:ok"),
        ("Needs a look", [("Means", "still counted, but its orbit scores under 80, or it has left its slot or fallen "
                                    "out of step"),
                          ("Is it a fault?", "not always: it is a reason to look closer, on its own page")],
         "mark:warn"),
        ("Set aside", [("Means", "retired: moved up to a graveyard orbit, above the working ones, after its service "
                                 "ended"),
                       ("Counted?", "in the total, never judged")], "mark:bad"),
        "Key health attributes",
        ("Orbit kept", [("Means", "the satellite is on the orbit it was placed in"),
                        ("Passes when", "every part of its orbit scores 80 or more of 100: its tilt for one held over a "
                                        "longitude; its plane, tilt, height and shape for one in a medium orbit"),
                        ("Why it matters", "a receiver's sums assume that orbit")], "planet"),
        ("Station held", [("Means", "the satellite stays at its own place among the others"),
                          ("Passes when", "it is in its slot and not drifting along the belt, or keeps its spacing in "
                                          "its plane"),
                          ("Why it matters", "coverage depends on where each satellite is; how often it burns to stay "
                                             "there is on its own page")], "satellite"),
        ("Clock steady", [("Means", "the satellite's atomic clock keeps even time"),
                          ("Passes when", "all day, each clock message lands within 30 ns of what the one before "
                                          "predicted (30 ns is our line)"),
                          ("Why it matters", "a position is worked out from time: 1 ns off is 30 cm off")],
         "hourglass"),
        "Extra details",
        ("Says healthy", [("Means", "the health flag each satellite sends about itself"),
                          ("From", "the IGS daily broadcast file, read every day; shown, not scored")], "broadcast"),
        ("Flag matches our check", [("Means", "the operator's flag says healthy exactly where our orbit check does"),
                                    ("Why it matters", "where they differ, one of the two needs a closer look")],
         "circle-check"),
        ("Burns", [("Means", "engine burns found in the last 90 days of public tracking records"),
                   ("Medium orbits", "rarely show any yet: their records are too short")], "rocket"),
    ]),
    ("calculator", "How", [
        ("Two sources, never mixed", ["orbit and station: public tracking records from CelesTrak and Space-Track",
                                      "clock and flag: the IGS daily broadcast file",
                                      "where the two disagree, Worth a look says so"], "database"),
        ("Counted ahead", ["Home's counts are made four times a day", "the headline says when they were made"],
         "hourglass"),
        ("Default limits", ["Home always uses the default limits",
                            "limits moved on a constellation's page apply there only"], "tool"),
        ("Findings by rule", ["each comes from a named rule, never a hand pick; the largest of each rule first",
                              "odd one out: 3 spreads under the median (our line)"], "search"),
    ]),
    ("rocket", "What we are working towards", [
        ("Signals as declared", ["whether each satellite broadcasts every signal its operator declares",
                                 "for example NavIC's L5 and S, and L1 on NVS-01"], "broadcast"),
        ("Measured accuracy", ["how accurate each signal and clock really are",
                               "needs precise orbit and clock products we do not read yet"], "radar"),
        ("New satellites", ["on its way to its slot, or there under 30 days", "named on its card, not yet scored"],
         "satellite"),
        ("Working together", ["open to working with anyone measuring these constellations",
                              "data, methods, or a review of ours"], "quote"),
    ]),
]

# Where to write to us, shown under "Working together". Mail to it goes to the console's Contact inbox through the
# newsletters Worker (cloudflare/newsletters); live since 17 Nov 2026. Set it to "" to hide it if the routing ever stops.
CONTACT_ADDRESS = "contact@opengnss.org"

# The words on a row that "Need help reading this page?" explains: {words on the row: the heading of the card that explains
# them}. On the row they are a link to that card, landing on the point itself when its term is the same words.
HOW_LINKS = {
    "score": "What is measured",
    "flag matches our check": "What is measured",
    "burns": "What is measured",
    "healthy and in place": "What is measured",
    "needs a look": "What is measured",
    "set aside": "What is measured",
    "new, not scored yet": "What we are working towards",
    "orbit kept": "What is measured",
    "station held": "What is measured",
    "clock steady": "What is measured",
    "says healthy": "What is measured",
    "not scored yet": "What we are working towards",
}
