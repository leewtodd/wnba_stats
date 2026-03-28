# Domain Model: WNBA Analytics Platform

## Entities

### Team
- **Description:** A WNBA franchise. Relatively static — teams occasionally relocate or rebrand but this is rare.
- **Source of Truth:** stats.wnba.com (via `leaguedashteamstats` endpoint). Seeded during historical pull, updated at start of each new season.
- **Key Attributes:**
  - `id` (Integer, PK) — WNBA Stats API team ID. Stable across seasons.
  - `full_name` (String) — e.g., "Las Vegas Aces"
  - `abbreviation` (String, unique) — e.g., "LVA"
  - `city` (String) — e.g., "Las Vegas"
  - `conference` (String) — "Eastern Conference" or "Western Conference"
  - `created_at` / `updated_at` (DateTime)
- **State Transitions:** None. Teams are reference data.
- **Testability Notes:** Verify 13 teams exist after a season pull. Verify no duplicate abbreviations.

### Player
- **Description:** A WNBA player. Pure identity record — no team affiliation. Team context is always derived from game-level data.
- **Source of Truth:** stats.wnba.com (via `playerindex` endpoint and `boxscoretraditionalv2` fallback).
- **Key Attributes:**
  - `id` (Integer, PK) — WNBA Stats API player ID. Stable across seasons.
  - `first_name` (String)
  - `last_name` (String)
  - `position` (String) — e.g., "Guard", "Forward", "Center"
  - `height` (String) — e.g., "6' 0\""
  - `weight` (String) — e.g., "157 lbs"
  - `created_at` / `updated_at` (DateTime)
- **State Transitions:** None. Players are reference data. Physical attributes may update between seasons (upsert handles this).
- **Testability Notes:** Verify player exists before inserting game stats (FK constraint). Verify no team_id on this table.

### Game
- **Description:** A single WNBA game between two teams. The central join entity — everything connects through games.
- **Source of Truth:** stats.wnba.com (via `leaguegamelog` endpoint, paired by game ID).
- **Key Attributes:**
  - `id` (String, PK) — WNBA Stats API game ID (format: "10220XXXXX"). Consistent across endpoints.
  - `game_date` (Date) — date the game was played.
  - `season` (Integer, indexed) — e.g., 2025.
  - `season_type` (String) — "Regular Season" or "Playoffs".
  - `home_team_id` (Integer, FK → teams.id)
  - `away_team_id` (Integer, FK → teams.id)
  - `home_score` (Integer)
  - `away_score` (Integer)
  - `game_status` (String) — "Final", "In Progress", "Scheduled".
  - `created_at` / `updated_at` (DateTime)
- **State Transitions:** Scheduled → In Progress → Final. For historical pulls, all games arrive as Final. For live season, games may transition.
- **Testability Notes:** Verify each game has exactly two team_game_stats rows and the expected number of player_game_stats rows. Verify home/away detection from matchup string parsing.

### PlayerGameStats
- **Description:** One player's box score for one game. The highest-granularity fact table. Team affiliation lives HERE, not on the player record — this is the trade-safety mechanism.
- **Source of Truth:** stats.wnba.com (via `boxscoretraditionalv2` endpoint, resultSets[0]).
- **Key Attributes:**
  - `id` (Integer, PK, auto-increment)
  - `player_id` (Integer, FK → players.id)
  - `game_id` (String, FK → games.id)
  - `team_id` (Integer, FK → teams.id) — **the team this player was on for THIS game**
  - `minutes` (String) — playing time
  - `points` (Integer)
  - `fgm`, `fga`, `fg_pct` (Integer, Integer, Float) — field goals
  - `fg3m`, `fg3a`, `fg3_pct` (Integer, Integer, Float) — three-pointers
  - `ftm`, `fta`, `ft_pct` (Integer, Integer, Float) — free throws
  - `oreb`, `dreb`, `reb` (Integer) — rebounds
  - `ast` (Integer) — assists
  - `stl` (Integer) — steals
  - `blk` (Integer) — blocks
  - `tov` (Integer) — turnovers
  - `pf` (Integer) — personal fouls
  - `plus_minus` (Float)
  - `created_at` (DateTime)
- **Unique Constraint:** (player_id, game_id) — one row per player per game.
- **State Transitions:** None. Stats are immutable once the game is final (though corrections can arrive via upsert).
- **Testability Notes:** Verify unique constraint prevents duplicates. Verify that a traded player's rows show different team_ids across games. Verify stat sums are reasonable (points ≤ reasonable max, minutes ≤ game length).

### TeamGameStats
- **Description:** One team's aggregate box score for one game. Pre-computed from player stats but stored separately for query performance.
- **Source of Truth:** stats.wnba.com (via `boxscoretraditionalv2` endpoint, resultSets[1]).
- **Key Attributes:** Same stat columns as PlayerGameStats, but at team level. Plus:
  - `team_id` (Integer, FK → teams.id)
  - `game_id` (String, FK → games.id)
- **Unique Constraint:** (team_id, game_id) — one row per team per game.
- **State Transitions:** None.
- **Testability Notes:** Verify exactly 2 rows per game. Verify team points match game.home_score / game.away_score.

