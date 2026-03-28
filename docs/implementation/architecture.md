# Architecture: WNBA Analytics Platform

## Overview

The system is a local-first analytics platform with four distinct layers: data ingestion, storage, analysis, and interaction. All layers run on a single Mac (Apple Silicon) with no external hosting dependencies.

The ingestion layer pulls structured JSON from stats.wnba.com endpoints, normalizes the response format, and upserts into a local Postgres 17 database. The analysis layer is a Python library of correlation and statistical functions that operate on the database via SQLAlchemy and return pandas DataFrames. The interaction layer has two modes: a Streamlit-based visual UI with pre-built chart types, and a Claude API-powered natural language chat interface that can run arbitrary SQL or call engine functions. A thin visualization layer (Plotly) sits between the analysis engine and the UI, translating DataFrames into interactive charts.

The pluggable external data source architecture allows new data sources to be added as independent Python modules without modifying any existing code. Each module implements a standard interface and writes to its own database table. The correlation engine discovers available data sources dynamically.

## Components

### Scraper (`wnba_stats/scraper/`)
- **Responsibility:** Pull data from stats.wnba.com JSON endpoints, normalize responses, and upsert into Postgres.
- **Technology:** Python 3.x, requests, SQLAlchemy.
- **Interfaces:**
  - Consumes: stats.wnba.com HTTP endpoints (leaguedashteamstats, playerindex, leaguegamelog, boxscoretraditionalv2, boxscoresummaryv2).
  - Produces: rows in teams, players, games, player_game_stats, team_game_stats, game_officials tables.
- **Data Storage:** Writes to Postgres via SQLAlchemy ORM with pg_insert upserts.
- **Failure Mode:** Logs errors per game, skips failed games, continues with remaining games. Does not crash on individual game failures. Re-runnable (upserts are idempotent). Auto-recovery detects last successful game_date and resumes from there.
- **Rate Limiting:** 1.5s delay between API calls. Historical pulls staggered across days (one season per day recommended).

### External Source Modules (`wnba_stats/sources/`)
- **Responsibility:** Each module pulls from one external data source and loads into its own table. Modules are self-contained and independently deployable.
- **Technology:** Python 3.x, requests (or appropriate client library per source).
- **Standard Interface:**
  ```python
  class DataSource:
      name: str                    # e.g., "injury_reports"
      table_name: str              # e.g., "injury_reports"
      
      def fetch(self, season: int, date_from: str = None, date_to: str = None) -> list[dict]:
          """Pull raw data from the external source."""
          
      def load(self, session, data: list[dict]) -> int:
          """Upsert data into the source's dedicated table. Returns row count."""
          
      def create_table(self, engine):
          """Create the source's table if it doesn't exist."""
  ```
- **Data Storage:** Each source owns one table. Table schema defined within the module.
- **Failure Mode:** Source failures are isolated — a failed injury report pull does not affect game stat ingestion. Logged and skipped.

### Correlation Engine (`wnba_stats/engine/`)
- **Responsibility:** Python library of analytical functions. Accepts parameters (team names, player names, stat columns, date ranges, etc.), queries the database, performs statistical computations, and returns DataFrames. No visualization logic. No UI awareness.
- **Technology:** Python 3.x, SQLAlchemy (query builder), pandas, scipy, statsmodels.
- **Interfaces:**
  - Consumes: Postgres database (read-only queries).
  - Produces: pandas DataFrames with analysis results.
  - Exposed to: Streamlit UI (direct function calls), Claude API NLP layer (as tool definitions).
- **Module Structure:**
  ```
  engine/
  ├── __init__.py
  ├── team_matchups.py        # Team A vs Team B analysis
  ├── player_trends.py        # Rolling averages, streaks, splits
  ├── game_context.py         # Home/away, rest days, travel, schedule density
  ├── referee_analysis.py     # Officiating impact on game stats
  ├── correlation.py          # General-purpose stat correlation (Pearson, Spearman)
  ├── computed_fields.py      # Rest days, travel distance calculations
  └── utils.py                # Shared query builders, stat helpers
  ```
- **Data Storage:** Read-only against Postgres. No writes except through the scraper.
- **Failure Mode:** Returns empty DataFrames with warning messages for invalid queries. Does not raise exceptions to the UI layer — wraps all errors.
- **Key Design Decision:** Functions accept human-readable parameters (team names, player names) not raw IDs. The engine resolves names to IDs internally. This makes both the UI and the NLP layer simpler.

