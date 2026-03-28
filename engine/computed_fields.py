"""Computed fields for game context and schedule analysis.

Provides functions that enrich game data with context like rest days,
travel distance, and schedule density.
"""
import logging
import pandas as pd
from sqlalchemy import text
from engine.base import engine_function
from engine.utils import get_session, resolve_team

logger = logging.getLogger(__name__)


@engine_function(
    name="get_rest_days",
    description="Get rest days before each game for a team in a season",
    parameters={
        "team": {"type": "str", "description": "Team name or abbreviation"},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def get_rest_days(team: str, season=None):
    """Get rest days data for a team.

    Queries the v_team_rest_days view (created in Phase 1).

    Args:
        team: Team name or abbreviation
        season: Optional season year. If None, returns all seasons.

    Returns:
        DataFrame with columns: game_id, game_date, opponent, rest_days
    """
    session = get_session()
    try:
        team_id = resolve_team(team, session)

        query = """
            SELECT game_id, game_date, opponent, rest_days
            FROM v_team_rest_days
            WHERE team_id = :team_id
        """
        params = {"team_id": team_id}

        if season is not None:
            query += " AND season = :season"
            params["season"] = season

        query += " ORDER BY game_date ASC"

        result = session.execute(text(query), params)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df
    except Exception as e:
        logger.warning(f"Error getting rest days for team '{team}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="get_travel_distance",
    description="Get travel distance for each game for a team in a season",
    parameters={
        "team": {"type": "str", "description": "Team name or abbreviation"},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def get_travel_distance(team: str, season=None):
    """Get travel distance data for a team.

    Queries the v_team_travel_distance view (created in Phase 1).

    Args:
        team: Team name or abbreviation
        season: Optional season year. If None, returns all seasons.

    Returns:
        DataFrame with columns: game_id, game_date, opponent, travel_distance_miles, from_city, to_city
    """
    session = get_session()
    try:
        team_id = resolve_team(team, session)

        query = """
            SELECT game_id, game_date, opponent, travel_distance_miles, from_city, to_city
            FROM v_team_travel_distance
            WHERE team_id = :team_id
        """
        params = {"team_id": team_id}

        if season is not None:
            query += " AND season = :season"
            params["season"] = season

        query += " ORDER BY game_date ASC"

        result = session.execute(text(query), params)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df
    except Exception as e:
        logger.warning(f"Error getting travel distance for team '{team}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


def classify_rest(rest_days: int) -> str:
    """Classify rest days into categories.

    Args:
        rest_days: Number of days of rest

    Returns:
        Rest category: "back-to-back", "short_rest", or "normal_rest"
    """
    if rest_days in (0, 1):
        return "back-to-back"
    elif rest_days == 2:
        return "short_rest"
    else:
        return "normal_rest"


@engine_function(
    name="get_schedule_context",
    description="Get enriched game log with rest days, travel, home/away, and results",
    parameters={
        "team": {"type": "str", "description": "Team name or abbreviation"},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def get_schedule_context(team: str, season=None):
    """Get enriched game schedule with context.

    Combines rest days, travel distance, home/away flag, opponent name, and game result.

    Args:
        team: Team name or abbreviation
        season: Optional season year. If None, returns all seasons.

    Returns:
        DataFrame with columns: game_id, game_date, opponent, home_away, rest_days,
        rest_category, travel_distance_miles, result, points_scored, points_allowed
    """
    session = get_session()
    try:
        team_id = resolve_team(team, session)

        # Get rest days
        rest_df = get_rest_days(team, season)
        if rest_df.empty:
            return pd.DataFrame()

        # Get travel distance
        travel_df = get_travel_distance(team, season)

        # Query games with scores and home/away info
        from models.core import Game, Team, TeamGameStats
        from sqlalchemy import and_

        games = session.query(
            Game.id,
            Game.game_date,
            Game.season,
            Game.home_team_id,
            Game.away_team_id,
            Game.home_score,
            Game.away_score,
            TeamGameStats.points  # Team's points
        ).join(
            TeamGameStats,
            and_(TeamGameStats.game_id == Game.id, TeamGameStats.team_id == team_id)
        ).filter(TeamGameStats.team_id == team_id)

        if season is not None:
            games = games.filter(Game.season == season)

        games = games.order_by(Game.game_date).all()

        # Build enriched dataframe
        rows = []
        for game in games:
            game_id, game_date, season_val, home_id, away_id, home_score, away_score, team_points = game

            # Determine home/away
            home_away = "Home" if home_id == team_id else "Away"

            # Determine opponent
            opponent_id = away_id if home_id == team_id else home_id
            opponent = session.query(Team).filter(Team.id == opponent_id).first()
            opponent_name = opponent.abbreviation if opponent else "Unknown"

            # Determine result and opponent points
            if home_away == "Home":
                opponent_points = away_score
                if home_score and away_score:
                    result = "W" if home_score > away_score else "L"
                else:
                    result = None
            else:
                opponent_points = home_score
                if home_score and away_score:
                    result = "W" if away_score > home_score else "L"
                else:
                    result = None

            # Get rest days for this game
            rest_info = rest_df[rest_df['game_id'] == game_id]
            rest_days = int(rest_info['rest_days'].iloc[0]) if not rest_info.empty else None

            # Get travel distance for this game
            travel_info = travel_df[travel_df['game_id'] == game_id]
            travel_miles = float(travel_info['travel_distance_miles'].iloc[0]) if not travel_info.empty else None

            rows.append({
                'game_id': game_id,
                'game_date': game_date,
                'opponent': opponent_name,
                'home_away': home_away,
                'rest_days': rest_days,
                'rest_category': classify_rest(rest_days) if rest_days is not None else None,
                'travel_distance_miles': travel_miles,
                'result': result,
                'points_scored': team_points,
                'points_allowed': opponent_points,
            })

        df = pd.DataFrame(rows)
        return df
    except Exception as e:
        logger.warning(f"Error getting schedule context for team '{team}': {e}")
        return pd.DataFrame()
    finally:
        session.close()
