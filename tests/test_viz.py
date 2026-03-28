"""Tests for visualization layer functions."""
import pytest
import pandas as pd
import plotly.graph_objects as go
from viz.common import apply_theme, no_data_chart, WNBA_TEAM_COLORS, format_stat_label
from viz.trends import trend_line, animated_timeline
from viz.heatmaps import heat_map
from viz.scatter import scatter_correlation
from viz.comparisons import split_comparison, radar_chart


# ── Fixture: sample DataFrames ──

@pytest.fixture
def trend_df():
    """Sample DataFrame for trend charts."""
    return pd.DataFrame({
        "game_date": pd.date_range("2024-05-14", periods=10, freq="3D"),
        "value": [20, 25, 18, 30, 22, 28, 15, 33, 27, 21],
        "rolling_avg": [20, 22.5, 21, 23.25, 23, 23.8, 22.6, 24.4, 24.8, 23.9],
    })


@pytest.fixture
def scatter_df():
    """Sample DataFrame for scatter plots."""
    return pd.DataFrame({
        "stat_x_value": [10, 20, 30, 40, 50, 15, 25, 35],
        "stat_y_value": [5, 12, 14, 22, 28, 8, 16, 19],
    })


@pytest.fixture
def split_df():
    """Sample DataFrame for split comparison charts."""
    return pd.DataFrame({
        "split_category": ["Home", "Away"],
        "avg_value": [85.5, 79.2],
        "games": [20, 20],
    })


@pytest.fixture
def heatmap_df():
    """Sample DataFrame for heatmaps."""
    return pd.DataFrame({
        "team": ["LVA", "LVA", "NYL", "NYL"],
        "stat": ["FG%", "3P%", "FG%", "3P%"],
        "value": [0.48, 0.36, 0.45, 0.39],
    })


@pytest.fixture
def empty_df():
    """Empty DataFrame."""
    return pd.DataFrame()


# ── Tests: each viz function returns a Figure ──

def test_trend_line_returns_figure(trend_df):
    fig = trend_line(trend_df, "game_date", "value", "Test Trend")
    assert isinstance(fig, go.Figure)


def test_trend_line_with_rolling(trend_df):
    fig = trend_line(trend_df, "game_date", "value", "Test", rolling_col="rolling_avg")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2


def test_scatter_returns_figure(scatter_df):
    fig = scatter_correlation(scatter_df, "stat_x_value", "stat_y_value", "Test Scatter")
    assert isinstance(fig, go.Figure)


def test_scatter_with_regression(scatter_df):
    fig = scatter_correlation(scatter_df, "stat_x_value", "stat_y_value", "Test", show_regression=True)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2


def test_split_comparison_returns_figure(split_df):
    fig = split_comparison(split_df, "split_category", "avg_value", "Test Split")
    assert isinstance(fig, go.Figure)


def test_heat_map_returns_figure(heatmap_df):
    fig = heat_map(heatmap_df, "stat", "team", "value", "Test Heatmap")
    assert isinstance(fig, go.Figure)


def test_radar_chart_returns_figure():
    df = pd.DataFrame({
        "stat_name": ["points", "reb", "ast", "stl", "blk"],
        "player_a": [22.0, 6.5, 5.0, 1.8, 0.5],
        "player_b": [18.0, 8.0, 3.5, 1.2, 2.1],
    })
    fig = radar_chart(df, "stat_name", ["player_a", "player_b"], ["Player A", "Player B"], "Test Radar")
    assert isinstance(fig, go.Figure)


def test_animated_timeline_returns_figure(trend_df):
    fig = animated_timeline(trend_df, "game_date", "value", "game_date", "Test Animation")
    assert isinstance(fig, go.Figure)


# ── Tests: empty DataFrame handling ──

def test_trend_line_empty_df(empty_df):
    fig = trend_line(empty_df, "x", "y", "Empty")
    assert isinstance(fig, go.Figure)


def test_scatter_empty_df(empty_df):
    fig = scatter_correlation(empty_df, "x", "y", "Empty")
    assert isinstance(fig, go.Figure)


def test_split_comparison_empty_df(empty_df):
    fig = split_comparison(empty_df, "cat", "val", "Empty")
    assert isinstance(fig, go.Figure)


def test_heat_map_empty_df(empty_df):
    fig = heat_map(empty_df, "x", "y", "v", "Empty")
    assert isinstance(fig, go.Figure)


# ── Tests: common utilities ──

def test_apply_theme_modifies_layout():
    fig = go.Figure()
    apply_theme(fig)
    assert fig.layout.font.family is not None


def test_no_data_chart_returns_figure():
    fig = no_data_chart("Test")
    assert isinstance(fig, go.Figure)


def test_team_colors_has_all_teams():
    required = {"LVA", "NYL", "CHI", "CON", "DAL", "IND", "LAS", "MIN", "PHO", "SEA", "WAS", "ATL"}
    assert required.issubset(set(WNBA_TEAM_COLORS.keys()))


def test_format_stat_label():
    assert format_stat_label("fg_pct") == "FG%"
    assert format_stat_label("reb") == "Rebounds"
    assert format_stat_label("plus_minus") == "+/-"
    assert format_stat_label("unknown_col") != ""
