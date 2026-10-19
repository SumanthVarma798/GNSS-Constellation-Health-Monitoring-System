"""Shared by every test: no test reads or writes the real per-user CelesTrak copy."""
import pytest

from data import celestrak


@pytest.fixture(autouse=True)
def private_celestrak_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(celestrak, "SAVED", tmp_path / "celestrak.json")
