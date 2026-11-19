"""Signal IDs that changed spacecraft: notices set the reason they give, and the cases brought forward."""
from evidence.master_map import signal_id_changes
from evidence.registry_settings import REGISTRY_SIGNAL_IDS_FILE
from evidence.registry_tables import read_table
from ui import signal_id_history as sih


def _items():
    return sih.with_notices(signal_id_changes(read_table(REGISTRY_SIGNAL_IDS_FILE)))


def test_the_beidou_notice_makes_the_april_2026_c01_change_a_reassignment_and_leaves_2020_alone():
    c01 = next(item for item in _items() if item["signal_id"] == "C01")
    (first, second) = c01["changes"]
    assert (first["kind"], first["notices"]) == ("replaced", [])   # 2020: the table alone speaks
    assert second["kind"] == "reassigned"
    assert {n.id for n in second["notices"]} == {"beidou3-signal-ids", "beidou3-slot-swap"}   # C231 is G4


def test_brought_forward_most_holders_then_a_swap_then_a_notice_then_another_constellation():
    picked = [(item["signal_id"], why) for item, why in sih.featured(_items())]
    assert picked[:3] == [("G04", "7 spacecraft"), ("C59", "swap"), ("C01", "notice")]
    assert picked[3][0][0] == "R" and len(picked) == 4   # C62, C59's pair, is not shown again


def test_a_row_with_no_start_date_does_not_fail_the_axis():
    from datetime import date
    from ui import signal_id_history
    x, ticks = signal_id_history._axis("", date(2026, 11, 19))
    assert 0 <= x("2026-06-01") <= 100
