"""Referee and officiating crew analysis."""
import logging
import pandas as pd
from scipy import stats as sp_stats
from sqlalchemy import and_
from engine.base import engine_function
from engine.utils import get_session, validate_stat
from models.core import Game, Team, TeamGameStats
from models.officials import GameOfficial

logger = logging.getLogger(__name__)


@engine_function(
    name="referee_game_log",
    description="Show all games officiated by a referee",
    parameters={
        "referee_name": {"type": "str", "description": "Referee name (full or partial)"},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def referee_game_log(referee_name: str, season=None):
    """Get game log for a referee.

    Args:
        referee_name: Referee name (full or partial match)
        season: Optional season year

    Returns:
        DataFrame with columns: game_date, home_team, away_team, home_score, away_score,
        total_fouls, total_fta
    """
    session = get_session()
    try:
        # Find referee
        query = session.query(GameOfficial).filter(
            GameOfficial.official_name.ilike(f"%{referee_name}%")
        )

        officials = query.all()
        if not officials:
            return pd.DataFrame()

        # Get unique game IDs for this referee
        game_ids = set(off.game_id for off in officials)

        # Query games with team stats
        games = session.query(Game).filter(Game.id.in_(game_ids))

        if season is not None:
            games = games.filter(Game.season == season)

        games = games.all()

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

            total_fouls = (home_stats.pf if home_stats else 0) + (away_stats.pf if away_stats else 0)
            total_fta = (home_stats.fta if home_stats else 0) + (away_stats.fta if away_stats else 0)

            rows.append({
                'game_date': game.game_date,
                'home_team': home_team.abbreviation if home_team else 'Unknown',
                'away_team': away_team.abbreviation if away_team else 'Unknown',
                'home_score': game.home_score,
                'away_score': game.away_score,
                'total_fouls': total_fouls,
                'total_fta': total_fta,
            })

        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning(f"Error getting referee game log for '{referee_name}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="referee_impact",
    description="For each referee, show average stat in their games vs league average",
    parameters={
        "stat": {"type": "str", "description": "Stat to analyze (default: personal fouls)", "optional": True},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def referee_impact(stat="pf", season=None):
    """Analyze referee impact on game stats.

    Args:
        stat: Stat to analyze (default: pf for personal fouls)
        season: Optional season year

    Returns:
        DataFrame with columns: referee_name, games_officiated, avg_stat, league_avg,
        deviation, p_value
    """
    session = get_session()
    try:
        validate_stat(stat)
        stat_col = validate_stat(stat)

        # Get league average
        query = session.query(TeamGameStats)

        if season is not None:
            query = query.join(Game, Game.id == TeamGameStats.game_id).filter(Game.season == season)

        all_stats = query.all()
        league_values = [getattr(s, stat_col) for s in all_stats if getattr(s, stat_col) is not None]
        league_avg = sum(league_values) / len(league_values) if league_values else 0

        # Get unique referees
        refs = session.query(GameOfficial.official_name).distinct().all()

        rows = []
        for (ref_name,) in refs:
            # Get games for this referee
            ref_games = session.query(GameOfficial).filter(
                GameOfficial.official_name == ref_name
            ).all()

            game_ids = [rg.game_id for rg in ref_games]

            # Get stats for games with this referee
            query = session.query(TeamGameStats).filter(TeamGameStats.game_id.in_(game_ids))

            if season is not None:
                query = query.join(Game, Game.id == TeamGameStats.game_id).filter(Game.season == season)

            ref_stats = query.all()
            ref_values = [getattr(s, stat_col) for s in ref_stats if getattr(s, stat_col) is not None]

            if len(ref_values) >= 10:  # Filter to >= 10 games
                ref_avg = sum(ref_values) / len(ref_values)
                deviation = ref_avg - league_avg

                # T-test
                t_stat, p_val = sp_stats.ttest_1samp(ref_values, league_avg, nan_policy='omit')

                rows.append({
                    'referee_name': ref_name,
                    'games_officiated': len(ref_values),
                    'avg_stat': ref_avg,
                    'league_avg': league_avg,
                    'deviation': deviation,
                    'p_value': p_val,
                })

        df = pd.DataFrame(rows)
        df = df.sort_values('deviation', key=abs, ascending=False)
        return df
    except Exception as e:
        logger.warning(f"Error analyzing referee impact: {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="referee_team_tendencies",
    description="How a referee's games affect each team's stats",
    parameters={
        "referee_name": {"type": "str", "description": "Referee name"},
        "season": {"type": "int", "description": "Season year", "optional": True},
    }
)
def referee_team_tendencies(referee_name: str, season=None):
    """Analyze how a referee's calls affect team statistics.

    Args:
        referee_name: Referee name
        season: Optional season year

    Returns:
        DataFrame with columns: team_name, games_with_ref, avg_pf_with_ref,
        avg_pf_overall, difference
    """
    session = get_session()
    try:
        # Find games with this referee
        ref_games = session.query(GameOfficial).filter(
            GameOfficial.official_name.ilike(f"%{referee_name}%")
        ).all()

        ref_game_ids = [rg.game_id for rg in ref_games]

        # Get all teams
        teams = session.query(Team).all()

        rows = []
        for team in teams:
            # Stats with referee
            with_ref = session.query(TeamGameStats).filter(
                and_(TeamGameStats.team_id == team.id, TeamGameStats.game_id.in_(ref_game_ids))
            )

            if season is not None:
                with_ref = with_ref.join(Game, Game.id == TeamGameStats.game_id).filter(Game.season == season)

            with_ref_stats = with_ref.all()
            with_ref_pf = [s.pf for s in with_ref_stats if s.pf is not None]

            # All stats for team
            all_team = session.query(TeamGameStats).filter(TeamGameStats.team_id == team.id)

            if season is not None:
                all_team = all_team.join(Game, Game.id == TeamGameStats.game_id).filter(Game.season == season)

            all_stats = all_team.all()
            all_pf = [s.pf for s in all_stats if s.pf is not None]

            if with_ref_pf:
                avg_with_ref = sum(with_ref_pf) / len(with_ref_pf)
                avg_overall = sum(all_pf) / len(all_pf) if all_pf else 0
                difference = avg_with_ref - avg_overall

                rows.append({
                    'team_name': team.abbreviation,
                    'games_with_ref': len(with_ref_pf),
                    'avg_pf_with_ref': avg_with_ref,
                    'avg_pf_overall': avg_overall,
                    'difference': difference,
                })

        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning(f"Error analyzing referee team tendencies for '{referee_name}': {e}")
        return pd.DataFrame()
    finally:
        session.close()


@engine_function(
    name="crew_analysis",
    description="Show the officiating crew for a game and their historical tendencies",
    parameters={
        "game_id": {"type": "str", "description": "Game ID string"},
    }
)
def crew_analysis(game_id: str):
    """Analyze the officiating crew for a game.

    Args:
        game_id: Game ID string

    Returns:
        DataFrame with columns: official_name, jersey_number, career_games,
        avg_total_fouls, avg_total_fta
    """
    session = get_session()
    try:
        # Get officials for this game
        officials = session.query(GameOfficial).filter(GameOfficial.game_id == game_id).all()

        rows = []
        for official in officials:
            # Get all games this official worked
            career_games = session.query(GameOfficial).filter(
                GameOfficial.official_id == official.official_id
            ).all()

            career_game_ids = [cg.game_id for cg in career_games]

            # Get team stats for career games
            career_stats = session.query(TeamGameStats).filter(
                TeamGameStats.game_id.in_(career_game_ids)
            ).all()

            total_fouls = [s.pf for s in career_stats if s.pf is not None]
            total_fta = [s.fta for s in career_stats if s.fta is not None]

            avg_total_fouls = sum(total_fouls) / len(total_fouls) if total_fouls else 0
            avg_total_fta = sum(total_fta) / len(total_fta) if total_fta else 0

            rows.append({
                'official_name': official.official_name,
                'jersey_number': official.jersey_number,
                'career_games': len(career_game_ids),
                'avg_total_fouls': avg_total_fouls,
                'avg_total_fta': avg_total_fta,
            })

        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning(f"Error analyzing crew for game '{game_id}': {e}")
        return pd.DataFrame()
    finally:
        session.close()
