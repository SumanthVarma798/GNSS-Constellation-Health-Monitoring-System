"""The navigation under the top bar: the pages across every system and the systems first, then one system's pages."""
import pytest

from test_dashboard_shell import (celestrak_answers_with_nothing_new, run,  # noqa: F401 (fixtures)
                                  segmented_controls_rerun)
from ui import shell, systems


@pytest.fixture(autouse=True)
def the_dashboard_opens_on_home(monkeypatch):
    monkeypatch.setattr(shell, "DEFAULT_PAGE", shell.HOME)


def group(at, key):
    return next(w for w in at.get("button_group") if w.key == key)


def keys(at):
    return {w.key for w in at.get("button_group")} | {b.key for b in at.button}


def options(at, key):
    return [option.content for option in group(at, key).options]


PATHS = dict(shell.PAGES)


def on(scope, page):
    """Arrive on `page` with `scope` chosen. AppTest keeps its own note of the page, so it is told of the switch."""
    def setup(at):
        at.session_state["scope"] = scope
        at.switch_page(PATHS[page]).run()
    return setup


def test_home_offers_the_pages_across_every_system_and_the_systems_with_no_system_chosen():
    at = run()

    assert group(at, "nav_all").value == shell.HOME and options(at, "nav_all") == shell.ALL_PAGES
    assert options(at, "nav_system") == list(systems.SYSTEMS) and not group(at, "nav_system").value
    assert not group(at, "nav_page").value                       # the second row is closed: none of its pages is chosen
    assert not {"compare_toggle", "nav_part"} & keys(at)         # and nothing that filters one system's page is drawn


def test_choosing_a_system_opens_its_overview_and_the_second_row():
    at = run(lambda at: group(at, "nav_system").set_value("GPS"))

    assert (at.session_state["scope"], at.session_state["page"]) == ("GPS", "Overview")
    assert group(at, "nav_page").value == "Overview" and options(at, "nav_page") == shell.SYSTEM_PAGES
    assert group(at, "nav_system").value == "GPS" and not group(at, "nav_all").value   # one page chosen across the rows
    assert "compare_toggle" in keys(at)


def test_a_system_of_two_parts_offers_them_one_step_deeper_and_a_system_of_one_part_does_not():
    def medium_orbit(at):
        on("BeiDou-3", "Overview")(at)
        group(at, "nav_part").set_value("BeiDou-3 MEO")

    at = run(medium_orbit)

    assert at.session_state["scope"] == "BeiDou-3 MEO" and group(at, "nav_system").value == "BeiDou-3"
    assert options(at, "nav_part") == ["IGSO & GEO", "MEO"]
    assert "nav_part" not in keys(run(on("NavIC", "Overview")))


def test_coming_back_to_a_system_returns_to_the_page_last_read_for_one():
    assert run(on("GPS", "Geometry")).session_state["system_page"] == "Geometry"   # a system's page is remembered

    def back_from_home(at):
        at.session_state["system_page"] = "Geometry"
        group(at, "nav_system").set_value("Galileo")

    at = run(back_from_home)

    assert (at.session_state["scope"], at.session_state["page"]) == ("Galileo", "Geometry")


def test_another_system_chosen_on_a_systems_page_keeps_the_page():
    def other(at):
        on("NavIC", "Station-keeping")(at)
        group(at, "nav_system").set_value("QZSS")

    at = run(other)

    assert (at.session_state["scope"], at.session_state["page"]) == ("QZSS", "Station-keeping")


def test_every_part_belongs_to_one_system_in_the_top_bars_order():
    assert [part for parts in systems.SYSTEMS.values() for part in parts] == list(shell.CONSTELLATIONS)
    assert systems.system_of("BeiDou-3 MEO") == "BeiDou-3" and systems.part_name("BeiDou-3 MEO") == "MEO"
    assert systems.system_of("GPS") == "GPS" and systems.part_name("GPS") == ""
