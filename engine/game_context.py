"""Game context analysis: rest days, travel, home/away, schedule density."""
import logging
import pandas as pd
from scipy import stats as sp_stats
from sqlalchemy import and_, text
from engine.base import engine_function
from engine.utils import get_session, resolve_team, validate_stat
from engine.computed_fields import classify_rest
from models.core import Game, TeamGameStats

logger = logging.getLogger(__name__)


@engine_function(
    name="rest_day_impact",
    description="Compare team performance across rest day categories (back-to-back, short rest, normal rest)",
    parameters={
        "team": {"type": "str", "description": "Team name (None for league-wide)", "optional": True},
        "stat": {"type": "str", "description": "Stat to analyze", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def rest_day_impact(team=None, stat="points", season=None):
    """Analyze impact of rest days on team performance.

    Args:
        team: Optional team name. If None, league-wide analysis
        stat: Stat to analyze (default: points)
        season: Optional season year

    Returns:
        DataFrame with columns: rest_category, games, mean, std, p_value
    """
    session = get_session()
    try:
        validate_stat(stat)
        team_id = resolve_team(team, session) if team else None
        stat_col = validate_stat(stat)

        # Query TeamGameStats with rest days
        query = f"""
            SELECT tgs.{stat_col}, vtr.rest_days, g.season
            FROM team_game_stats tgs
            JOIN games g ON tgs.game_id = g.id
            LEFT JOIN v_team_rest_days vtr ON tgs.team_id = vtr.team_id AND tgs.game_id = vtr.game_id
            WHERE 1=1
        """
        params = {}

        if team_id:
            query += " AND tgs.team_id = :team_id"
            params['team_id'] = team_id

        if season:
            query += " AND g.season = :season"
            params['season'] = season

        result = session.execute(text(query), params)
        rows = result.fetchall()

        data = []
        for row in rows:
            stat_val, rest_days, season_val = row
            if stat_val is not None and rest_days is not None:
                rest_cat = classify_rest(int(rest_days))
                data.append({'rest_category': rest_cat, 'value': stat_val})

        df = pd.DataFrame(data)
        if df.empty:
            return df

        grouped = df.groupby('rest_category')['value'].agg(['count', 'mean', 'std']).reset_index()
        grouped.columns = ['rest_category', 'games', 'mean', 'std']

        # Add p-values
        overall_mean = df['value'].mean()
        p_values = []
        for cat in grouped['rest_category']:
            cat_values = df[df['rest_category'] == cat]['value'].values
            if len(cat_values) > 1:
                t_stat, p_val = sp_stats.ttest_1samp(cat_values, overall_mean, nan_policy='omit')
                p_values.append(p_val)
            else:
                p_values.append(None)

        grouped['p_value'] = p_values
        return grouped
    except Exception as e:
        logger.warning(f"Error analyzing rest day impact: {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="travel_impact",
    description="Correlate travel distance with team performance",
    parameters={
        "team": {"type": "str", "description": "Team name (None for league-wide)", "optional": True},
        "stat": {"type": "str", "description": "Stat to analyze", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
        "distance_buckets": {"type": "list", "description": "Distance bucket boundaries in miles", "optional": True},
    }
)
def travel_impact(team=None, stat="points", season=None, distance_buckets=None):
    """Analyze impact of travel distance on performance.

    Args:
        team: Optional team name
        stat: Stat to analyze (default: points)
        season: Optional season year
        distance_buckets: Optional list of bucket boundaries

    Returns:
        DataFrame with columns: distance_bucket, games, mean, std
    """
    session = get_session()
    try:
        validate_stat(stat)
        team_id = resolve_team(team, session) if team else None
        stat_col = validate_stat(stat)

        if distance_buckets is None:
            distance_buckets = [0, 500, 1000, 2000, float('inf')]

        # Query travel data
        query = f"""
            SELECT tgs.{stat_col}, vtd.travel_distance_miles, g.season
            FROM team_game_stats tgs
            JOIN games g ON tgs.game_id = g.id
            LEFT JOIN v_team_travel_distance vtd ON tgs.team_id = vtd.team_id AND tgs.game_id = vtd.game_id
            WHERE 1=1
        """
        params = {}

        if team_id:
            query += " AND tgs.team_id = :team_id"
            params['team_id'] = team_id

        if season:
            query += " AND g.season = :season"
            params['season'] = season

        result = session.execute(text(query), params)
        rows = result.fetchall()

        data = []
        for row in rows:
            stat_val, distance, season_val = row
            if stat_val is not None and distance is not None:
                # Find bucket
                bucket_idx = next((i for i, b in enumerate(distance_buckets[1:]) if distance < b), len(distance_buckets) - 1)
                bucket_label = f"{distance_buckets[bucket_idx]}-{distance_buckets[bucket_idx + 1]}"
                data.append({'distance_bucket': bucket_label, 'value': stat_val})

        df = pd.DataFrame(data)
        if df.empty:
            return df

        grouped = df.groupby('distance_bucket')['value'].agg(['count', 'mean', 'std']).reset_index()
        grouped.columns = ['distance_bucket', 'games', 'mean', 'std']
        return grouped
    except Exception as e:
        logger.warning(f"Error analyzing travel impact: {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="home_away_analysis",
    description="Compare team performance at home vs away",
    parameters={
        "team": {"type": "str", "description": "Team name (None for league-wide)", "optional": True},
        "stat": {"type": "str", "description": "Stat to analyze", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def home_away_analysis(team=None, stat="points", season=None):
    """Analyze home vs away performance.

    Args:
        team: Optional team name
        stat: Stat to analyze (default: points)
        season: Optional season year

    Returns:
        DataFrame with columns: location, games, mean, std, win_pct
    """
    session = get_session()
    try:
        validate_stat(stat)
        team_id = resolve_team(team, session) if team else None
        stat_col = validate_stat(stat)

        query = session.query(
            Game.id,
            Game.game_date,
            Game.home_team_id,
            Game.away_team_id,
            Game.home_score,
            Game.away_score,
            TeamGameStats
        ).join(
            TeamGameStats, and_(TeamGameStats.game_id == Game.id)
        )

        if team_id:
            query = query.filter(TeamGameStats.team_id == team_id)

        if season:
            query = query.filter(Game.season == season)

        games = query.all()

        rows = []
        for game_id, game_date, home_id, away_id, home_score, away_score, stats in games:
            is_home = stats.team_id == home_id
            location = "Home" if is_home else "Away"

            # Determine win
            if home_score and away_score:
                is_win = (home_score > away_score) if is_home else (away_score > home_score)
            else:
                is_win = None

            stat_val = getattr(stats, stat_col)
            if stat_val is not None:
                rows.append({
                    'location': location,
                    'value': stat_val,
                    'win': 1 if is_win else (0 if is_win is False else None)
                })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        grouped = df.groupby('location').agg({
            'value': ['count', 'mean', 'std'],
            'win': 'mean'
        }).reset_index()

        grouped.columns = ['location', 'games', 'mean', 'std', 'win_pct']
        grouped['win_pct'] = grouped['win_pct'] * 100  # Convert to percentage
        return grouped
    except Exception as e:
        logger.warning(f"Error analyzing home/away impact: {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="schedule_density_impact",
    description="Measure how the number of games in the last N days correlates with performance",
    parameters={
        "team": {"type": "str", "description": "Team name (None for league-wide)", "optional": True},
        "stat": {"type": "str", "description": "Stat to analyze", "optional": True},
        "window": {"type": "int", "description": "Lookback window in days", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def schedule_density_impact(team=None, stat="points", window=7, season=None):
    """Analyze impact of schedule density on performance.

    Args:
        team: Optional team name
        stat: Stat to analyze (default: points)
        window: Lookback window in days (default: 7)
        season: Optional season year

    Returns:
        DataFrame with columns: games_in_window, sample_size, mean, std
    """
    session = get_session()
    try:
        validate_stat(stat)
        team_id = resolve_team(team, session) if team else None
        stat_col = validate_stat(stat)

        query = session.query(
            Game.game_date,
            Game.id,
            TeamGameStats
        ).join(
            TeamGameStats, TeamGameStats.game_id == Game.id
        )

        if team_id:
            query = query.filter(TeamGameStats.team_id == team_id)

        if season:
            query = query.filter(Game.season == season)

        games = query.order_by(Game.game_date).all()

        rows = []
        for game_date, game_id, stats in games:
            # Count games in preceding window
            from datetime import timedelta
            window_start = game_date - timedelta(days=window)

            games_in_window = len([
                g for g in games
                if g[0] >= window_start and g[0] < game_date and g[2].team_id == stats.team_id
            ])

            stat_val = getattr(stats, stat_col)
            if stat_val is not None:
                rows.append({
                    'games_in_window': games_in_window,
                    'value': stat_val
                })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        grouped = df.groupby('games_in_window')['value'].agg(['count', 'mean', 'std']).reset_index()
        grouped.columns = ['games_in_window', 'sample_size', 'mean', 'std']
        return grouped
    except Exception as e:
        logger.warning(f"Error analyzing schedule density impact: {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="back_to_back_analysis",
    description="Comprehensive back-to-back game analysis: win rate, scoring, key stat changes",
    parameters={
        "team": {"type": "str", "description": "Team name (None for league-wide)", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def back_to_back_analysis(team=None, season=None):
    """Analyze back-to-back game performance.

    Args:
        team: Optional team name
        season: Optional season year

    Returns:
        DataFrame with columns: metric, b2b_value, non_b2b_value, difference, sample_b2b, sample_non_b2b
    """
    session = get_session()
    try:
        team_id = resolve_team(team, session) if team else None

        # Query with rest days
        query = """
            SELECT tgs.points, tgs.fg_pct, tgs.reb, tgs.tov, vtr.rest_days, g.season, g.home_team_id, g.away_team_id, g.home_score, g.away_score, tgs.team_id
            FROM team_game_stats tgs
            JOIN games g ON tgs.game_id = g.id
            LEFT JOIN v_team_rest_days vtr ON tgs.team_id = vtr.team_id AND tgs.game_id = vtr.game_id
            WHERE 1=1
        """
        params = {}

        if team_id:
            query += " AND tgs.team_id = :team_id"
            params['team_id'] = team_id

        if season:
            query += " AND g.season = :season"
            params['season'] = season

        result = session.execute(text(query), params)
        rows = result.fetchall()

        b2b_rows = []
        non_b2b_rows = []

        for row in rows:
            points, fg_pct, reb, tov, rest_days, season_val, home_id, away_id, home_score, away_score, team_id_val = row

            if rest_days is None:
                continue

            is_b2b = int(rest_days) <= 1
            team_id_for_calc = team_id_val

            # Determine win
            is_home = team_id_for_calc == home_id
            if home_score and away_score:
                is_win = (home_score > away_score) if is_home else (away_score > home_score)
            else:
                is_win = None

            data = {
                'win': 1 if is_win else 0 if is_win is False else None,
                'points': points,
                'fg_pct': fg_pct,
                'reb': reb,
                'tov': tov
            }

            if is_b2b:
                b2b_rows.append(data)
            else:
                non_b2b_rows.append(data)

        b2b_df = pd.DataFrame(b2b_rows)
        non_b2b_df = pd.DataFrame(non_b2b_rows)

        results = []
        for metric in ['win', 'points', 'fg_pct', 'reb', 'tov']:
            b2b_val = b2b_df[metric].mean() if not b2b_df.empty else None
            non_b2b_val = non_b2b_df[metric].mean() if not non_b2b_df.empty else None

            if metric == 'win' and b2b_val is not None:
                b2b_val *= 100
                non_b2b_val *= 100
                metric_name = 'win_pct'
            else:
                metric_name = f'avg_{metric}'

            results.append({
                'metric': metric_name,
                'b2b_value': b2b_val,
                'non_b2b_value': non_b2b_val,
                'difference': b2b_val - non_b2b_val if b2b_val and non_b2b_val else None,
                'sample_b2b': len(b2b_df),
                'sample_non_b2b': len(non_b2b_df)
            })

        return pd.DataFrame(results)
    except Exception as e:
        logger.warning(f"Error analyzing back-to-back impact: {e}")
        return pd.DataFrame()
    finally:
        session.close()