### Visualization Layer (`wnba_stats/viz/`)
- **Responsibility:** Thin translation layer that takes DataFrames from the correlation engine and produces Plotly chart objects. No data logic — purely rendering.
- **Technology:** Plotly.
- **Chart Types (must-have):**
  - `trend_line()` — rolling averages with confidence interval bands
  - `heat_map()` — 2D grid with color intensity (e.g., stat by team × quarter)
  - `scatter_correlation()` — scatter plot with regression line, R², p-value annotation
  - `split_comparison()` — grouped bar/line chart for multi-dimensional splits (e.g., Player A vs Team X, home vs away)
- **Chart Types (nice-to-have):**
  - `small_multiples()` — grid of identical charts across a dimension (teams, players)
  - `animated_timeline()` — animated scatter/line showing evolution over a season
  - `drilldown_chart()` — chart with click events that reveal game-level detail
- **Interfaces:**
  - Consumes: pandas DataFrames from the correlation engine.
  - Produces: Plotly Figure objects (rendered by Streamlit or returned as JSON).
- **Failure Mode:** Returns a placeholder "no data" chart if the DataFrame is empty.
- **Swappability:** The UI calls viz functions that return Figure objects. Replacing Plotly with Matplotlib, Altair, or any other library means rewriting this layer only — the engine and UI interfaces stay the same.

### Streamlit UI (`wnba_stats/app/`)
- **Responsibility:** Local web application providing interactive exploration of WNBA statistics. Two modes: structured exploration (dropdowns, filters, pre-built charts) and NLP chat interface.
- **Technology:** Streamlit, Plotly (via viz layer).
- **Interfaces:**
  - Consumes: correlation engine functions (for structured mode), Claude API (for NLP mode), viz layer (for chart rendering).
  - Produces: interactive web pages served locally.
- **Page Structure:**
  ```
  app/
  ├── main.py                 # Entry point, sidebar navigation
  ├── pages/
  │   ├── team_analysis.py    # Team matchup explorer
  │   ├── player_analysis.py  # Player trend/split explorer
  │   ├── game_context.py     # Context effects (rest, travel, refs)
  │   ├── correlation_lab.py  # Free-form stat-vs-stat correlation
  │   └── chat.py             # Claude API NLP interface
  └── components/
      ├── filters.py          # Reusable filter widgets (season, team, player, date range)
      └── chart_wrapper.py    # Standard chart display with download/expand options
  ```
- **Data Storage:** None. Stateless — all data comes from engine queries on each interaction.
- **Failure Mode:** Displays user-friendly error messages if engine queries fail. NLP errors show the failed SQL for debugging transparency.

### NLP Query Executor (`wnba_stats/nlp/`)
- **Responsibility:** Bridge between the Claude API and the local database. Sends natural language questions to Claude with schema context and tool definitions. Receives SQL or function calls back. Executes them. Logs everything.
- **Technology:** Python 3.x, anthropic SDK, SQLAlchemy.
- **Interfaces:**
  - Consumes: natural language question (from Streamlit chat), database schema metadata, correlation engine function signatures.
  - Produces: query results (DataFrames), optional chart objects (via viz layer), query log entries.
- **Data Storage:** Writes to query_log table (append-only).
- **Failure Mode:** If Claude generates invalid SQL, catch the database error, log it with the failed SQL and error message, and return a user-friendly error. Do not retry automatically — surface the error so the user can rephrase.
- **Security Considerations:** Claude can run arbitrary SELECT queries. The executor wraps all queries in a read-only transaction (SET TRANSACTION READ ONLY) to prevent any accidental writes. INSERT/UPDATE/DELETE statements are rejected before execution regardless of what Claude generates.
- **System Prompt Design:** Claude receives:
  - Complete table schemas with column descriptions
  - List of available correlation engine functions with parameter specs (as tool definitions)
  - Examples of common question → SQL/function mappings
  - Instruction to prefer engine functions over raw SQL when a function covers the question

### Database (`wnba_stats` Postgres database)
- **Responsibility:** Single source of truth for all WNBA statistical data.
- **Technology:** PostgreSQL 17 (local, via Homebrew).
- **Tables:** teams, players, games, player_game_stats, team_game_stats, game_officials, arenas, query_log, plus one table per external data source.
- **Views/Functions (computed data):**
  - `v_team_rest_days` — view joining games to compute days since last game per team
  - `v_team_travel_distance` — view joining games to arenas to compute distance between consecutive game cities
  - `f_haversine(lat1, lon1, lat2, lon2)` — Postgres function for great-circle distance
