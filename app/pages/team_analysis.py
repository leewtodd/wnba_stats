"""Team Analysis page."""
import streamlit as st
import plotly.express as px
from components.filters import team_selector, stat_selector
from components.chart_wrapper import render_chart, render_dataframe
from viz import split_comparison, no_data_chart, format_stat_label
from engine.team_matchups import compare_teams, head_to_head, team_splits, team_rankings


def render(season):
    st.header("Team Analysis")
    
    # ──────────────────────────────────────
    # SECTION 1: Team Comparison
    # ──────────────────────────────────────
    st.subheader("Team Comparison")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        team_a = team_selector("Team A", key="tc_team_a")
    with col2:
        team_b = team_selector("Team B", key="tc_team_b")
    with col3:
        stat = stat_selector("Stat", key="tc_stat")
    
    if team_a and team_b and team_a != team_b:
        df = compare_teams(team_a, team_b, stat, season)
        if not df.empty:
            # compare_teams returns DYNAMIC columns: {abbr}_name, {abbr}_value
            value_cols = [c for c in df.columns if c.endswith("_value")]
            name_cols = [c for c in df.columns if c.endswith("_name")]
            
            if len(value_cols) == 2:
                label_a = df[name_cols[0]].iloc[0] if not df[name_cols[0]].isna().all() else "Team A"
                label_b = df[name_cols[1]].iloc[0] if not df[name_cols[1]].isna().all() else "Team B"
                
                import plotly.graph_objects as go
                from viz.common import apply_theme
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df["game_date"], y=df[value_cols[0]],
                    mode="lines+markers", name=label_a, opacity=0.8,
                ))
                fig.add_trace(go.Scatter(
                    x=df["game_date"], y=df[value_cols[1]],
                    mode="lines+markers", name=label_b, opacity=0.8,
                ))
                fig.update_layout(
                    title=f"{label_a} vs {label_b} — {format_stat_label(stat)} ({season})",
                    xaxis_title="Date", yaxis_title=format_stat_label(stat),
                )
                apply_theme(fig)
                render_chart(fig, key="tc_chart")
            else:
                render_chart(no_data_chart("Team Comparison"), key="tc_chart")
        else:
            render_chart(no_data_chart("Team Comparison"), key="tc_chart")
    elif team_a == team_b:
        st.warning("Select two different teams to compare.")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 2: Head to Head
    # ──────────────────────────────────────
    st.subheader("Head to Head")
    
    col1, col2 = st.columns(2)
    with col1:
        h2h_team_a = team_selector("Team A", key="h2h_team_a")
    with col2:
        h2h_team_b = team_selector("Team B", key="h2h_team_b")
    
    if h2h_team_a and h2h_team_b and h2h_team_a != h2h_team_b:
        df = head_to_head(h2h_team_a, h2h_team_b, seasons=[season])
        if not df.empty:
            if hasattr(df, 'attrs') and 'team_a_wins' in df.attrs:
                st.metric(
                    label="Record",
                    value=f"{df.attrs.get('team_a_wins', '?')} - {df.attrs.get('team_b_wins', '?')}",
                )
            render_dataframe(df, title=f"{h2h_team_a} vs {h2h_team_b} — All Games")
        else:
            st.info("No head-to-head games found for the selected teams and season.")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 3: Team Splits
    # ──────────────────────────────────────
    st.subheader("Team Splits")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        split_team = team_selector("Team", key="ts_team")
    with col2:
        split_by = st.selectbox(
            "Split By",
            ["home_away", "rest_days", "conference", "month"],
            format_func=lambda x: x.replace("_", " ").title(),
            key="ts_split",
        )
    with col3:
        split_stat = stat_selector("Stat", key="ts_stat")
    
    if split_team:
        df = team_splits(split_team, split_by, split_stat, season)
        if not df.empty:
            fig = split_comparison(
                df, category_col="split_category",
                value_cols="avg_value",
                title=f"{split_team} — {format_stat_label(split_stat)} by {split_by.replace('_', ' ').title()}",
            )
            render_chart(fig, key="ts_chart")
            render_dataframe(df, title="Split Details")
        else:
            render_chart(no_data_chart("Team Splits"), key="ts_chart")
    
    st.divider()
    
    # ──────────────────────────────────────
    # SECTION 4: Team Rankings
    # ──────────────────────────────────────
    st.subheader("Team Rankings")
    
    rank_stat = stat_selector("Stat", key="tr_stat")
    
    if rank_stat:
        df = team_rankings(rank_stat, season)
        if not df.empty:
            fig = px.bar(
                df, x="value", y="team_name", orientation="h",
                title=f"Team Rankings — {format_stat_label(rank_stat)} ({season})",
                labels={"value": format_stat_label(rank_stat), "team_name": ""},
            )
            fig.update_layout(yaxis=dict(categoryorder="total ascending"))
            from viz.common import apply_theme
            apply_theme(fig)
            render_chart(fig, key="tr_chart")
        else:
            render_chart(no_data_chart("Team Rankings"), key="tr_chart")
