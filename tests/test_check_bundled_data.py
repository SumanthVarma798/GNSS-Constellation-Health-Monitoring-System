"""The bundled-data smoke check script: it should pass against the frozen test snapshot."""

import sys
from datetime import datetime
from pathlib import Path

import time_machine

from test_golden_scores import GOLDEN

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_bundled_data as checker  # noqa: E402


def test_check_bundled_data_passes_on_frozen_fixture(capsys):
    # The frozen snapshot only holds data up to its own date, so the clock is frozen there too.
    with time_machine.travel(datetime.fromisoformat(GOLDEN["frozen_utc"]), tick=False):
        assert checker.main() == 0
    out = capsys.readouterr().out
    for label in checker.CONSTELLATIONS:
        assert f"{label}: satellites assessed=" in out
