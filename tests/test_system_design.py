"""System design (ui/components/system_design.*): the picture and its words agree, and nothing from them is markup."""
import json
import re

from ui.components import system_design as sd

PAGE = sd.PAGE_FILE.read_text()


def test_every_box_in_the_picture_has_its_words_and_every_part_has_a_box():
    assert set(re.findall(r'data-n="([a-z]+)"', PAGE)) == set(sd.PARTS)


def test_every_step_lights_parts_and_arrows_that_exist():
    edges = set(re.findall(r'data-e="([a-z-]+)"', PAGE))
    for words, nodes, lit in sd.STEPS:
        assert nodes and set(nodes) <= set(sd.PARTS), words
        assert set(lit) <= edges, words


def test_each_part_says_what_it_is_its_details_its_limits_and_where_it_lives():
    for key, (name, kind, simple, tech, limits, where) in sd.PARTS.items():
        assert kind in ("built", "planned", "key") and name and simple and tech and limits and where, key


def test_the_step_bar_has_previous_and_next_arrow_buttons():
    assert 'setAttribute("aria-label", "Previous step")' in PAGE
    assert 'setAttribute("aria-label", "Next step")' in PAGE
    assert PAGE.count('el("button", "‹"') == 1 and PAGE.count('el("button", "›"') == 1


def test_text_cannot_break_out_of_the_page_and_is_put_in_as_text():
    page = sd.system_design_html(":root{}", "sans-serif", [("</script><b>1</b>", "words")])

    data = page[page.index("const DATA = ") + len("const DATA = "):page.index(";\nconst $")]
    assert "</script>" not in data and json.loads(data)["facts"][0]["figure"] == "</script><b>1</b>"
    assert "innerHTML" not in page and "textContent" in page
