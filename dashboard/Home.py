"""Run from the repository root: streamlit run dashboard/Home.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from dashboard.context import load_context
from dashboard.ui import inject_mobile_css, footer

st.set_page_config(page_title="Farmboard", page_icon=":material/sports_baseball:", layout="wide", initial_sidebar_state="auto")
inject_mobile_css()
page = st.navigation([
    st.Page("pages/0_Overview.py", title="Overview", icon=":material/grid_view:", default=True),
    st.Page("pages/1_Player_Dashboard.py", title="Player lab", icon=":material/person_search:"),
    st.Page("pages/2_Team_Dashboard.py", title="Team room", icon=":material/groups:"),
    st.Page("pages/3_Trade_Simulator.py", title="Roster scenarios", icon=":material/swap_horiz:"),
    st.Page("pages/4_Metric_Guide.py", title="Analyst guide", icon=":material/school:"),
], position="top")
st.session_state["_context"] = load_context()
page.run()
footer()
