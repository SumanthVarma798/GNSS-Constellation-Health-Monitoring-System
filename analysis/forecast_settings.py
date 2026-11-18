"""Constants for slot-forecasting and fuel planning.

All values are centralized here so the forecast engine remains pure and
auditable. Comments include source and confidence notes.
"""

from analysis.score_rules import SLOT_ALLOWED, SLOT_ALLOWED_TILTED

# GEO drift and tangential-burn conversion constants
# Source: standard GEO two-body linearization around geostationary altitude.
A_GEO_KM = 42164.0
DRIFT_PER_KM = -0.012842  # deg/day per km of semi-major axis (lower a drifts east)
DV_PER_KM = 0.03646  # m/s per km, tangential burn delta-v = (n/2) * delta-a
DRIFT_PER_MS = 0.352  # deg/day per m/s (from DRIFT_PER_KM and DV_PER_KM)

# Triaxial gravity longitude dynamics
# Source: Soop, Handbook of Geostationary Orbits. Derived from J22 ~= 1.8157e-6,
# lambda22 ~= -14.9 deg. Moderate confidence pending internal calibration.
TRIAX_K = 0.0017  # deg/day^2, longitude acceleration amplitude
STABLE_LON = 75.1  # degE (stable points near 75E and 105W)

# North-south station-keeping
# Source: Soop; Wertz SMAD.
NS_DV_PER_DEG = 53.7  # m/s per degree of inclination at GEO (Vc = 3.0747 km/s)
NS_GROWTH_DEG_PER_YEAR = (0.75, 0.95)  # luni-solar cycle range over 18.6 years

# Inclined-geometry scaling for drift forcing
# Source: Kaula inclination function. Confidence: moderate, team to confirm.
IGSO_K_SCALE_CONFIDENCE = "moderate confidence, team to confirm"

def igso_k_scale(inclination_deg):
    """Return Kaula scaling factor ((1 + cos i)^2)/4 for inclined cases."""
    import math

    return ((1.0 + math.cos(math.radians(inclination_deg))) ** 2) / 4.0


# Operational choices and imported box definitions
PLANNING_LEAD_DAYS = 2  # team planning choice
DASHBOARD_BOX_GEO_DEG = SLOT_ALLOWED["GEO"]  # imported from score rules, do not duplicate
DASHBOARD_BOX_TILTED_DEG = SLOT_ALLOWED_TILTED

# Fuel priors for class-level lifetime banding (not operator-specific)
FUEL_PRIOR_M_S_PER_YEAR = 50
FUEL_PRIOR_RESERVE = 1.1
EOL_RAISE_M_S = (7, 11)  # 200-300 km raise, typical for this class
FUEL_BUDGET_CONFIDENCE = (
    "typical for this class of satellite; the operator's real budget is not public"
)
