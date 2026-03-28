# Requirements Brief: WNBA Analytics Platform

## Problem Statement

Build a local analytics platform that ingests WNBA game-level statistics, stores them in a relational database, computes correlations and pattern analysis across player, team, and game dimensions, and supports both structured exploration (pre-built analysis functions with a visual UI) and natural language querying (Claude API with tool use against the local database). The system covers four historical seasons (2022-2025) for baseline pattern recognition and will ingest the 2026 season daily once play begins. External data sources (referee assignments, travel distance, rest days) can be added or removed over time as their signal value is evaluated.

## Actors

- **Primary user (Lee):** Solo operator. Explores correlations, asks ad-hoc questions, reviews visualizations. Runs the system locally on a Mac (Apple Silicon) with Postgres 17. Comfortable with Python and CLIs but prefers visual/NLP interaction over writing SQL.
- **Automated scraper:** Unattended process that pulls daily game data during the active season and loads it into Postgres. Runs via macOS launchd/cron at 10am daily.
- **Claude API (tool-using agent):** Receives natural language questions, translates them into SQL or correlation engine function calls, executes against the local database, and returns answers with visualizations. All generated SQL is logged to a query_log table.

## Core Requirements

1. **Historical data ingestion:** Pull player game stats, team game stats, game results, and referee assignments from stats.wnba.com for the 2022, 2023, 2024, and 2025 seasons. Stagger pulls across multiple days to avoid rate limiting. All data stored in local Postgres 17.
2. **Current season ingestion:** When the 2026 season begins, pull data daily at 10am local time via macOS launchd. The scraper automatically detects the last successful pull date by querying the max game_date in the database and pulls everything from that date forward — no data is lost if a pull is missed.
3. **Auto-recovery:** The scraper determines its pull window dynamically: query the database for the most recent game_date, pull from that date to today. A week-long gap (vacation, laptop closed) recovers in a single run.
4. **Schema design:** Core tables: teams, players, games, player_game_stats, team_game_stats, game_officials. Player-team affiliation lives at the game level (player_game_stats.team_id), not the player level, to correctly handle mid-season trades. All loaders use upserts for idempotent re-runs.
5. **Referee data:** Pull from the `boxscoresummaryv2` endpoint on stats.wnba.com (same API, no additional external source). Store referee-to-game assignments. Enable correlation of officiating crews with foul rates, scoring patterns, and game outcomes.
6. **Derived contextual data (computed, not pulled):**
   - **Rest days:** Gap between consecutive game dates for a team. Stored as a computed column or view.
   - **Travel distance:** Great-circle distance between consecutive game city coordinates. Requires a one-time seed table of arena lat/long for all 13 WNBA teams (with historical awareness if arenas changed across 2022-2025).
7. **External data sources (pluggable architecture):**
   - Each external source is a self-contained Python module with a standard `fetch()` and `load()` interface.
   - Each source writes to its own dedicated database table.
   - Adding a source = new module + new table. Removing = stop calling it.
   - The correlation engine discovers available data by checking which tables exist and have data.
   - No changes to core engine or UI code required to add/remove a source.
   - Initial external sources: referee data (from stats.wnba.com), injury reports (from stats.wnba.com). Future candidates: betting lines (The Odds API), weather (Open-Meteo), others TBD.
8. **Correlation engine:** Python library of analytical functions that accept parameters and return DataFrames. Decoupled from any visualization layer. Covers three analysis domains:
   - **Team matchup dynamics:** Team A vs Team B performance, stylistic matchups, pace differentials, home/away splits per matchup.
   - **Player performance trends:** Fatigue/hot streaks, rest day impact, rolling averages, split analysis (Player A vs Team X at home vs away).
   - **Game context effects:** Home/away, back-to-back, schedule density, travel impact, referee crew impact on foul rates/scoring.
   - Engine functions return data (DataFrames), not charts. Visualization is a separate layer.
9. **Structured UI (Streamlit):** Local web app with dropdowns, filters, and interactive charts that call the correlation engine functions. No SQL required from the user. Swappable — the engine functions plug into any Python visualization tool if Streamlit doesn't work out.
10. **Natural language interface (Claude API with tool use):** Chat interface embedded in the Streamlit app. User types a question in plain English. Claude API receives the question along with a system prompt describing the database schema and available correlation engine functions (exposed as tools). Claude translates the question into SQL queries or engine function calls, executes them against local Postgres, and returns answers with optional visualizations.
11. **SQL query logging:** Every SQL statement generated by the Claude API NLP interface is logged to a `query_log` table with: timestamp, original question text, generated SQL, execution time (ms), row count returned, and success/error status. Enables review and improvement of the NLP layer over time.

## Visualization Requirements

### Must-Have
- **Trend lines with confidence intervals:** Rolling averages (configurable window), streak visualization, performance over time with statistical bands.
- **Heat maps:** Team/player shooting efficiency by zone, quarter, game segment, or matchup. Color-coded intensity grids.
- **Correlation scatter plots with regression lines:** Any two stats plotted against each other with fitted line, R-squared value, and p-value displayed.
- **Multi-dimensional split charts:** Player A's performance against Team X, split by home/away (or other dimensions). Bar/line hybrid.

