from evidence import news_stories


def item(title, day="2026-11-01", category="launch", grade="", summary="", source="a.com"):
    return {"title": title, "published_at": f"{day}T10:00:00Z", "category": category, "grade": grade,
            "summary": summary, "source_id": source, "constellations": ["NavIC"]}


def test_items_sharing_a_mission_id_are_one_story_with_the_most_shared_headline():
    shown = [item("ISRO launches NVS-03 on GSLV-F18", source="a.com"),
             item("PM congratulates ISRO on NVS-03 launch", source="b.com", grade="B", summary="The PM spoke."),
             item("NVS-03 lifts off: ISRO launches NavIC satellite", source="c.com"),
             item("Galileo contract awarded to Airbus", category="programme and policy", source="d.com")]

    found = news_stories.stories(shown)

    assert [len(story["items"]) for story in found] == [3, 1]
    assert found[0]["items"][0]["source_id"] == "b.com"           # best grade first
    assert found[0]["summary"] == "The PM spoke."
    assert "nvs-03" in found[0]["words"] and "launch" in found[0]["words"]
    assert found[0]["headline"] == "PM congratulates ISRO on NVS-03 launch"   # as many shared words, better grade


def test_different_ids_categories_or_far_apart_days_stay_apart():
    shown = [item("Notice advisory to Galileo users (NAGU) 2026047", category="satellite status and outages"),
             item("Notice advisory to Galileo users (NAGU) 2026046", category="satellite status and outages"),
             item("ISRO completes orbit raising of NVS-03", category="other"),
             item("ISRO launches NVS-03", day="2026-11-01"),
             item("ISRO launches NVS-03 again", day="2026-12-01")]

    assert len(news_stories.stories(shown)) == 5


def test_shared_words_tie_headlines_without_an_id():
    assert news_stories.same_story(news_stories.words("Airbus awarded Galileo satellites contract"),
                                   news_stories.words("Airbus wins contract for Galileo satellites"), common=set())
    assert not news_stories.same_story(news_stories.words("Galileo signal jamming in the Baltic"),
                                       news_stories.words("Galileo open service accuracy report"), common=set())


def test_taken_from_says_the_rule_word_and_the_claim():
    lines = news_stories.taken_from(item("ISRO launches NVS-03"), "a.com")
    assert lines[0] == 'Sorted under launch because it says "launches".'
    assert lines[1] == "Listed under NavIC: the headline names it."
    assert "launch claim for NavIC" in lines[2] and "a.com's grade" in lines[2]
    assert "No claim is taken" in news_stories.taken_from(item("A plan", category="programme and policy"), "a.com")[2]


def test_word_endings_and_ids():
    assert news_stories.words("Launches satellites") == news_stories.words("launched satellite")
    assert "nvs-03" in news_stories.words("ISRO's NVS-03") and "l5" not in news_stories.words("the L5 signal")
