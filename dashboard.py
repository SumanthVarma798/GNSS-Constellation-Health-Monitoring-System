"""The dashboard: `streamlit run dashboard.py`. A top bar, then the page chosen in it. No side panel.

The page's notices gather in the inbox (ui/notices.py), drawn after the page so it holds all of them.
"""
import streamlit as st

from ui import notices, shell
from ui.theme import apply_theme

st.set_page_config(page_title="GNSS Health Monitor", layout="wide", initial_sidebar_state="collapsed")
apply_theme()
page = st.navigation(shell.pages(), position="hidden")
notices.clear()
shell.top_bar(page)
page.run()
shell.footer()
notices.inbox()