### GameOfficial
- **Description:** Assignment of a referee to a game. Many-to-many relationship (each game has ~3 officials, each official works many games).
- **Source of Truth:** stats.wnba.com (via `boxscoresummaryv2` endpoint, "Officials" resultSet).
- **Key Attributes:**
  - `id` (Integer, PK, auto-increment)
  - `game_id` (String, FK → games.id)
  - `official_id` (Integer) — WNBA Stats API official person ID
  - `official_name` (String) — full name
  - `jersey_number` (String, nullable) — official's jersey number if available
  - `created_at` (DateTime)
- **Unique Constraint:** (game_id, official_id) — one row per official per game.
- **State Transitions:** None.
- **Testability Notes:** Verify 2-3 officials per game. Verify official_id consistency across seasons (Open Question #1).

### Arena
- **Description:** Physical venue where a team plays home games. Static seed table for travel distance computation.
- **Source of Truth:** Manual seed (one-time compilation).
- **Key Attributes:**
  - `id` (Integer, PK, auto-increment)
  - `team_id` (Integer, FK → teams.id)
  - `arena_name` (String) — e.g., "Michelob ULTRA Arena"
  - `city` (String)
  - `state` (String)
  - `latitude` (Float)
  - `longitude` (Float)
  - `season_start` (Integer) — first season at this venue
  - `season_end` (Integer, nullable) — last season at this venue (null = current)
- **State Transitions:** None. Updated manually if a team relocates.
- **Testability Notes:** Verify all 13 current teams have an arena with null season_end. Verify lat/long values are reasonable (within continental US).

### QueryLog
- **Description:** Audit trail of all SQL generated by the Claude API NLP interface.
- **Source of Truth:** Local system (written by the NLP query executor).
- **Key Attributes:**
  - `id` (Integer, PK, auto-increment)
  - `timestamp` (DateTime) — when the query was executed
  - `question_text` (Text) — the natural language question the user asked
  - `generated_sql` (Text) — the SQL Claude produced
  - `execution_time_ms` (Integer) — how long the query took
  - `row_count` (Integer, nullable) — rows returned
  - `success` (Boolean) — did it execute without error
  - `error_message` (Text, nullable) — error details if failed
  - `created_at` (DateTime)
- **State Transitions:** None. Append-only.
- **Testability Notes:** Verify every NLP query produces a log entry. Verify failed queries still get logged with error details.

## Relationships

```
teams ─────────────────────────────────┐
  │                                     │
  ├──< games.home_team_id               │
  ├──< games.away_team_id               │
  ├──< player_game_stats.team_id        │
  ├──< team_game_stats.team_id          │
  └──< arenas.team_id                   │
                                        │
players ──< player_game_stats.player_id │
                                        │
games ─┬──< player_game_stats.game_id   │
       ├──< team_game_stats.game_id     │
       └──< game_officials.game_id      │
```

- Team → Games: one-to-many (a team plays many games, as home or away)
- Team → PlayerGameStats: one-to-many (a team has many player stat rows across games)
- Team → TeamGameStats: one-to-many (a team has one stat row per game)
- Team → Arenas: one-to-many (a team may have multiple arenas across seasons)
- Player → PlayerGameStats: one-to-many (a player has one stat row per game played)
- Game → PlayerGameStats: one-to-many (a game has ~20-24 player stat rows)
- Game → TeamGameStats: one-to-two (exactly two rows per game — home and away)
- Game → GameOfficials: one-to-few (2-3 officials per game)

## Aggregate Boundaries

**Game aggregate:** A Game and its associated PlayerGameStats, TeamGameStats, and GameOfficials form a consistency boundary. When loading a box score, all four entities for that game should be committed together. A partial load (e.g., player stats without team stats) leaves the database in an inconsistent state for that game.

**Team context aggregate:** For any analytical query, the team context for a player always comes from the player_game_stats row, never from a player-level attribute. This is the core invariant that makes mid-season trades work correctly.

## Data Ownership Map

| Data Entity | Source of Truth | Consumers | Sync Mechanism |
|---|---|---|---|
| Team | stats.wnba.com | All tables (FK references), correlation engine, UI | Upsert on scraper run |
| Player | stats.wnba.com | player_game_stats (FK), correlation engine, UI | Upsert on scraper run |
| Game | stats.wnba.com (leaguegamelog) | player_game_stats, team_game_stats, game_officials (FK), correlation engine | Upsert on scraper run |
| PlayerGameStats | stats.wnba.com (boxscoretraditionalv2) | Correlation engine, UI, NLP interface | Upsert on scraper run |
| TeamGameStats | stats.wnba.com (boxscoretraditionalv2) | Correlation engine, UI, NLP interface | Upsert on scraper run |
| GameOfficial | stats.wnba.com (boxscoresummaryv2) | Correlation engine (referee analysis) | Upsert on scraper run |
| Arena | Manual seed | Correlation engine (travel distance calc) | Manual update if team relocates |
| QueryLog | Local NLP executor | Review/debugging by user | Append-only on each NLP query |
| Rest days | Computed from games table | Correlation engine | Derived on query (view or function) |
| Travel distance | Computed from games + arenas | Correlation engine | Derived on query (view or function) |
