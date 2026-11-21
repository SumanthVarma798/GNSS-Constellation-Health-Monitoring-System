"""The dashboard: `streamlit run dashboard.py`. A top bar, then the page chosen in it. No side panel.

The page's notices gather in the inbox (ui/notices.py), drawn after the page so it holds all of them.
"""
from pathlib import Path

import streamlit as st

from ui import notices, shell
from ui.theme import apply_theme

# The tab icon: the OpenGNSS logo on the dashboard's own surface (ui/opengnss_tab_icon.svg, drawn to PNG with
# rsvg-convert -w 128 so every browser shows it).
st.set_page_config(page_title="GNSS Health Monitor", page_icon=str(Path(__file__).parent / "ui" / "opengnss_tab_icon.png"),
                   layout="wide", initial_sidebar_state="collapsed")
apply_theme()
page = st.navigation(shell.pages(), position="hidden")
notices.clear()
shell.top_bar(page)
page.run()
shell.footer(page)
notices.inbox()