### Nice-to-Have
- **Small multiples:** Same chart type repeated across teams or players for side-by-side comparison (e.g., all 13 teams' 3-point trends on one page).
- **Animated timeline charts:** Season-long performance animation showing how a stat evolves game by game.
- **Interactive drill-down:** Click a data point on a summary chart to see the underlying game-level detail.

### Visualization Architecture
- Charts rendered via Plotly (interactive, supports all required chart types, works in Streamlit).
- Chart generation is a thin layer that takes DataFrames from the correlation engine and renders them. Swappable independently of the engine.

## Constraints

- **Technical:**
  - Mac (Apple Silicon) as primary runtime.
  - Postgres 17 (already installed via Homebrew).
  - Python 3.x with SQLAlchemy, requests, pandas, scipy/statsmodels, plotly.
  - stats.wnba.com JSON endpoints (undocumented, no SLA, stable for years).
  - Claude API for NLP interface (requires API key, minimal cost per query).
- **Business:**
  - No hosting or deployment infrastructure. Everything runs locally.
  - Timeline: working system before the 2026 WNBA season begins (target: May 2026).
  - No budget constraints beyond Claude API usage (pennies per query).
- **Operational:**
  - Single maintainer (Lee).
  - Daily scraper at 10am local time via macOS launchd, with auto-recovery if missed.
  - No uptime requirements — personal analytics tool.

## Data Classification

- **Data categories present:** Public sports statistics.
- **Highest sensitivity level:** Public/non-sensitive.
- **Regulatory frameworks:** None.
- **Compliance implications for design:** None. Standard local machine security is sufficient.

## Extensibility Requirement

The system must be architected so that new capabilities can be added without modifying existing core code. Specifically:
- **New data sources:** Adding a data source = one new Python module (implementing the standard DataSource interface) + one new database table. No changes to engine, UI, or scraper.
- **New analysis modules:** Adding an analysis capability = one new Python module in the engine directory exposing functions that return DataFrames. The Streamlit UI picks up new pages via file-based routing. The NLP layer picks up new functions via a tool registry.
- **New visualization types:** Adding a chart type = one new function in the viz layer. The UI calls it the same way it calls existing chart functions.
- **Predictive modeling (backlog):** The engine directory must support adding ML model modules that consume the same DataFrames the correlation engine produces. Models should be trainable from the existing data and callable from both the Streamlit UI and the NLP interface. The architecture should not assume analysis is limited to descriptive statistics.
- **New external signals (backlog):** Sources like social media sentiment, betting lines, weather, etc. should plug in via the standard DataSource interface and join to games via date + team composite keys.

## Out of Scope (This Version)

- Hosted web application or public-facing website.
- Real-time live game data streaming.
- Mobile interface.
- Multi-user access or authentication.
- Historical betting odds data.

## Backlog (Next Version)

- **Predictive modeling / ML:** Build models on top of the correlation engine's output. Game outcome prediction, player performance forecasting, trend projection. The engine and data layer should be ready to support this without rearchitecting.
- **Social media sentiment analysis:** Ingest sentiment signals from public social media APIs (X/Twitter, Reddit) as an external data source module. Correlate sentiment with player/team performance. Joins to games via date + team/player.
- **Hosted web application:** Move from local-only to a hosted platform with public-facing dashboards.
- **Betting line integration:** The Odds API or similar for spread/moneyline/over-under data as a pluggable source.

## Success Criteria

1. All player game stats, team game stats, game results, and referee assignments for the 2022-2025 seasons are loaded cleanly into Postgres with zero duplicates.
2. The scraper correctly handles mid-season trades (same player appears on different teams in different games) and idempotent re-runs (no duplicates on repeated pulls).
3. The correlation engine answers multi-dimensional questions like:
   - "What is Team X's win rate on back-to-back games vs. games with 2+ days rest?"
   - "How does Player Y's scoring trend over a rolling 5-game window?"
   - "Is there a statistically significant correlation between travel distance and team shooting percentage?"
   - "How does Player A perform against Team X at home vs. away?"
   - "Do games officiated by Referee Z have higher foul rates than league average?"
4. The Streamlit UI renders interactive charts (heat maps, trend lines, scatter plots, split charts) for all three analysis domains without the user writing any code.
5. The Claude API NLP interface correctly translates a natural language question into SQL or engine function calls, executes them, and returns an accurate answer at least 80% of the time. All generated SQL is logged.
6. A new external data source can be added by creating one Python module and one database table, with no changes to core engine or UI code.
7. The scraper recovers from gaps of up to 7 days in a single run.
8. All visualization types listed as "must-have" are functional in the Streamlit UI.

## Open Questions

1. **Referee ID consistency:** Do referee IDs from `boxscoresummaryv2` stay consistent across seasons? Need to validate with a sample pull across 2022-2025.
2. **Arena coordinates:** Need a one-time seed of all WNBA arena lat/long coordinates. 13 teams, some may have changed arenas across 2022-2025. Manual compilation or geocoding pass.
3. **stats.wnba.com endpoint stability:** The API could change for the 2026 season. The scraper needs defensive parsing — log warnings on unexpected response shapes, don't crash on missing optional fields.
4. **Game ID format:** Confirm that game IDs are consistent across the `leaguegamelog`, `boxscoretraditionalv2`, and `boxscoresummaryv2` endpoints so we can join across them reliably.
