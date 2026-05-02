import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

"""WNBA Analytics Streamlit Application."""
import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="WNBA Analytics",
    page_icon="🏀",
    layout="wide",
)

st.title("🏀 WNBA Analytics")
st.caption("Local analytics platform — 4 seasons of WNBA data")

# Sidebar navigation
page = st.sidebar.radio(
    "Navigation",
    ["Team Analysis", "Player Analysis", "Game Context", "Correlation Lab", "Chat"],
)

# Global season filter — available on all pages via st.session_state
from components.filters import season_selector  # noqa: E402
with st.sidebar:
    st.divider()
    selected_season = season_selector(key="global_season")
    st.session_state["selected_season"] = selected_season

# Page routing
if page == "Team Analysis":
    from pages import team_analysis
    team_analysis.render(selected_season)
elif page == "Player Analysis":
    from pages import player_analysis
    player_analysis.render(selected_season)
elif page == "Game Context":
    from pages import game_context
    game_context.render(selected_season)
elif page == "Correlation Lab":
    from pages import correlation_lab
    correlation_lab.render(selected_season)
elif page == "Chat":
    from pages import chat
    chat.render()
