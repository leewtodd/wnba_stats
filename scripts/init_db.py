"""Initialize database schema with views and functions.

Phase 1: Database Schema & Historical Data Ingestion

Creates:
- f_haversine(lat1, lon1, lat2, lon2) — Postgres function for great-circle distance in miles
- v_team_rest_days — View computing days since last game for each team/game
- v_team_travel_distance — View computing distance traveled between consecutive games
"""
import os
import sys

# Add project root to path so we can import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from models import get_engine, init_db


def create_functions(engine):
    """Create database functions."""
    with engine.connect() as conn:
        haversine_sql = """
        CREATE OR REPLACE FUNCTION f_haversine(lat1 float, lon1 float, lat2 float, lon2 float)
        RETURNS float AS $$
        DECLARE
            R float := 3959;  -- Earth's radius in miles
            dlat float;
            dlon float;
            a float;
            c float;
        BEGIN
            dlat := radians(lat2 - lat1);
            dlon := radians(lon2 - lon1);
            a := sin(dlat/2) * sin(dlat/2) + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2) * sin(dlon/2);
            c := 2 * asin(sqrt(a));
            RETURN R * c;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
        """
        conn.execute(text(haversine_sql))
        conn.commit()
        print("✓ Created f_haversine function")


def create_views(engine):
    """Create database views.

    CRITICAL: Both views use a CTE to UNION ALL home and away appearances
    BEFORE applying window functions. The LAG() must operate across ALL games
    for a team (home + away combined), not separately within each branch.
    """
    with engine.connect() as conn:
        rest_days_sql = """
        CREATE OR REPLACE VIEW v_team_rest_days AS
        WITH all_team_games AS (
            SELECT g.id AS game_id, g.home_team_id AS team_id, g.season, g.game_date
            FROM games g
            WHERE g.game_status = 'Final'

            UNION ALL

            SELECT g.id AS game_id, g.away_team_id AS team_id, g.season, g.game_date
            FROM games g
            WHERE g.game_status = 'Final'
        )
        SELECT
            game_id,
            team_id,
            season,
            game_date,
            COALESCE(
                game_date - LAG(game_date) OVER (
                    PARTITION BY team_id, season
                    ORDER BY game_date, game_id
                ),
                0
            ) AS rest_days
        FROM all_team_games;
        """
        conn.execute(text(rest_days_sql))
        print("✓ Created v_team_rest_days view")

        travel_distance_sql = """
        CREATE OR REPLACE VIEW v_team_travel_distance AS
        WITH team_game_locations AS (
            SELECT
                g.id AS game_id,
                g.home_team_id AS team_id,
                g.season,
                g.game_date,
                a.latitude,
                a.longitude
            FROM games g
            JOIN arenas a ON a.team_id = g.home_team_id
                AND g.season >= a.season_start
                AND (a.season_end IS NULL OR g.season <= a.season_end)
            WHERE g.game_status = 'Final'

            UNION ALL

            SELECT
                g.id AS game_id,
                g.away_team_id AS team_id,
                g.season,
                g.game_date,
                a.latitude,
                a.longitude
            FROM games g
            JOIN arenas a ON a.team_id = g.home_team_id
                AND g.season >= a.season_start
                AND (a.season_end IS NULL OR g.season <= a.season_end)
            WHERE g.game_status = 'Final'
        ),
        with_prev AS (
            SELECT
                game_id,
                team_id,
                season,
                game_date,
                latitude,
                longitude,
                LAG(latitude) OVER (
                    PARTITION BY team_id, season
                    ORDER BY game_date, game_id
                ) AS prev_lat,
                LAG(longitude) OVER (
                    PARTITION BY team_id, season
                    ORDER BY game_date, game_id
                ) AS prev_lon
            FROM team_game_locations
        )
        SELECT
            game_id,
            team_id,
            season,
            game_date,
            CASE
                WHEN prev_lat IS NOT NULL AND prev_lon IS NOT NULL
                THEN f_haversine(prev_lat, prev_lon, latitude, longitude)
                ELSE NULL
            END AS travel_miles
        FROM with_prev;
        """
        conn.execute(text(travel_distance_sql))
        print("✓ Created v_team_travel_distance view")

        conn.commit()


def main():
    """Initialize database schema."""
    try:
        engine = get_engine()

        print("Creating tables from models...")
        init_db(engine)
        print("✓ Created all tables")

        print("\nCreating database functions...")
        create_functions(engine)

        print("\nCreating database views...")
        create_views(engine)

        print("\n✓ Database initialization complete!")
        return 0
    except Exception as e:
        print(f"✗ Error initializing database: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
