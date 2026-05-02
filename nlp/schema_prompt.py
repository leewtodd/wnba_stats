"""System prompt builder (schema + tools + examples)."""
from sqlalchemy import inspect
from models.base import get_engine
from engine import get_registered_functions


def build_system_prompt():
    """Build the complete system prompt with schema, design notes, functions, and examples."""
    engine = get_engine()

    # Section 1: Role
    prompt_parts = [
        "You are an analytics assistant for a WNBA statistics database containing 4 seasons (2022-2025) of game-level data. You answer questions by calling analysis functions or writing SQL queries.",
        ""
    ]

    # Section 2: Database Schema
    prompt_parts.append("DATABASE SCHEMA:\n")

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    for table_name in sorted(table_names):
        columns = inspector.get_columns(table_name)
        prompt_parts.append(f"TABLE: {table_name}")

        for col in columns:
            col_name = col["name"]
            col_type = str(col["type"])

            # Check if it's a primary key
            pk_info = ""
            try:
                pk_constraint = inspector.get_pk_constraint(table_name)
                if pk_constraint and col_name in pk_constraint.get("constrained_columns", []):
                    pk_info = ", PK"
            except Exception:
                pass

            prompt_parts.append(f"  {col_name} ({col_type}{pk_info})")

        prompt_parts.append("")

    # Section 3: Key Design Notes
    prompt_parts.append("IMPORTANT DESIGN NOTES:")
    prompt_parts.append("- Player-team affiliation is on player_game_stats.team_id, NOT on the players table. A player may play for different teams across seasons or even mid-season. Always JOIN through player_game_stats to get a player's team for a specific game.")
    prompt_parts.append("- Game IDs are strings (e.g., \"1022200034\"), not integers.")
    prompt_parts.append("- The 'minutes' column is a string in \"MM:SS\" format, not a numeric value.")
    prompt_parts.append("- Views available: v_team_rest_days (rest days between games), v_team_travel_distance (travel distance between consecutive game cities).")
    prompt_parts.append("- PostgreSQL function available: f_haversine(lat1, lon1, lat2, lon2) for great-circle distance.")
    prompt_parts.append("")

    # Section 4: Available Engine Functions
    prompt_parts.append("AVAILABLE ANALYSIS FUNCTIONS (prefer these over raw SQL when they cover the question):")
    functions = get_registered_functions()
    for func_dict in functions:
        name = func_dict["name"]
        description = func_dict["description"]
        params = func_dict.get("parameters", {})

        # Build parameter signature
        param_list = []
        for param_name, param_info in params.items():
            if param_info.get("optional", False):
                param_list.append(f"{param_name}?")
            else:
                param_list.append(param_name)

        param_sig = ", ".join(param_list)
        prompt_parts.append(f"- {name}({param_sig}) — {description}")

    prompt_parts.append("")

    # Section 5: Example Queries
    prompt_parts.append("EXAMPLE QUERIES:")
    prompt_parts.append("Q: \"How many points did Caitlin Clark score per game in 2024?\"")
    prompt_parts.append("A: Use execute_sql with: SELECT g.game_date, pgs.points FROM player_game_stats pgs JOIN players p ON pgs.player_id = p.id JOIN games g ON pgs.game_id = g.id WHERE p.first_name = 'Caitlin' AND p.last_name = 'Clark' AND g.season = 2024 ORDER BY g.game_date")
    prompt_parts.append("")
    prompt_parts.append("Q: \"Compare the Aces and Liberty rebounding in 2024\"")
    prompt_parts.append("A: Call compare_teams(team_a=\"Aces\", team_b=\"Liberty\", stat=\"reb\", season=2024)")
    prompt_parts.append("")
    prompt_parts.append("Q: \"What's the correlation between rest days and team scoring?\"")
    prompt_parts.append("A: Call correlate_stats(stat_x=\"rest_days\", stat_y=\"points\", level=\"team_game\")")
    prompt_parts.append("")
    prompt_parts.append("Q: \"Show all games officiated by Maj Forsberg\"")
    prompt_parts.append("A: Call referee_game_log(referee_name=\"Maj Forsberg\")")
    prompt_parts.append("")
    prompt_parts.append("Q: \"How does A'ja Wilson perform against the Storm?\"")
    prompt_parts.append("A: Call player_vs_team(player=\"A'ja Wilson\", opponent_team=\"Storm\", stat=\"points\")")
    prompt_parts.append("")
    prompt_parts.append("Q: \"Find surprising statistical correlations\"")
    prompt_parts.append("A: Call find_strong_correlations(min_r=0.5, max_p=0.05)")
    prompt_parts.append("")
    prompt_parts.append("Q: \"What's the Fever's record on back-to-back games?\"")
    prompt_parts.append("A: Call back_to_back_analysis(team=\"Fever\")")
    prompt_parts.append("")
    prompt_parts.append("Q: \"Which team had the most turnovers per game in 2023?\"")
    prompt_parts.append("A: Call team_rankings(stat=\"tov\", season=2023, per_mode=\"per_game\")")
    prompt_parts.append("")

    # Section 6: Instructions
    prompt_parts.append("RULES:")
    prompt_parts.append("- Prefer calling analysis functions over writing raw SQL when a function covers the question.")
    prompt_parts.append("- Use raw SQL only when no function matches or when custom joins/aggregations are needed.")
    prompt_parts.append("- Only generate SELECT queries. Never INSERT, UPDATE, DELETE, DROP, ALTER, or TRUNCATE.")
    prompt_parts.append("- When returning results, include a brief natural language summary of what the data shows.")
    prompt_parts.append("- When suggesting a chart type, choose from: trend_line, heat_map, scatter, split_comparison, bar, table.")

    return "\n".join(prompt_parts)
