"""Shared by every test: no test reads or writes the real per-user CelesTrak or Space-Track copy, and none asks
GitHub for the published orbit-record check or the archive job's orbit copy."""
import os
from pathlib import Path

# A one-off exception, not the norm: the tests below pin dates and scores of one data snapshot, so they read a
# frozen copy while the weekly job refreshes data/. The app and every job read data/. New tests should not lean on it.
os.environ["BUNDLED_DATA_DIR"] = str((Path(__file__).resolve().parent / "fixtures" / "bundled_data").resolve())

import pytest
import requests

from data import celestrak, spacetrack
from ui import data


@pytest.fixture(autouse=True)
def private_celestrak_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(celestrak, "SAVED", tmp_path / "celestrak.json")
    monkeypatch.setattr(spacetrack, "SAVED", tmp_path / "spacetrack.json")
    monkeypatch.setattr(spacetrack, "state", {"rows": {}, "tried": None, "fetched": None, "refused_until": None,
                                              "note": "ok"})
    monkeypatch.setattr(data, "orbit_gap", lambda: {})
    monkeypatch.setattr(data, "fitted_orbits", lambda: {})
    monkeypatch.setattr(celestrak, "fetch_copy", _no_copy)


def _no_copy(norads):
    raise requests.ConnectionError("no orbit copy in tests")
