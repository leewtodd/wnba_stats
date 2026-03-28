"""Team matchup and comparative analysis."""
import logging
import pandas as pd
from sqlalchemy import and_
from engine.base import engine_function
from engine.utils import get_session, resolve_team, validate_stat
from models.core import Game, Team, TeamGameStats

logger = logging.getLogger(__name__)


@engine_function(
    name="compare_teams",
    description="Compare two teams' game-by-game values for a stat across a season",
    parameters={
        "team_a": {"type": "str", "description": "First team name or abbreviation"},
        "team_b": {"type": "str", "description": "Second team name or abbreviation"},
        "stat": {"type": "str", "description": "Stat to compare (e.g., 'points', 'rebounds', 'fg_pct')"},
        "season": {"type": "int", "description": "Season year (e.g., 2024)", "optional": True},
    }
)
def compare_teams(team_a: str, team_b: str, stat: str, season=None):
    """Compare two teams across a stat.

    Args:
        team_a: First team name or abbreviation
        team_b: Second team name or abbreviation
        stat: Stat column name
        season: Optional season year

    Returns:
        DataFrame with columns: game_date, team_a_name, team_a_value, team_b_name, team_b_value
    """
    session = get_session()
    try:
        team_a_id = resolve_team(team_a, session)
        team_b_id = resolve_team(team_b, session)
        stat_col = validate_stat(stat)

        team_a_obj = session.query(Team).filter(Team.id == team_a_id).first()
        team_b_obj = session.query(Team).filter(Team.id == team_b_id).first()
        team_a_name = team_a_obj.abbreviation if team_a_obj else team_a
        team_b_name = team_b_obj.abbreviation if team_b_obj else team_b

        # Query for team_a
        query_a = session.query(
            Game.game_date,
            getattr(TeamGameStats, stat_col)
        ).join(
            Game, Game.id == TeamGameStats.game_id
        ).filter(
            TeamGameStats.team_id == team_a_id
        )
        if season is not None:
            query_a = query_a.filter(Game.season == season)
        stats_a = query_a.order_by(Game.game_date).all()

        # Query for team_b
        query_b = session.query(
            Game.game_date,
            getattr(TeamGameStats, stat_col)
        ).join(
            Game, Game.id == TeamGameStats.game_id
        ).filter(
            TeamGameStats.team_id == team_b_id
        )
        if season is not None:
            query_b = query_b.filter(Game.season == season)
        stats_b = query_b.order_by(Game.game_date).all()

        # Create dataframes
        df_a = pd.DataFrame(stats_a, columns=['game_date', 'value_a'])
        df_b = pd.DataFrame(stats_b, columns=['game_date', 'value_b'])

        # Merge by date
        df = pd.merge(df_a, df_b, on='game_date', how='outer').sort_values('game_date')
        df.columns = ['game_date', f'{team_a_name}_value', f'{team_b_name}_value']
        df.insert(1, f'{team_a_name}_name', team_a_name)
        df.insert(3, f'{team_b_name}_name', team_b_name)

        return df[['game_date', f'{team_a_name}_name', f'{team_a_name}_value', f'{team_b_name}_name', f'{team_b_name}_value']]
    except Exception as e:
        logger.warning(f"Error comparing teams '{team_a}' and '{team_b}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="head_to_head",
    description="Show all games between two teams with scores and key stats",
    parameters={
        "team_a": {"type": "str", "description": "First team name or abbreviation"},
        "team_b": {"type": "str", "description": "Second team name or abbreviation"},
        "seasons": {"type": "list", "description": "List of season years (e.g., [2023, 2024])", "optional": True},
    }
)
def head_to_head(team_a: str, team_b: str, seasons=None):
    """Show head-to-head games between two teams.

    Args:
        team_a: First team name or abbreviation
        team_b: Second team name or abbreviation
        seasons: Optional list of season years

    Returns:
        DataFrame with columns: game_date, season, home_team, away_team, home_score, away_score,
        winner, home_fg_pct, away_fg_pct, home_reb, away_reb, home_tov, away_tov
    """
    session = get_session()
    try:
        team_a_id = resolve_team(team_a, session)
        team_b_id = resolve_team(team_b, session)

        # Query games where teams face each other
        games = session.query(Game).filter(
            ((Game.home_team_id == team_a_id) & (Game.away_team_id == team_b_id)) |
            ((Game.home_team_id == team_b_id) & (Game.away_team_id == team_a_id))
        )

        if seasons is not None:
            games = games.filter(Game.season.in_(seasons))

        games = games.order_by(Game.game_date).all()

        rows = []
        for game in games:
            home_team = session.query(Team).filter(Team.id == game.home_team_id).first()
            away_team = session.query(Team).filter(Team.id == game.away_team_id).first()

            home_stats = session.query(TeamGameStats).filter(
                and_(TeamGameStats.game_id == game.id, TeamGameStats.team_id == game.home_team_id)
            ).first()
            away_stats = session.query(TeamGameStats).filter(
                and_(TeamGameStats.game_id == game.id, TeamGameStats.team_id == game.away_team_id)
            ).first()

            if home_stats and away_stats and game.home_score and game.away_score:
                winner = "Home" if game.home_score > game.away_score else "Away"
            else:
                winner = None

            rows.append({
                'game_date': game.game_date,
                'season': game.season,
                'home_team': home_team.abbreviation if home_team else 'Unknown',
                'away_team': away_team.abbreviation if away_team else 'Unknown',
                'home_score': game.home_score,
                'away_score': game.away_score,
                'winner': winner,
                'home_fg_pct': home_stats.fg_pct if home_stats else None,
                'away_fg_pct': away_stats.fg_pct if away_stats else None,
                'home_reb': home_stats.reb if home_stats else None,
                'away_reb': away_stats.reb if away_stats else None,
                'home_tov': home_stats.tov if home_stats else None,
                'away_tov': away_stats.tov if away_stats else None,
            })

        df = pd.DataFrame(rows)

        # Add summary to attrs
        if not df.empty:
            team_a_wins = len(df[
                ((df['home_team'] == session.query(Team).filter(Team.id == team_a_id).first().abbreviation) & (df['winner'] == 'Home')) |
                ((df['away_team'] == session.query(Team).filter(Team.id == team_a_id).first().abbreviation) & (df['winner'] == 'Away'))
            ]) if session.query(Team).filter(Team.id == team_a_id).first() else 0
            team_b_wins = len(df) - team_a_wins
            df.attrs['team_a_wins'] = team_a_wins
            df.attrs['team_b_wins'] = team_b_wins
            df.attrs['total_games'] = len(df)

        return df
    except Exception as e:
        logger.warning(f"Error getting head-to-head for '{team_a}' vs '{team_b}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="team_splits",
    description="Show a team's average stat split by a dimension (home/away, rest days, etc.)",
    parameters={
        "team": {"type": "str", "description": "Team name or abbreviation"},
        "split_by": {"type": "str", "description": "Split dimension: 'home_away', 'rest_days', 'conference', 'month'"},
        "stat": {"type": "str", "description": "Stat to analyze"},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def team_splits(team: str, split_by: str, stat: str, season=None):
    """Show team's stats split by a dimension.

    Args:
        team: Team name or abbreviation
        split_by: Dimension ('home_away', 'rest_days', 'conference', 'month')
        stat: Stat to analyze
        season: Optional season year

    Returns:
        DataFrame with columns: split_category, games, avg_value, std_value, min_value, max_value
    """
    session = get_session()
    try:
        team_id = resolve_team(team, session)
        stat_col = validate_stat(stat)

        query = session.query(
            Game.game_date,
            getattr(TeamGameStats, stat_col),
            Game.home_team_id,
            Game.away_team_id,
        ).join(
            TeamGameStats, and_(TeamGameStats.game_id == Game.id, TeamGameStats.team_id == team_id)
        ).filter(
            TeamGameStats.team_id == team_id
        )

        if season is not None:
            query = query.filter(Game.season == season)

        games = query.order_by(Game.game_date).all()

        rows = []
        for game_date, value, home_id, away_id in games:
            home_away = "Home" if home_id == team_id else "Away"

            if split_by == "home_away":
                rows.append({'split_category': home_away, 'value': value})
            elif split_by == "rest_days":
                # This would require joining v_team_rest_days, for now return empty
                return pd.DataFrame()
            elif split_by == "conference":
                opp_id = away_id if home_id == team_id else home_id
                opp = session.query(Team).filter(Team.id == opp_id).first()
                rows.append({'split_category': opp.conference if opp else 'Unknown', 'value': value})
            elif split_by == "month":
                month = game_date.month
                rows.append({'split_category': f'Month {month}', 'value': value})

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        grouped = df.groupby('split_category')['value'].agg(['count', 'mean', 'std', 'min', 'max']).reset_index()
        grouped.columns = ['split_category', 'games', 'avg_value', 'std_value', 'min_value', 'max_value']
        return grouped
    except Exception as e:
        logger.warning(f"Error getting team splits for '{team}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="team_rankings",
    description="Rank all teams by a stat for a season",
    parameters={
        "stat": {"type": "str", "description": "Stat to rank by"},
        "season": {"type": "int", "description": "Season year"},
        "per_mode": {"type": "str", "description": "'per_game' or 'total'", "optional": True},
    }
)
def team_rankings(stat: str, season: int, per_mode: str = "per_game"):
    """Rank all teams by a stat.

    Args:
        stat: Stat to rank by
        season: Season year
        per_mode: 'per_game' or 'total'

    Returns:
        DataFrame with columns: rank, team_name, abbreviation, value, games_played
    """
    session = get_session()
    try:
        stat_col = validate_stat(stat)

        query = session.query(
            TeamGameStats.team_id,
            getattr(TeamGameStats, stat_col)
        ).join(
            Game, Game.id == TeamGameStats.game_id
        ).filter(
            Game.season == season
        )

        stats_data = query.all()

        rows = []
        for team_id, value in stats_data:
            rows.append({'team_id': team_id, 'value': value})

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        grouped = df.groupby('team_id')['value'].agg(['mean', 'sum', 'count']).reset_index()

        if per_mode == "total":
            grouped.rename(columns={'sum': 'value'}, inplace=True)
        else:
            grouped.rename(columns={'mean': 'value'}, inplace=True)

        grouped.columns = ['team_id', 'per_game_avg', 'total_sum', 'games_played'] if per_mode == "per_game" else ['team_id', 'total_sum', 'total_sum_dup', 'games_played']

        # Fix columns
        if per_mode == "per_game":
            grouped['value'] = grouped['per_game_avg']
        else:
            grouped['value'] = grouped['total_sum']

        # Add team info
        team_map = {}
        for team_id_val in grouped['team_id'].unique():
            team = session.query(Team).filter(Team.id == team_id_val).first()
            if team:
                team_map[team_id_val] = {'name': team.full_name, 'abbr': team.abbreviation}

        grouped['team_name'] = grouped['team_id'].map(lambda x: team_map.get(x, {}).get('name', 'Unknown'))
        grouped['abbreviation'] = grouped['team_id'].map(lambda x: team_map.get(x, {}).get('abbr', 'Unknown'))

        grouped = grouped.sort_values('value', ascending=False).reset_index(drop=True)
        grouped['rank'] = range(1, len(grouped) + 1)

        return grouped[['rank', 'team_name', 'abbreviation', 'value', 'games_played']]
    except Exception as e:
        logger.warning(f"Error ranking teams by '{stat}': {e}")
        return pd.DataFrame()
    finally:
        session.close()
