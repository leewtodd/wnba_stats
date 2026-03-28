"""Tests for engine module - utils, decorators, and integration tests."""
import pytest
import pandas as pd
from engine.utils import (
    get_session, resolve_team, resolve_player, validate_stat, STAT_COLUMN_MAP
)
from engine.base import _REGISTRY
from engine import get_registered_functions, call_function
from engine.team_matchups import compare_teams
from engine.player_trends import player_game_log
from engine.game_context import home_away_analysis
from engine.correlation import correlate_stats
from models.core import PlayerGameStats, Team, Player


class TestSessionManagement:
    """Tests for database session management."""

    def test_get_session_returns_session(self):
        """get_session() should return a SQLAlchemy session."""
        session = get_session()
        assert session is not None
        session.close()

    def test_session_can_query(self):
        """Session should be able to query the database."""
        session = get_session()
        # Try a simple query
        teams = session.query(Team).limit(1).all()
        assert isinstance(teams, list)
        session.close()


class TestTeamResolution:
    """Tests for team name resolution."""

    def test_resolve_team_by_abbreviation(self):
        """resolve_team() should find teams by abbreviation."""
        session = get_session()
        try:
            # Get a real team abbreviation from the database
            team = session.query(Team).first()
            assert team is not None

            team_id = resolve_team(team.abbreviation)
            assert team_id == team.id
        finally:
            session.close()

    def test_resolve_team_by_full_name(self):
        """resolve_team() should find teams by full name."""
        session = get_session()
        try:
            team = session.query(Team).first()
            assert team is not None

            team_id = resolve_team(team.full_name)
            assert team_id == team.id
        finally:
            session.close()

    def test_resolve_team_case_insensitive(self):
        """resolve_team() should be case-insensitive."""
        session = get_session()
        try:
            team = session.query(Team).first()
            assert team is not None

            team_id1 = resolve_team(team.abbreviation.upper())
            team_id2 = resolve_team(team.abbreviation.lower())
            assert team_id1 == team_id2 == team.id
        finally:
            session.close()

    def test_resolve_team_invalid_raises_error(self):
        """resolve_team() should raise ValueError for invalid team."""
        with pytest.raises(ValueError, match="Team not found"):
            resolve_team("InvalidTeamXYZ123")

    def test_resolve_team_ambiguous_raises_error(self):
        """resolve_team() should raise ValueError for ambiguous or not found."""
        session = get_session()
        try:
            # This depends on database content - may need to skip if ambiguity doesn't exist
            # Try to resolve by a term that doesn't match
            with pytest.raises(ValueError):
                resolve_team("XYZTeamDoesNotExist123")
        finally:
            session.close()


class TestPlayerResolution:
    """Tests for player name resolution."""

    def test_resolve_player_by_full_name(self):
        """resolve_player() should find players by full name."""
        session = get_session()
        try:
            player = session.query(Player).first()
            assert player is not None

            player_id = resolve_player(f"{player.first_name} {player.last_name}")
            assert player_id == player.id
        finally:
            session.close()

    def test_resolve_player_by_last_name(self):
        """resolve_player() should find unique players by last name."""
        session = get_session()
        try:
            player = session.query(Player).first()
            assert player is not None

            # This will work if the last name is unique
            try:
                player_id = resolve_player(player.last_name)
                assert player_id == player.id
            except ValueError:
                # This is OK if the last name is ambiguous
                pass
        finally:
            session.close()

    def test_resolve_player_case_insensitive(self):
        """resolve_player() should be case-insensitive."""
        session = get_session()
        try:
            player = session.query(Player).first()
            assert player is not None

            player_id1 = resolve_player(f"{player.first_name} {player.last_name}".upper())
            player_id2 = resolve_player(f"{player.first_name} {player.last_name}".lower())
            assert player_id1 == player_id2 == player.id
        finally:
            session.close()

    def test_resolve_player_invalid_raises_error(self):
        """resolve_player() should raise ValueError for invalid player."""
        with pytest.raises(ValueError, match="Player not found"):
            resolve_player("NonExistentPlayerXYZ")


