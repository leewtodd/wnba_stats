# Design Summary: WNBA Analytics Platform

## What This System Does

A local analytics tool that ingests WNBA game-level statistics, finds correlations across player performance, team matchups, and game context, and lets you explore patterns through interactive charts or natural language questions.

## How It Works

**Data flows in one direction: API → Postgres → Engine → Charts.**

A Python scraper pulls game data from stats.wnba.com's undocumented JSON endpoints. It normalizes the response format (parallel arrays → dicts) and upserts into a local Postgres 17 database. The scraper handles four endpoints per game: team stats, player box scores, game summary, and referee assignments. It's rate-limited (1.5s between calls) and idempotent (safe to re-run).

The database has 8 tables. The critical design decision: player-team affiliation lives at the game level (player_game_stats.team_id), not on the player record. This means mid-season trades are handled correctly — the same player can show up on different teams in different games without any special logic.

Rest days and travel distance are computed, not stored. Postgres views calculate rest days from game date gaps and travel distance from arena coordinates using a haversine function.

A correlation engine (Python library) sits on top of the database. It exposes functions like `compare_teams()`, `player_trend()`, `referee_impact()`, and `correlate_stats()`. These accept human-readable parameters (team names, player names) and return DataFrames. No SQL required.

Charts are rendered by a thin Plotly layer that translates DataFrames into interactive visualizations: trend lines with confidence intervals, heat maps, scatter plots with regression lines, and multi-dimensional split charts.

A Streamlit app serves as the local UI — dropdowns, filters, and charts for structured exploration, plus a chat interface that sends natural language questions to Claude's API. Claude translates questions into SQL or engine function calls, executes them against the local database, and returns answers. All generated SQL is logged for auditability.

## Implementation Sequence

1. **Phase 1 (Week 1):** Update the database schema (add game_officials, arenas, query_log tables). Pull 2022-2025 historical data with the staggered scraper. Validate data integrity.

2. **Phase 2 (Weeks 2-3):** Build the correlation engine — start with the three analysis domains (team matchups, player trends, game context). Add referee analysis. Implement computed fields (rest days, travel distance). Seed arena coordinates.

3. **Phase 3 (Week 3-4):** Build the visualization layer and Streamlit UI. Must-have charts first: trend lines, heat maps, scatter plots, split charts. Wire up the structured exploration pages.

4. **Phase 4 (Week 4-5):** Claude API NLP integration. System prompt with schema and tool definitions. Query executor with read-only enforcement and logging. Chat interface in Streamlit.

5. **Phase 5 (Days):** Harden the scraper for daily automated runs. macOS launchd config. Auto-recovery logic (detect last game_date, pull forward).

## Key Design Decisions

| Decision | What | Why |
|---|---|---|
| No team on player | Team affiliation at game level only | Trades handled correctly, no sync issues |
| Local-only | No cloud hosting | Single user, personal tool, zero infrastructure |
| Arbitrary SQL via Claude | NLP can run any SELECT | Max flexibility, read-only enforcement prevents harm |
| Pluggable sources | One module + one table per source | Add/remove data sources without touching core code |
| Views for derived data | Rest days and travel distance computed, not stored | Always accurate, zero maintenance, fast enough at this scale |
| Streamlit + Plotly | UI and charting | Lowest friction, swappable, handles all required chart types |

## What Could Go Wrong

The main risk is stats.wnba.com changing its API format. The scraper uses defensive parsing and the community around the wehoop R package serves as an early warning system. If the API breaks, the data already in Postgres is safe — only new ingestion is affected.

Everything else is low-stakes. Missed scraper runs auto-recover. Bad NLP queries get logged for debugging. The system handles public data only, so there are no security or compliance concerns beyond standard practice.
