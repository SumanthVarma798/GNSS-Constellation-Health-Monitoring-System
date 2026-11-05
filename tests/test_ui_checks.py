"""What the checks found: every finding kept, grouped by the outcome its sign gives, worst first, counts first."""
import pandas as pd

from ui import checks

HEALTH = pd.DataFrame([
    {"Satellite": "IRNSS-1B", "Remarks": "Excellent inclination control (±0.02°) | 🔴 E-W maneuver overdue by 12 days"},
    {"Satellite": "IRNSS-1C", "Remarks": "⚠️ High drift - requires correction (🟠 0.080°/day) | ✅ E-W: Consistent pattern "
                                         "(every 40 days) | ✓ Good longitude position (+0.70° from 83.0°)"},
])


def test_findings_are_grouped_by_outcome_worst_first_without_their_signs():
    grouped = checks.by_outcome(HEALTH)

    assert list(grouped) == ["bad", "warn", "ok", "idle"]
    assert grouped["bad"] == {"IRNSS-1B": ["E-W maneuver overdue by 12 days"]}
    assert grouped["warn"] == {"IRNSS-1C": ["High drift - requires correction (0.080°/day)"]}
    assert grouped["ok"] == {"IRNSS-1C": ["E-W: Consistent pattern (every 40 days)",
                                          "Good longitude position (+0.70° from 83.0°)"]}
    assert grouped["idle"] == {"IRNSS-1B": ["Excellent inclination control (±0.02°)"]}


def test_the_summary_and_body_lead_with_the_counts():
    grouped = checks.by_outcome(HEALTH)
    html = checks.body(grouped)

    assert checks.summary(grouped, 2) == "2 satellites · 5 findings · needs attention 1 · to watch 1"
    assert html.startswith('<div class="ck-counts">')
    assert html.index("Needs attention 1") < html.index("To watch 1") < html.index("Within limits 2") < html.index("Notes 1")
    assert html.index("E-W maneuver overdue") < html.index("High drift") < html.index("Good longitude")
