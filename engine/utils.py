"""Name resolution, stat column map, and shared utilities.

Provides functions for resolving team and player names to IDs, validating stat names,
and managing database sessions.
"""

import numpy as np
import psycopg2.extensions
psycopg2.extensions.register_adapter(np.int64, lambda val: psycopg2.extensions.AsIs(int(val)))
psycopg2.extensions.register_adapter(np.float64, lambda val: psycopg2.extensions.AsIs(float(val)))
import logging  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from models.base import get_engine, get_session_factory  # noqa: E402
from models.core import Team, Player  # noqa: E402

logger = logging.getLogger(__name__)


def get_session() -> Session:
    """Create and return a new SQLAlchemy session.

    Reads DATABASE_URL from environment (default: postgresql://localhost:5432/wnba_stats).

    Returns:
        A SQLAlchemy Session instance
    """
    engine = get_engine()
    session_factory = get_session_factory(engine)
    return session_factory()


# Maps human-readable stat names and aliases to actual PlayerGameStats/TeamGameStats column names.
# EVERY entry here must correspond to an actual column in models/core.py.
STAT_COLUMN_MAP = {
    # Direct column names (already valid)
    "points": "points",
    "minutes": "minutes",
    "fgm": "fgm",
    "fga": "fga",
    "fg_pct": "fg_pct",
    "fg3m": "fg3m",
    "fg3a": "fg3a",
    "fg3_pct": "fg3_pct",
    "ftm": "ftm",
    "fta": "fta",
    "ft_pct": "ft_pct",
    "oreb": "oreb",
    "dreb": "dreb",
    "reb": "reb",
    "ast": "ast",
    "stl": "stl",
    "blk": "blk",
    "tov": "tov",
    "pf": "pf",
    "plus_minus": "plus_minus",

    # Human-readable aliases → actual column names
    "rebounds": "reb",
    "assists": "ast",
    "steals": "stl",
    "blocks": "blk",
    "turnovers": "tov",
    "fouls": "pf",
    "personal_fouls": "pf",
    "field_goal_pct": "fg_pct",
    "field_goal_percentage": "fg_pct",
    "three_point_pct": "fg3_pct",
    "three_pointers_made": "fg3m",
    "three_pointers_attempted": "fg3a",
    "free_throw_pct": "ft_pct",
    "free_throws_made": "ftm",
    "free_throws_attempted": "fta",
    "offensive_rebounds": "oreb",
    "defensive_rebounds": "dreb",
    "field_goals_made": "fgm",
    "field_goals_attempted": "fga",
}


def validate_stat(stat_name: str) -> str:
    """Resolve a human-readable stat name to the actual database column name.

    Args:
        stat_name: Human-readable name like "rebounds" or actual column like "reb"

    Returns:
        The actual column name from PlayerGameStats/TeamGameStats

    Raises:
        ValueError: if stat_name is not recognized. Error message includes all valid options.
    """
    key = stat_name.lower().strip()
    if key in STAT_COLUMN_MAP:
        return STAT_COLUMN_MAP[key]
    valid_options = sorted(set(STAT_COLUMN_MAP.values()))
    raise ValueError(
        f"Unknown stat: '{stat_name}'. Valid options: {valid_options}"
    )


def resolve_team(name_or_abbr: str, session: Session = None) -> int:
    """Resolve a team name or abbreviation to a team ID.

    Resolution priority:
    1. Exact match on Team.abbreviation (case-insensitive)
    2. Exact match on Team.full_name (case-insensitive)
    3. Substring match on Team.full_name (only if exactly one match)
    4. Substring match on Team.city (only if exactly one match)

    Args:
        name_or_abbr: Team name, abbreviation, or city name
        session: Optional SQLAlchemy Session. If None, creates one internally.

    Returns:
        Integer team ID

    Raises:
        ValueError: if team not found or ambiguous
    """
    close_session = False
    if session is None:
        session = get_session()
        close_session = True

    try:
        search_term = name_or_abbr.lower().strip()

        # 1. Exact match on abbreviation
        team = session.query(Team).filter(Team.abbreviation.ilike(search_term)).first()
        if team:
            return int(team.id)

        # 2. Exact match on full_name
        team = session.query(Team).filter(Team.full_name.ilike(search_term)).first()
        if team:
            return int(team.id)

        # 3. Substring match on full_name
        matching_teams = session.query(Team).filter(
            Team.full_name.ilike(f"%{search_term}%")
        ).all()
        if len(matching_teams) == 1:
            return int(matching_teams[0].id)
        elif len(matching_teams) > 1:
            team_names = ", ".join([t.full_name for t in matching_teams])
            raise ValueError(
                f"Ambiguous team name: '{name_or_abbr}'. Matches: {team_names}"
            )

        # 4. Substring match on city
        matching_teams = session.query(Team).filter(
            Team.city.ilike(f"%{search_term}%")
        ).all()
        if len(matching_teams) == 1:
            return int(matching_teams[0].id)
        elif len(matching_teams) > 1:
            team_names = ", ".join([t.full_name for t in matching_teams])
            raise ValueError(
                f"Ambiguous team name: '{name_or_abbr}'. Matches: {team_names}"
            )

        # No match
        all_teams = session.query(Team).all()
        team_names = ", ".join([t.full_name for t in all_teams])
        raise ValueError(
            f"Team not found: '{name_or_abbr}'. Available teams: {team_names}"
        )
    finally:
        if close_session:
            session.close()


