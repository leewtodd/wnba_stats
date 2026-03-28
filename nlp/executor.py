"""NLPExecutor class — query execution with logging."""
import logging
import time
import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import anthropic
from sqlalchemy import text

from models.base import get_engine, get_session_factory
from models.logs import QueryLog
from nlp.schema_prompt import build_system_prompt
from nlp.tools import get_all_tools
from engine import call_function

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a query execution."""
    question: str                          # Original question
    answer: str                            # Claude's natural language answer
    data: pd.DataFrame = field(default_factory=pd.DataFrame)  # Query results
    sql: Optional[str] = None              # Generated SQL (if SQL was used)
    function_call: Optional[str] = None    # Function call string (if function was used)
    execution_time_ms: int = 0
    success: bool = True
    error: Optional[str] = None
    suggested_chart: Optional[str] = None  # Chart type suggestion from Claude


class NLPExecutor:
    """Execute natural language questions against the WNBA database via Claude API."""

    FORBIDDEN_KEYWORDS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER',
        'TRUNCATE', 'CREATE', 'GRANT', 'REVOKE'
    ]

    def __init__(self, db_url: str = None, api_key: str = None):
        """Initialize the NLP executor.

        Args:
            db_url: Database URL (optional, uses default from models.base if None)
            api_key: Anthropic API key (optional, uses ANTHROPIC_API_KEY env var if None)
        """
        self.engine = get_engine()
        self.Session = get_session_factory(self.engine)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.system_prompt = build_system_prompt()
        self.tools = get_all_tools()

    def ask(self, question: str) -> ExecutionResult:
        """Execute a natural language question and return results.

        Args:
            question: Natural language question from user

        Returns:
            ExecutionResult with answer, data, and metadata
        """
        start_time = time.time()
        result = ExecutionResult(question=question, answer="", success=True)

        try:
            # Call Claude to get initial response
            response = self._call_claude(question)

            # Check for tool use blocks
            tool_use_block = None
            for content in response.content:
                if content.type == "tool_use":
                    tool_use_block = content
                    break

            if tool_use_block:
                # Execute the tool
                if tool_use_block.name == "execute_sql":
                    sql = tool_use_block.input.get("sql")
                    chart_suggestion = tool_use_block.input.get("chart_suggestion")
                    result.sql = sql
                    result.suggested_chart = chart_suggestion

                    try:
                        result.data = self._execute_sql(sql)
                        tool_result = result.data.to_string() if not result.data.empty else "No results"
                    except Exception as e:
                        tool_result = f"Error: {str(e)}"
                        result.success = False
                        result.error = str(e)

                else:
                    # It's an engine function call
                    func_name = tool_use_block.name
                    func_kwargs = tool_use_block.input
                    result.function_call = f"{func_name}({', '.join(f'{k}={repr(v)}' for k, v in func_kwargs.items())})"

                    try:
                        result.data = self._execute_function(func_name, func_kwargs)
                        tool_result = result.data.to_string() if not result.data.empty else "No results"
                    except Exception as e:
                        tool_result = f"Error: {str(e)}"
                        result.success = False
                        result.error = str(e)

                # Call Claude again with tool result for natural language summary
                follow_up_messages = [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": response.content},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_block.id,
                                "content": tool_result,
                            }
                        ],
                    },
                ]

                summary_response = self._call_claude(question, follow_up_messages)

                # Extract text from summary response
                for content in summary_response.content:
                    if hasattr(content, "text"):
                        result.answer = content.text
                        break

            else:
                # No tool use, just return text
                for content in response.content:
                    if hasattr(content, "text"):
                        result.answer = content.text
                        break

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error(f"Error in ask(): {e}", exc_info=True)

        # Calculate execution time
        execution_time_s = time.time() - start_time
        result.execution_time_ms = int(execution_time_s * 1000)

        # Log the query
        self._log_query(
            question=question,
            generated_sql=result.sql or result.function_call or "",
            execution_time_ms=result.execution_time_ms,
            row_count=len(result.data) if not result.data.empty else 0,
            success=result.success,
            error_message=result.error
        )

        return result

    def _call_claude(self, question: str, messages=None):
        """Call Claude API with question and optional message history.

        Args:
            question: User's question
            messages: Optional message history for follow-up calls

        Returns:
            Claude API response object
        """
        if messages is None:
            messages = [{"role": "user", "content": question}]

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self.system_prompt,
            tools=self.tools,
            messages=messages,
        )
        return response

    def _execute_sql(self, sql: str) -> pd.DataFrame:
        """Execute a read-only SQL query.

        Args:
            sql: SQL SELECT query to execute

        Returns:
            DataFrame with query results

        Raises:
            ValueError: If SQL contains forbidden keywords
        """
        # Pre-filter forbidden keywords BEFORE opening connection
        for keyword in self.FORBIDDEN_KEYWORDS:
            if re.search(rf'\b{keyword}\b', sql, re.IGNORECASE):
                raise ValueError(f"Forbidden SQL keyword detected: {keyword}")

        # Execute in read-only transaction with timeout
        with self.engine.connect() as conn:
            conn.execute(text("SET statement_timeout = '30s'"))
            conn.execute(text("SET TRANSACTION READ ONLY"))
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            return df

    def _execute_function(self, name: str, kwargs: dict) -> pd.DataFrame:
        """Execute an engine function.

        Args:
            name: Function name
            kwargs: Function arguments

        Returns:
            DataFrame with function results
        """
        return call_function(name, **kwargs)

    def _log_query(self, question: str, generated_sql: str, execution_time_ms: int,
                   row_count: int, success: bool, error_message: str = None):
        """Log a query execution to the database.

        Args:
            question: User's question text
            generated_sql: Generated SQL or function call string
            execution_time_ms: Execution time in milliseconds
            row_count: Number of rows returned
            success: Whether execution was successful
            error_message: Error message if unsuccessful
        """
        session = self.Session()
        try:
            log_entry = QueryLog(
                question_text=question,
                generated_sql=generated_sql or "",
                execution_time_ms=execution_time_ms,
                row_count=row_count,
                success=success,
                error_message=error_message,
            )
            session.add(log_entry)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to log query: {e}")
        finally:
            session.close()
