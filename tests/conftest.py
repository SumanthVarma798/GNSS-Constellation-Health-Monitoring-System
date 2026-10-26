"""Shared by every test: no test reads or writes the real per-user CelesTrak or Space-Track copy, and none asks
GitHub for the published orbit-record check."""
import pytest

from data import celestrak, spacetrack
from ui import data


@pytest.fixture(autouse=True)
def private_celestrak_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(celestrak, "SAVED", tmp_path / "celestrak.json")
    monkeypatch.setattr(spacetrack, "SAVED", tmp_path / "spacetrack.json")
    monkeypatch.setattr(spacetrack, "state", {"rows": {}, "tried": None, "fetched": None, "refused_until": None,
                                              "note": "ok"})
    monkeypatch.setattr(data, "orbit_gap", lambda: {})
