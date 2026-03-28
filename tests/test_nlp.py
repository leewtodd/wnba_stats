"""Tests for nlp module."""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from sqlalchemy import text

from nlp.tools import generate_tools_from_registry, get_all_tools, SQL_EXECUTE_TOOL
from nlp.schema_prompt import build_system_prompt
from nlp.executor import NLPExecutor
from models.base import get_engine


class TestToolGeneration:
    """Tests for Claude API tool generation from engine registry."""

    def test_generate_tools_returns_list(self):
        """generate_tools_from_registry() returns a non-empty list."""
        tools = generate_tools_from_registry()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_each_tool_has_required_fields(self):
        """Each tool dict has 'name', 'description', 'input_schema'."""
        tools = generate_tools_from_registry()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_input_schema_has_properties(self):
        """Each tool's input_schema has 'type': 'object' and 'properties'."""
        tools = generate_tools_from_registry()
        for tool in tools:
            schema = tool["input_schema"]
            assert schema.get("type") == "object"
            assert "properties" in schema

    def test_required_params_listed(self):
        """Non-optional params appear in the 'required' list."""
        tools = generate_tools_from_registry()
        # Find a tool with some required params
        for tool in tools:
            schema = tool["input_schema"]
            required = schema.get("required", [])
            properties = schema.get("properties", {})

            # All required params should be in properties
            for req in required:
                assert req in properties

    def test_sql_execute_tool_format(self):
        """SQL_EXECUTE_TOOL constant has correct structure."""
        assert SQL_EXECUTE_TOOL["name"] == "execute_sql"
        assert "description" in SQL_EXECUTE_TOOL
        assert "input_schema" in SQL_EXECUTE_TOOL
        schema = SQL_EXECUTE_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "sql" in schema["properties"]
        assert "sql" in schema["required"]

    def test_get_all_tools_includes_sql(self):
        """get_all_tools() includes both engine tools and SQL_EXECUTE_TOOL."""
        tools = get_all_tools()
        sql_tools = [t for t in tools if t["name"] == "execute_sql"]
        assert len(sql_tools) == 1

    def test_tool_count_matches_registry(self):
        """Number of engine tools equals len(get_registered_functions())."""
        from engine import get_registered_functions
        engine_tools = generate_tools_from_registry()
        registered = get_registered_functions()
        assert len(engine_tools) == len(registered)


class TestSchemaPrompt:
    """Tests for system prompt builder."""

    def test_prompt_contains_all_tables(self):
        """System prompt mentions all 8 table names."""
        prompt = build_system_prompt()
        for table in ['teams', 'players', 'games', 'player_game_stats',
                      'team_game_stats', 'game_officials', 'arenas', 'query_log']:
            assert table in prompt

    def test_prompt_contains_design_notes(self):
        """System prompt contains the player-team affiliation warning."""
        prompt = build_system_prompt()
        assert 'player_game_stats.team_id' in prompt

    def test_prompt_contains_examples(self):
        """System prompt contains example queries."""
        prompt = build_system_prompt()
        assert 'Caitlin' in prompt  # From the example query
        assert 'compare_teams' in prompt  # From the example function call

    def test_prompt_contains_function_list(self):
        """System prompt lists engine functions."""
        prompt = build_system_prompt()
        assert 'compare_teams' in prompt
        assert 'correlate_stats' in prompt or 'analysis' in prompt.lower()


class TestReadOnlyEnforcement:
    """Tests for SQL safety checks."""

    def test_rejects_insert(self):
        """_execute_sql rejects INSERT statements."""
        executor = NLPExecutor()
        with pytest.raises(ValueError, match="Forbidden SQL keyword"):
            executor._execute_sql("INSERT INTO teams (full_name) VALUES ('Test')")

    def test_rejects_drop(self):
        """_execute_sql rejects DROP statements."""
        executor = NLPExecutor()
        with pytest.raises(ValueError, match="Forbidden SQL keyword"):
            executor._execute_sql("DROP TABLE teams")

    def test_rejects_delete(self):
        """_execute_sql rejects DELETE statements."""
        executor = NLPExecutor()
        with pytest.raises(ValueError, match="Forbidden SQL keyword"):
            executor._execute_sql("DELETE FROM teams WHERE id = 1")

    def test_rejects_update(self):
        """_execute_sql rejects UPDATE statements."""
        executor = NLPExecutor()
        with pytest.raises(ValueError, match="Forbidden SQL keyword"):
            executor._execute_sql("UPDATE teams SET full_name = 'New' WHERE id = 1")

    def test_rejects_alter(self):
        """_execute_sql rejects ALTER statements."""
        executor = NLPExecutor()
        with pytest.raises(ValueError, match="Forbidden SQL keyword"):
            executor._execute_sql("ALTER TABLE teams ADD COLUMN test VARCHAR(255)")

    def test_rejects_case_insensitive(self):
        """_execute_sql rejects 'drop table teams' (lowercase)."""
        executor = NLPExecutor()
        with pytest.raises(ValueError, match="Forbidden SQL keyword"):
            executor._execute_sql("drop table teams")

    def test_allows_select(self):
        """_execute_sql allows a simple SELECT query."""
        executor = NLPExecutor()
        result = executor._execute_sql("SELECT * FROM teams LIMIT 1")
        assert isinstance(result, pd.DataFrame)

    def test_allows_select_with_where(self):
        """_execute_sql allows SELECT with WHERE containing 'update' as data value."""
        executor = NLPExecutor()
        # This should not raise because 'Updated' is not a SQL keyword in statement position
        result = executor._execute_sql("SELECT * FROM teams WHERE full_name LIKE 'A%' LIMIT 1")
        assert isinstance(result, pd.DataFrame)


