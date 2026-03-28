"""Database upsert functions using PostgreSQL INSERT ... ON CONFLICT DO UPDATE.

API Field Name Reference (verified via verify_api_fields.py diagnostic):
  playerindex:            PERSON_ID, PLAYER_FIRST_NAME, PLAYER_LAST_NAME, POSITION, HEIGHT, WEIGHT,
                          TEAM_ID, TEAM_NAME, TEAM_CITY, TEAM_ABBREVIATION
  leaguegamelog:          GAME_ID, GAME_DATE (string "2024-08-25"), TEAM_ID, MATCHUP, PTS, WL
  boxscoretraditionalv2:  PLAYER_ID, PLAYER_NAME, TEAM_ID, MIN, PTS, FGM, ..., TO (not TOV!), PF, PLUS_MINUS
  boxscoresummaryv2:      OFFICIAL_ID, FIRST_NAME, LAST_NAME, JERSEY_NUM

API Team Abbreviations (verified via check_teams.py):
  Eastern: ATL, CHI, CON, IND, NYL, WAS
  Western: DAL, LAS, LVA, MIN, PHO, SEA
  Expansion (2025): GS (Golden State Valkyries)
"""
import logging
from datetime import datetime, date as date_type, timezone
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models import Team, Player, Game, PlayerGameStats, TeamGameStats, GameOfficial

logger = logging.getLogger(__name__)

# Conference lookup — uses API abbreviations (verified via check_teams.py).
TEAM_CONFERENCE = {
    "ATL": "Eastern", "CHI": "Eastern", "CON": "Eastern",
    "IND": "Eastern", "NYL": "Eastern", "WAS": "Eastern",
    "DAL": "Western", "LAS": "Western", "LVA": "Western",
    "MIN": "Western", "PHO": "Western", "SEA": "Western",
    "GS": "Western",  # Golden State Valkyries, expansion 2025
}


