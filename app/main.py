import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))   # repo root  -> engine.X, models.X, viz.X
sys.path.insert(0, _HERE)                        # app/        -> components.X, pages.X

"""WNBA Analytics Streamlit Application."""
import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="WNBA Analytics",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Design system: Plotly template + global CSS. Must come right after
# set_page_config so every page renders with the tokens applied.
from components.theme import apply_design_system  # noqa: E402
from components import tokens as T  # noqa: E402
apply_design_system()

# ── Sidebar — branded header + navigation ──
NAV_ITEMS = [
    "Launchpad",
    "Team Analysis",
    "Player Analysis",
    "Game Context",
    "Correlation Lab",
    "Chat",
]

with st.sidebar:
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:10px;
                    padding:6px 0 14px; border-bottom:1px solid {T.LINE['1']};
                    margin-bottom:14px;">
          <div style="width:32px; height:32px; border-radius:{T.RADIUS['2']};
                      background:{T.ACCENT['primary']}; color:{T.ACCENT['primary_ink']};
                      display:flex; align-items:center; justify-content:center;
                      font-family:{T.FONT['mono']}; font-weight:700; font-size:14px;
                      box-shadow:0 0 18px {T.ACCENT['primary_glow']};">w</div>
          <div>
            <div style="font-size:13px; color:{T.FG['0']}; font-weight:500;
                        letter-spacing:-0.01em;">WNBA Analytics</div>
            <div style="font-size:10px; color:{T.FG['3']}; font-family:{T.FONT['mono']};
                        text-transform:uppercase; letter-spacing:0.12em;">
              Court chalk + neon
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Allow pages to programmatically set the active nav (e.g. Launchpad CTAs).
nav_default = st.session_state.pop("__nav__", None)
if nav_default and nav_default in NAV_ITEMS:
    st.session_state["__nav_radio__"] = nav_default

page = st.sidebar.radio(
    "Navigation",
    NAV_ITEMS,
    key="__nav_radio__",
    label_visibility="collapsed",
)

# Global season filter — available on all pages via st.session_state
from components.filters import season_selector  # noqa: E402
with st.sidebar:
    st.divider()
    selected_season = season_selector(key="global_season")
    st.session_state["selected_season"] = selected_season

# Page routing
if page == "Launchpad":
    from pages import launchpad
    launchpad.render(selected_season)
elif page == "Team Analysis":
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
