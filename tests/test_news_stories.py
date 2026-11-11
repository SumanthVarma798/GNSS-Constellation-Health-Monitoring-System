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


def test_many_identical_headlines_are_one_story_though_their_words_are_common():
    shown = [item("Galileo contract awarded", category="programme and policy", source=f"s{n}.com") for n in range(25)]
    shown.append(item("Galileo signal anomaly", category="signal and service"))
    assert sorted(len(story["items"]) for story in news_stories.stories(shown)) == [1, 25]


def test_a_time_without_a_zone_is_read_as_utc():
    shown = [item("ISRO launches NVS-03"), {**item("NVS-03 lifts off"), "published_at": "2026-11-01T09:00:00"}]
    assert len(news_stories.stories(shown)) == 1


def test_a_post_in_styled_letters_reads_as_plain_words():
    from evidence.news_stories import words

    assert words("𝐍𝐚𝐯𝐈𝐂 𝐈𝐒 𝐁𝐀𝐂𝐊 with 𝐍𝐕𝐒-𝟎𝟑") == words("NavIC is back with NVS-03")


def _registry(monkeypatch, satellites, tracked=()):
    from evidence import news_stories

    tables = {"satellites.csv": satellites, "sightings.csv": [], "dashboard_satellites.csv": list(tracked)}
    monkeypatch.setattr(news_stories, "read_table", lambda name: tables[name])
    news_stories._aliases.cache_clear()
    monkeypatch.setattr(news_stories, "_aliases", news_stories._aliases)   # cleared again after the test
    return news_stories


def test_a_satellites_other_name_tells_the_same_story_but_a_family_name_does_not(monkeypatch):
    stories_module = _registry(monkeypatch, [
        {"svn": "I-101228", "note": "Launched 2026-10-30; NVS-03 (IRNSS-1L)"},
        {"svn": "C017", "note": "Launched 2016-03-29; BEIDOU IGSO-6"},
        {"svn": "C019", "note": "Launched 2018-07-09; BEIDOU IGSO-7"},
    ], tracked=[{"svn": "C017", "dashboard_name": "BeiDou-2 IGSO-6"}, {"svn": "C019", "dashboard_name": "BeiDou-2 IGSO-7"}])

    # The dashboard's name (NVS-03) stands for the other; BeiDou-2 is on two rows, a family, so IGSO-6 and IGSO-7 pair
    # with nothing.
    assert stories_module._aliases() == {"irnss-1l": "nvs-03"}
    grouped = stories_module.stories([
        item("ISRO launches GSLV-F18 with NVS-03 navigation satellite", "2026-10-31"),
        item("LAUNCH at 1821 UTC Oct 30 of Indian's IRNSS-1L navigation sat on a GSLV Mk II", "2026-10-31", source="b.com"),
    ])
    assert [len(story["items"]) for story in grouped] == [2]
    stories_module._aliases.cache_clear()


def test_a_post_cut_short_joins_its_story_by_the_satellite_its_text_names(monkeypatch):
    stories_module = _registry(monkeypatch, [])
    post = item("𝐍𝐚𝐯𝐈𝐂 𝐈𝐒 𝐁𝐀𝐂𝐊 🎉 8 months ago, India's regional satellite navigation constellation fell below…",
                "2026-11-04", source="x.com/a",
                summary="... Last Friday, ISRO had launched the NVS-03 satellite on GSLV-F18, aiming to bring it back")
    unnamed = item("NavIC satellite launch restores India's regional navigation network", "2026-11-01", source="u.in")

    grouped = stories_module.stories([item("ISRO launches NVS-03", "2026-10-31"), post, unnamed])
    nvs_03 = next(story for story in grouped if any(i["title"] == "ISRO launches NVS-03" for i in story["items"]))
    assert post in nvs_03["items"]   # its headline names nothing; its text names NVS-03
    stories_module._aliases.cache_clear()


def test_a_satellites_other_name_is_marked_like_its_story_word(monkeypatch):
    from ui import news as news_ui

    stories_module = _registry(monkeypatch, [{"svn": "I-101228", "note": "Launched 2026-10-30; NVS-03 (IRNSS-1L)"}],
                               tracked=[{"svn": "I-101228", "dashboard_name": "NVS-03"}])
    html = news_ui.marked_html("LAUNCH of IRNSS-1L on GSLV", {"nvs-03"})

    assert "<mark>IRNSS-1L</mark>" in html and "<mark>GSLV</mark>" not in html
    stories_module._aliases.cache_clear()
