"""Statistical correlation analysis between stats."""
import logging
import pandas as pd
import numpy as np
from scipy import stats as sp_stats
from itertools import combinations
from engine.base import engine_function
from engine.utils import get_session, resolve_team, validate_stat
from models.core import Game, PlayerGameStats, TeamGameStats

logger = logging.getLogger(__name__)


@engine_function(
    name="correlate_stats",
    description="Compute Pearson and Spearman correlation between two stats",
    parameters={
        "stat_x": {"type": "str", "description": "First stat"},
        "stat_y": {"type": "str", "description": "Second stat"},
        "level": {"type": "str", "description": "'player_game', 'team_game', or 'player_season'", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
        "team": {"type": "str", "description": "Filter to one team", "optional": True},
    }
)
def correlate_stats(stat_x: str, stat_y: str, level: str = "player_game", season=None, team=None):
    """Compute correlation between two stats.

    Args:
        stat_x: First stat
        stat_y: Second stat
        level: 'player_game', 'team_game', or 'player_season'
        season: Optional season year
        team: Optional team name

    Returns:
        DataFrame with columns: stat_x_value, stat_y_value
        df.attrs contains: r_value, p_value, r_squared, spearman_r, spearman_p, sample_size
    """
    session = get_session()
    try:
        col_x = validate_stat(stat_x)
        col_y = validate_stat(stat_y)
        team_id = resolve_team(team, session) if team else None

        data_x = []
        data_y = []

        if level == "player_game":
            query = session.query(PlayerGameStats, Game.season)
            query = query.join(Game, Game.id == PlayerGameStats.game_id)

            if season:
                query = query.filter(Game.season == season)
            if team_id:
                query = query.filter(PlayerGameStats.team_id == team_id)

            rows = query.all()
            for stat, season_val in rows:
                x_val = getattr(stat, col_x)
                y_val = getattr(stat, col_y)
                if x_val is not None and y_val is not None:
                    data_x.append(x_val)
                    data_y.append(y_val)

        elif level == "team_game":
            query = session.query(TeamGameStats, Game.season)
            query = query.join(Game, Game.id == TeamGameStats.game_id)

            if season:
                query = query.filter(Game.season == season)
            if team_id:
                query = query.filter(TeamGameStats.team_id == team_id)

            rows = query.all()
            for stat, season_val in rows:
                x_val = getattr(stat, col_x)
                y_val = getattr(stat, col_y)
                if x_val is not None and y_val is not None:
                    data_x.append(x_val)
                    data_y.append(y_val)

        elif level == "player_season":
            # Aggregate by player and season
            query = session.query(PlayerGameStats, Game.season)
            query = query.join(Game, Game.id == PlayerGameStats.game_id)

            if season:
                query = query.filter(Game.season == season)
            if team_id:
                query = query.filter(PlayerGameStats.team_id == team_id)

            rows = query.all()
            player_season_data = {}

            for stat, season_val in rows:
                key = (stat.player_id, season_val)
                if key not in player_season_data:
                    player_season_data[key] = []
                x_val = getattr(stat, col_x)
                y_val = getattr(stat, col_y)
                if x_val is not None and y_val is not None:
                    player_season_data[key].append((x_val, y_val))

            for values in player_season_data.values():
                if values:
                    avg_x = sum(x for x, y in values) / len(values)
                    avg_y = sum(y for x, y in values) / len(values)
                    data_x.append(avg_x)
                    data_y.append(avg_y)

        if not data_x or not data_y or len(data_x) < 2:
            return pd.DataFrame()

        # Compute correlations
        r_value, p_value = sp_stats.pearsonr(data_x, data_y)
        r_squared = r_value ** 2
        spearman_r, spearman_p = sp_stats.spearmanr(data_x, data_y)

        df = pd.DataFrame({'stat_x_value': data_x, 'stat_y_value': data_y})
        df.attrs['r_value'] = r_value
        df.attrs['p_value'] = p_value
        df.attrs['r_squared'] = r_squared
        df.attrs['spearman_r'] = spearman_r
        df.attrs['spearman_p'] = spearman_p
        df.attrs['sample_size'] = len(data_x)

        return df
    except Exception as e:
        logger.warning(f"Error correlating stats '{stat_x}' and '{stat_y}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="correlation_matrix",
    description="Compute correlation matrix across multiple stats",
    parameters={
        "stats": {"type": "list", "description": "List of stat names (3-8 recommended)"},
        "level": {"type": "str", "description": "'player_game' or 'team_game'", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def correlation_matrix(stats: list, level: str = "team_game", season=None):
    """Compute correlation matrix across multiple stats.

    Args:
        stats: List of stat names
        level: 'player_game' or 'team_game'
        season: Optional season year

    Returns:
        Correlation matrix DataFrame
        df.attrs['p_values'] contains p-value matrix
    """
    session = get_session()
    try:
        cols = [validate_stat(s) for s in stats]

        if level == "team_game":
            query = session.query(TeamGameStats, Game.season)
            query = query.join(Game, Game.id == TeamGameStats.game_id)

            if season:
                query = query.filter(Game.season == season)

            rows = query.all()
            data = []
            for stat, season_val in rows:
                values = {}
                for col in cols:
                    val = getattr(stat, col)
                    if val is not None:
                        values[col] = val
                    else:
                        values[col] = np.nan
                data.append(values)

        elif level == "player_game":
            query = session.query(PlayerGameStats, Game.season)
            query = query.join(Game, Game.id == PlayerGameStats.game_id)

            if season:
                query = query.filter(Game.season == season)

            rows = query.all()
            data = []
            for stat, season_val in rows:
                values = {}
                for col in cols:
                    val = getattr(stat, col)
                    if val is not None:
                        values[col] = val
                    else:
                        values[col] = np.nan
                data.append(values)

        df = pd.DataFrame(data)
        corr_matrix = df.corr(method='pearson')

        # Compute p-values
        p_values = pd.DataFrame(index=corr_matrix.index, columns=corr_matrix.columns)
        for stat1, stat2 in combinations(cols, 2):
            if stat1 in df.columns and stat2 in df.columns:
                data1 = df[stat1].dropna()
                data2 = df[stat2].dropna()
                if len(data1) > 1 and len(data2) > 1:
                    _, p = sp_stats.pearsonr(data1, data2)
                    p_values.loc[stat1, stat2] = p
                    p_values.loc[stat2, stat1] = p

        corr_matrix.attrs['p_values'] = p_values
        return corr_matrix
    except Exception as e:
        logger.warning(f"Error computing correlation matrix: {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="stat_vs_outcome",
    description="Correlate a stat with win/loss outcome using logistic regression",
    parameters={
        "stat": {"type": "str", "description": "Stat to test"},
        "level": {"type": "str", "description": "'team_game' level", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def stat_vs_outcome(stat: str, level: str = "team_game", season=None):
    """Analyze stat's correlation with winning.

    Args:
        stat: Stat to analyze
        level: 'team_game' level (default)
        season: Optional season year

    Returns:
        DataFrame with columns: stat_value, win (0/1)
        df.attrs contains: coefficient, p_value, odds_ratio, pseudo_r_squared
    """
    session = get_session()
    try:
        import statsmodels.api as sm

        col = validate_stat(stat)

        query = session.query(TeamGameStats, Game.home_team_id, Game.away_team_id, Game.home_score, Game.away_score)
        query = query.join(Game, Game.id == TeamGameStats.game_id)

        if season:
            query = query.filter(Game.season == season)

        rows = query.all()
        data = []

        for tgs, home_id, away_id, home_score, away_score in rows:
            stat_val = getattr(tgs, col)
            if stat_val is not None and home_score and away_score:
                is_home = tgs.team_id == home_id
                is_win = (home_score > away_score) if is_home else (away_score > home_score)
                data.append({'stat_value': stat_val, 'win': 1 if is_win else 0})

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Logistic regression
        X = df[['stat_value']].values
        y = df['win'].values

        X = sm.add_constant(X)
        model = sm.Logit(y, X)
        result = model.fit(disp=0)

        coef = result.params[1]
        p_val = result.pvalues[1]
        odds_ratio = np.exp(coef)
        pseudo_r2 = result.prsquared

        df = df[['stat_value', 'win']]
        df.attrs['coefficient'] = coef
        df.attrs['p_value'] = p_val
        df.attrs['odds_ratio'] = odds_ratio
        df.attrs['pseudo_r_squared'] = pseudo_r2

        return df
    except Exception as e:
        logger.warning(f"Error analyzing stat vs outcome for '{stat}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="find_strong_correlations",
    description="Scan all stat pairs and find statistically significant correlations",
    parameters={
        "level": {"type": "str", "description": "'player_game' or 'team_game'", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
        "min_r": {"type": "float", "description": "Minimum absolute r-value", "optional": True},
        "max_p": {"type": "float", "description": "Maximum p-value", "optional": True},
    }
)
def find_strong_correlations(level: str = "team_game", season=None, min_r: float = 0.5, max_p: float = 0.05):
    """Find strong correlations across all stat pairs.

    Args:
        level: 'player_game' or 'team_game'
        season: Optional season year
        min_r: Minimum absolute r-value (default 0.5)
        max_p: Maximum p-value (default 0.05)

    Returns:
        DataFrame with columns: stat_x, stat_y, r_value, p_value, abs_r
    """
    session = get_session()
    try:
        # Get all stat columns
        if level == "team_game":
            model = TeamGameStats
        else:
            model = PlayerGameStats

        stat_cols = []
        for col in model.__table__.columns:
            if col.name not in ['id', 'team_id', 'player_id', 'game_id', 'created_at', 'updated_at', 'minutes']:
                try:
                    validate_stat(col.name)
                    stat_cols.append(col.name)
                except ValueError:
                    pass

        rows = []

        # Check all pairs
        for stat_x, stat_y in combinations(stat_cols, 2):
            df = correlate_stats(stat_x, stat_y, level=level, season=season)

            if not df.empty and 'r_value' in df.attrs:
                r_val = df.attrs['r_value']
                p_val = df.attrs['p_value']

                if abs(r_val) >= min_r and p_val <= max_p:
                    rows.append({
                        'stat_x': stat_x,
                        'stat_y': stat_y,
                        'r_value': r_val,
                        'p_value': p_val,
                        'abs_r': abs(r_val)
                    })

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        df = df.sort_values('abs_r', ascending=False)
        return df
    except Exception as e:
        logger.warning(f"Error finding strong correlations: {e}")
        return pd.DataFrame()
    finally:
        session.close()
