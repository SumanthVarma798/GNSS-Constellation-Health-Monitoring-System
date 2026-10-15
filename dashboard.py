"""The dashboard: `streamlit run dashboard.py`. A top bar, then the page chosen in it. No side panel."""
import streamlit as st

from ui import shell
from ui.theme import apply_theme

st.set_page_config(page_title="GNSS Health", layout="wide", initial_sidebar_state="collapsed")
apply_theme()
page = st.navigation(shell.pages(), position="hidden")
shell.top_bar(page)
page.run()
