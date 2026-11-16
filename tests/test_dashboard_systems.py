"""The dashboard_systems table: one row per page system, and every tracked satellite lands on exactly one page."""
from evidence.registry_tables import (constellation_names, dashboard_satellites, dashboard_satellites_not_in_registry,
                                       dashboard_systems, read_table, registry_name)
from evidence.settings import REGISTRY_DASHBOARD_SATELLITES_FILE


def test_every_registry_name_is_a_constellation():
    constellations = set(constellation_names().values())

    assert all(row["registry_name"] in constellations for row in dashboard_systems())


def test_every_dashboard_satellite_belongs_to_exactly_one_page_system():
    pages = [row["page_name"] for row in dashboard_systems()]
    shown = [name for page in pages for name in dashboard_satellites(page)]
    shown += [name for page in pages for name in dashboard_satellites_not_in_registry(page)]
    tracked = [row["dashboard_name"] for row in read_table(REGISTRY_DASHBOARD_SATELLITES_FILE)]

    assert len(shown) == len(set(shown)) == len(tracked)
    assert sorted(shown) == sorted(tracked)


def test_registry_name_maps_the_two_beidou_pages_and_leaves_the_others_alone():
    assert registry_name("BeiDou-3") == "BeiDou"
    assert registry_name("BeiDou-3 MEO") == "BeiDou"
    for page in ("NavIC", "QZSS", "GPS", "GLONASS", "Galileo"):
        assert registry_name(page) == page
    assert registry_name("Starlink") == "Starlink"
