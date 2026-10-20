"""Settings for the admin page (issue 17): which pull requests wait on a decision, how they are grouped, who may sign in.

Every item on the page is a pull request in the private mirror, and the pull request stays the only record. A pull
request waits on a decision when it carries a label "decision: <kind>". The reading is in evidence/decisions.py, the
page in views/admin.py.

Who may sign in, and the GitHub token the page reads with, are never here: they are in .streamlit/secrets.toml (git
ignores it), under [admin], next to the [auth] block Google sign-in needs. .streamlit/secrets.example.toml shows the
shape.
"""

REPOSITORY = "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System"   # the private mirror, never the team's
LABEL_PREFIX = "decision: "

# Each kind (the label after the prefix) and the group it is shown in. A pull request whose kind is not listed is
# still shown, under OTHER_GROUP, so nothing waiting is hidden. The four news kinds are the labels issue 16 names.
KINDS = {
    "registry update": "Satellites",   # the weekly rebuild from the IGS file (.github/workflows/registry-update.yml)
    "status": "Satellites",
    "slot": "Satellites",
    "signal ID": "Satellites",
    "retirement": "Satellites",
}
GROUPS = ["Sources", "Satellites", "Rules"]   # issue 17's three groups, in the order the page shows them
OTHER_GROUP = "Other kinds"

# An item waiting longer than this is shown as a warning.
WAIT_WARN_DAYS = 14

# GitHub accounts that are the system, not a person, in the words the page uses.
RAISED_BY = {"github-actions[bot]": "the weekly job"}

SECRETS_SECTION = "admin"   # in .streamlit/secrets.toml: allowed = [emails], github_token = "...", accounts = {email = login}

# The three calls the team can make (issue 16), and what each does to the pull request (decided 20 Oct 2026, issue 17):
# the decision is always written on the pull request first, as a comment; then it is merged, left open or closed.
APPROVE, AFTER_CHANGES, REJECT = "approved as proposed", "approved after changes", "rejected"
CHOICES = {APPROVE: "Approve as proposed", AFTER_CHANGES: "Approve after changes", REJECT: "Reject"}
ACTIONS = {APPROVE: "then merges it, once its tests have passed", AFTER_CHANGES: "and leaves it open until the changes are made",
           REJECT: "then closes it"}
DECISION_MARKER = "admin-decision"   # an HTML comment in each decision, so the outcomes can be counted from GitHub
REQUIRED_CHECK = "pytest"            # the Tests job (.github/workflows/tests.yml); it must pass on the commit merged
MERGE_METHOD = "squash"
READ_EVERY_SECONDS = 300    # how long one reading of GitHub is kept before the page reads again
