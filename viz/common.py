"""Common visualization utilities and styling for WNBA Analytics."""
import plotly.graph_objects as go


# WNBA team colors — primary and secondary for each franchise.
# Keys are team abbreviations as they appear in the database.
WNBA_TEAM_COLORS = {
    "LVA": {"primary": "#000000", "secondary": "#C4CED4"},      # Aces
    "NYL": {"primary": "#6ECEB2", "secondary": "#000000"},       # Liberty
    "CHI": {"primary": "#418FDE", "secondary": "#FFCD00"},       # Sky
    "CON": {"primary": "#0C2340", "secondary": "#F05023"},       # Sun
    "DAL": {"primary": "#002B5C", "secondary": "#C4D600"},       # Wings
    "IND": {"primary": "#002D62", "secondary": "#E03A3E"},       # Fever
    "LAS": {"primary": "#552583", "secondary": "#FDB927"},       # Sparks
    "MIN": {"primary": "#266092", "secondary": "#78BE20"},       # Lynx
    "PHO": {"primary": "#201747", "secondary": "#CB6015"},       # Mercury
    "SEA": {"primary": "#2C5234", "secondary": "#FEE11A"},       # Storm
    "WAS": {"primary": "#002B5C", "secondary": "#E03A3E"},       # Mystics
    "ATL": {"primary": "#C8102E", "secondary": "#418FDE"},       # Dream
    "GSV": {"primary": "#5B2B82", "secondary": "#F4AF23"},       # Valkyries
}

# Stat label formatting — maps database column names to display-friendly labels.
STAT_LABELS = {
    "points": "Points",
    "minutes": "Minutes",
    "fgm": "FGM",
    "fga": "FGA",
    "fg_pct": "FG%",
    "fg3m": "3PM",
    "fg3a": "3PA",
    "fg3_pct": "3P%",
    "ftm": "FTM",
    "fta": "FTA",
    "ft_pct": "FT%",
    "oreb": "Off Reb",
    "dreb": "Def Reb",
    "reb": "Rebounds",
    "ast": "Assists",
    "stl": "Steals",
    "blk": "Blocks",
    "tov": "Turnovers",
    "pf": "Fouls",
    "plus_minus": "+/-",
}


def format_stat_label(column_name: str) -> str:
    """Convert a database column name to a display label.

    Returns the column_name unchanged if not in the mapping.
    """
    return STAT_LABELS.get(column_name, column_name.replace("_", " ").title())


def apply_theme(fig: go.Figure) -> go.Figure:
    """Apply WNBA Analytics styling by selecting the registered Plotly template.

    The actual look-and-feel lives in `app.components.theme.register_plotly_template`,
    which builds the `wnba_dark` template from design tokens. We try to use that
    template if it's been registered (i.e. the Streamlit app has booted) and fall
    back to a stripped-down inline style for non-app callers (tests, scripts).
    Modifies the figure in place AND returns it.
    """
    import plotly.io as pio
    if "wnba_dark" in pio.templates:
        fig.update_layout(template="wnba_dark")
    else:
        fig.update_layout(
            font_family="Inter Tight, Helvetica Neue, Helvetica, Arial, sans-serif",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
            margin=dict(l=56, r=24, t=56, b=48),
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="right", x=1),
        )
    return fig


def no_data_chart(title: str, message: str = "No data available for the selected filters") -> go.Figure:
    """Return a placeholder figure with a centered message. Used when input DataFrame is empty."""
    fig = go.Figure()
    fig.add_annotation(
        text=message, xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False, font=dict(size=16, color="gray"),
    )
    fig.update_layout(title=title, xaxis=dict(visible=False), yaxis=dict(visible=False))
    return apply_theme(fig)
