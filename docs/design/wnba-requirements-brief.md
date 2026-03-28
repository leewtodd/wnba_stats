# Requirements Brief: WNBA Analytics Platform

## Problem Statement

Build a local analytics platform that ingests WNBA game-level statistics, stores them in a relational database, computes correlations and pattern analysis across player, team, and game dimensions, and supports both structured exploration (pre-built analysis functions with a visual UI) and natural language querying (Claude API with tool use). The system covers the current season with daily automated pulls and 3 seasons of historical data for baseline pattern recognition. External data sources (betting lines, travel distance, rest days, referee data, injury reports) can be added or removed over time as their signal value is evaluated.

## Actors

- **Primary user (Lee):** Solo operator. Explores correlations, asks ad-hoc questions, reviews visualizations. Runs the system locally on a Mac (Apple Silicon). Comfortable with Python and CLIs but prefers visual/NLP interaction over writing SQL.
- **Automated scraper:** Unattended process that pulls daily game data during the active season and loads it into Postgres.
- **Claude API (tool-using agent):** Receives natural language questions, translates them into SQL or correlation engine function calls, executes against the local database, and returns answers with visualizations.

## Core Requirements

1. **Historical data ingestion:** Pull player game stats, team game stats, and game results from stats.wnba.com for the 2022, 2023, and 2024 seasons. Stagger pulls across multiple days to avoid rate limiting. All data stored in local Postgres.
2. **Current season ingestion:** When the 2025 season begins (May 2026 season TBD), pull data daily. The scraper automatically detects the last successful pull date by querying the max game_date in the database and pulls everything from that date forward — no data is lost if a pull is missed.
3. **Schema design:** Five core tables (teams, players, games, player_game_stats, team_game_stats). Player-team affiliation lives at the game level, not the player level, to correctly handle mid-season trades. All loaders use upserts for idempotent re-runs.
4. **Derived contextual data:** Rest days and travel distance are computed from existing game/team data, not pulled from external sources. Rest days = gap between consecutive game dates for a team. Travel distance = great-circle distance between consecutive game city coordinates (seeded from a static arena lookup table).
5. **External data sources (pluggable):**
   - **Betting lines:** The Odds API (free tier, 500 req/month). Spreads, moneylines, over/unders.
   - **Injury reports:** stats.wnba.com injury endpoint.
   - **Referee assignments:** NBA/WNBA officials data (scrape if no API available).
   - Each external source is a self-contained Python module with a standard interface. Adding a source = new module + new table. Removing = stop calling it.
   - Architecture must support adding/removing sources without modifying core engine code.
6. **Correlation engine:** Python library of analytical functions that accept parameters and return DataFrames. Covers three analysis domains:
   - **Team matchup dynamics:** Team A vs Team B performance, stylistic matchups, pace differentials.
   - **Player performance trends:** Fatigue/hot streaks, rest day impact, rolling averages, split analysis.
   - **Game context effects:** Home/away, back-to-back, schedule density, travel impact.
   - Engine is decoupled from any visualization layer — functions return data, not charts.
7. **Structured UI (Streamlit):** Local web app with dropdowns, filters, and interactive charts that call the correlation engine functions. No SQL required. Swappable — if Streamlit doesn't work out, the engine functions plug into any other Python visualization tool.
8. **Natural language interface (Claude API):** Chat interface embedded in the Streamlit app. User types a question in plain English. Claude API receives the question with a system prompt describing the schema and available tool functions. Claude translates the question into SQL or engine function calls, executes them against local Postgres, and returns the answer with an optional visualization.
9. **Auto-recovery on missed pulls:** The scraper determines its pull window dynamically: query the database for the most recent game_date, pull from that date to today. A week-long gap recovers in a single run.

## Constraints

- **Technical:**
  - Local Mac (Apple Silicon) as primary runtime.
  - Postgres 17 (already installed via Homebrew).
  - Python 3.x with SQLAlchemy, requests, pandas, scipy/statsmodels for stats.
  - stats.wnba.com JSON endpoints (undocumented, no SLA, but stable for years).
  - Claude API for NLP interface (requires API key, minimal cost).
  - The Odds API for betting lines (free tier, 500 req/month).
- **Business:**
  - No hosting or deployment infrastructure for Phase 1. Everything runs locally.
  - No budget constraints beyond API free tiers and Claude API usage (pennies per query).
  - Timeline: working system before the next WNBA season begins (target: May 2026).
- **Operational:**
  - Single maintainer (Lee).
  - Daily scraper runs at 10am local time via macOS cron/launchd, with fallback auto-recovery if missed.
  - No uptime requirements — this is a personal analytics tool.

## Data Classification

- **Data categories present:** Public sports statistics, public betting odds.
- **Highest sensitivity level:** Public/non-sensitive.
- **Regulatory frameworks:** None.
- **Compliance implications for design:** None. No encryption requirements beyond standard practice. No access control beyond local machine security. No audit logging required.

## Out of Scope

- Hosted web application or public-facing website (deferred to a future phase).
- Real-time live game data streaming.
- Predictive modeling / ML (the correlation engine identifies patterns; building predictive models is a future phase).
- Mobile interface.
- Multi-user access or authentication.
- Social media sentiment analysis (may be added later as an external source).

## Success Criteria

1. All player game stats, team game stats, and game results for 2022-2024 seasons are loaded cleanly into Postgres with zero duplicates.
2. The scraper can pull a one-week window of data and correctly populate all five tables, including handling mid-season trades (player appears on different teams in different games).
3. The correlation engine can answer questions like:
   - "What is Team X's win rate on back-to-back games vs. games with 2+ days rest?"
   - "How does Player Y's scoring trend over a rolling 5-game window?"
   - "Is there a statistically significant correlation between travel distance and team shooting percentage?"
4. The Streamlit UI renders interactive charts for all three analysis domains without the user writing any code.
5. The Claude API NLP interface correctly translates a natural language question into a SQL query or engine function call, executes it, and returns an accurate answer at least 80% of the time.
6. A new external data source can be added by creating one Python module and one database table, with no changes to the core engine or UI code.
7. The scraper recovers gracefully from missed days — a gap of up to 7 days is fully recovered on the next successful run.

## Open Questions

1. **The Odds API game ID mapping:** How do we join betting lines to games in our database? The Odds API likely uses different game identifiers than stats.wnba.com. We'll need a matching strategy (date + team combination as a composite key).
2. **Referee data availability:** Is there a reliable, scrapable source for WNBA referee assignments per game? This needs validation before committing to it as a data source.
3. **stats.wnba.com endpoint stability:** The 2025 season may bring API changes. The scraper needs defensive parsing (log warnings on unexpected fields, don't crash on missing optional fields).
4. **Arena coordinates:** Need a one-time seed of all WNBA arena lat/long coordinates. 13 teams = 13 arenas (some may have moved across seasons). Manual compilation or a quick geocoding pass.