def _parse_game_date(date_val):
    """Parse game date from API response to Python date.
    leaguegamelog returns GAME_DATE as string like '2024-08-25'.
    """
    if isinstance(date_val, date_type):
        return date_val
    if isinstance(date_val, str):
        for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%b %d, %Y", "%B %d, %Y"]:
            try:
                return datetime.strptime(date_val, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Could not parse game date: {date_val!r}")
    return date_val


def _split_player_name(full_name):
    """Split 'First Last' or 'First M. Last' into (first, last).
    If only one word, treat it as last name.
    """
    if not full_name:
        return ("", "")
    parts = full_name.strip().split()
    if len(parts) == 1:
        return ("", parts[0])
    return (parts[0], " ".join(parts[1:]))


def upsert_teams(session, teams_data):
    """Upsert teams. Fields: TEAM_ID, TEAM_NAME, TEAM_CITY, TEAM_ABBREVIATION."""
    if not teams_data:
        return 0
    count = 0
    for td in teams_data:
        team_id = td.get("TEAM_ID")
        if not team_id:
            logger.warning(f"Team data missing TEAM_ID: {td}")
            continue
        abbr = td.get("TEAM_ABBREVIATION", "")
        team_name = td.get("TEAM_NAME", "")
        city = td.get("TEAM_CITY", "")
        full_name = f"{city} {team_name}".strip() if city and team_name else team_name
        conference = TEAM_CONFERENCE.get(abbr, "Unknown")
        stmt = pg_insert(Team).values(
            id=team_id, full_name=full_name, abbreviation=abbr,
            city=city, conference=conference,
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={"full_name": full_name, "abbreviation": abbr,
                   "city": city, "conference": conference,
                   "updated_at": datetime.now(timezone.utc)},
        )
        session.execute(stmt)
        count += 1
    session.flush()
    return count


def upsert_players(session, players_data):
    """Upsert players. Fields: PERSON_ID, PLAYER_FIRST_NAME, PLAYER_LAST_NAME, POSITION, HEIGHT, WEIGHT."""
    if not players_data:
        return 0
    count = 0
    for pd_ in players_data:
        player_id = pd_.get("PERSON_ID")
        if not player_id:
            logger.warning(f"Player data missing PERSON_ID: {pd_}")
            continue
        first_name = pd_.get("PLAYER_FIRST_NAME", "")
        last_name = pd_.get("PLAYER_LAST_NAME", "")
        position = pd_.get("POSITION")
        height = pd_.get("HEIGHT")
        weight = pd_.get("WEIGHT")
        if weight is not None:
            weight = str(weight)
        stmt = pg_insert(Player).values(
            id=player_id, first_name=first_name, last_name=last_name,
            position=position, height=height, weight=weight,
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={"first_name": first_name, "last_name": last_name,
                   "position": position, "height": height, "weight": weight,
                   "updated_at": datetime.now(timezone.utc)},
        )
        session.execute(stmt)
        count += 1
    session.flush()
    return count


def _ensure_players_from_boxscore(session, player_stats):
    """Auto-upsert players found in box score data that may not exist in the players table.

    The playerindex endpoint returns a limited roster snapshot (~52 players).
    Box scores contain ALL players who actually played (~150-180 per season).
    This function creates minimal player records from box score data so the
    FK constraint on player_game_stats doesn't fail.

    Uses ON CONFLICT DO NOTHING to avoid overwriting richer data from playerindex.
    """
    seen = set()
    count = 0
    for pstat in player_stats:
        player_id = pstat.get("PLAYER_ID")
        if not player_id or player_id in seen:
            continue
        seen.add(player_id)

        player_name = pstat.get("PLAYER_NAME", "")
        first_name, last_name = _split_player_name(player_name)
        start_position = pstat.get("START_POSITION", "")

        # DO NOTHING on conflict — if playerindex already loaded this player
        # with richer data (height, weight, position), keep it.
        stmt = pg_insert(Player).values(
            id=player_id,
            first_name=first_name,
            last_name=last_name,
            position=start_position if start_position else None,
        ).on_conflict_do_nothing(index_elements=["id"])
        session.execute(stmt)
        count += 1
    if count > 0:
        session.flush()
    return count


def upsert_games_from_log(session, game_log, season, season_type):
    """Upsert games from game log. 'vs.' = home, '@' = away.
    Fields: GAME_ID, GAME_DATE (string), TEAM_ID, MATCHUP, PTS.
    """
    if not game_log:
        return 0
    games_by_id = {}
    for entry in game_log:
        gid = entry.get("GAME_ID")
        if not gid:
            continue
        gid = str(gid)
        games_by_id.setdefault(gid, []).append(entry)

    count = 0
    for game_id, entries in games_by_id.items():
        if len(entries) < 2:
            logger.warning(f"Game {game_id} has {len(entries)} entries, expected 2")
            continue
        home_team_id = away_team_id = game_date = home_score = away_score = None
        for entry in entries:
            team_id = entry.get("TEAM_ID")
            matchup = entry.get("MATCHUP", "")
            points = entry.get("PTS")
            raw_date = entry.get("GAME_DATE")
            if not team_id:
                continue
            if raw_date and game_date is None:
                game_date = _parse_game_date(raw_date)
            if "vs." in matchup:
                home_team_id = team_id
                home_score = points
            elif "@" in matchup:
                away_team_id = team_id
                away_score = points
        if not (home_team_id and away_team_id and game_date):
            logger.warning(f"Could not parse home/away for game {game_id}")
            continue
        stmt = pg_insert(Game).values(
            id=str(game_id), game_date=game_date, season=season,
            season_type=season_type, home_team_id=home_team_id,
            away_team_id=away_team_id, home_score=home_score,
            away_score=away_score, game_status="Final",
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={"home_score": home_score, "away_score": away_score,
                   "game_status": "Final", "updated_at": datetime.now(timezone.utc)},
        )
        session.execute(stmt)
        count += 1
    session.flush()
    return count


def load_boxscore(session, game_id, boxscore):
    """Load player and team stats from a box score.

    CRITICAL: Auto-upserts players from box score data before inserting stats.
    The playerindex endpoint returns a limited roster (~52 players), but box scores
    contain every player who appeared in a game (~20-24 per game, ~150-180 per season).

    CRITICAL: Turnovers is 'TO' in API, mapped to 'tov' column.
    """
    player_stats = boxscore.get("player_stats", [])
    team_stats = boxscore.get("team_stats", [])
    player_count = 0
    team_count = 0

    # Step 1: Ensure all players from this box score exist in the players table
    _ensure_players_from_boxscore(session, player_stats)

    # Step 2: Insert player game stats
    for pstat in player_stats:
        player_id = pstat.get("PLAYER_ID")
        team_id = pstat.get("TEAM_ID")
        if not (player_id and team_id):
            logger.warning(f"Player stat missing PLAYER_ID or TEAM_ID: {pstat}")
            continue
        values = {
            "player_id": player_id, "game_id": game_id, "team_id": team_id,
            "minutes": pstat.get("MIN"), "points": pstat.get("PTS"),
            "fgm": pstat.get("FGM"), "fga": pstat.get("FGA"), "fg_pct": pstat.get("FG_PCT"),
            "fg3m": pstat.get("FG3M"), "fg3a": pstat.get("FG3A"), "fg3_pct": pstat.get("FG3_PCT"),
            "ftm": pstat.get("FTM"), "fta": pstat.get("FTA"), "ft_pct": pstat.get("FT_PCT"),
            "oreb": pstat.get("OREB"), "dreb": pstat.get("DREB"), "reb": pstat.get("REB"),
            "ast": pstat.get("AST"), "stl": pstat.get("STL"), "blk": pstat.get("BLK"),
            "tov": pstat.get("TO"),  # API "TO" -> model "tov"
            "pf": pstat.get("PF"), "plus_minus": pstat.get("PLUS_MINUS"),
        }
        update_vals = {k: v for k, v in values.items() if k not in ("player_id", "game_id")}
        stmt = pg_insert(PlayerGameStats).values(**values).on_conflict_do_update(
            index_elements=["player_id", "game_id"], set_=update_vals,
        )
        session.execute(stmt)
        player_count += 1

    # Step 3: Insert team game stats
    for tstat in team_stats:
        team_id = tstat.get("TEAM_ID")
        if not team_id:
            logger.warning(f"Team stat missing TEAM_ID: {tstat}")
            continue
        values = {
            "team_id": team_id, "game_id": game_id,
            "minutes": tstat.get("MIN"), "points": tstat.get("PTS"),
            "fgm": tstat.get("FGM"), "fga": tstat.get("FGA"), "fg_pct": tstat.get("FG_PCT"),
            "fg3m": tstat.get("FG3M"), "fg3a": tstat.get("FG3A"), "fg3_pct": tstat.get("FG3_PCT"),
            "ftm": tstat.get("FTM"), "fta": tstat.get("FTA"), "ft_pct": tstat.get("FT_PCT"),
            "oreb": tstat.get("OREB"), "dreb": tstat.get("DREB"), "reb": tstat.get("REB"),
            "ast": tstat.get("AST"), "stl": tstat.get("STL"), "blk": tstat.get("BLK"),
            "tov": tstat.get("TO"),  # API "TO" -> model "tov"
            "pf": tstat.get("PF"), "plus_minus": tstat.get("PLUS_MINUS"),
        }
        update_vals = {k: v for k, v in values.items() if k not in ("team_id", "game_id")}
        stmt = pg_insert(TeamGameStats).values(**values).on_conflict_do_update(
            index_elements=["team_id", "game_id"], set_=update_vals,
        )
        session.execute(stmt)
        team_count += 1

    session.flush()
    return (player_count, team_count)


def load_officials(session, game_id, officials_data):
    """Load officials. API has FIRST_NAME + LAST_NAME (no OFFICIAL_NAME)."""
    if not officials_data:
        return 0
    count = 0
    for od in officials_data:
        official_id = od.get("OFFICIAL_ID")
        if not official_id:
            logger.warning(f"Official data missing OFFICIAL_ID: {od}")
            continue
        first = od.get("FIRST_NAME", "").strip()
        last = od.get("LAST_NAME", "").strip()
        official_name = f"{first} {last}".strip()
        jersey = od.get("JERSEY_NUM")
        if jersey:
            jersey = jersey.strip()
        stmt = pg_insert(GameOfficial).values(
            game_id=game_id, official_id=official_id,
            official_name=official_name, jersey_number=jersey,
        ).on_conflict_do_update(
            index_elements=["game_id", "official_id"],
            set_={"official_name": official_name, "jersey_number": jersey},
        )
        session.execute(stmt)
        count += 1
    session.flush()
    return count
