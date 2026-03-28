"""Player Analysis page."""
import streamlit as st
from components.filters import player_selector, stat_selector, team_selector
from components.chart_wrapper import render_chart, render_dataframe
from viz import trend_line, split_comparison, radar_chart, no_data_chart, format_stat_label
from engine.player_trends import (
    player_game_log, player_rolling_average, player_splits,
    player_vs_team, player_comparison,
)


def render(season):
    st.header("Player Analysis")
    
    # ──────────────────────────────────────
    # SECTION 1: Player Game Log
    # ──────────────────────────────────────
    st.subheader("Player Game Log")
    
    log_player = player_selector("Player", key="gl_player")
    
    if log_player:
        df = player_game_log(log_player, season)
        if not df.empty:
            render_dataframe(df, title=f"{log_player} — {season} Game Log")
        else:
            st.info(f"No game data found for {log_player} in {season}.")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 2: Rolling Trends
    # ──────────────────────────────────────
    st.subheader("Rolling Trends")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        trend_player = player_selector("Player", key="rt_player")
    with col2:
        trend_stat = stat_selector("Stat", key="rt_stat")
    with col3:
        window = st.slider("Window Size", min_value=3, max_value=15, value=5, key="rt_window")
    
    if trend_player:
        df = player_rolling_average(trend_player, trend_stat, window, season)
        if not df.empty:
            fig = trend_line(
                df, x_col="game_date", y_col="value",
                title=f"{trend_player} — {format_stat_label(trend_stat)} ({window}-Game Rolling Avg)",
                rolling_col="rolling_avg",
            )
            render_chart(fig, key="rt_chart")
        else:
            render_chart(no_data_chart("Rolling Trends"), key="rt_chart")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 3: Player Splits
    # ──────────────────────────────────────
    st.subheader("Player Splits")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        ps_player = player_selector("Player", key="ps_player")
    with col2:
        ps_split = st.selectbox(
            "Split By",
            ["home_away", "opponent", "rest_days", "month"],
            format_func=lambda x: x.replace("_", " ").title(),
            key="ps_split",
        )
    with col3:
        ps_stat = stat_selector("Stat", key="ps_stat")
    
    if ps_player:
        df = player_splits(ps_player, ps_split, ps_stat, season)
        if not df.empty:
            fig = split_comparison(
                df, category_col="split_category",
                value_cols="avg_value",
                title=f"{ps_player} — {format_stat_label(ps_stat)} by {ps_split.replace('_', ' ').title()}",
            )
            render_chart(fig, key="ps_chart")
            render_dataframe(df, title="Split Details")
        else:
            render_chart(no_data_chart("Player Splits"), key="ps_chart")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 4: Player vs Team
    # ──────────────────────────────────────
    st.subheader("Player vs Team")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        pvt_player = player_selector("Player", key="pvt_player")
    with col2:
        pvt_opponent = team_selector("Opponent", key="pvt_opponent")
    with col3:
        pvt_stat = stat_selector("Stat", key="pvt_stat")
    
    if pvt_player and pvt_opponent:
        df = player_vs_team(pvt_player, pvt_opponent, pvt_stat, season, split_by_location=True)
        if not df.empty:
            fig = split_comparison(
                df, category_col="location",
                value_cols="avg_value",
                title=f"{pvt_player} vs {pvt_opponent} — {format_stat_label(pvt_stat)}",
            )
            render_chart(fig, key="pvt_chart")
            render_dataframe(df, title="Performance Details")
        else:
            render_chart(no_data_chart("Player vs Team"), key="pvt_chart")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 5: Player Comparison
    # ──────────────────────────────────────
    st.subheader("Player Comparison")
    
    col1, col2 = st.columns(2)
    with col1:
        pc_player_a = player_selector("Player A", key="pc_player_a")
    with col2:
        pc_player_b = player_selector("Player B", key="pc_player_b")
    
    if pc_player_a and pc_player_b and pc_player_a != pc_player_b:
        df = player_comparison(pc_player_a, pc_player_b, season=season)
        if not df.empty:
            radar_stats = ["points", "reb", "ast", "stl", "blk", "fg_pct", "fg3_pct"]
            radar_df = df[df["stat_name"].isin(radar_stats)].copy()
            
            if not radar_df.empty:
                fig = radar_chart(
                    radar_df,
                    categories_col="stat_name",
                    values_cols=["player_a_avg", "player_b_avg"],
                    labels=[pc_player_a, pc_player_b],
                    title=f"{pc_player_a} vs {pc_player_b} — {season}",
                )
                render_chart(fig, key="pc_radar")
            
            render_dataframe(df, title="Full Season Comparison")
        else:
            st.info("No comparison data available.")
    elif pc_player_a == pc_player_b:
        st.warning("Select two different players to compare.")