- **Failure Mode:** Standard Postgres crash recovery. WAL-based. Local backups via pg_dump on a weekly schedule (manual or scripted).
- **Connection:** `postgresql://localhost:5432/wnba_stats` (or via Unix socket on macOS).

## Communication Patterns

All communication is synchronous and local. No message queues, no async events, no network calls between components (only to external APIs during scraping).

```
[stats.wnba.com] ←HTTP→ [Scraper] →SQL→ [Postgres]
                                              ↑
[External APIs]  ←HTTP→ [Source Modules] →SQL→┘
                                              ↓
                                    [Correlation Engine] ←SQL (read-only)
                                              ↓
                                    [Viz Layer] (DataFrames → Plotly Figures)
                                              ↓
                                    [Streamlit UI] (renders Figures, handles user input)
                                              ↑
                                    [NLP Executor] ←HTTP→ [Claude API]
                                         ↓
                                    [query_log table] (append-only)
```

## Audit Logging Strategy

- **Purpose:** Operational debugging only. No compliance requirements.
- **Operational logs:** Python logging module, INFO level, to stdout/file. Scraper logs every API call, every upsert count, every error. Correlation engine logs query execution times.
- **NLP audit logs:** The query_log table serves as a structured audit trail for all Claude-generated SQL. This is the primary debugging tool for improving NLP accuracy over time.
- **Retention:** Logs kept indefinitely (disk space is not a concern for this data volume). query_log table grows at ~10-50 rows/day during active use.

## Error Handling Strategy

- **User-facing (Streamlit):** Display a clear message: "This query returned no results" or "Error: [brief description]. The generated SQL is shown below for debugging." No stack traces in the UI.
- **Scraper errors:** Log the error with full context (endpoint, parameters, response status/body), skip the failed item, continue processing remaining items. Summary at end of run: "Loaded X games successfully, Y failed."
- **NLP errors:** Log the question, the generated SQL, the error message, and the execution time to query_log. Display the failed SQL to the user in the chat interface so they can see what went wrong and rephrase.
- **Engine errors:** Return empty DataFrames with a warning string. Never raise exceptions to the UI layer.

## Deployment Topology

Everything runs on a single Mac (Apple Silicon):

- **Postgres 17:** Homebrew-managed service, always running (`brew services start postgresql@17`).
- **Scraper:** Invoked by macOS launchd at 10am daily during active season. Also runnable manually via CLI for historical pulls.
- **Streamlit app:** Started manually when the user wants to explore data (`streamlit run app/main.py`). Serves on localhost:8501.
- **Claude API:** Outbound HTTPS calls from the NLP executor. Requires `ANTHROPIC_API_KEY` environment variable.

No containers, no cloud services, no CI/CD. Simplest possible deployment for a single-user local tool.

## Extensibility Architecture

The system is designed with three explicit extension points, each following the same pattern: add a file in the right directory, implement a known interface, and the system discovers it automatically.

### Extension Point 1: Data Sources (`sources/`)
**Pattern:** Module-per-source with standard interface.
**How to add:** Create a new Python file in `sources/` that subclasses `DataSource` and implements `fetch()`, `load()`, and `create_table()`. The scraper's runner discovers all DataSource subclasses in the directory and calls them.
**Backlog examples:** Social media sentiment (X/Twitter API, Reddit API), betting lines (The Odds API), weather (Open-Meteo).
**Join pattern:** External sources join to the core data via date + team_id composite keys. For player-level external data (e.g., sentiment about a specific player), join via date + player_id. The DataSource interface includes a `join_keys()` method that declares how the source connects to core tables.

### Extension Point 2: Analysis Modules (`engine/`)
**Pattern:** Module-per-domain with function registry.
**How to add:** Create a new Python file in `engine/` that exposes functions decorated with `@engine_function(name, description, parameters)`. The registry auto-discovers decorated functions at startup. The NLP layer's tool definitions are generated from the registry (no manual tool definition needed). The Streamlit UI can query the registry to build dynamic page content.
**Backlog examples:** Predictive modeling module (`engine/predictions.py`) that trains scikit-learn or statsmodels models on historical data and exposes `predict_game_outcome()`, `forecast_player_performance()`, `project_season_trend()`. These functions consume the same DataFrames the correlation modules produce and return prediction DataFrames with confidence intervals.
**Key constraint:** All engine functions must accept human-readable parameters and return DataFrames. This contract is what makes the UI and NLP layers work without modification when new modules are added.