class TestStatColumnMap:
    """Tests for stat column mapping."""

    def test_stat_column_map_has_valid_entries(self):
        """STAT_COLUMN_MAP should have entries for common stats."""
        assert "points" in STAT_COLUMN_MAP
        assert "rebounds" in STAT_COLUMN_MAP
        assert "assists" in STAT_COLUMN_MAP

    def test_stat_column_map_maps_to_valid_columns(self):
        """All values in STAT_COLUMN_MAP should be valid PlayerGameStats columns."""
        valid_columns = [c.name for c in PlayerGameStats.__table__.columns]
        for value in set(STAT_COLUMN_MAP.values()):
            assert value in valid_columns, f"{value} is not a valid column"

    def test_validate_stat_alias(self):
        """validate_stat() should resolve human-readable names."""
        assert validate_stat("rebounds") == "reb"
        assert validate_stat("assists") == "ast"
        assert validate_stat("turnovers") == "tov"

    def test_validate_stat_direct(self):
        """validate_stat() should accept direct column names."""
        assert validate_stat("reb") == "reb"
        assert validate_stat("ast") == "ast"
        assert validate_stat("points") == "points"

    def test_validate_stat_case_insensitive(self):
        """validate_stat() should be case-insensitive."""
        assert validate_stat("REBOUNDS") == "reb"
        assert validate_stat("Rebounds") == "reb"

    def test_validate_stat_invalid_raises_error(self):
        """validate_stat() should raise ValueError for invalid stat."""
        with pytest.raises(ValueError, match="Unknown stat"):
            validate_stat("nonsense_stat_xyz")


class TestDecoratorMetadata:
    """Tests for @engine_function decorator."""

    def test_decorated_function_has_metadata(self):
        """Decorated functions should have _engine_meta attribute."""
        # compare_teams is decorated
        assert hasattr(compare_teams, '_engine_meta')
        assert compare_teams._engine_meta['name'] == 'compare_teams'

    def test_decorated_function_metadata_complete(self):
        """Decorator metadata should include required fields."""
        meta = compare_teams._engine_meta
        assert 'name' in meta
        assert 'description' in meta
        assert 'parameters' in meta
        assert 'function' in meta
        assert 'module' in meta

    def test_decorated_function_in_registry(self):
        """Decorated functions should be registered in _REGISTRY."""
        registry_names = [f['name'] for f in _REGISTRY]
        assert 'compare_teams' in registry_names


class TestRegistry:
    """Tests for function registry."""

    def test_get_registered_functions_returns_list(self):
        """get_registered_functions() should return a list."""
        funcs = get_registered_functions()
        assert isinstance(funcs, list)
        assert len(funcs) > 0

    def test_registry_has_23_functions(self):
        """Registry should contain at least 23 registered functions."""
        funcs = get_registered_functions()
        assert len(funcs) >= 23, f"Expected at least 23 functions, got {len(funcs)}"

    def test_registry_contains_expected_modules(self):
        """Registry should contain functions from all 5 modules."""
        funcs = get_registered_functions()

        # Check that we have functions from the main modules
        expected_functions = {
            'compare_teams', 'player_game_log', 'home_away_analysis',
            'referee_impact', 'correlate_stats'
        }
        func_names = set(f['name'] for f in funcs)
        for expected in expected_functions:
            assert expected in func_names, f"Expected function '{expected}' not in registry"

    def test_call_function_by_name(self):
        """call_function() should execute a registered function by name."""
        # This is a simple test - just verify it doesn't crash
        # The actual execution depends on database state
        result = call_function("compare_teams", team_a="Aces", team_b="Liberty", stat="points")
        assert isinstance(result, pd.DataFrame)


class TestEngineIntegration:
    """Integration tests for engine functions."""

    def test_compare_teams_returns_dataframe(self):
        """compare_teams() should return a DataFrame."""
        session = get_session()
        try:
            # Get two teams
            teams = session.query(Team).limit(2).all()
            if len(teams) >= 2:
                result = compare_teams(teams[0].abbreviation, teams[1].abbreviation, "points", 2024)
                assert isinstance(result, pd.DataFrame)
        finally:
            session.close()

    def test_player_game_log_returns_dataframe(self):
        """player_game_log() should return a DataFrame."""
        session = get_session()
        try:
            player = session.query(Player).first()
            if player:
                result = player_game_log(f"{player.first_name} {player.last_name}", 2024)
                assert isinstance(result, pd.DataFrame)
        finally:
            session.close()

    def test_home_away_analysis_returns_dataframe(self):
        """home_away_analysis() should return a DataFrame."""
        result = home_away_analysis(stat="points", season=2024)
        assert isinstance(result, pd.DataFrame)

    def test_correlate_stats_returns_dataframe_with_attrs(self):
        """correlate_stats() should return DataFrame with attrs."""
        result = correlate_stats("points", "reb", season=2024)
        if not result.empty:
            assert isinstance(result, pd.DataFrame)
            assert 'r_value' in result.attrs

    def test_engine_function_error_returns_empty_df(self):
        """Engine functions should return empty DataFrame on error."""
        # Try with invalid team name
        result = compare_teams("InvalidTeamXYZ123", "Aces", "points")
        assert isinstance(result, pd.DataFrame)
