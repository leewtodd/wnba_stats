"""One-time arena seeding script.

Reads seeds/arenas.json and upserts arena records into the database,
matching by team abbreviation from the teams table.

PREREQUISITE: Teams must be loaded first. Run the scraper for at least
one season before running this script:
    python3 -m scraper.runner --season 2024
"""
import json
import os
import sys
from pathlib import Path

# Add project root to path so we can import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from models import get_engine, get_session_factory, Team, Arena


def load_arena_seed():
    """Load arena seed data from JSON."""
    seed_file = Path(__file__).parent.parent / "seeds" / "arenas.json"
    with open(seed_file) as f:
        return json.load(f)


def seed_arenas():
    """Load arena seed data and upsert into database."""
    try:
        engine = get_engine()
        SessionFactory = get_session_factory(engine)
        session = SessionFactory()

        # Check if teams are loaded
        team_count = session.execute(select(func.count(Team.id))).scalar()
        if team_count == 0:
            print("✗ No teams in database. Teams must be loaded before seeding arenas.")
            print("  Run the scraper for at least one season first:")
            print("    python3 -m scraper.runner --season 2024")
            print("  Then run this script again.")
            return 1

        print(f"Found {team_count} teams in database")
        arenas = load_arena_seed()
        loaded = 0
        skipped = 0

        for arena_data in arenas:
            abbr = arena_data["team_abbreviation"]
            team = session.execute(
                select(Team).where(Team.abbreviation == abbr)
            ).scalar_one_or_none()

            if not team:
                print(f"⚠ Team '{abbr}' not found in database, skipping {arena_data['arena_name']}")
                skipped += 1
                continue

            existing = session.execute(
                select(Arena).where(
                    (Arena.team_id == team.id) &
                    (Arena.season_start == arena_data["season_start"])
                )
            ).scalar_one_or_none()

            if existing:
                existing.arena_name = arena_data["arena_name"]
                existing.city = arena_data["city"]
                existing.state = arena_data["state"]
                existing.latitude = arena_data["latitude"]
                existing.longitude = arena_data["longitude"]
                existing.season_end = arena_data.get("season_end")
                print(f"✓ Updated arena {arena_data['arena_name']} for {abbr}")
            else:
                new_arena = Arena(
                    team_id=team.id,
                    arena_name=arena_data["arena_name"],
                    city=arena_data["city"],
                    state=arena_data["state"],
                    latitude=arena_data["latitude"],
                    longitude=arena_data["longitude"],
                    season_start=arena_data["season_start"],
                    season_end=arena_data.get("season_end"),
                )
                session.add(new_arena)
                print(f"✓ Added arena {arena_data['arena_name']} for {abbr}")
            loaded += 1

        session.commit()
        print(f"\n✓ Processed {loaded} arenas ({skipped} skipped)")
        return 0
    except Exception as e:
        print(f"✗ Error seeding arenas: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(seed_arenas())
