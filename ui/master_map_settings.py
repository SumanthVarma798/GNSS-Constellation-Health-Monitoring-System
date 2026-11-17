"""The Master map page's words and mappings, in one place. Change a value here by pull request; nothing else needs editing.

Rows follow the constellations as the other pages name them (ui/systems.py SYSTEMS). The registry's name for a
constellation is read from registry/dashboard_systems.csv (evidence/registry_tables.py).
"""

from ui.home_settings import SYSTEMS as WHO

# Every source named in full wherever a reader meets it on this page, never "the catalogue" or "the file":
# {short name the evidence code uses (evidence/settings.py): the name a reader sees}.
IGS = "the IGS satellite metadata file"
GCAT = "GCAT (J. McDowell's catalogue of space objects)"
SOURCE_NAMES = {"IGS satellite file": "IGS satellite metadata file", "GCAT": GCAT,
                "CelesTrak orbit feed": "CelesTrak's orbit feed", "CelesTrak GNSS group": "CelesTrak's GNSS group",
                "our dashboard registry": "this dashboard's list of the satellites it follows"}
ISSUER_NAMES = {"this project's registry": "this dashboard's list of the satellites it follows"}
# How the IGS satellite metadata file and GCAT stand on who a spacecraft is (evidence/settings.py IDENTITY_*).
IDENTITY_WORDS = {"two sources agree": f"{IGS} and GCAT give the same launch designator",
                  "one source only": f"only {IGS} lists it; GCAT does not yet"}
# Each kind of identifier in a few words, for a card's hover tip (evidence/settings.py SCHEME_*).
SCHEME_SHORT = {"US catalogue number (NORAD)": "catalogue number (NORAD)", "Launch designator (COSPAR)": "launch designator",
                "Catalogue of space objects (GCAT)": "GCAT name", "Signal ID today (PRN)": "signal ID",
                "Orbit feed name (CelesTrak)": "CelesTrak name", "Dashboard name": "dashboard name"}
SIGHTING_WORDS ="Stand-in SVN: seen in CelesTrak's GNSS group, not yet in the IGS satellite metadata file"

# What a row's count holds beyond what the other pages follow, said under its dots: {name: one plain sentence}.
NOTES = {"BeiDou-3": "Counts every BeiDou generation on record; the other pages follow BeiDou-3 only."}

# One dot per spacecraft: (kind, what it means, its shape), in the order the legend lists them and the row draws them.
# Each has its own shape (ui/theme.css), as on Home, so the colour only backs it up.
DOTS = [("now", "has a signal ID today", "round"), ("past", "no signal ID today: retired, spare or lost", "small round"),
        ("seen", "seen in CelesTrak's GNSS group, not yet in the IGS satellite metadata file", "ring"),
        ("look", "the IGS satellite metadata file, GCAT or CelesTrak's orbit feed disagree: worth a look", "diamond")]

# The weekly job that rebuilds the registry tables (in .github/workflows/).
REGISTRY_WORKFLOW = "registry-update.yml"

# "Need help reading this page?", in the order every page follows: (icon in ui/icons.py MASKED, heading,
# [(the term in bold, what to know about it)]).
HOW = [
    ("radar", "What is shown", [
        ("Who is who", "Every navigation spacecraft the public records know of, launched or retired, and every name "
         "it goes by. Nothing is measured on this page."),
        ("Signal ID", "The number a satellite broadcasts (its PRN) so receivers can tell it apart. It can pass from an "
         "old satellite to its replacement, so the dashboard keys everything on the physical spacecraft (its SVN)."),
    ]),
    ("calculator", "How", [
        ("Three sources", "The IGS satellite metadata file says which spacecraft exist and which signal ID each holds. "
         "GCAT, J. McDowell's catalogue of space objects, says who owns each one and whether it still works. "
         "CelesTrak's orbit feed gives the name each orbit is published under."),
        ("Disagreements", "Where two of those three disagree, the spacecraft is marked and listed with the two names "
         "and what each says. Neither is taken as right."),
        ("Approved changes", "A weekly job (registry-update) rebuilds the tables from the IGS satellite metadata file and "
         "GCAT. What it finds arrives as a proposal a person approves, so an addition or a removal can show here a "
         "week or more after the source changed."),
    ]),
    ("alert-triangle", "What is left out", [
        ("Service", "Whether a satellite gives a navigation service: the IGS satellite metadata file does not say, and "
         "GCAT's \"still operating\" is not the same thing. Health is on each constellation's Overview."),
        ("Very new satellites", "One the IGS satellite metadata file does not list yet appears only once CelesTrak's "
         "GNSS group names it, under a stand-in SVN."),
        ("GPS names", "CelesTrak writes a GPS satellite's signal ID as \"(PRN 25)\"; that form is not compared with "
         "the IGS satellite metadata file yet."),
    ]),
    ("rocket", "What comes next", [
        ("Last checked", "When the IGS satellite metadata file and GCAT were last checked, not only when they last "
         "changed, once the weekly registry-update job publishes that."),
    ]),
]
