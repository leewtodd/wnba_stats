# Decision Log: WNBA Analytics Platform

## DEC-001: Player-Team Affiliation at Game Level
- **Date:** 2026-03-25
- **Phase:** Domain Model
- **Decision:** Player table has no team reference. Team affiliation lives on player_game_stats.team_id, capturing which team the player was on for each specific game.
- **Alternatives Considered:**
  - Player × Season snapshot (one row per player per season with team_id): Fails for mid-season trades. Player on two teams in one season produces incorrect attributions for half the season.
  - Stint-based (player × team × date range): Adds complexity and duplicates information already in the game-level data.
  - Fully denormalized (all player info on every stat row): Bloated, harder to maintain.
- **Rationale:** The game-level data already captures the correct team for each stat row. Duplicating that at the player level creates a sync problem with no upside. Queries that need "current team" can derive it from the most recent game.
- **Revisit When:** If a use case emerges that requires fast lookup of "which team is Player X on right now" without querying game stats. (Unlikely for an analytics tool.)
- **Adversarial Review Status:** Challenged. Confirmed that no analytical query in the requirements needs a player-level team reference.

## DEC-002: Local-First, No Hosting
- **Date:** 2026-03-25
- **Phase:** Architecture
- **Decision:** Entire system runs locally on a Mac. No cloud hosting, no containers, no CI/CD.
- **Alternatives Considered:**
  - VPS for scraper + Postgres: More reliable for unattended daily pulls, but adds infrastructure overhead and cost for a personal tool.
  - Docker Compose locally: Clean isolation but adds startup complexity for a single-user system.
- **Rationale:** Single user, personal tool, no uptime requirements. The auto-recovery mechanism on the scraper eliminates the main risk of local-only (missed pulls). Adding hosting later is a deployment decision, not an architecture change.
- **Revisit When:** The daily pull failure rate becomes annoying, or the system needs to serve more than one user.
- **Adversarial Review Status:** Challenged on scraper reliability. Auto-recovery mechanism (detect last game_date, pull from there to today) mitigates the risk. Accepted.

## DEC-003: Streamlit for UI
- **Date:** 2026-03-25
- **Phase:** Architecture
- **Decision:** Use Streamlit for the interactive UI. Plotly for chart rendering.
- **Alternatives Considered:**
  - Jupyter notebooks: More flexible for exploration but less app-like. Harder to build a chat interface.
  - Plotly Dash: More powerful for dashboards but higher learning curve and more boilerplate.
  - Panel/Voila: Less ecosystem support.
- **Rationale:** Lowest friction for someone who hasn't used any of these tools. Streamlit's declarative model means less code. Plotly handles all required chart types (heat maps, confidence intervals, scatter with regression, small multiples, animation). The correlation engine is decoupled from the UI, so swapping Streamlit for something else later means rewriting only the app/ directory.
- **Revisit When:** Streamlit's performance becomes a bottleneck with large DataFrames, or the chat interface needs more sophisticated UI than Streamlit supports.
- **Adversarial Review Status:** Warning raised on Streamlit's limitations for complex interactive charts (drill-down, click events). Plotly's native interactivity covers most of this. Accepted with the caveat that drill-down charts may need custom Streamlit components.

## DEC-004: Claude API for NLP with Arbitrary SQL
- **Date:** 2026-03-25
- **Phase:** Architecture
- **Decision:** Claude API can generate and execute arbitrary SELECT queries against the database. All generated SQL is logged. Writes are blocked (read-only transaction enforcement).
- **Alternatives Considered:**
  - Constrained to engine functions only: Safer but limits the "ask anything" value proposition. Many interesting questions won't map to pre-built functions.
  - SQL generation with approval step: User must approve SQL before execution. Safer but adds friction to every query.
- **Rationale:** This is a local, single-user system with public data. The risk of a bad SELECT query is a slow query or an error, not data loss or security exposure. Read-only transaction enforcement prevents any writes. Query logging provides full auditability.
- **Revisit When:** If the system ever becomes multi-user or handles sensitive data.
- **Adversarial Review Status:** Hard block concern raised on write protection. Resolved: executor wraps all queries in SET TRANSACTION READ ONLY and pre-filters for INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE keywords. Accepted.

## DEC-005: Pluggable External Data Source Architecture
- **Date:** 2026-03-25
- **Phase:** Architecture
- **Decision:** Each external data source is a self-contained Python module implementing a standard interface (fetch, load, create_table). Each source owns one database table. The correlation engine discovers available sources by checking which tables exist.
- **Alternatives Considered:**
  - Configuration-driven: YAML file listing active sources with connection params. More formal but adds a config layer that's overkill for a single-user system.
  - Monolithic scraper: All sources in one module. Simpler initially but creates coupling — a change to one source risks breaking others.
