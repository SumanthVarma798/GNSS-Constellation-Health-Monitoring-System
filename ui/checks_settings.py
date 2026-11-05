"""What the checks found, on the Overview: how a finding's sign gives its outcome, and the outcomes' names.

The health assessment (analysis/health_assessment.py) starts some findings with a sign: 🔴 needs attention now,
⚠️ to watch, ✅ or ✓ within limits. A finding with any other sign (ℹ️, 📊, ⏱️, 📈, 📉) or none is a note.
"""

# A finding's first character -> its outcome, a status of ui/surfaces.py. Anything else is a note ("idle").
SIGN_OUTCOME = {"🔴": "bad", "⚠": "warn", "✅": "ok", "✓": "ok"}
# The outcomes in the order shown, worst first, with each one's name.
OUTCOMES = {"bad": "Needs attention", "warn": "To watch", "ok": "Within limits", "idle": "Notes"}
