"""The ferris-wheel picker's value handling (ui/components/ferris.py), as st.selectbox's callers expect it."""
from ui.components.ferris import chosen, take

CITIES = ["Beijing", "Hyderabad", "Tokyo"]


def test_the_picker_stands_at_the_value_kept_else_the_placeholder_or_the_first_choosable_option():
    assert chosen(CITIES, "Tokyo") == "Tokyo"
    assert chosen(CITIES, "Atlantis") == "Beijing" and chosen(CITIES, None) == "Beijing"
    assert chosen(CITIES, None, placeholder="Choose a city") is None
    assert chosen([30, 90, 182], 182, disabled=[182]) == 30          # a struck-through option is never stood at
    assert chosen([30], 30, disabled=[30]) is None


def test_a_pick_from_the_frame_sets_the_value_and_a_stale_or_bad_one_is_ignored():
    state = {"place": "Beijing"}
    assert take(state, "place", CITIES, {"i": 2, "n": 1}) and state["place"] == "Tokyo"
    assert not take(state, "place", CITIES, None)                    # nothing picked yet
    assert not take(state, "place", CITIES, {"i": 5, "n": 2})        # the list changed under an old pick
    assert not take(state, "place", CITIES, {"i": 0, "n": 3}, disabled=["Beijing"])
    assert state["place"] == "Tokyo"
