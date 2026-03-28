"""Player performance trends, rolling averages, and streak analysis."""
import logging
import pandas as pd
from engine.base import engine_function
from engine.utils import get_session, resolve_player, resolve_team, validate_stat
from models.core import Game, Player, PlayerGameStats, Team

logger = logging.getLogger(__name__)


@engine_function(
    name="player_game_log",
    description="Get all games for a player in a season with full box score stats",
    parameters={
        "player": {"type": "str", "description": "Player name"},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def player_game_log(player: str, season=None):
    """Get player's game log for a season.

    Args:
        player: Player name
        season: Optional season year

    Returns:
        DataFrame with columns: game_date, opponent, team, home_away, minutes, points, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct, oreb, dreb, reb, ast, stl, blk, tov, pf, plus_minus
    """
    session = get_session()
    try:
        player_id = resolve_player(player, session)

        query = session.query(
            Game.game_date,
            Game.home_team_id,
            Game.away_team_id,
            PlayerGameStats
        ).join(
            PlayerGameStats, PlayerGameStats.game_id == Game.id
        ).filter(
            PlayerGameStats.player_id == player_id
        )

        if season is not None:
            query = query.filter(Game.season == season)

        games = query.order_by(Game.game_date).all()

        rows = []
        for game_date, home_id, away_id, stats in games:
            home_away = "Home" if stats.team_id == home_id else "Away"
            opp_id = away_id if stats.team_id == home_id else home_id
            opponent = session.query(Team).filter(Team.id == opp_id).first()
            team = session.query(Team).filter(Team.id == stats.team_id).first()

            rows.append({
                'game_date': game_date,
                'opponent': opponent.abbreviation if opponent else 'Unknown',
                'team': team.abbreviation if team else 'Unknown',
                'home_away': home_away,
                'minutes': stats.minutes,
                'points': stats.points,
                'fgm': stats.fgm,
                'fga': stats.fga,
                'fg_pct': stats.fg_pct,
                'fg3m': stats.fg3m,
                'fg3a': stats.fg3a,
                'fg3_pct': stats.fg3_pct,
                'ftm': stats.ftm,
                'fta': stats.fta,
                'ft_pct': stats.ft_pct,
                'oreb': stats.oreb,
                'dreb': stats.dreb,
                'reb': stats.reb,
                'ast': stats.ast,
                'stl': stats.stl,
                'blk': stats.blk,
                'tov': stats.tov,
                'pf': stats.pf,
                'plus_minus': stats.plus_minus,
            })

        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning(f"Error getting game log for player '{player}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="player_rolling_average",
    description="Calculate rolling average for a player stat over a game window",
    parameters={
        "player": {"type": "str", "description": "Player name"},
        "stat": {"type": "str", "description": "Stat to track"},
        "window": {"type": "int", "description": "Rolling window size (games)", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def player_rolling_average(player: str, stat: str, window: int = 5, season=None):
    """Calculate rolling average for a player stat.

    Args:
        player: Player name
        stat: Stat to track
        window: Rolling window size in games (default 5)
        season: Optional season year

    Returns:
        DataFrame with columns: game_date, opponent, value, rolling_avg
    """
    session = get_session()
    try:
        validate_stat(stat)
        df = player_game_log(player, season)

        if df.empty:
            return df

        stat_col = validate_stat(stat)
        df['value'] = df[stat_col]
        df['rolling_avg'] = df['value'].rolling(window=window, min_periods=1).mean()

        return df[['game_date', 'opponent', 'value', 'rolling_avg']]
    except Exception as e:
        logger.warning(f"Error calculating rolling average for '{player}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="player_splits",
    description="Show a player's average stat split by a dimension",
    parameters={
        "player": {"type": "str", "description": "Player name"},
        "split_by": {"type": "str", "description": "Split dimension: 'home_away', 'opponent', 'rest_days', 'month'"},
        "stat": {"type": "str", "description": "Stat to analyze"},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def player_splits(player: str, split_by: str, stat: str, season=None):
    """Show player's stats split by a dimension.

    Args:
        player: Player name
        split_by: Dimension ('home_away', 'opponent', 'rest_days', 'month')
        stat: Stat to analyze
        season: Optional season year

    Returns:
        DataFrame with columns: split_category, games, avg_value, std_value
    """
    session = get_session()
    try:
        resolve_player(player, session)  # validate player exists
        validate_stat(stat)

        df = player_game_log(player, season)
        if df.empty:
            return df

        stat_col = validate_stat(stat)
        df['value'] = df[stat_col]

        if split_by == "home_away":
            grouped = df.groupby('home_away')['value'].agg(['count', 'mean', 'std']).reset_index()
            grouped.columns = ['split_category', 'games', 'avg_value', 'std_value']
        elif split_by == "opponent":
            grouped = df.groupby('opponent')['value'].agg(['count', 'mean', 'std']).reset_index()
            grouped.columns = ['split_category', 'games', 'avg_value', 'std_value']
        elif split_by == "month":
            df['month'] = df['game_date'].dt.month
            grouped = df.groupby('month')['value'].agg(['count', 'mean', 'std']).reset_index()
            grouped['split_category'] = 'Month ' + grouped['month'].astype(str)
            grouped = grouped[['split_category', 'count', 'mean', 'std']]
            grouped.columns = ['split_category', 'games', 'avg_value', 'std_value']
        else:
            # rest_days requires v_team_rest_days view, not implemented yet
            return pd.DataFrame()

        return grouped
    except Exception as e:
        logger.warning(f"Error getting player splits for '{player}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="player_vs_team",
    description="Show a player's performance against a specific team, optionally split by home/away",
    parameters={
        "player": {"type": "str", "description": "Player name"},
        "opponent_team": {"type": "str", "description": "Opponent team name or abbreviation"},
        "stat": {"type": "str", "description": "Stat to analyze"},
        "season": {"type": "int", "description": "Season year", "optional": True},
        "split_by_location": {"type": "bool", "description": "Split by home vs away", "optional": True},
    }
)
def player_vs_team(player: str, opponent_team: str, stat: str, season=None, split_by_location: bool = True):
    """Show player's performance vs a specific team.

    Args:
        player: Player name
        opponent_team: Opponent team name or abbreviation
        stat: Stat to analyze
        season: Optional season year
        split_by_location: Whether to split by home/away

    Returns:
        DataFrame with columns: location, games, avg_value, std_value, game_dates
    """
    session = get_session()
    try:
        resolve_player(player, session)
        opp_id = resolve_team(opponent_team, session)
        validate_stat(stat)

        df = player_game_log(player, season)
        if df.empty:
            return df

        # Filter games against opponent team
        df = df[df['opponent'] == session.query(Team).filter(Team.id == opp_id).first().abbreviation]

        if df.empty:
            return df

        stat_col = validate_stat(stat)
        df['value'] = df[stat_col]

        if split_by_location:
            grouped = df.groupby('home_away').agg({
                'value': ['count', 'mean', 'std'],
                'game_date': lambda x: list(x.astype(str))
            }).reset_index()
            grouped.columns = ['location', 'games', 'avg_value', 'std_value', 'game_dates']
        else:
            grouped = pd.DataFrame([{
                'location': 'All',
                'games': len(df),
                'avg_value': df['value'].mean(),
                'std_value': df['value'].std(),
                'game_dates': list(df['game_date'].astype(str))
            }])

        return grouped
    except Exception as e:
        logger.warning(f"Error getting player vs team for '{player}' vs '{opponent_team}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="player_streak_finder",
    description="Find consecutive game streaks where a player was above/below a threshold for a stat",
    parameters={
        "player": {"type": "str", "description": "Player name"},
        "stat": {"type": "str", "description": "Stat to check"},
        "threshold": {"type": "float", "description": "Threshold value"},
        "direction": {"type": "str", "description": "'above' or 'below'", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def player_streak_finder(player: str, stat: str, threshold: float, direction: str = "above", season=None):
    """Find consecutive game streaks above/below a threshold.

    Args:
        player: Player name
        stat: Stat to check
        threshold: Threshold value
        direction: 'above' or 'below'
        season: Optional season year

    Returns:
        DataFrame with columns: streak_start, streak_end, length, avg_during_streak, games_in_streak
    """
    session = get_session()
    try:
        validate_stat(stat)
        df = player_game_log(player, season)

        if df.empty:
            return df

        stat_col = validate_stat(stat)
        df['value'] = df[stat_col]

        # Apply threshold
        if direction == "above":
            df['meets_threshold'] = df['value'] >= threshold
        else:
            df['meets_threshold'] = df['value'] <= threshold

        # Identify streaks using cumsum
        df['streak_group'] = (df['meets_threshold'] != df['meets_threshold'].shift()).cumsum()

        # Filter to only streaks that meet the threshold
        streaks = df[df['meets_threshold']].groupby('streak_group').agg({
            'game_date': ['first', 'last', 'count'],
            'value': 'mean'
        }).reset_index(drop=True)

        streaks.columns = ['streak_start', 'streak_end', 'length', 'avg_during_streak']
        streaks['games_in_streak'] = streaks['length']
        streaks = streaks.sort_values('length', ascending=False)

        return streaks[['streak_start', 'streak_end', 'length', 'avg_during_streak', 'games_in_streak']]
    except Exception as e:
        logger.warning(f"Error finding streaks for '{player}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="player_comparison",
    description="Side-by-side season averages for two players",
    parameters={
        "player_a": {"type": "str", "description": "First player name"},
        "player_b": {"type": "str", "description": "Second player name"},
        "stats": {"type": "list", "description": "List of stats to compare (default: all)", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def player_comparison(player_a: str, player_b: str, stats=None, season=None):
    """Compare season averages for two players.

    Args:
        player_a: First player name
        player_b: Second player name
        stats: Optional list of stats to compare (default: all)
        season: Optional season year

    Returns:
        DataFrame with columns: stat_name, player_a_name, player_a_avg, player_a_games, player_b_name, player_b_avg, player_b_games
    """
    session = get_session()
    try:
        df_a = player_game_log(player_a, season)
        df_b = player_game_log(player_b, season)

        if df_a.empty or df_b.empty:
            return pd.DataFrame()

        # Get player names
        player_a_obj = session.query(Player).filter(Player.first_name.ilike(player_a.split()[0]), Player.last_name.ilike(player_a.split()[-1])).first()
        player_b_obj = session.query(Player).filter(Player.first_name.ilike(player_b.split()[0]), Player.last_name.ilike(player_b.split()[-1])).first()

        player_a_name = f"{player_a_obj.first_name} {player_a_obj.last_name}" if player_a_obj else player_a
        player_b_name = f"{player_b_obj.first_name} {player_b_obj.last_name}" if player_b_obj else player_b

        # Define all possible stat columns
        all_stats = ['points', 'fgm', 'fga', 'fg_pct', 'fg3m', 'fg3a', 'fg3_pct', 'ftm', 'fta', 'ft_pct',
                     'oreb', 'dreb', 'reb', 'ast', 'stl', 'blk', 'tov', 'pf', 'plus_minus']

        if stats is None:
            stats = all_stats
        else:
            stats = [validate_stat(s) for s in stats]

        rows = []
        for stat_name in stats:
            if stat_name not in df_a.columns or stat_name not in df_b.columns:
                continue

            rows.append({
                'stat_name': stat_name,
                'player_a_name': player_a_name,
                'player_a_avg': df_a[stat_name].mean(),
                'player_a_games': len(df_a),
                'player_b_name': player_b_name,
                'player_b_avg': df_b[stat_name].mean(),
                'player_b_games': len(df_b),
            })

        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning(f"Error comparing players '{player_a}' and '{player_b}': {e}")
        return pd.DataFrame()
    finally:
        session.close()
