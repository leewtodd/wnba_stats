"""Diagnostic script: Verify stats.wnba.com API field names and Season format.

Run this BEFORE fixing loaders.py field names. It hits each endpoint,
captures the actual header names, and prints a mapping report.

Usage:
    python3 scripts/verify_api_fields.py

This script uses the existing scraper client (with correct headers and rate limiting).
It pulls minimal data (one season, one game) to minimize API load.
"""
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.client import fetch_endpoint


def test_season_format():
    """Test which Season format the API accepts."""
    print("=" * 70)
    print("TEST 1: Season parameter format")
    print("=" * 70)

    formats_to_try = ["2024-25", "2024", "2025"]

    for fmt in formats_to_try:
        try:
            print(f"\n  Trying Season={fmt} on leaguedashteamstats...")
            response = fetch_endpoint("leaguedashteamstats", {
                "LeagueID": "10",
                "Season": fmt,
                "PerMode": "PerGame",
                "MeasureType": "Base",
            })
            result_set = response.get("resultSets", [{}])[0]
            row_count = len(result_set.get("rowSet", []))
            print(f"  ✓ Season={fmt} returned {row_count} rows")
            if row_count > 0:
                print(f"  >>> USE THIS FORMAT: Season={fmt}")
                return fmt
        except Exception as e:
            print(f"  ✗ Season={fmt} failed: {e}")

    print("\n  ⚠ No format worked. API may be down or parameters may have changed.")
    return None


def capture_endpoint_headers(endpoint, params, label):
    """Fetch an endpoint and print its headers and first row."""
    print(f"\n{'=' * 70}")
    print(f"ENDPOINT: {endpoint} ({label})")
    print(f"{'=' * 70}")
    print(f"  Params: {params}")

    try:
        response = fetch_endpoint(endpoint, params)
    except Exception as e:
        print(f"  ✗ Request failed: {e}")
        return None

    result_sets = response.get("resultSets", [])
    print(f"  ResultSets found: {len(result_sets)}")

    all_headers = {}

    for i, rs in enumerate(result_sets):
        name = rs.get("name", f"resultSet[{i}]")
        headers = rs.get("headers", [])
        rows = rs.get("rowSet", [])

        print(f"\n  --- ResultSet {i}: '{name}' ---")
        print(f"  Headers ({len(headers)}):")
        for j, h in enumerate(headers):
            print(f"    [{j:2d}] {h}")

        if rows:
            print(f"  First row ({len(rows)} total rows):")
            first_row = rows[0]
            for j, (h, v) in enumerate(zip(headers, first_row)):
                print(f"    {h}: {repr(v)}")
        else:
            print("  No rows returned")

        all_headers[name] = headers

    return all_headers


def main():
    print("=" * 70)
    print("WNBA Stats API Field Name Diagnostic")
    print("=" * 70)
    print("\nThis script hits stats.wnba.com to capture actual field names.")
    print("Results will tell us exactly what loaders.py should reference.\n")

    # Test season format first
    season_fmt = test_season_format()
    if not season_fmt:
        print("\n⚠ Could not determine season format. Trying '2024-25' for remaining tests.")
        season_fmt = "2024-25"

    time.sleep(1)

    # 1. leaguedashteamstats — used by fetch_teams()
    _team_headers = capture_endpoint_headers(
        "leaguedashteamstats",
        {
            "LeagueID": "10",
            "Season": season_fmt,
            "PerMode": "PerGame",
            "MeasureType": "Base",
        },
        "Teams list + season stats"
    )

    time.sleep(1.5)

    # 2. playerindex — used by fetch_players()
    _player_headers = capture_endpoint_headers(
        "playerindex",
        {
            "LeagueID": "10",
            "Season": season_fmt,
        },
        "Player roster info"
    )

    time.sleep(1.5)

    # 3. leaguegamelog — used by fetch_game_log()
    _gamelog_headers = capture_endpoint_headers(
        "leaguegamelog",
        {
            "LeagueID": "10",
            "Season": season_fmt,
            "SeasonType": "Regular Season",
            "PlayerOrTeam": "T",
        },
        "Game log (team level)"
    )

    # Extract a game_id from the game log for box score test
    game_id = None
    try:
        response = fetch_endpoint("leaguegamelog", {
            "LeagueID": "10",
            "Season": season_fmt,
            "SeasonType": "Regular Season",
            "PlayerOrTeam": "T",
        })
        rows = response.get("resultSets", [{}])[0].get("rowSet", [])
        headers = response.get("resultSets", [{}])[0].get("headers", [])
        if rows:
            # Find the GAME_ID column index
            for idx, h in enumerate(headers):
                if "GAME" in h.upper() and "ID" in h.upper():
                    game_id = str(rows[0][idx])
                    print(f"\n  Using game_id={game_id} for box score test")
                    break
    except Exception:
        pass

    time.sleep(1.5)

    # 4. boxscoretraditionalv2 — used by fetch_boxscore()
    if game_id:
        _boxscore_headers = capture_endpoint_headers(
            "boxscoretraditionalv2",
            {"GameID": game_id},
            f"Box score for game {game_id}"
        )
    else:
        print("\n⚠ No game_id available, skipping boxscoretraditionalv2")

    time.sleep(1.5)

    # 5. boxscoresummaryv2 — used by fetch_game_summary()
    if game_id:
        _summary_headers = capture_endpoint_headers(
            "boxscoresummaryv2",
            {"GameID": game_id},
            f"Game summary for game {game_id}"
        )
    else:
        print("\n⚠ No game_id available, skipping boxscoresummaryv2")

    # Print mapping report
    print("\n" + "=" * 70)
    print("FIELD NAME MAPPING REPORT")
    print("=" * 70)
    print("""
Use this output to fix the field names in scraper/loaders.py.

For each loader function, verify that every .get("FIELD_NAME") call
matches the actual header name printed above.

Key fields to check:
  upsert_teams():      TeamID → ?, TeamName → ?, Abbreviation → ?, City → ?, Conference → ?
  upsert_players():    PersonID → ?, FirstName → ?, LastName → ?, Position → ?, Height → ?, Weight → ?
  upsert_games_from_log(): Game_ID → ?, Game_Date → ?, Team_ID → ?, Matchup → ?, PTS → ?
  load_boxscore():     PLAYER_ID → ?, TEAM_ID → ?, MIN → ?, PTS → ?, etc.
  load_officials():    OFFICIAL_ID → ?, OFFICIAL_NAME → ?, JERSEY_NUM → ?

Copy the exact header names from the output above into the loader functions.
""")

    print("✓ Diagnostic complete. Use the headers above to fix loaders.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
