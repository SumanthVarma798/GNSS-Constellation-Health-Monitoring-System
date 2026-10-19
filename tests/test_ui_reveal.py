"""The one expandable section (ui/reveal.py): its header words, its body, and its state kept for the session."""
from streamlit.testing.v1 import AppTest

from ui import reveal


def test_the_header_is_the_title_in_bold_then_the_summary():
    assert reveal.label("Every burn", "8 satellites · 2 need a look") == "**Every burn** 8 satellites · 2 need a look"
    assert reveal.label("Notes") == "**Notes**"


def test_header_words_are_not_read_as_markdown_or_markup():
    text = reveal.label('<b>"QZS-2"</b> *x* :red[y] $z$', "1 < 2 'quoted'")

    for raw in ("<b>", "*x*", ":red[", "$z$", "1 < 2"):
        assert raw not in text
    assert '"QZS' in text and "'quoted'" in text   # quotes are plain text in a label


def test_counts_read_naturally():
    assert reveal.count(1, "satellite") == "1 satellite" and reveal.count(8, "satellite") == "8 satellites"


def test_the_body_is_wrapped_and_passed_through():
    assert reveal.body("<table></table>") == '<div class="rv-body"><table></table></div>'


def _page():
    from ui import reveal

    reveal.section("demo", "Title", "summary", "<p>inside</p>")
    reveal.section("shown", "Main table", "", "<p>main</p>", open=True)


def test_sections_start_as_asked_and_stay_as_the_reader_leaves_them():
    at = AppTest.from_function(_page).run()

    assert [box.value for box in at.checkbox] == [False, True]
    assert any(h.proto.body == '<div class="rv-body"><p>inside</p></div>' for h in at.get("html"))   # always drawn

    at.checkbox(key="rvx_demo").check().run()
    assert at.session_state[reveal.MEMORY] == {"demo": True}
    at.run()
    assert at.checkbox(key="rvx_demo").value is True
