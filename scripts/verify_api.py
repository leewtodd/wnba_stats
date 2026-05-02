"""API Verification Script — Capture actual field names from stats.wnba.com.

Run this ONCE before fixing loaders.py field names.
Hits each endpoint, prints the headers array, and saves raw responses
to tests/fixtures/ for offline testing.

Usage:
    python scripts/verify_api.py

This script exists because CC invented plausible-sounding field names
(e.g., "TeamID" instead of "TEAM_ID") without verifying against the
actual API. This script captures what the API actually returns.
"""
import json
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.client import fetch_endpoint

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures")


def save_fixture(name, data):
    """Save raw API response to fixtures directory."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    filepath = os.path.join(FIXTURES_DIR, f"{name}.json")
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  → Saved to {filepath}")


def print_headers(label, result_sets):
    """Print headers from each resultSet."""
    if not result_sets:
        print("  ⚠ No resultSets returned")
        return

    for i, rs in enumerate(result_sets):
        name = rs.get("name", f"resultSet[{i}]")
        headers = rs.get("headers", [])
        row_count = len(rs.get("rowSet", []))
        print(f"  [{i}] {name}: {row_count} rows")
        print(f"      Headers: {headers}")
        # Print first row as sample
        rows = rs.get("rowSet", [])
        if rows:
            print(f"      Sample row[0]: {rows[0]}")


def verify_season_format():
    """Test different season format strings to see which one works."""
    print("\n" + "=" * 70)
    print("TESTING SEASON FORMAT")
    print("=" * 70)

    formats_to_try = ["2024", "2024-25", "2024-2025"]

    for fmt in formats_to_try:
        print(f"\n  Trying Season={fmt}...")
        try:
            response = fetch_endpoint("leaguegamelog", {
                "LeagueID": "10",
                "Season": fmt,
                "SeasonType": "Regular Season",
                "PlayerOrTeam": "T",
            })
            result_sets = response.get("resultSets", [])
            if result_sets:
                rows = result_sets[0].get("rowSet", [])
                print(f"  ✓ Season={fmt} returned {len(rows)} rows")
                if rows:
                    return fmt  # First format that works
            else:
                print(f"  ✗ Season={fmt} returned no resultSets")
        except Exception as e:
            print(f"  ✗ Season={fmt} failed: {e}")

    print("\n  ⚠ No season format returned data. API may be down or require different params.")
    return None


def verify_endpoint(name, endpoint, params, fixture_name):
    """Hit an endpoint, print headers, save fixture."""
    print(f"\n{'=' * 70}")
    print(f"ENDPOINT: {endpoint}")
    print(f"Params: {params}")
    print(f"{'=' * 70}")

    try:
        response = fetch_endpoint(endpoint, params)
        result_sets = response.get("resultSets", [])
        print_headers(name, result_sets)
        save_fixture(fixture_name, response)
        return response
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return None


def main():
    print("=" * 70)
    print("WNBA Stats API Verification")
    print("Capturing actual field names from each endpoint")
    print("=" * 70)

    # Step 1: Figure out the right season format
    working_format = verify_season_format()
    if not working_format:
        print("\n⚠ Could not determine season format. Using '2024' as fallback.")
        working_format = "2024"

    print(f"\n✓ Using season format: {working_format}")

    # Step 2: Hit each endpoint and capture headers

    # leaguedashteamstats — used by fetch_teams()
    verify_endpoint(
        "Teams",
        "leaguedashteamstats",
        {
            "LeagueID": "10",
            "Season": working_format,
            "PerMode": "PerGame",
            "MeasureType": "Base",
        },
        "leaguedashteamstats"
    )

    time.sleep(2)  # Extra delay between endpoints

    # playerindex — used by fetch_players()
    verify_endpoint(
        "Players",
        "playerindex",
        {
            "LeagueID": "10",
            "Season": working_format,
        },
        "playerindex"
    )

    time.sleep(2)

    # leaguegamelog — used by fetch_game_log()
    game_log_response = verify_endpoint(
        "Game Log",
        "leaguegamelog",
        {
            "LeagueID": "10",
            "Season": working_format,
            "SeasonType": "Regular Season",
            "PlayerOrTeam": "T",
        },
        "leaguegamelog"
    )

    time.sleep(2)

    # Get a game_id from the game log for boxscore/summary calls
    game_id = None
    if game_log_response:
        result_sets = game_log_response.get("resultSets", [])
        if result_sets:
            rows = result_sets[0].get("rowSet", [])
            headers = result_sets[0].get("headers", [])
            if rows and headers:
                # Find the GAME_ID column index
                for idx, h in enumerate(headers):
                    if "GAME" in h.upper() and "ID" in h.upper():
                        game_id = str(rows[0][idx])
                        print(f"\n  Using game_id={game_id} for boxscore/summary tests")
                        break

    if game_id:
        # boxscoretraditionalv2 — used by fetch_boxscore()
        verify_endpoint(
            "Box Score",
            "boxscoretraditionalv2",
            {"GameID": game_id},
            "boxscoretraditionalv2"
        )

        time.sleep(2)

        # boxscoresummaryv2 — used by fetch_game_summary()
        verify_endpoint(
            "Game Summary",
            "boxscoresummaryv2",
            {"GameID": game_id},
            "boxscoresummaryv2"
        )
    else:
        print("\n⚠ No game_id found — skipping boxscore and game summary endpoints.")

    # Step 3: Print summary of what to fix
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Check the headers printed above against the field names in scraper/loaders.py
2. Check tests/fixtures/ for saved raw responses
3. Fix loaders.py field names to match actual API headers
4. Fix endpoints.py Season format to use: """ + repr(working_format) + """
5. Update test fixtures to use real API response shapes
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