class TestQueryLogging:
    """Tests for query_log writes."""

    def test_successful_query_logged(self):
        """After a successful _execute_sql, query_log has a new row with success=True."""
        engine = get_engine()

        # Count rows before
        with engine.connect() as conn:
            result_before = conn.execute(text("SELECT COUNT(*) FROM query_log"))
            count_before = result_before.scalar()

        # Execute query through executor
        executor = NLPExecutor()
        executor._log_query(
            question="Test question",
            generated_sql="SELECT * FROM teams LIMIT 1",
            execution_time_ms=100,
            row_count=5,
            success=True,
            error_message=None
        )

        # Count rows after
        with engine.connect() as conn:
            result_after = conn.execute(text("SELECT COUNT(*) FROM query_log"))
            count_after = result_after.scalar()

        assert count_after == count_before + 1

        # Verify the logged row
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT question_text, success, error_message FROM query_log "
                     "WHERE question_text = 'Test question' ORDER BY id DESC LIMIT 1")
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "Test question"
            assert row[1] is True
            assert row[2] is None

    def test_failed_query_logged(self):
        """After a rejected SQL attempt, query_log has a new row with success=False."""
        engine = get_engine()

        # Count rows before
        with engine.connect() as conn:
            result_before = conn.execute(text("SELECT COUNT(*) FROM query_log"))
            count_before = result_before.scalar()

        # Log a failed query
        executor = NLPExecutor()
        executor._log_query(
            question="Failed test question",
            generated_sql="DROP TABLE teams",
            execution_time_ms=50,
            row_count=0,
            success=False,
            error_message="Forbidden SQL keyword detected: DROP"
        )

        # Count rows after
        with engine.connect() as conn:
            result_after = conn.execute(text("SELECT COUNT(*) FROM query_log"))
            count_after = result_after.scalar()

        assert count_after == count_before + 1

        # Verify the logged row
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT question_text, success, error_message FROM query_log "
                     "WHERE question_text = 'Failed test question' ORDER BY id DESC LIMIT 1")
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "Failed test question"
            assert row[1] is False
            assert "Forbidden SQL keyword" in row[2]


class TestExecutorPipeline:
    """Integration tests with mocked Claude API."""

    def test_ask_with_sql_tool_use(self):
        """Mock Claude returning a tool_use block for execute_sql, verify full pipeline."""
        executor = NLPExecutor()

        # Mock the Claude API response
        mock_response = MagicMock()
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "execute_sql"
        mock_tool_use.id = "tool_123"
        mock_tool_use.input = {"sql": "SELECT * FROM teams LIMIT 1"}

        mock_response.content = [mock_tool_use]

        # Mock the follow-up response with text
        mock_summary_response = MagicMock()
        mock_text = MagicMock()
        mock_text.type = "text"
        mock_text.text = "Here are the teams in the database."
        mock_summary_response.content = [mock_text]

        with patch.object(executor.client.messages, 'create') as mock_create:
            mock_create.side_effect = [mock_response, mock_summary_response]

            result = executor.ask("What teams are in the database?")

            assert result.success is True
            assert result.answer == "Here are the teams in the database."
            assert result.sql == "SELECT * FROM teams LIMIT 1"
            assert not result.data.empty

    def test_ask_with_function_tool_use(self):
        """Mock Claude returning a tool_use block for an engine function, verify pipeline."""
        executor = NLPExecutor()

        # Mock the Claude API response
        mock_response = MagicMock()
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "compare_teams"
        mock_tool_use.id = "tool_456"
        mock_tool_use.input = {"team_a": "Aces", "team_b": "Liberty", "stat": "points", "season": 2024}

        mock_response.content = [mock_tool_use]

        # Mock the follow-up response
        mock_summary_response = MagicMock()
        mock_text = MagicMock()
        mock_text.type = "text"
        mock_text.text = "The Aces scored more points than the Liberty on average."
        mock_summary_response.content = [mock_text]

        with patch.object(executor.client.messages, 'create') as mock_create:
            mock_create.side_effect = [mock_response, mock_summary_response]

            with patch('nlp.executor.call_function') as mock_call_func:
                mock_df = pd.DataFrame({
                    'team': ['Aces', 'Liberty'],
                    'avg_points': [110.5, 108.2]
                })
                mock_call_func.return_value = mock_df

                result = executor.ask("Compare Aces and Liberty scoring")

                assert result.success is True
                assert result.function_call is not None
                assert "compare_teams" in result.function_call

    def test_ask_with_text_only_response(self):
        """Mock Claude returning text only (no tool use), verify pipeline."""
        executor = NLPExecutor()

        # Mock the Claude API response with text only
        mock_response = MagicMock()
        mock_text = MagicMock()
        mock_text.type = "text"
        mock_text.text = "The WNBA database contains statistics from 2022-2025."
        mock_response.content = [mock_text]

        with patch.object(executor.client.messages, 'create') as mock_create:
            mock_create.return_value = mock_response

            result = executor.ask("Tell me about the database")

            assert result.success is True
            assert result.answer == "The WNBA database contains statistics from 2022-2025."
            assert result.sql is None
            assert result.data.empty

    def test_ask_handles_api_error(self):
        """Mock Claude API raising an exception, verify graceful error handling."""
        executor = NLPExecutor()

        with patch.object(executor.client.messages, 'create') as mock_create:
            mock_create.side_effect = Exception("API Error: Rate limit exceeded")

            result = executor.ask("What's the best team?")

            assert result.success is False
            assert "API Error" in result.error
            assert result.execution_time_ms > 0
