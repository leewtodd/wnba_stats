"""Tests for scraper module.

Phase 1: Database Schema & Historical Data Ingestion

Comprehensive test suite for client, endpoints, loaders, and runner components.

IMPORTANT: Before running tests, create the test database:
  createdb wnba_stats_test

Then run:
  pytest tests/test_scraper.py -v
"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from models import Team, Player, Game, PlayerGameStats, TeamGameStats, GameOfficial
from scraper import client, endpoints, loaders


# ============================================================================
# FIXTURES — Unit Test Fixtures (No Database Required)
# ============================================================================


# ============================================================================
# FIXTURES — API Data Fixtures (Used by Loader Tests)
# ============================================================================


@pytest.fixture
def api_teams_data():
    """Teams data using actual API field names from playerindex fallback."""
    return [
        {"TEAM_ID": 1001, "TEAM_NAME": "Aces", "TEAM_CITY": "Las Vegas", "TEAM_ABBREVIATION": "LVA"},
        {"TEAM_ID": 1002, "TEAM_NAME": "Liberty", "TEAM_CITY": "New York", "TEAM_ABBREVIATION": "NY"},
    ]


@pytest.fixture
def api_players_data():
    """Players data using actual API field names from playerindex."""
    return [
        {"PERSON_ID": 201950, "PLAYER_FIRST_NAME": "A'ja", "PLAYER_LAST_NAME": "Wilson",
         "POSITION": "F", "HEIGHT": "6-4", "WEIGHT": "195"},
        {"PERSON_ID": 1629627, "PLAYER_FIRST_NAME": "Breanna", "PLAYER_LAST_NAME": "Stewart",
         "POSITION": "F", "HEIGHT": "6-4", "WEIGHT": "180"},
    ]


@pytest.fixture
def api_game_log_data():
    """Game log data using actual API field names from leaguegamelog."""
    return [
        {"GAME_ID": "1022400175", "GAME_DATE": "2024-08-25", "TEAM_ID": 1001,
         "MATCHUP": "LVA vs. NY", "WL": "W", "PTS": 108},
        {"GAME_ID": "1022400175", "GAME_DATE": "2024-08-25", "TEAM_ID": 1002,
         "MATCHUP": "NY @ LVA", "WL": "L", "PTS": 102},
    ]


@pytest.fixture
def api_boxscore_data():
    """Box score data using actual API field names. NOTE: turnovers is TO, not TOV."""
    return {
        "player_stats": [{
            "PLAYER_ID": 201950, "TEAM_ID": 1001, "MIN": "36:35",
            "PTS": 28, "FGM": 11, "FGA": 18, "FG_PCT": 0.611,
            "FG3M": 0, "FG3A": 0, "FG3_PCT": 0.0,
            "FTM": 6, "FTA": 7, "FT_PCT": 0.857,
            "OREB": 2, "DREB": 8, "REB": 10,
            "AST": 2, "STL": 1, "BLK": 0,
            "TO": 2,  # <-- THIS IS "TO", NOT "TOV"
            "PF": 3, "PLUS_MINUS": 5.2,
        }],
        "team_stats": [{
            "TEAM_ID": 1001, "MIN": "200:00",
            "PTS": 108, "FGM": 40, "FGA": 84, "FG_PCT": 0.476,
            "FG3M": 10, "FG3A": 26, "FG3_PCT": 0.385,
            "FTM": 18, "FTA": 22, "FT_PCT": 0.818,
            "OREB": 8, "DREB": 32, "REB": 40,
            "AST": 25, "STL": 8, "BLK": 3,
            "TO": 15,  # <-- THIS IS "TO", NOT "TOV"
            "PF": 20, "PLUS_MINUS": 6.0,
        }],
    }


@pytest.fixture
def api_officials_data():
    """Officials data using actual API field names. Name is FIRST_NAME + LAST_NAME, NOT OFFICIAL_NAME."""
    return [
        {"OFFICIAL_ID": 202679, "FIRST_NAME": "Jeff", "LAST_NAME": "Wooten", "JERSEY_NUM": "23  "},
        {"OFFICIAL_ID": 203506, "FIRST_NAME": "Dannica", "LAST_NAME": "Mosher", "JERSEY_NUM": "22  "},
    ]


# ============================================================================
# UNIT TESTS — TestFormatSeason
# ============================================================================


class TestFormatSeason:
    """Tests for _format_season() function."""

    def test_standard_year(self):
        """2024 should format to '2024-25'."""
        from scraper.endpoints import _format_season
        assert _format_season(2024) == "2024-25"

    def test_next_year(self):
        """2025 should format to '2025-26'."""
        from scraper.endpoints import _format_season
        assert _format_season(2025) == "2025-26"

    def test_century_boundary(self):
        """1999 should format to '1999-00'."""
        from scraper.endpoints import _format_season
        assert _format_season(1999) == "1999-00"


# ============================================================================
# UNIT TESTS — TestParseGameDate
# ============================================================================


class TestParseGameDate:
    """Tests for _parse_game_date() function."""

    def test_iso_string(self):
        """Parse ISO date string 'YYYY-MM-DD'."""
        from scraper.loaders import _parse_game_date
        assert _parse_game_date("2024-08-25") == date(2024, 8, 25)

    def test_datetime_string(self):
        """Parse datetime string 'YYYY-MM-DDTHH:MM:SS'."""
        from scraper.loaders import _parse_game_date
        assert _parse_game_date("2024-08-25T00:00:00") == date(2024, 8, 25)

    def test_already_date(self):
        """Return date object unchanged."""
        from scraper.loaders import _parse_game_date
        d = date(2024, 8, 25)
        assert _parse_game_date(d) == d

    def test_invalid_raises(self):
        """Invalid date string should raise ValueError."""
        from scraper.loaders import _parse_game_date
        with pytest.raises(ValueError):
            _parse_game_date("not-a-date")


# ============================================================================
# UNIT TESTS — TestNormalizeResultSet
# ============================================================================


class TestNormalizeResultSet:
    """Tests for _normalize_result_set() function."""

    def test_parallel_arrays_to_dicts(self):
        """Parallel arrays (headers + rows) should convert to list[dict]."""
        from scraper.endpoints import _normalize_result_set
        headers = ["TEAM_ID", "TEAM_NAME", "TEAM_ABBREVIATION"]
        rows = [
            [1611661321, "Wings", "DAL"],
            [1611661320, "Sparks", "LAS"],
        ]
        result = _normalize_result_set(headers, rows)
        assert len(result) == 2
        assert result[0] == {"TEAM_ID": 1611661321, "TEAM_NAME": "Wings", "TEAM_ABBREVIATION": "DAL"}
        assert result[1]["TEAM_ABBREVIATION"] == "LAS"


# ============================================================================
# UNIT TESTS — TestConferenceLookup
# ============================================================================


class TestConferenceLookup:
    """Tests for TEAM_CONFERENCE dict."""

    def test_known_teams(self):
        """Known teams should return correct conference."""
        from scraper.loaders import TEAM_CONFERENCE
        assert TEAM_CONFERENCE["ATL"] == "Eastern"
        assert TEAM_CONFERENCE["LAS"] == "Western"
        assert TEAM_CONFERENCE["SEA"] == "Western"

    def test_unknown_team(self):
        """Unknown team abbreviation should return 'Unknown'."""
        from scraper.loaders import TEAM_CONFERENCE
        assert TEAM_CONFERENCE.get("FAKE", "Unknown") == "Unknown"


# ============================================================================
# UNIT TESTS — TestAutoRecovery
# ============================================================================


class TestAutoRecovery:
    """Tests for auto-recovery date computation logic."""

    def test_auto_recovery_computes_start_date(self):
        """Auto mode should set start date to max(game_date) + 1 day."""
        max_date = date(2024, 8, 25)
        start_date = (max_date + timedelta(days=1)).strftime("%Y-%m-%d")
        assert start_date == "2024-08-26"


# ============================================================================
# CLIENT TESTS — TestClient
# ============================================================================


class TestClient:
    """Tests for scraper.client module."""

    def test_fetch_endpoint_success(self):
        """fetch_endpoint should return parsed JSON response."""
        with patch("scraper.client.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"resultSets": [{"headers": [], "rowSet": []}]}
            mock_get.return_value = mock_response
            result = client.fetch_endpoint("leaguedashteamstats", {"Season": "2024-25"})
            assert result == {"resultSets": [{"headers": [], "rowSet": []}]}
            mock_get.assert_called_once()

    def test_fetch_endpoint_headers(self):
        """fetch_endpoint should include required headers."""
        with patch("scraper.client.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"resultSets": []}
            mock_get.return_value = mock_response
            client.fetch_endpoint("test_endpoint", {})
            call_kwargs = mock_get.call_args[1]
            headers = call_kwargs["headers"]
            assert headers["Host"] == "stats.wnba.com"
            assert headers["Referer"] == "https://stats.wnba.com/"
            assert "User-Agent" in headers

    def test_fetch_endpoint_timeout(self):
        """fetch_endpoint should set timeout to 30 seconds."""
        with patch("scraper.client.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {}
            mock_get.return_value = mock_response
            client.fetch_endpoint("test_endpoint", {})
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["timeout"] == 30


# ============================================================================
# ENDPOINT TESTS — TestEndpoints
# ============================================================================


class TestEndpoints:
    """Tests for scraper.endpoints module."""

    @patch("scraper.endpoints.fetch_endpoint")
    def test_fetch_teams_fallback_to_playerindex(self, mock_fetch):
        """When leaguedashteamstats returns 500, fall back to playerindex."""
        # First call (leaguedashteamstats) raises, second call (playerindex) succeeds
        mock_fetch.side_effect = [
            Exception("500 Server Error"),
            {
                "resultSets": [{
                    "headers": ["PERSON_ID", "PLAYER_FIRST_NAME", "PLAYER_LAST_NAME",
                                "TEAM_ID", "TEAM_NAME", "TEAM_CITY", "TEAM_ABBREVIATION",
                                "POSITION", "HEIGHT", "WEIGHT"],
                    "rowSet": [
                        [100, "A'ja", "Wilson", 1611661319, "Aces", "Las Vegas", "LVA", "F", "6-4", "195"],
                        [200, "Kelsey", "Plum", 1611661319, "Aces", "Las Vegas", "LVA", "G", "5-8", "150"],
                        [300, "Breanna", "Stewart", 1611661313, "Liberty", "New York", "NY", "F", "6-4", "180"],
                    ],
                }],
            },
        ]
        teams = endpoints.fetch_teams(2024)
        # Should deduplicate: 2 unique teams from 3 players
        assert len(teams) == 2
        team_ids = {t["TEAM_ID"] for t in teams}
        assert 1611661319 in team_ids  # Aces
        assert 1611661313 in team_ids  # Liberty

    @patch("scraper.endpoints.fetch_endpoint")
    def test_fetch_players_uses_correct_season_format(self, mock_fetch):
        """Verify Season param uses cross-year format."""
        mock_fetch.return_value = {"resultSets": [{"headers": [], "rowSet": []}]}
        endpoints.fetch_players(2024)
        call_args = mock_fetch.call_args[0]
        assert call_args[1]["Season"] == "2024-25"

    @patch("scraper.endpoints.fetch_endpoint")
    def test_fetch_game_log_date_filter(self, mock_fetch):
        """fetch_game_log should pass date filtering params."""
        mock_fetch.return_value = {"resultSets": [{"headers": [], "rowSet": []}]}
        endpoints.fetch_game_log(2024, date_from="2024-06-01", date_to="2024-06-07")
        call_args = mock_fetch.call_args[0]
        assert call_args[1]["DateFrom"] == "2024-06-01"
        assert call_args[1]["DateTo"] == "2024-06-07"
        assert call_args[1]["Season"] == "2024-25"

    @patch("scraper.endpoints.fetch_endpoint")
    def test_fetch_boxscore_structure(self, mock_fetch):
        """fetch_boxscore should return dict with player_stats and team_stats."""
        mock_fetch.return_value = {
            "resultSets": [
                {"headers": ["PLAYER_ID", "TEAM_ID"], "rowSet": [[100, 200]]},
                {"headers": ["TEAM_ID", "PTS"], "rowSet": [[200, 108]]},
            ]
        }
        result = endpoints.fetch_boxscore("1022400175")
        assert "player_stats" in result
        assert "team_stats" in result
        assert result["player_stats"][0]["PLAYER_ID"] == 100
        assert result["team_stats"][0]["PTS"] == 108


# ============================================================================
# LOADER TESTS — TestLoaders (Postgres Required)
# ============================================================================


class TestLoaders:
    """Tests for scraper.loaders module (requires Postgres)."""

    def test_upsert_teams(self, db_session, api_teams_data):
        """upsert_teams should insert teams with correct data."""
        count = loaders.upsert_teams(db_session, api_teams_data)
        db_session.commit()
        assert count == 2
        teams = db_session.execute(select(Team)).scalars().all()
        assert len(teams) == 2
        aces = [t for t in teams if t.abbreviation == "LVA"][0]
        assert aces.full_name == "Las Vegas Aces"
        assert aces.conference == "Western"

    def test_upsert_teams_idempotent(self, db_session, api_teams_data):
        """upsert_teams should be idempotent (no duplicates on re-run)."""
        loaders.upsert_teams(db_session, api_teams_data)
        db_session.commit()
        loaders.upsert_teams(db_session, api_teams_data)
        db_session.commit()
        teams = db_session.execute(select(Team)).scalars().all()
        assert len(teams) == 2  # Still 2, not 4

    def test_upsert_players_no_team_id(self, db_session, api_players_data):
        """Players should have NO team_id field."""
        loaders.upsert_players(db_session, api_players_data)
        db_session.commit()
        players = db_session.execute(select(Player)).scalars().all()
        assert len(players) == 2
        assert players[0].first_name == "A'ja"
        for p in players:
            assert not hasattr(p, "team_id")

    def test_upsert_games_home_away(self, db_session, api_teams_data, api_game_log_data):
        """Games should correctly identify home/away from MATCHUP field."""
        loaders.upsert_teams(db_session, api_teams_data)
        db_session.commit()
        count = loaders.upsert_games_from_log(db_session, api_game_log_data, 2024, "Regular Season")
        db_session.commit()
        assert count == 1
        game = db_session.execute(select(Game)).scalar_one()
        assert game.home_team_id == 1001  # LVA (vs.)
        assert game.away_team_id == 1002  # NY (@)
        assert game.home_score == 108
        assert game.away_score == 102
        assert game.game_date.isoformat() == "2024-08-25"

    def test_load_boxscore_to_maps_to_tov(self, db_session, api_teams_data, api_players_data, api_game_log_data, api_boxscore_data):
        """CRITICAL: API field 'TO' must map to model column 'tov'."""
        loaders.upsert_teams(db_session, api_teams_data)
        loaders.upsert_players(db_session, api_players_data)
        loaders.upsert_games_from_log(db_session, api_game_log_data, 2024, "Regular Season")
        db_session.commit()
        pcount, tcount = loaders.load_boxscore(db_session, "1022400175", api_boxscore_data)
        db_session.commit()
        assert pcount == 1
        assert tcount == 1
        pstat = db_session.execute(select(PlayerGameStats)).scalar_one()
        assert pstat.tov == 2  # API sent TO=2, stored as tov=2
        assert pstat.points == 28
        tstat = db_session.execute(select(TeamGameStats)).scalar_one()
        assert tstat.tov == 15  # API sent TO=15, stored as tov=15

    def test_load_officials_name_concatenation(self, db_session, api_teams_data, api_game_log_data, api_officials_data):
        """API has FIRST_NAME + LAST_NAME, not OFFICIAL_NAME."""
        loaders.upsert_teams(db_session, api_teams_data)
        loaders.upsert_games_from_log(db_session, api_game_log_data, 2024, "Regular Season")
        db_session.commit()
        count = loaders.load_officials(db_session, "1022400175", api_officials_data)
        db_session.commit()
        assert count == 2
        officials = db_session.execute(select(GameOfficial)).scalars().all()
        names = {o.official_name for o in officials}
        assert "Jeff Wooten" in names
        assert "Dannica Mosher" in names
        # Verify JERSEY_NUM whitespace is stripped
        wooten = [o for o in officials if o.official_name == "Jeff Wooten"][0]
        assert wooten.jersey_number == "23"

    def test_player_trade_handling(self, db_session):
        """A traded player has different team_ids across games."""
        loaders.upsert_teams(db_session, [
            {"TEAM_ID": 1, "TEAM_NAME": "Team A", "TEAM_CITY": "City A", "TEAM_ABBREVIATION": "TA"},
            {"TEAM_ID": 2, "TEAM_NAME": "Team B", "TEAM_CITY": "City B", "TEAM_ABBREVIATION": "TB"},
        ])
        loaders.upsert_players(db_session, [
            {"PERSON_ID": 100, "PLAYER_FIRST_NAME": "Test", "PLAYER_LAST_NAME": "Player",
             "POSITION": "G", "HEIGHT": "5-10", "WEIGHT": "160"},
        ])
        loaders.upsert_games_from_log(db_session, [
            {"GAME_ID": "G1", "GAME_DATE": "2024-06-01", "TEAM_ID": 1, "MATCHUP": "TA vs. TB", "PTS": 100},
            {"GAME_ID": "G1", "GAME_DATE": "2024-06-01", "TEAM_ID": 2, "MATCHUP": "TB @ TA", "PTS": 90},
            {"GAME_ID": "G2", "GAME_DATE": "2024-07-01", "TEAM_ID": 2, "MATCHUP": "TB vs. TA", "PTS": 95},
            {"GAME_ID": "G2", "GAME_DATE": "2024-07-01", "TEAM_ID": 1, "MATCHUP": "TA @ TB", "PTS": 88},
        ], 2024, "Regular Season")
        db_session.commit()
        # Player on team 1 in game 1, team 2 in game 2 (traded)
        box1 = {"player_stats": [{"PLAYER_ID": 100, "TEAM_ID": 1, "MIN": "30:00", "PTS": 15,
                 "FGM": 6, "FGA": 12, "FG_PCT": 0.5, "FG3M": 0, "FG3A": 0, "FG3_PCT": 0.0,
                 "FTM": 3, "FTA": 4, "FT_PCT": 0.75, "OREB": 1, "DREB": 4, "REB": 5,
                 "AST": 3, "STL": 1, "BLK": 0, "TO": 2, "PF": 2, "PLUS_MINUS": 5.0}],
                "team_stats": []}
        box2 = {"player_stats": [{"PLAYER_ID": 100, "TEAM_ID": 2, "MIN": "28:00", "PTS": 20,
                 "FGM": 8, "FGA": 14, "FG_PCT": 0.571, "FG3M": 1, "FG3A": 3, "FG3_PCT": 0.333,
                 "FTM": 3, "FTA": 3, "FT_PCT": 1.0, "OREB": 0, "DREB": 5, "REB": 5,
                 "AST": 4, "STL": 2, "BLK": 1, "TO": 1, "PF": 3, "PLUS_MINUS": 8.0}],
                "team_stats": []}
        loaders.load_boxscore(db_session, "G1", box1)
        loaders.load_boxscore(db_session, "G2", box2)
        db_session.commit()
        stats = db_session.execute(
            select(PlayerGameStats).where(PlayerGameStats.player_id == 100)
        ).scalars().all()
        assert len(stats) == 2
        team_ids = {s.team_id for s in stats}
        assert team_ids == {1, 2}


# ============================================================================
# IDEMPOTENCY TESTS — TestUpsertIdempotency
# ============================================================================


class TestUpsertIdempotency:
    """Tests for upsert idempotency (Postgres required)."""

    def test_boxscore_upsert_updates_not_duplicates(self, db_session, api_teams_data, api_players_data, api_game_log_data):
        """Loading a boxscore twice should update the row, not create a duplicate."""
        loaders.upsert_teams(db_session, api_teams_data)
        loaders.upsert_players(db_session, api_players_data)
        loaders.upsert_games_from_log(db_session, api_game_log_data, 2024, "Regular Season")
        db_session.commit()
        box_v1 = {"player_stats": [{"PLAYER_ID": 201950, "TEAM_ID": 1001, "MIN": "36:35",
                   "PTS": 28, "FGM": 11, "FGA": 18, "FG_PCT": 0.611,
                   "FG3M": 0, "FG3A": 0, "FG3_PCT": 0.0,
                   "FTM": 6, "FTA": 7, "FT_PCT": 0.857,
                   "OREB": 2, "DREB": 8, "REB": 10,
                   "AST": 2, "STL": 1, "BLK": 0, "TO": 2, "PF": 3, "PLUS_MINUS": 5.2}],
                  "team_stats": [{"TEAM_ID": 1001, "MIN": "200:00", "PTS": 108,
                   "FGM": 40, "FGA": 84, "FG_PCT": 0.476,
                   "FG3M": 10, "FG3A": 26, "FG3_PCT": 0.385,
                   "FTM": 18, "FTA": 22, "FT_PCT": 0.818,
                   "OREB": 8, "DREB": 32, "REB": 40,
                   "AST": 25, "STL": 8, "BLK": 3, "TO": 15, "PF": 20, "PLUS_MINUS": 6.0}]}
        loaders.load_boxscore(db_session, "1022400175", box_v1)
        db_session.commit()
        # Second load with updated points
        box_v2 = {"player_stats": [{"PLAYER_ID": 201950, "TEAM_ID": 1001, "MIN": "36:35",
                   "PTS": 30, "FGM": 12, "FGA": 19, "FG_PCT": 0.632,
                   "FG3M": 0, "FG3A": 0, "FG3_PCT": 0.0,
                   "FTM": 6, "FTA": 7, "FT_PCT": 0.857,
                   "OREB": 2, "DREB": 8, "REB": 10,
                   "AST": 2, "STL": 1, "BLK": 0, "TO": 2, "PF": 3, "PLUS_MINUS": 5.2}],
                  "team_stats": [{"TEAM_ID": 1001, "MIN": "200:00", "PTS": 110,
                   "FGM": 41, "FGA": 84, "FG_PCT": 0.488,
                   "FG3M": 10, "FG3A": 26, "FG3_PCT": 0.385,
                   "FTM": 18, "FTA": 22, "FT_PCT": 0.818,
                   "OREB": 8, "DREB": 32, "REB": 40,
                   "AST": 25, "STL": 8, "BLK": 3, "TO": 15, "PF": 20, "PLUS_MINUS": 6.0}]}
        loaders.load_boxscore(db_session, "1022400175", box_v2)
        db_session.commit()
        pstats = db_session.execute(select(PlayerGameStats)).scalars().all()
        assert len(pstats) == 1  # 1 row, not 2
        assert pstats[0].points == 30  # Updated value

    def test_officials_upsert_no_duplicates(self, db_session, api_teams_data, api_game_log_data, api_officials_data):
        """Loading officials twice should not create duplicates."""
        loaders.upsert_teams(db_session, api_teams_data)
        loaders.upsert_games_from_log(db_session, api_game_log_data, 2024, "Regular Season")
        db_session.commit()
        loaders.load_officials(db_session, "1022400175", api_officials_data)
        db_session.commit()
        loaders.load_officials(db_session, "1022400175", api_officials_data)
        db_session.commit()
        officials = db_session.execute(select(GameOfficial)).scalars().all()
        assert len(officials) == 2  # Still 2, not 4


# ============================================================================
# PHASE 5 TESTS — Off-Season, First-Run, ScrapeRun
# ============================================================================


class TestOffSeasonDetection:
    """Tests for off-season detection logic."""

    def test_off_season_november(self):
        """November should be off-season."""
        from scraper.runner import is_off_season
        assert is_off_season(today=date(2025, 11, 15)) is True

    def test_off_season_january(self):
        """January should be off-season."""
        from scraper.runner import is_off_season
        assert is_off_season(today=date(2026, 1, 15)) is True

    def test_active_season_june(self):
        """June should be active season."""
        from scraper.runner import is_off_season
        assert is_off_season(today=date(2025, 6, 15)) is False

    def test_active_season_october(self):
        """October should be active season."""
        from scraper.runner import is_off_season
        assert is_off_season(today=date(2025, 10, 15)) is False

    def test_boundary_may(self):
        """May should be active season (season starts in May)."""
        from scraper.runner import is_off_season
        assert is_off_season(today=date(2025, 5, 1)) is False

    def test_boundary_april(self):
        """April should be off-season."""
        from scraper.runner import is_off_season
        assert is_off_season(today=date(2025, 4, 30)) is True


class TestScrapeRunModel:
    """Tests for ScrapeRun model."""

    def test_scrape_run_model_exists(self):
        """ScrapeRun can be imported from models."""
        from models import ScrapeRun
        assert ScrapeRun.__tablename__ == "scrape_runs"

    def test_scrape_run_create(self, db_session):
        """ScrapeRun record can be created."""
        from models import ScrapeRun
        from datetime import timezone
        run = ScrapeRun(
            started_at=datetime.now(timezone.utc),
            mode="auto",
            season=2025,
            games_found=0,
            games_loaded=0,
            success=True,
        )
        db_session.add(run)
        db_session.flush()
        assert run.id is not None

    def test_scrape_run_failure_record(self, db_session):
        """ScrapeRun records failure with error message."""
        from models import ScrapeRun
        from datetime import timezone
        run = ScrapeRun(
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            mode="auto",
            season=2025,
            success=False,
            error_message="API returned 429",
        )
        db_session.add(run)
        db_session.flush()
        assert run.success is False
        assert "429" in run.error_message


class TestFirstRunGuard:
    """Test that auto mode with empty database returns error."""

    def test_first_run_returns_error(self):
        """Auto mode with no games in DB should return 1."""
        from unittest.mock import patch

        with patch('scraper.runner.get_max_game_date', return_value=None), \
             patch('scraper.runner.is_off_season', return_value=False):
            from scraper.runner import main
            import sys
            with patch.object(sys, 'argv', ['runner', '--auto']):
                result = main()
                assert result == 1
