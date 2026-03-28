"""Reusable Streamlit filter widgets."""
import streamlit as st
from engine.utils import get_session
from models.core import Team, Player, Game, PlayerGameStats
from sqlalchemy import select, distinct, func


def season_selector(key="season", default=None):
    """Dropdown of available seasons from the games table.
    
    Returns: selected season (int)
    """
    session = get_session()
    try:
        seasons = session.execute(
            select(distinct(Game.season)).order_by(Game.season.desc())
        ).scalars().all()
    finally:
        session.close()
    
    if default is None:
        default = seasons[0] if seasons else 2024
    
    idx = seasons.index(default) if default in seasons else 0
    return st.selectbox("Season", seasons, index=idx, key=key)


def team_selector(label="Team", multi=False, key=None, include_all=False):
    """Dropdown (or multiselect) of team full names.
    
    Returns: selected team name (str) or list of names
    """
    session = get_session()
    try:
        teams = session.execute(
            select(Team.full_name).order_by(Team.full_name)
        ).scalars().all()
    finally:
        session.close()
    
    if include_all:
        teams = ["All Teams"] + list(teams)
    
    if multi:
        return st.multiselect(label, teams, key=key)
    else:
        return st.selectbox(label, teams, key=key)


def player_selector(label="Player", team=None, key=None):
    """Dropdown of player names, optionally filtered by team.
    
    Returns: selected player name (str) — format: "First Last"
    """
    session = get_session()
    try:
        query = (
            select(
                distinct(Player.first_name + ' ' + Player.last_name)
            )
            .join(PlayerGameStats, Player.id == PlayerGameStats.player_id)
        )
        if team and team != "All Teams":
            from engine.utils import resolve_team
            team_id = resolve_team(team, session)
            query = query.where(PlayerGameStats.team_id == team_id)
        
        players = session.execute(query).scalars().all()
        players = sorted(players)
    finally:
        session.close()
    
    return st.selectbox(label, players, key=key)


def stat_selector(label="Stat", multi=False, key=None, default=None):
    """Dropdown of human-readable stat names.
    
    Options come from STAT_COLUMN_MAP — show human-readable keys,
    but only include each unique column value once.
    """
    display_stats = [
        "Points", "Rebounds", "Assists", "Steals", "Blocks", "Turnovers",
        "FG%", "3P%", "FT%", "FGM", "FGA", "3PM", "3PA", "FTM", "FTA",
        "Off Reb", "Def Reb", "Fouls", "+/-",
    ]
    
    display_to_engine = {
        "Points": "points", "Rebounds": "rebounds", "Assists": "assists",
        "Steals": "steals", "Blocks": "blocks", "Turnovers": "turnovers",
        "FG%": "fg_pct", "3P%": "fg3_pct", "FT%": "ft_pct",
        "FGM": "fgm", "FGA": "fga", "3PM": "fg3m", "3PA": "fg3a",
        "FTM": "ftm", "FTA": "fta", "Off Reb": "oreb", "Def Reb": "dreb",
        "Fouls": "pf", "+/-": "plus_minus",
    }
    
    if multi:
        selected = st.multiselect(label, display_stats, key=key)
        return [display_to_engine[s] for s in selected]
    else:
        idx = 0
        if default and default in display_stats:
            idx = display_stats.index(default)
        selected = st.selectbox(label, display_stats, index=idx, key=key)
        return display_to_engine[selected]


def date_range_selector(season, key=None):
    """Date range picker bounded by the season's start/end dates."""
    session = get_session()
    try:
        result = session.execute(
            select(func.min(Game.game_date), func.max(Game.game_date))
            .where(Game.season == season)
        ).one()
        min_date, max_date = result
    finally:
        session.close()
    
    if min_date and max_date:
        return st.date_input(
            "Date Range", value=(min_date, max_date),
            min_value=min_date, max_value=max_date, key=key
        )
    return None
