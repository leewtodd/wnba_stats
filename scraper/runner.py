"""CLI entry point and orchestration.

Phase 1: Database Schema & Historical Data Ingestion

Commands:
  python3 -m scraper.runner --season 2025
  python3 -m scraper.runner --season 2025 --start 2025-06-01 --end 2025-06-07
  python3 -m scraper.runner --seasons 2022,2023,2024,2025
  python3 -m scraper.runner --auto (queries max game_date from database)

Known API behaviors:
  - leaguedashteamstats returns 500 for all seasons (endpoint may be deprecated).
    The scraper falls back to extracting teams from playerindex. This is expected.
  - playerindex returns a limited roster snapshot (~45-52 players per season).
    Full player coverage comes from auto-upserting players found in box scores.
"""
import argparse
import logging
import sys
from datetime import datetime, date, timezone
from sqlalchemy import select, func

from models import get_engine, get_session_factory, Game, Player
from . import endpoints, loaders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def is_off_season(today=None):
    """Check if current date is in the WNBA off-season (November-April).

    Returns:
        True if off-season, False if active season (May-October).
    """
    if today is None:
        today = date.today()
    return today.month < 5 or today.month > 10


def fetch_and_load_season(season, date_from=None, date_to=None, season_type="Regular Season"):
    """Fetch and load a season worth of data.

    Args:
        season: Season year
        date_from: Optional start date (YYYY-MM-DD)
        date_to: Optional end date (YYYY-MM-DD)
        season_type: "Regular Season" or "Playoffs"

    Returns:
        Dict with counts and errors
    """
    engine = get_engine()
    SessionFactory = get_session_factory(engine)
    session = SessionFactory()

    results = {
        "teams": 0,
        "players_from_index": 0,
        "players_total": 0,
        "games": 0,
        "player_stats": 0,
        "team_stats": 0,
        "officials": 0,
        "errors": [],
    }

    try:
        # Step 1: Fetch and upsert teams
        logger.info(f"Fetching teams for {season}...")
        teams_data = endpoints.fetch_teams(season)
        teams_count = loaders.upsert_teams(session, teams_data)
        session.commit()
        results["teams"] = teams_count
        logger.info(f"✓ Loaded {teams_count} teams")

        # Step 2: Fetch and upsert players from playerindex
        # NOTE: playerindex returns a limited roster snapshot (~45-52 players).
        # Additional players are auto-upserted from box score data during Step 4.
        logger.info(f"Fetching players for {season}...")
        players_data = endpoints.fetch_players(season)
        players_count = loaders.upsert_players(session, players_data)
        session.commit()
        results["players_from_index"] = players_count
        logger.info(f"✓ Loaded {players_count} players from index (more will be added from box scores)")

        # Step 3: Fetch game log and upsert games
        logger.info(f"Fetching game log for {season}...")
        game_log = endpoints.fetch_game_log(season, date_from, date_to, season_type)
        games_count = loaders.upsert_games_from_log(session, game_log, season, season_type)
        session.commit()
        results["games"] = games_count
        logger.info(f"✓ Loaded {games_count} games")

        # Step 4: For each game, fetch box score and game summary
        # NOTE: load_boxscore auto-upserts players not in the playerindex.
        # Field name is GAME_ID (all caps) per stats.wnba.com API
        game_ids = set()
        for log_entry in game_log:
            game_id = log_entry.get("GAME_ID")
            if game_id:
                game_ids.add(str(game_id))

        logger.info(f"Fetching box scores for {len(game_ids)} unique games...")

        for i, game_id in enumerate(game_ids, 1):
            try:
                # Fetch box score (also auto-upserts players)
                boxscore = endpoints.fetch_boxscore(game_id)
                pcount, tcount = loaders.load_boxscore(session, game_id, boxscore)
                results["player_stats"] += pcount
                results["team_stats"] += tcount

                # Fetch game summary (officials)
                summary = endpoints.fetch_game_summary(game_id)
                ocount = loaders.load_officials(session, game_id, summary.get("officials", []))
                results["officials"] += ocount

                # Commit every 10 games to avoid holding a huge transaction
                if i % 10 == 0:
                    session.commit()
                    logger.info(f"  Loaded {i}/{len(game_ids)} games...")
            except Exception as e:
                error_msg = f"Game {game_id}: {str(e)}"
                logger.error(f"✗ {error_msg}")
                results["errors"].append(error_msg)
                session.rollback()
                continue

        session.commit()

        # Get actual total player count from database
        total_players = session.execute(select(func.count(Player.id))).scalar()
        results["players_total"] = total_players

        logger.info(f"✓ Loaded {results['player_stats']} player stats, "
                   f"{results['team_stats']} team stats, {results['officials']} officials")

    except Exception as e:
        logger.error(f"✗ Fatal error: {e}")
        results["errors"].append(f"Fatal: {str(e)}")
        session.rollback()
    finally:
        session.close()

    return results


def get_max_game_date():
    """Query the database for the most recent game_date.

    Returns:
        date object or None
    """
    engine = get_engine()
    SessionFactory = get_session_factory(engine)
    session = SessionFactory()

    try:
        max_date = session.execute(
            select(func.max(Game.game_date))
        ).scalar()
        return max_date
    finally:
        session.close()


