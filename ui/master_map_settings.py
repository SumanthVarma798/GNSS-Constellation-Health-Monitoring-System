"""The Master map page's words and mappings, in one place. Change a value here by pull request; nothing else needs editing.

Rows follow the constellations as the other pages name them (ui/systems.py SYSTEMS). The registry names one of them
differently: REGISTRY_NAMES maps the page's name to the registry's.
"""

# The registry's name for a constellation the pages name differently: {page name: registry name}.
REGISTRY_NAMES = {"BeiDou-3": "BeiDou"}

# Who runs each constellation and where it serves, in the Home page's words (ui/home_settings.py): {name: (who, where)}.
WHO = {
    "NavIC": ("India", "regional: India and 1,500 km around"),
    "QZSS": ("Japan", "regional: Japan and Asia-Oceania"),
    "BeiDou-3": ("China", "global, with high orbits over Asia-Pacific"),
    "GPS": ("United States", "global"),
    "GLONASS": ("Russia", "global"),
    "Galileo": ("European Union", "global"),
}

# What a row's count holds beyond what the other pages follow, said under its dots: {name: one plain sentence}.
NOTES = {"BeiDou-3": "Counts every BeiDou generation on record; the other pages follow BeiDou-3 only."}

# One dot per spacecraft: (kind, what it means, its shape), in the order the legend lists them and the row draws them.
# Each has its own shape (ui/theme.css), as on Home, so the colour only backs it up.
DOTS = [("now", "has a signal ID today", "round"), ("past", "no signal ID today: retired, spare or lost", "small round"),
        ("seen", "seen in orbit, not yet in the IGS file", "ring"), ("look", "our sources disagree: worth a look", "diamond")]

# The weekly job that rebuilds the registry tables (in .github/workflows/).
REGISTRY_WORKFLOW = "registry-update.yml"

# "How to read this page", in the order every page follows: (icon in ui/icons.py MASKED, heading,
# [(the term in bold, what to know about it)]).
HOW = [
    ("radar", "What is shown", [
        ("Who is who", "Every navigation spacecraft the public records know of, launched or retired, and every name "
         "it goes by. Nothing is measured on this page."),
        ("Signal ID", "The number a satellite broadcasts (its PRN) so receivers can tell it apart. It can pass from an "
         "old satellite to its replacement, so the dashboard keys everything on the physical spacecraft (its SVN)."),
    ]),
    ("calculator", "How", [
        ("Three sources", "The IGS satellite file says which spacecraft exist and which signal ID each holds; the GCAT "
         "catalogue says who owns it and whether it still works; CelesTrak's orbit feed gives the name its orbit is "
         "published under."),
        ("Disagreements", "Where two sources disagree, the spacecraft is marked and listed. Neither source is taken "
         "as right."),
        ("Approved changes", "A weekly job rebuilds the tables. What it finds arrives as a proposal a person approves, "
         "so an addition or a removal can show here a week or more after the source changed."),
    ]),
    ("alert-triangle", "What is left out", [
        ("Service", "Whether a satellite gives a navigation service: the IGS file does not say, and the catalogue's "
         "\"still operating\" is not the same thing. Health is on each constellation's Overview."),
        ("Very new satellites", "One the IGS file does not list yet appears only once CelesTrak names it, under a "
         "stand-in SVN."),
        ("GPS names", "CelesTrak writes a GPS satellite's signal ID as \"(PRN 25)\"; that form is not compared yet."),
    ]),
    ("rocket", "What comes next", [
        ("Last checked", "When each source was last checked, not only when it last changed, once the weekly job "
         "publishes that."),
    ]),
]
