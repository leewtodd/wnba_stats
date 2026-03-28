"""Endpoint-specific fetch functions.

Each function fetches from a stats.wnba.com endpoint and normalizes the response
from the API's parallel-array format to list[dict].

Season format: WNBA uses cross-year format "2024-25" even though
the season runs within a single calendar year (May-October).
"""
import logging
from .client import fetch_endpoint

logger = logging.getLogger(__name__)


def _normalize_result_set(headers, rows):
    """Normalize parallel array format to list[dict]."""
    return [dict(zip(headers, row)) for row in rows]


def _format_season(year):
    """Convert integer year to API season format.

    The WNBA stats API uses cross-year format like "2024-25"
    even though the WNBA season runs within a single calendar year.
    """
    next_year_short = str(year + 1)[-2:]
    return f"{year}-{next_year_short}"


def fetch_teams(season):
    """Fetch all teams for a season.

    NOTE: leaguedashteamstats returns 500 errors as of 2026-03.
    We fall back to extracting unique teams from playerindex, which
    includes TEAM_ID, TEAM_NAME, TEAM_CITY, TEAM_ABBREVIATION.
    """
    season_str = _format_season(season)

    try:
        response = fetch_endpoint("leaguedashteamstats", {
            "LeagueID": "10",
            "Season": season_str,
            "PerMode": "PerGame",
            "MeasureType": "Base",
        })
        result_set = response.get("resultSets", [{}])[0]
        headers = result_set.get("headers", [])
        rows = result_set.get("rowSet", [])
        if rows:
            logger.info(f"leaguedashteamstats returned {len(rows)} teams")
            return _normalize_result_set(headers, rows)
    except Exception as e:
        logger.warning(f"leaguedashteamstats failed ({e}), falling back to playerindex")

    # Fallback: extract unique teams from playerindex
    logger.info("Extracting teams from playerindex endpoint")
    response = fetch_endpoint("playerindex", {
        "LeagueID": "10",
        "Season": season_str,
    })
    result_set = response.get("resultSets", [{}])[0]
    headers = result_set.get("headers", [])
    rows = result_set.get("rowSet", [])
    players = _normalize_result_set(headers, rows)

    teams_seen = {}
    for player in players:
        team_id = player.get("TEAM_ID")
        if team_id and team_id not in teams_seen:
            teams_seen[team_id] = {
                "TEAM_ID": team_id,
                "TEAM_NAME": player.get("TEAM_NAME", ""),
                "TEAM_CITY": player.get("TEAM_CITY", ""),
                "TEAM_ABBREVIATION": player.get("TEAM_ABBREVIATION", ""),
            }

    teams = list(teams_seen.values())
    logger.info(f"Extracted {len(teams)} unique teams from playerindex")
    return teams


def fetch_players(season):
    """Fetch all players for a season.

    Returns list of dicts with keys: PERSON_ID, PLAYER_FIRST_NAME,
    PLAYER_LAST_NAME, POSITION, HEIGHT, WEIGHT, TEAM_ID, etc.
    """
    season_str = _format_season(season)
    response = fetch_endpoint("playerindex", {
        "LeagueID": "10",
        "Season": season_str,
    })
    result_set = response.get("resultSets", [{}])[0]
    headers = result_set.get("headers", [])
    rows = result_set.get("rowSet", [])
    return _normalize_result_set(headers, rows)


def fetch_game_log(season, date_from=None, date_to=None, season_type="Regular Season"):
    """Fetch game log for a season (optionally filtered by date range).

    Returns list of dicts with keys: GAME_ID, GAME_DATE (string "2024-08-25"),
    TEAM_ID, MATCHUP, WL, PTS, etc.
    """
    season_str = _format_season(season)
    params = {
        "LeagueID": "10",
        "Season": season_str,
        "SeasonType": season_type,
        "PlayerOrTeam": "T",
    }
    if date_from:
        params["DateFrom"] = date_from
    if date_to:
        params["DateTo"] = date_to

    response = fetch_endpoint("leaguegamelog", params)
    result_set = response.get("resultSets", [{}])[0]
    headers = result_set.get("headers", [])
    rows = result_set.get("rowSet", [])
    return _normalize_result_set(headers, rows)


def fetch_boxscore(game_id):
    """Fetch box score for a game.

    Returns dict with player_stats and team_stats lists.
    NOTE: Turnovers field is "TO" not "TOV" in the boxscore endpoints.
    """
    response = fetch_endpoint("boxscoretraditionalv2", {"GameID": game_id})
    result_sets = response.get("resultSets", [])

    player_result = result_sets[0] if len(result_sets) > 0 else {}
    team_result = result_sets[1] if len(result_sets) > 1 else {}

    return {
        "player_stats": _normalize_result_set(
            player_result.get("headers", []), player_result.get("rowSet", [])
        ),
        "team_stats": _normalize_result_set(
            team_result.get("headers", []), team_result.get("rowSet", [])
        ),
    }


def fetch_game_summary(game_id):
    """Fetch game summary (officials and game info).

    Officials resultSet has: OFFICIAL_ID, FIRST_NAME, LAST_NAME, JERSEY_NUM.
    NOTE: There is no OFFICIAL_NAME field — name is FIRST_NAME + LAST_NAME.
    """
    response = fetch_endpoint("boxscoresummaryv2", {"GameID": game_id})
    result_sets = response.get("resultSets", [])

    officials = []
    game_info = []
    for result_set in result_sets:
        name = result_set.get("name", "")
        headers = result_set.get("headers", [])
        rows = result_set.get("rowSet", [])
        normalized = _normalize_result_set(headers, rows)
        if name == "Officials":
            officials = normalized
        elif name == "GameInfo":
            game_info = normalized

    return {"officials": officials, "game_info": game_info}
