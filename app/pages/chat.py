"""Chat interface with Claude NLP backend."""
import logging
import os
import streamlit as st
from sqlalchemy import text

from nlp.executor import NLPExecutor
from models.base import get_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def render():
    """Render the chat interface page."""
    st.header("💬 WNBA Chat")
    st.caption("Ask questions about WNBA stats in plain English")

    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.warning("Set ANTHROPIC_API_KEY environment variable to use the chat interface.")
        return

    # Initialize session state for chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "executor" not in st.session_state:
        try:
            st.session_state.executor = NLPExecutor()
        except Exception as e:
            st.error(f"Failed to initialize chat: {e}")
            return

    # Example question chips
    st.subheader("Quick start:")
    cols = st.columns(4)
    example_questions = [
        ("A'ja Wilson stats", "How did A'ja Wilson perform in 2024?"),
        ("Aces vs Liberty", "Compare the Aces and Liberty in rebounding for 2024"),
        ("Strong correlations", "Find strong statistical correlations"),
        ("Fever back-to-backs", "What is the Fever's record on back-to-back games?"),
    ]

    pending_question = None
    for col, (btn_text, full_question) in zip(cols, example_questions):
        with col:
            if st.button(btn_text, key=f"btn_{btn_text}", use_container_width=True):
                pending_question = full_question

    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

            # Display additional info for assistant messages
            if message["role"] == "assistant":
                if message["data"] is not None and not message["data"].empty:
                    st.dataframe(message["data"], use_container_width=True)

                if message["sql"]:
                    with st.expander("Generated SQL"):
                        st.code(message["sql"], language="sql")

                if message.get("function_call"):
                    with st.expander("Function Call"):
                        st.code(message["function_call"])

                if message["error"]:
                    st.error(f"Error: {message['error']}")
                    if message["sql"]:
                        st.code(message["sql"], language="sql")

    # Chat input
    user_input = st.chat_input("Ask a question about WNBA stats...")
    if pending_question:
        user_input = pending_question

    if user_input:
        # Add user message to history
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input,
            "data": None,
            "sql": None,
            "chart": None,
            "error": None
        })

        # Display user message
        with st.chat_message("user"):
            st.write(user_input)

        # Generate assistant response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing your question..."):
                try:
                    executor = st.session_state.executor
                    result = executor.ask(user_input)

                    # Display answer
                    if result.success:
                        st.write(result.answer)

                        # Display data if present
                        if not result.data.empty:
                            st.dataframe(result.data, use_container_width=True)

                        # Display generated SQL
                        if result.sql:
                            with st.expander("Generated SQL"):
                                st.code(result.sql, language="sql")

                        # Display function call
                        if result.function_call:
                            with st.expander("Function Call"):
                                st.code(result.function_call)

                    else:
                        st.error(f"Error: {result.error}")
                        if result.sql:
                            st.code(result.sql, language="sql")

                    # Add assistant response to history
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": result.answer if result.success else f"Error: {result.error}",
                        "data": result.data,
                        "sql": result.sql,
                        "function_call": result.function_call,
                        "chart": result.suggested_chart,
                        "error": result.error
                    })

                except Exception as e:
                    error_msg = f"Unexpected error: {str(e)}"
                    st.error(error_msg)
                    logger.error(f"Chat error: {e}", exc_info=True)

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg,
                        "data": None,
                        "sql": None,
                        "chart": None,
                        "error": str(e)
                    })

        st.rerun()

    # Sidebar query log
    with st.sidebar:
        st.divider()
        with st.expander("📋 Query Log", expanded=False):
            try:
                engine = get_engine()
                with engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT question_text, generated_sql, execution_time_ms, success, timestamp "
                             "FROM query_log ORDER BY timestamp DESC LIMIT 10")
                    )
                    rows = result.fetchall()

                    if rows:
                        for row in rows:
                            question = row[0][:60] + "..." if len(row[0]) > 60 else row[0]
                            sql_text = row[1][:80] + "..." if len(row[1]) > 80 else row[1]
                            exec_time = row[2] if row[2] else 0
                            success = row[3]
                            status = "✅" if success else "❌"

                            st.caption(f"{status} {question} ({exec_time}ms)")
                            st.caption(f"   {sql_text}")
                    else:
                        st.caption("No queries logged yet")

            except Exception as e:
                st.caption(f"Error loading query log: {str(e)}")
