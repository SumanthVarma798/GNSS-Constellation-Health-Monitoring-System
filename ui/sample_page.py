"""Every part of the look once, beside a few built-in Streamlit widgets, so the theme can be judged by eye.

Run it with: streamlit run ui/sample_page.py
No real data is used.
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui import palette, reveal, surfaces, tooltip
from ui.theme import apply_theme

st.set_page_config(page_title="Look sample", layout="wide")
apply_theme()

st.title("Look sample")
st.caption("Our own parts first, then Streamlit's built-in widgets in the same theme.")

st.header("Our parts")
left, right = st.columns(2)
with left:
    surfaces.show(surfaces.raised("A card that stands out of the page.", title="Raised"))
with right:
    surfaces.show(surfaces.well("An area pressed into the page, for quiet detail.", title="Well"))

surfaces.show(
    " ".join(surfaces.chip(f"{status} chip", status) for status in surfaces.STATUSES)
)
for status in ("ok", "warn", "bad"):
    surfaces.show(surfaces.notice(f"A {status} notice says what happened in words.", status))
surfaces.show(surfaces.big_number("24 of 31", "satellites scored this run"))
surfaces.show(tooltip.legend([(palette.SLOT_COLOURS[state], state) for state in palette.SLOT_COLOURS], "Slot legend")
              + " " + tooltip.tip("A word with a tip", "The same card opens on hover, focus and tap."))
reveal.section("sample", "An expandable section", "2 rows · 1 needs a look",
               '<p class="small">Hidden detail, shown on request; the open state is kept for the session.</p>')

st.header("Streamlit built-ins")
cols = st.columns(3)
cols[0].metric("Tracked", "31", "2")
cols[1].metric("Healthy", "24")
cols[2].metric("Set aside", "3")

st.button("A button")
st.text_input("A text box", value="Type here")
st.selectbox("A select box", ["GPS", "Galileo", "BeiDou"])

tab_one, tab_two = st.tabs(["First tab", "Second tab"])
tab_one.write("Content of the first tab.")
tab_two.write("Content of the second tab.")

st.warning("A built-in warning.")
st.info("A built-in note.")
st.dataframe(pd.DataFrame({"satellite": ["G01", "E05", "C19"], "state": ["in slot", "off its slot", "left its slot"]}))
