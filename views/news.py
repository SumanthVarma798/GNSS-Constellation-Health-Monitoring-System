"""News by constellation, from the latest-news file."""
from datetime import datetime, timezone
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from ui import news, reveal, shell, surfaces, tooltip

st.html(f"<style>{news.CSS}</style>")
data, problem = news.load_news()
if problem:
    surfaces.show(surfaces.notice(f"No news to show just now: {problem}. The rest of the dashboard works as usual; "
                                  f"news collection runs every {news.NEWS_CYCLE_HOURS} hours.", "warn"))
else:
    now = datetime.now(timezone.utc)
    scope = st.session_state.get("scope", shell.CONSTELLATIONS[0])
    zone = shell.viewer_zone()
    as_of = news.as_of_line(data.get("generated_at", ""), now, zone)
    surfaces.show(as_of)
    if data.get("invalid_items", 0):
        surfaces.show(surfaces.notice(
            f'{data["invalid_items"]} news items in the file were not in the expected shape and are not shown', "idle"))

    def keep(key, default):
        """A single-choice filter always keeps one choice: clicking the chosen pill puts it back."""
        if st.session_state[key] is None:
            st.session_state[key] = st.session_state.get(f"_{key}_was", default)
        st.session_state[f"_{key}_was"] = st.session_state[key]

    categories = list(news.NEWS_CATEGORIES)
    seen_at = news.cookie_seen()
    for key, default in (("news_date", "90 days"), ("news_show", "all")):
        st.session_state.setdefault(key, st.session_state.get(f"_{key}_was", default))
        st.session_state[f"_{key}_was"] = st.session_state[key]
    # One band: each filter's heading on the same line as its choices, the groups side by side (ui/news.py CSS).
    with st.container(key="news_filters"):
        news.screen_reader_heading("Category")
        picked_categories = st.pills("Category", categories, default=categories, selection_mode="multi",
                                     key="news_category")
        news.screen_reader_heading("Source grade")
        standings = st.pills("Source grade", news.GRADE_STANDINGS, default=news.GRADE_STANDINGS,
                             selection_mode="multi", key="news_grade")
        news.screen_reader_heading("Published within")
        window = st.pills("Published within", news.DATE_FILTERS, selection_mode="single", key="news_date",
                          on_change=keep, args=("news_date", "90 days"))
        news.screen_reader_heading("Show")
        show = st.pills("Show", news.SHOW_FILTERS, selection_mode="single", key="news_show",
                        on_change=keep, args=("news_show", "all"))
    only_new = show == "new only"

    category_filter, grade_filter = set(picked_categories or []), set(standings or [])
    if not category_filter:
        surfaces.show(surfaces.notice("Choose at least one category", "idle"))
    if not grade_filter:
        surfaces.show(surfaces.notice("Choose at least one grade", "idle"))
    filtered = news.filter_items(data["items"], scope, category_filter, grade_filter, window or "90 days",
                                 only_new, seen_at, now)
    new_count = sum(1 for item in filtered if item["_new"])
    new_words = tooltip.tip_html(f'<span class="num">{new_count}</span> new', escape(news.seen_note(seen_at)))
    surfaces.show(f'<p class="news-topline"><span class="num">{len(filtered)}</span> news items for {escape(scope)} · '
                  f'{new_words}</p>')
    surfaces.show(news.category_tiles_html(filtered))

    opened = False
    for category in categories:
        rows = [item for item in filtered if item["category"] == category]
        if not rows:
            continue
        new_rows = sum(1 for item in rows if item["_new"])
        reveal.section(f"news_{scope}_{category}", category,
                       f"{reveal.count(len(rows), 'item')} · {new_rows} new",
                       news.category_body_html(rows, data.get("sources", {}), zone), open=not opened)
        opened = True
    reveal.section("news_rules", "How items are sorted", "categories, word rules, and grade standing",
                   news.sorting_rules_html())

    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    components.html(
        f"<script>document.cookie = \"gnss_news_seen={stamp}; path=/; max-age=31536000; SameSite=Lax\";</script>",
        height=0,
        width=0,
    )
