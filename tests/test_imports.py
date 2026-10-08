"""Every module the app loads must import on its own, without network access."""
import importlib

import pytest

MODULES = [
    "config.config",
    "api.celestrak_api",
    "api.spacetrack_api",
    "data.tle_cache",
    "analysis.drift_analysis",
    "analysis.maneuver_detection",
    "analysis.health_assessment",
    "analysis.dop_calculations",
    "analysis.raan_analysis",
    "visualizations.visualization",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    importlib.import_module(name)
