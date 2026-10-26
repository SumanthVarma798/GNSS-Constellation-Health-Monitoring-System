"""Shared by every test: no test reads or writes the real per-user CelesTrak or Space-Track copy."""
import pytest

from data import celestrak, spacetrack


@pytest.fixture(autouse=True)
def private_celestrak_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(celestrak, "SAVED", tmp_path / "celestrak.json")
    monkeypatch.setattr(spacetrack, "SAVED", tmp_path / "spacetrack.json")
    monkeypatch.setattr(spacetrack, "state", {"rows": {}, "tried": None, "fetched": None, "refused_until": None,
                                              "note": "ok"})
