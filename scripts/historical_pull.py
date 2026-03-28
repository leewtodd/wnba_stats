"""Multi-season historical ingestion orchestrator.

Phase 1: Database Schema & Historical Data Ingestion

Orchestrates pulling all four historical seasons (2022-2025) with delays
between seasons to avoid rate limiting. Can pull one season or all.

Usage:
  python scripts/historical_pull.py                  # Pull all 4 seasons with delays
  python scripts/historical_pull.py --season 2025    # Pull just 2025
"""
import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SEASONS = [2022, 2023, 2024, 2025]
INTER_SEASON_DELAY = 60  # seconds between seasons


def estimate_pull_time():
    """Estimate how long a full historical pull will take."""
    # Rough estimate: 4 seasons × 40 games × 3 API calls per game
    # = ~480 API calls × 1.5s rate limit = ~12 minutes, plus overhead
    num_games_per_season = 40  # rough estimate
    api_calls_per_game = 3  # boxscore + game_summary + game_log fetch
    rate_limit_delay = 1.5  # seconds

    total_api_calls = len(SEASONS) * num_games_per_season * api_calls_per_game
    total_time_seconds = total_api_calls * rate_limit_delay
    total_time_seconds += (len(SEASONS) - 1) * INTER_SEASON_DELAY

    hours = total_time_seconds / 3600
    return total_time_seconds, hours


def pull_season(season):
    """Pull one season of data using the scraper.runner module.

    Args:
        season: Season year

    Returns:
        0 on success, 1 on failure
    """
    logger.info(f"Starting pull for season {season}...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scraper.runner", "--season", str(season)],
            capture_output=False,
            text=True,
        )
        return result.returncode
    except Exception as e:
        logger.error(f"Error pulling season {season}: {e}")
        return 1


def main():
    """Parse arguments and orchestrate historical pull."""
    parser = argparse.ArgumentParser(
        description="Pull historical WNBA data (2022-2025)"
    )
    parser.add_argument(
        "--season",
        type=int,
        help="Pull a single season (e.g., --season 2025)"
    )
    args = parser.parse_args()

    seasons_to_pull = []

    if args.season:
        if args.season not in SEASONS:
            logger.error(f"Season {args.season} not in {SEASONS}")
            return 1
        seasons_to_pull = [args.season]
    else:
        seasons_to_pull = SEASONS

    # Warn user about timing
    if len(seasons_to_pull) > 1:
        total_time, hours = estimate_pull_time()
        logger.warning(f"\n{'='*70}")
        logger.warning(f"Estimated time: {hours:.1f} hours ({int(total_time/60)} minutes)")
        logger.warning(f"Will pull seasons: {', '.join(str(s) for s in seasons_to_pull)}")
        logger.warning(f"Delay between seasons: {INTER_SEASON_DELAY}s")
        logger.warning(f"{'='*70}\n")

        # Prompt user
        response = input("Continue? (y/n) ")
        if response.lower() != "y":
            logger.info("Cancelled.")
            return 0

    # Pull each season
    failed_seasons = []
    for i, season in enumerate(seasons_to_pull):
        logger.info(f"\nPulling season {season} ({i+1}/{len(seasons_to_pull)})...")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        returncode = pull_season(season)
        if returncode != 0:
            failed_seasons.append(season)

        # Wait before next season if not the last one
        if i < len(seasons_to_pull) - 1:
            logger.info(f"Waiting {INTER_SEASON_DELAY}s before next season...")
            time.sleep(INTER_SEASON_DELAY)

    # Final report
    logger.info(f"\n{'='*70}")
    logger.info("Historical Pull Complete")
    logger.info(f"{'='*70}")
    logger.info(f"Pulled {len(seasons_to_pull)} seasons")
    if failed_seasons:
        logger.error(f"Failed seasons: {', '.join(str(s) for s in failed_seasons)}")
        return 1
    else:
        logger.info("✓ All seasons pulled successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