def print_summary(season, results):
    """Print a summary of the load operation."""
    print(f"\n{'='*70}")
    print(f"Season {season} Summary:")
    print(f"{'='*70}")
    print(f"  Teams:         {results['teams']:>6}")
    if results.get("players_total"):
        print(f"  Players:       {results['players_total']:>6}  "
              f"({results['players_from_index']} from index, rest from box scores)")
    else:
        print(f"  Players:       {results.get('players_from_index', results.get('players', 0)):>6}")
    print(f"  Games:         {results['games']:>6}")
    print(f"  Player Stats:  {results['player_stats']:>6}")
    print(f"  Team Stats:    {results['team_stats']:>6}")
    print(f"  Officials:     {results['officials']:>6}")
    if results["errors"]:
        print(f"  Errors:        {len(results['errors']):>6}")
        for error in results["errors"][:5]:
            print(f"    - {error}")
        if len(results["errors"]) > 5:
            print(f"    ... and {len(results['errors']) - 5} more")
    print(f"{'='*70}\n")


def main():
    """Parse arguments and run the scraper."""
    parser = argparse.ArgumentParser(description="WNBA Stats Scraper")
    parser.add_argument("--season", type=int, help="Single season to pull (e.g., 2025)")
    parser.add_argument("--seasons", help="Comma-separated seasons (e.g., 2022,2023,2024,2025)")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--auto", action="store_true",
                       help="Auto-recovery mode: query max game_date and pull forward")

    args = parser.parse_args()

    seasons_to_pull = []

    if args.auto:
        # Off-season check
        if is_off_season():
            logger.info("Off-season (November-April). No pull needed.")
            return 0

        max_date = get_max_game_date()

        # First-run check
        if max_date is None:
            logger.error("No games in database. Run a historical pull first:")
            logger.error("  python3 scripts/historical_pull.py --season 2025")
            return 1

        logger.info(f"Auto-recovery: last game date is {max_date}")

        # Determine season from max_date
        current_season = max_date.year
        if max_date.month < 5:
            current_season -= 1

        # Set date window
        import datetime as dt
        start_date = (max_date + dt.timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = date.today().strftime("%Y-%m-%d")

        seasons_to_pull = [current_season]
        args.start = start_date
        args.end = today_str

        # Create ScrapeRun record
        engine = get_engine()
        SessionFactory = get_session_factory(engine)
        session = SessionFactory()

        from models.logs import ScrapeRun
        run = ScrapeRun(
            started_at=datetime.now(timezone.utc),
            mode="auto",
            season=current_season,
            date_from=max_date + dt.timedelta(days=1),
            date_to=date.today(),
        )
        session.add(run)
        session.commit()
        run_id = run.id

        try:
            results = fetch_and_load_season(
                current_season, date_from=start_date, date_to=today_str,
                season_type="Regular Season"
            )
            print_summary(current_season, results)

            # Update ScrapeRun with results
            # games = game log entries upserted; errors = box score fetch failures
            run = session.get(ScrapeRun, run_id)
            run.completed_at = datetime.now(timezone.utc)
            run.games_found = results.get("games", 0)
            run.games_failed = len(results.get("errors", []))
            run.games_loaded = run.games_found - run.games_failed
            run.player_stats_loaded = results.get("player_stats", 0)
            run.officials_loaded = results.get("officials", 0)
            run.success = len(results.get("errors", [])) == 0
            if results.get("errors"):
                run.error_message = "; ".join(results["errors"][:5])
            session.commit()

            if results.get("errors"):
                return 1
            return 0

        except Exception as e:
            logger.error(f"Auto mode failed: {e}")
            try:
                run = session.get(ScrapeRun, run_id)
                run.completed_at = datetime.now(timezone.utc)
                run.success = False
                run.error_message = str(e)[:500]
                session.commit()
            except Exception as log_err:
                logger.error(f"Failed to update ScrapeRun: {log_err}")
            return 1
        finally:
            session.close()

    elif args.seasons:
        seasons_to_pull = [int(s) for s in args.seasons.split(",")]

    elif args.season:
        seasons_to_pull = [args.season]

    else:
        parser.print_help()
        return 1

    total_results = {
        "teams": 0, "players_from_index": 0, "players_total": 0, "games": 0,
        "player_stats": 0, "team_stats": 0, "officials": 0,
        "errors": [],
    }

    for season in seasons_to_pull:
        logger.info(f"\n{'='*70}")
        logger.info(f"Pulling season {season}")
        logger.info(f"{'='*70}")

        results = fetch_and_load_season(
            season, date_from=args.start, date_to=args.end,
            season_type="Regular Season"
        )
        print_summary(season, results)

        for key in total_results:
            if key == "errors":
                total_results["errors"].extend(results["errors"])
            else:
                total_results[key] += results[key]

        if len(seasons_to_pull) > 1 and season != seasons_to_pull[-1]:
            logger.info("Waiting 60 seconds before next season...")
            import time
            time.sleep(60)

    if len(seasons_to_pull) > 1:
        logger.info(f"\nFinal Summary (all {len(seasons_to_pull)} seasons):")
        print_summary("ALL", total_results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
