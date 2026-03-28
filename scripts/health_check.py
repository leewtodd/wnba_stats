#!/usr/bin/env python3
"""WNBA Stats system health check."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from datetime import datetime, date
from sqlalchemy import text, inspect, table as sa_table, select, func
from models import get_engine

# Hardcoded table list — validated against inspector at runtime
EXPECTED_TABLES = [
    "teams", "players", "games", "player_game_stats",
    "team_game_stats", "game_officials", "arenas",
    "scrape_runs", "query_log",
]


def check_database(engine):
    """Check database connectivity. Returns (ok, message)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        url = engine.url.render_as_string(hide_password=True)
        return True, f"Connected ({url})"
    except Exception as e:
        return False, str(e)


def check_last_game(engine):
    """Check last game date. Returns (ok, message)."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT MAX(game_date) FROM games"))
            max_date = result.scalar()

        if max_date is None:
            return False, "No games in database"

        days_ago = (date.today() - max_date).days
        current_month = date.today().month
        active_season = 5 <= current_month <= 10

        if active_season and days_ago > 3:
            return False, f"{max_date} ({days_ago} days ago) \u26a0\ufe0f"
        else:
            return True, f"{max_date} ({days_ago} days ago) \u2713"
    except Exception as e:
        return False, str(e)


def check_table_counts(engine):
    """Get row counts for all tables. Returns dict of table->count."""
    # Validate expected tables against actual database schema
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())

    counts = {}
    for tbl_name in EXPECTED_TABLES:
        if tbl_name not in actual_tables:
            counts[tbl_name] = "MISSING"
            continue
        try:
            with engine.connect() as conn:
                t = sa_table(tbl_name)
                result = conn.execute(select(func.count()).select_from(t))
                counts[tbl_name] = result.scalar()
        except Exception as e:
            counts[tbl_name] = f"ERROR: {e}"
    return counts


def check_last_scrape(engine):
    """Check last auto scrape run. Returns message string."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT started_at, mode, games_loaded, success, error_message "
                "FROM scrape_runs WHERE mode = 'auto' "
                "ORDER BY started_at DESC LIMIT 1"
            ))
            row = result.fetchone()

        if row is None:
            return "No auto runs recorded"

        started_at, mode, games_loaded, success, error_message = row
        if success:
            return f"{started_at} SUCCESS ({games_loaded} games loaded)"
        else:
            return f"{started_at} FAILURE: {error_message}"
    except Exception as e:
        return f"Error: {e}"


def check_api_endpoint():
    """Check stats.wnba.com connectivity. Returns (ok, message)."""
    try:
        import requests
        url = "https://stats.wnba.com/stats/leaguegamelog"
        params = {
            "LeagueID": "10",
            "Season": "2024-25",
            "SeasonType": "Regular Season",
            "PlayerOrTeam": "T",
        }
        headers = {
            "Host": "stats.wnba.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://stats.wnba.com/",
            "Origin": "https://stats.wnba.com",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            return True, "stats.wnba.com responding"
        else:
            return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def check_claude_api():
    """Check Claude API key. Returns (ok, message)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY not set"
    try:
        import anthropic
        client = anthropic.Anthropic()
        client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say OK"}],
        )
        return True, "Key valid"
    except Exception as e:
        return False, str(e)


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"WNBA Stats Health Check \u2014 {now}")
    print("\u2500" * 47)

    all_ok = True

    # Database
    engine = get_engine()
    db_ok, db_msg = check_database(engine)
    status = "\u2713" if db_ok else "\u2717"
    print(f"Database:        {status} {db_msg}")
    if not db_ok:
        all_ok = False

    # Last game
    game_ok, game_msg = check_last_game(engine)
    print(f"Last game:       {game_msg}")
    if not game_ok:
        all_ok = False

    # Table counts
    counts = check_table_counts(engine)
    print("Tables:")
    for table, count in counts.items():
        if isinstance(count, int):
            print(f"  {table + ':':23s}{count:>6}")
        else:
            print(f"  {table + ':':23s} {count}")
            all_ok = False

    # Last scrape
    scrape_msg = check_last_scrape(engine)
    print(f"Last scrape:     {scrape_msg}")

    # API endpoint
    api_ok, api_msg = check_api_endpoint()
    status = "\u2713" if api_ok else "\u2717"
    print(f"API endpoint:    {status} {api_msg}")
    if not api_ok:
        all_ok = False

    # Claude API
    claude_ok, claude_msg = check_claude_api()
    if claude_ok is None:
        print(f"Claude API:      \u26a0\ufe0f {claude_msg}")
    elif claude_ok:
        print(f"Claude API:      \u2713 {claude_msg}")
    else:
        print(f"Claude API:      \u2717 {claude_msg}")
        all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