- **Rationale:** Module-per-source means adding a source is one new file. Removing is deleting the file (or just not calling it). No config files to maintain. The dynamic discovery pattern (check if table exists, query if it does) means the engine never crashes because an optional source isn't loaded.
- **Revisit When:** The number of external sources exceeds 10, at which point a registry/config pattern may be cleaner.
- **Adversarial Review Status:** Warning raised on table discovery being implicit rather than explicit. Accepted — for fewer than 10 sources, the simplicity outweighs the risk.

## DEC-006: Derived Fields (Rest Days, Travel Distance) as Views, Not Stored
- **Date:** 2026-03-25
- **Phase:** Domain Model
- **Decision:** Rest days and travel distance are computed via Postgres views/functions, not stored as columns in the games table.
- **Alternatives Considered:**
  - Store as computed columns on the games table: Faster reads but requires recomputation on every insert and creates a dependency between game insert order and correctness.
  - Compute in Python at query time: Slower for large datasets, duplicates logic across engine functions.
- **Rationale:** Postgres views execute the computation at query time, always reflect current data, and require no maintenance. At 4 seasons × ~280 games/season = ~1,120 games, the computation is trivial. A Postgres function for haversine distance keeps the math in one place.
- **Revisit When:** Query performance on derived fields becomes noticeable (unlikely at this data volume).
- **Adversarial Review Status:** No concerns raised.

## DEC-007: Game ID as String Type
- **Date:** 2026-03-25
- **Phase:** Domain Model
- **Decision:** Game ID stored as String, not Integer, in the games table.
- **Alternatives Considered:**
  - Integer: Slightly more efficient for joins and indexing.
- **Rationale:** WNBA Stats API game IDs have a specific format (e.g., "1022200034") that includes embedded metadata (league code, season, sequence). Storing as string preserves the original format and avoids any risk of integer overflow or leading-zero issues. The performance difference is negligible at this data volume.
- **Revisit When:** Never, practically.
- **Adversarial Review Status:** No concerns raised.

---

# Adversarial Review Summary

## Domain Model Review

### Hard Blocks — None identified.
- **Source of truth:** Unambiguous. Every entity has one source (stats.wnba.com or manual seed). No data is replicated across systems.
- **Data integrity:** Upserts prevent duplicates. FK constraints enforce referential integrity. Unique constraints on (player_id, game_id) and (team_id, game_id) prevent stat row duplication.
- **Security:** Public data only. No access control concerns for a local single-user system.

### Warnings — Resolved.
- **Scalability:** ~1,120 games × ~24 players/game = ~27,000 player_game_stats rows across 4 seasons. Trivial for Postgres. No index optimization needed beyond the defaults and FK indexes.
- **Complexity:** The model is lean — 8 tables (including query_log and arenas). No unnecessary abstractions.
- **Arena data staleness:** If a team changes arenas mid-season (unlikely but possible), the arena table needs a manual update. Low risk, low impact.

## Architecture Review

### Hard Blocks — Resolved.
- **stats.wnba.com dependency failure:** If the API is down during a scheduled pull, the scraper logs the failure and exits. The next run's auto-recovery catches up. No data loss. Resolved.
- **Claude API write protection:** The NLP executor could theoretically generate destructive SQL. Resolved: read-only transaction enforcement + keyword pre-filter + query logging.

### Warnings — Accepted.
- **stats.wnba.com API instability:** The API is undocumented and could change without notice. Mitigation: defensive parsing (log warnings on unexpected fields, don't crash), the wehoop R package community tracks changes and can serve as an early warning system.
- **Streamlit drill-down interactivity:** Streamlit's callback model may make complex click-to-drill-down charts awkward. Mitigation: Plotly's native hover/click interactivity covers basic cases. For deep drill-down, a custom Streamlit component may be needed. This is a nice-to-have, not a must-have.
- **Claude API cost creep:** If the user asks many NLP questions per day, costs could accumulate. At current Claude API pricing, even heavy use (50 queries/day) would be under $5/month. Accepted as non-issue.

## Known Failure Patterns Checked
- **Source of Truth Drift:** N/A — single source (stats.wnba.com), no replication.
- **Silent Dependency Failure:** Mitigated — scraper logs all API errors, auto-recovery catches up. Box score failures are per-game, logged and skipped.
- **The Missing Migration:** N/A — new system, no existing data to migrate.
- **Optimistic Concurrency Trap:** N/A — single-user system, no concurrent writes.
- **The Untestable Integration:** Mitigated — stats.wnba.com responses can be captured as JSON fixtures for test mocking.
- **Compliance Afterthought:** N/A — public data, no compliance requirements.
- **The Useless Error:** Mitigated — scraper provides per-game error details, NLP executor surfaces generated SQL on failure.
- **The Invisible Audit Gap:** N/A — no compliance logging needed. query_log covers NLP auditing.