def resolve_player(name: str, session: Session = None) -> int:
    """Resolve a player name to a player ID.

    Resolution priority:
    0. Concatenated match on (first_name || ' ' || last_name) — handles compound names
    1. Exact match on first_name + ' ' + last_name via naive split (case-insensitive)
    2. Exact match on last_name (case-insensitive, only if exactly one match)
    3. Partial match (first initial + last name) (only if exactly one match)
    4. Substring match on last_name (only if exactly one match)

    Args:
        name: Player full name, last name, or partial name
        session: Optional SQLAlchemy Session. If None, creates one internally.

    Returns:
        Integer player ID

    Raises:
        ValueError: if player not found or ambiguous
    """
    close_session = False
    if session is None:
        session = get_session()
        close_session = True

    try:
        search_term = name.lower().strip()

        # 0. Concatenated match — handles compound names like "Asia (AD) Durr",
        #    "Katie Lou Samuelson", "Elena Delle Donne", etc.
        player = session.query(Player).filter(
            (Player.first_name + ' ' + Player.last_name).ilike(search_term)
        ).first()
        if player:
            return int(player.id)

        # 1. Exact match on full name (first_name + last_name) via naive split
        parts = search_term.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = " ".join(parts[1:])
            player = session.query(Player).filter(
                Player.first_name.ilike(first_name),
                Player.last_name.ilike(last_name)
            ).first()
            if player:
                return int(player.id)

        # 2. Exact match on last_name only
        matching_players = session.query(Player).filter(
            Player.last_name.ilike(search_term)
        ).all()
        if len(matching_players) == 1:
            return int(matching_players[0].id)
        elif len(matching_players) > 1:
            player_list = ", ".join([
                f"{p.first_name} {p.last_name}" for p in matching_players
            ])
            raise ValueError(
                f"Ambiguous player name: '{name}'. Matches: {player_list}"
            )

        # 3. Partial match (first initial + last name)
        if len(parts) >= 1 and len(parts[0]) == 1:
            # Pattern: "C. Clark"
            initial = parts[0][0]
            last_part = " ".join(parts[1:]) if len(parts) > 1 else ""
            if last_part:
                matching_players = session.query(Player).filter(
                    Player.first_name.ilike(f"{initial}%"),
                    Player.last_name.ilike(last_part)
                ).all()
                if len(matching_players) == 1:
                    return int(matching_players[0].id)
                elif len(matching_players) > 1:
                    player_list = ", ".join([
                        f"{p.first_name} {p.last_name}" for p in matching_players
                    ])
                    raise ValueError(
                        f"Ambiguous player name: '{name}'. Matches: {player_list}"
                    )

        # 4. Substring match on last_name
        matching_players = session.query(Player).filter(
            Player.last_name.ilike(f"%{search_term}%")
        ).all()
        if len(matching_players) == 1:
            return int(matching_players[0].id)
        elif len(matching_players) > 1:
            player_list = ", ".join([
                f"{p.first_name} {p.last_name}" for p in matching_players[:20]
            ])
            raise ValueError(
                f"Ambiguous player name: '{name}'. Matches: {player_list}"
            )

        # No match
        all_players = session.query(Player).limit(20).all()
        available = ", ".join([f"{p.first_name} {p.last_name}" for p in all_players])
        raise ValueError(
            f"Player not found: '{name}'. Available players: {available} (and more...)"
        )
    finally:
        if close_session:
            session.close()
