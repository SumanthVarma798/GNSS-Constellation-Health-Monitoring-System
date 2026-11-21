"""The words the Overview draws with, named once: the technical term for each score part, and the satellite states.

Each part is named on the page by its technical term (ui/measures.py COLUMNS defines each in the shared tooltip).
"""

# A score part's label (analysis/score_rules.py SCORE_PARTS, ui/meo_overview.py LABELS) to its technical term.
PART_TERMS = {
    "Inclination": "inclination", "Drift": "longitude drift rate", "Longitude": "mean longitude",
    "Upkeep": "manoeuvre cadence", "Regularity": "manoeuvre regularity",
    # medium orbits, judged by plane
    "Plane": "RAAN offset", "Spacing": "along-track spacing", "Height": "semi-major axis", "Eccentricity": "eccentricity",
}

# The four score bands (analysis/score_rules.py STATUS_FROM) as the state bar draws them: the band's class, and whether
# its segment is hatched (Critical shares Degraded's colour, so shape tells them apart).
STATE_CLASS = {"Healthy": "ok", "Fair": "warn", "Degraded": "bad", "Critical": "bad crit"}

# Said for a satellite whose slot in our table is in doubt (ui/next_step.py's confirm flag; docs/team-confirm-slots.md).
SLOT_CONFIRM = "slot to confirm"
SLOT_CONFIRM_WHY = ("Kept steadily {off:.1f}° from the slot in our table for 90 days or more: the table may be out of "
                    "date. Judged against the table until the team confirms it.")
