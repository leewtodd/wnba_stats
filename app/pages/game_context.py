"""Game Context Analysis page."""
import streamlit as st
import plotly.express as px
from components.filters import team_selector, stat_selector
from components.chart_wrapper import render_chart, render_dataframe
from viz import split_comparison, no_data_chart, format_stat_label
from engine.game_context import (
    rest_day_impact, travel_impact, home_away_analysis,
)
from engine.referee_analysis import referee_impact, referee_game_log


def render(season):
    st.header("Game Context Analysis")
    
    # ──────────────────────────────────────
    # SECTION 1: Rest Day Impact
    # ──────────────────────────────────────
    st.subheader("Rest Day Impact")
    
    col1, col2 = st.columns(2)
    with col1:
        rdi_team = team_selector("Team (optional)", key="rdi_team", include_all=True)
    with col2:
        rdi_stat = stat_selector("Stat", key="rdi_stat", default="Points")
    
    team_arg = None if rdi_team == "All Teams" else rdi_team
    df = rest_day_impact(team=team_arg, stat=rdi_stat, season=season)
    if not df.empty:
        fig = split_comparison(
            df, category_col="rest_category",
            value_cols="mean",
            title=f"Rest Day Impact — {format_stat_label(rdi_stat)} ({season})",
        )
        render_chart(fig, key="rdi_chart")
        render_dataframe(df, title="Statistical Details (p-values and sample sizes)")
    else:
        render_chart(no_data_chart("Rest Day Impact"), key="rdi_chart")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 2: Travel Impact
    # ──────────────────────────────────────
    st.subheader("Travel Impact")
    
    col1, col2 = st.columns(2)
    with col1:
        ti_team = team_selector("Team (optional)", key="ti_team", include_all=True)
    with col2:
        ti_stat = stat_selector("Stat", key="ti_stat", default="Points")
    
    team_arg = None if ti_team == "All Teams" else ti_team
    df = travel_impact(team=team_arg, stat=ti_stat, season=season)
    if not df.empty:
        fig = split_comparison(
            df, category_col="distance_bucket",
            value_cols="mean",
            title=f"Travel Distance vs {format_stat_label(ti_stat)} ({season})",
        )
        render_chart(fig, key="ti_chart")
        render_dataframe(df, title="Distance Bucket Details")
    else:
        render_chart(no_data_chart("Travel Impact"), key="ti_chart")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 3: Home/Away Analysis
    # ──────────────────────────────────────
    st.subheader("Home/Away Analysis")
    
    col1, col2 = st.columns(2)
    with col1:
        ha_team = team_selector("Team (optional)", key="ha_team", include_all=True)
    with col2:
        ha_stat = stat_selector("Stat", key="ha_stat", default="Points")
    
    team_arg = None if ha_team == "All Teams" else ha_team
    df = home_away_analysis(team=team_arg, stat=ha_stat, season=season)
    if not df.empty:
        fig = split_comparison(
            df, category_col="location",
            value_cols="mean",
            title=f"Home vs Away — {format_stat_label(ha_stat)} ({season})",
        )
        render_chart(fig, key="ha_chart")
        render_dataframe(df, title="Home/Away Details (includes win %)")
    else:
        render_chart(no_data_chart("Home/Away Analysis"), key="ha_chart")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 4: Referee Impact
    # ──────────────────────────────────────
    st.subheader("Referee Impact")
    
    ref_stat = stat_selector("Stat", key="ri_stat", default="Fouls")
    
    df = referee_impact(stat=ref_stat, season=season)
    if not df.empty:
        from viz.common import apply_theme
        
        top_refs = df.head(15)
        fig = px.bar(
            top_refs, x="deviation", y="referee_name", orientation="h",
            title=f"Referee Impact — {format_stat_label(ref_stat)} Deviation from League Avg ({season})",
            labels={"deviation": f"Deviation ({format_stat_label(ref_stat)})", "referee_name": ""},
            color="deviation",
            color_continuous_scale="RdYlGn_r",
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        apply_theme(fig)
        render_chart(fig, key="ri_chart")
        
        selected_ref = st.selectbox(
            "Select a referee to see their game log",
            options=df["referee_name"].tolist(),
            key="ri_ref_select",
        )
        
        if selected_ref:
            with st.expander(f"Game Log: {selected_ref}", expanded=True):
                ref_log = referee_game_log(selected_ref, season)
                if not ref_log.empty:
                    render_dataframe(ref_log, title=f"{selected_ref} — Games Officiated")
                else:
                    st.info(f"No game log found for {selected_ref}.")
    else:
        render_chart(no_data_chart("Referee Impact"), key="ri_chart")