### Extension Point 3: Visualization Types (`viz/`)
**Pattern:** Function-per-chart-type.
**How to add:** Create a new function in the appropriate viz module (or a new module) that accepts a DataFrame and returns a Plotly Figure. The chart_wrapper component in the UI renders any Figure object identically.
**Backlog examples:** Prediction confidence charts, sentiment overlay on performance trends, model comparison dashboards.

### What This Means for Backlog Items

**Predictive modeling:** When ready, create `engine/predictions.py` with model training and prediction functions. Models are trained on DataFrames from the existing engine (e.g., train a logistic regression on `game_context.get_team_schedule_context()` output). Prediction results are DataFrames that flow through the existing viz layer. A new Streamlit page (`pages/predictions.py`) provides the UI. The NLP layer picks up prediction functions automatically via the registry. No changes to scraper, database, or existing engine code.

**Social media sentiment:** When ready, create `sources/social_sentiment.py` implementing the DataSource interface. It pulls from whatever API is available, normalizes to a standard schema (date, team_id or player_id, sentiment_score, source, volume), and writes to a `social_sentiment` table. The engine discovers the table and correlation functions can include sentiment as a variable. A viz function renders sentiment overlays on existing charts.

## Project Structure

```
wnba_stats/
├── docs/
│   └── design/                    # Design artifacts (this document lives here)
├── scraper/
│   ├── __init__.py
│   ├── client.py                  # HTTP client for stats.wnba.com
│   ├── endpoints.py               # Endpoint-specific fetch functions
│   ├── loaders.py                 # Database upsert functions
│   └── runner.py                  # CLI entry point and orchestration
├── sources/
│   ├── __init__.py
│   ├── base.py                    # DataSource base class / interface
│   ├── injury_reports.py          # Injury report source module
│   └── [future_source].py        # Future external sources
├── models/
│   ├── __init__.py
│   ├── base.py                    # SQLAlchemy Base, engine factory
│   ├── core.py                    # Team, Player, Game, PlayerGameStats, TeamGameStats
│   ├── officials.py               # GameOfficial
│   ├── arenas.py                  # Arena
│   └── logs.py                    # QueryLog
├── engine/
│   ├── __init__.py
│   ├── registry.py               # Auto-discovers and registers analysis modules
│   ├── base.py                    # Base class for analysis modules
│   ├── team_matchups.py
│   ├── player_trends.py
│   ├── game_context.py
│   ├── referee_analysis.py
│   ├── correlation.py
│   ├── computed_fields.py
│   └── utils.py
├── viz/
│   ├── __init__.py
│   ├── trends.py                  # trend_line, animated_timeline
│   ├── heatmaps.py                # heat_map
│   ├── scatter.py                 # scatter_correlation
│   ├── comparisons.py             # split_comparison, small_multiples
│   └── drilldown.py               # drilldown_chart
├── nlp/
│   ├── __init__.py
│   ├── executor.py                # Query execution with logging
│   ├── schema_prompt.py           # System prompt builder (schema + tools)
│   └── tools.py                   # Tool definitions for Claude API
├── app/
│   ├── main.py                    # Streamlit entry point
│   ├── pages/
│   │   ├── team_analysis.py
│   │   ├── player_analysis.py
│   │   ├── game_context.py
│   │   ├── correlation_lab.py
│   │   └── chat.py
│   └── components/
│       ├── filters.py
│       └── chart_wrapper.py
├── seeds/
│   └── arenas.json                # Static arena lat/long data
├── scripts/
│   ├── seed_arenas.py             # One-time arena seeding
│   ├── historical_pull.py         # Orchestrate multi-season historical ingestion
│   └── daily_pull.sh              # launchd-compatible daily pull script
├── tests/
│   ├── test_scraper.py
│   ├── test_engine.py
│   ├── test_viz.py
│   └── test_nlp.py
├── requirements.txt
├── README.md
└── .env.example                   # ANTHROPIC_API_KEY, DATABASE_URL
```
