"""Correlation Lab page."""
import streamlit as st
from components.filters import stat_selector, team_selector
from components.chart_wrapper import render_chart, render_dataframe
from viz import scatter_correlation, heat_map, no_data_chart, format_stat_label
from engine.correlation import (
    correlate_stats, correlation_matrix, find_strong_correlations,
)


def render(season):
    st.header("Correlation Lab")
    
    # ──────────────────────────────────────
    # SECTION 1: Two-Stat Correlation
    # ──────────────────────────────────────
    st.subheader("Two-Stat Correlation")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        corr_x = stat_selector("Stat X", key="cs_stat_x")
    with col2:
        corr_y = stat_selector("Stat Y", key="cs_stat_y", default="Rebounds")
    with col3:
        corr_level = st.selectbox(
            "Level",
            ["player_game", "team_game", "player_season"],
            format_func=lambda x: x.replace("_", " ").title(),
            key="cs_level",
        )
    
    corr_team = team_selector("Filter by team (optional)", key="cs_team", include_all=True)
    team_arg = None if corr_team == "All Teams" else corr_team
    
    if corr_x and corr_y and corr_x != corr_y:
        df = correlate_stats(corr_x, corr_y, level=corr_level, season=season, team=team_arg)
        if not df.empty:
            stats_dict = {
                "r_value": df.attrs.get("r_value"),
                "p_value": df.attrs.get("p_value"),
                "r_squared": df.attrs.get("r_squared"),
            }
            
            fig = scatter_correlation(
                df, x_col="stat_x_value", y_col="stat_y_value",
                title=f"{format_stat_label(corr_x)} vs {format_stat_label(corr_y)} ({season})",
                show_regression=True,
                stats_dict=stats_dict,
            )
            render_chart(fig, key="cs_chart")
            
            if df.attrs:
                st.caption(
                    f"Pearson r = {df.attrs.get('r_value', 'N/A'):.3f}, "
                    f"p = {df.attrs.get('p_value', 'N/A'):.4f}, "
                    f"R² = {df.attrs.get('r_squared', 'N/A'):.3f}, "
                    f"n = {df.attrs.get('sample_size', len(df))}"
                )
        else:
            render_chart(no_data_chart("Two-Stat Correlation"), key="cs_chart")
    elif corr_x == corr_y:
        st.warning("Select two different stats to correlate.")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 2: Correlation Matrix
    # ──────────────────────────────────────
    st.subheader("Correlation Matrix")
    
    matrix_stats = stat_selector("Select Stats (3-8)", multi=True, key="cm_stats")
    matrix_level = st.selectbox(
        "Level",
        ["player_game", "team_game"],
        format_func=lambda x: x.replace("_", " ").title(),
        key="cm_level",
    )
    
    if matrix_stats and len(matrix_stats) >= 3:
        df = correlation_matrix(matrix_stats, level=matrix_level, season=season)
        if not df.empty:
            display_df = df.copy()
            display_df.index = [format_stat_label(s) for s in display_df.index]
            display_df.columns = [format_stat_label(s) for s in display_df.columns]
            
            fig = heat_map(
                display_df.reset_index().melt(id_vars="index", var_name="stat_y", value_name="r_value"),
                x_col="stat_y", y_col="index", value_col="r_value",
                title=f"Correlation Matrix ({season})",
                color_scale="RdBu_r", zmid=0,
            )
            render_chart(fig, key="cm_chart")
        else:
            render_chart(no_data_chart("Correlation Matrix"), key="cm_chart")
    elif matrix_stats and len(matrix_stats) < 3:
        st.warning("Select at least 3 stats for the correlation matrix.")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 3: Discovery
    # ──────────────────────────────────────
    st.subheader("Find Strong Correlations")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        disc_level = st.selectbox(
            "Level",
            ["team_game", "player_game"],
            format_func=lambda x: x.replace("_", " ").title(),
            key="disc_level",
        )
    with col2:
        min_r = st.slider("Min |r|", min_value=0.3, max_value=0.9, value=0.5, step=0.05, key="disc_min_r")
    with col3:
        max_p = st.slider("Max p-value", min_value=0.001, max_value=0.1, value=0.05, step=0.005,
                          format="%.3f", key="disc_max_p")
    
    if st.button("Find Strong Correlations", key="disc_button"):
        with st.spinner("Scanning all stat pairs..."):
            df = find_strong_correlations(level=disc_level, season=season, min_r=min_r, max_p=max_p)
        
        if not df.empty:
            display_df = df.copy()
            display_df["stat_x"] = display_df["stat_x"].apply(format_stat_label)
            display_df["stat_y"] = display_df["stat_y"].apply(format_stat_label)
            display_df["r_value"] = display_df["r_value"].round(3)
            display_df["p_value"] = display_df["p_value"].apply(lambda p: f"{p:.4f}" if p >= 0.001 else f"{p:.2e}")
            
            st.success(f"Found {len(display_df)} significant correlations")
            render_dataframe(
                display_df[["stat_x", "stat_y", "r_value", "p_value"]],
                title="Stat pairs sorted by correlation strength",
            )
        else:
            st.info("No correlations found matching the specified thresholds. Try lowering min |r| or increasing max p-value.")
