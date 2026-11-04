"""Questions the team asks the Ask page, each with the facts a right answer must hold.

Each fact is a tuple of accepted spellings, matched without regard to case. `github` marks a question answered from what
GitHub says at the time (merged pull requests), which the offline test cannot check. A question with no facts and
`refuse` set must be refused. The live run is scripts/ask_eval.py; tests/test_assistant.py checks offline that the
material holds every other question's facts.
"""
import re

NOT_IN_MATERIAL = ("isn't in the project's material", "is not in the project's material")

QUESTIONS = [
    {"question": "How often is the news group fetched, and when does the first run of the day start?",
     "facts": [("every 3 hours", "every three hours"), ("00:50",)]},
    {"question": "When are orbit records archived each day?",
     "facts": [("01:15",), ("four times",)]},
    {"question": "What does the RINEX check job do, and where does it publish its results?",
     "facts": [("broadcast",), ("orbit-checks",)]},
    {"question": "At what time does the RINEX check run?",
     "facts": [("06:00", "6:00")]},
    {"question": "Which Healthchecks.io checks does the orbit ages job ping?",
     "facts": [("orbit-ages",), ("orbit-fresh",)]},
    {"question": "Where does the public dashboard get CelesTrak's data from?",
     "facts": [("orbit-data",), ("latest_gnss.json",)]},
    {"question": "How far off its broadcast positions may a fitted orbit record be before the satellite is left out?",
     "facts": [("5 km", "5 kilometres", "5 kilometers", "ORBIT_FIT_MAX_KM = 5")]},
    {"question": "How old must an orbit record be before it raises an alert, and when is it shown as stale?",
     "facts": [("2 days", "two days", "ORBIT_ALERT_DAYS = 2"), ("3 days", "three days", "ORBIT_STALE_DAYS = 3")]},
    {"question": "How long do big archive copies stay in the checkout, and how big is big?",
     "facts": [("14 days",), ("5 MB",)]},
    {"question": "How is QZSS broadcast health read?",
     "facts": [("bit", "bits"), ("IS-QZSS-PNT-005",)]},
    {"question": "What is the minimum gap between two downloads from CelesTrak?",
     "facts": [("2 hours", "two hours")]},
    {"question": "When does the registry update run, and what does it do when the tables change?",
     "facts": [("Sunday", "Sundays"), ("pull request", "pull requests")]},
    {"question": "Where does each archive run write its log line?",
     "facts": [("runs/archive.csv",)]},
    {"question": "How many satellites does the dashboard track?",
     "facts": [("113",)]},
    {"question": "How do I check that the RINEX check is working?",
     "facts": [("orbit-checks",), ("rinex-check",)]},
    {"question": "Where does the console run, and what does the hosting cost?",
     "facts": [("Render",), ("free",)]},
    {"question": "Which pull request added the Ask page, and which one changed archive retention?",
     "facts": [("184",), ("181",)], "github": True},
    {"question": "What is the team's budget for next year?", "facts": [], "refuse": True},
]


def missing_facts(answer, item):
    """The facts an answer lacks, each by its first spelling, matched as whole words ("bit" is not in "orbit"). A question
    to refuse must open with the refusal; anything it adds after that must still name real sources."""
    if item.get("refuse"):
        opening = answer.strip().lower()
        return [] if any(opening.startswith(f"that {s.lower()}") for s in NOT_IN_MATERIAL) else [NOT_IN_MATERIAL[0]]
    return [spellings[0] for spellings in item["facts"]
            if not any(re.search(rf"(?<!\w){re.escape(s)}(?!\w)", answer, re.IGNORECASE) for s in spellings)]
