"""News by constellation, from the latest-news file."""
from datetime import datetime, timezone
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from ui import news, reveal, shell, surfaces, tooltip

st.html(f"<style>{news.CSS}</style>")
data, problem = news.load_news()
if problem:
    surfaces.show(surfaces.notice(f"News could not be read just now: {problem}. The rest of the dashboard works as usual; "
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

    def keep_date():
        if st.session_state["news_date"] is None:
            st.session_state["news_date"] = st.session_state.get("_news_date_was", "90 days")
        st.session_state["_news_date_was"] = st.session_state["news_date"]

    categories = list(news.NEWS_CATEGORIES)
    seen_at = news.cookie_seen()
    st.session_state.setdefault("news_date", st.session_state.get("_news_date_was", "90 days"))
    st.session_state["_news_date_was"] = st.session_state["news_date"]
    with st.container(key="news_filters"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.html(tooltip.tip("Category", "Show one or more categories from the sorting rules."))
            picked_categories = st.pills("Category filter", categories, default=categories, selection_mode="multi",
                                         key="news_category", label_visibility="collapsed")
        with c2:
            st.html(tooltip.tip("Source grade", "Filter by standing in the source tables."))
            standings = st.pills("Source grade filter", news.GRADE_STANDINGS, default=news.GRADE_STANDINGS,
                                 selection_mode="multi", key="news_grade", label_visibility="collapsed")
        with c3:
            st.html(tooltip.tip("Date", "Published date, falling back to fetched date when needed."))
            window = st.pills("Date filter", news.DATE_FILTERS, default="90 days", selection_mode="single",
                              key="news_date", label_visibility="collapsed", on_change=keep_date)
        with c4:
            st.html(tooltip.tip("New", "Show only items fetched after your last stored visit."))
            only_new = st.toggle("New since your last visit", key="news_new_only", help=news.seen_note(seen_at))

    category_filter, grade_filter = set(picked_categories or []), set(standings or [])
    if not category_filter:
        surfaces.show(surfaces.notice("Choose at least one category", "idle"))
    if not grade_filter:
        surfaces.show(surfaces.notice("Choose at least one grade", "idle"))
    filtered = news.filter_items(data["items"], scope, category_filter, grade_filter, window or "90 days",
                                 only_new, seen_at, now)
    new_count = sum(1 for item in filtered if item["_new"])
    surfaces.show(f'<p class="news-topline"><span class="num">{len(filtered)}</span> news items for {escape(scope)} · '
                  f'<span class="num">{new_count}</span> new</p>')
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
