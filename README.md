# WNBA Analytics Platform

Local analytics platform for WNBA game-level statistics with correlation analysis, interactive visualizations, and natural language querying via Claude API.

## Quick Start

### Prerequisites
- macOS (Apple Silicon)
- PostgreSQL 17 (`brew install postgresql@17 && brew services start postgresql@17`)
- Python 3.11+ (`brew install python3`)
- Anthropic API key (for NLP chat)

### Setup
1. Clone and install dependencies:
   ```bash
   cd /Users/leetodd/Desktop/Projects/wnba_stats
   pip3 install -r requirements.txt
   ```

2. Create the database:
   ```bash
   createdb wnba_stats
   python3 -c "from models import init_db; init_db()"
   ```

3. Seed arena data:
   ```bash
   python3 scripts/seed_arenas.py
   ```

4. Pull historical data (takes ~45 min for all 4 seasons):
   ```bash
   python3 scripts/historical_pull.py
   ```

5. Set environment variables:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

6. Launch the app:
   ```bash
   streamlit run app/main.py
   ```
   Open http://localhost:8501

## Daily Automation (Season Auto-Pull)

The scraper automatically detects the last game in the database and pulls everything since then.

### Manual auto-pull
```bash
python3 -m scraper.runner --auto
```

### Scheduled daily pull (macOS LaunchAgent)

**Note:** The plist file contains a hardcoded project path. If you move the project, update the path in `scripts/com.wnba-stats.daily-pull.plist` before installing.

```bash
cp scripts/com.wnba-stats.daily-pull.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.wnba-stats.daily-pull.plist
```

Test it immediately:
```bash
launchctl start com.wnba-stats.daily-pull
```

Check logs:
```bash
cat ~/Library/Logs/wnba-stats/daily-pull.log
```

Disable:
```bash
launchctl unload ~/Library/LaunchAgents/com.wnba-stats.daily-pull.plist
```

## Health Check

```bash
python3 scripts/health_check.py
```

Checks database connectivity, data freshness, API availability, and run history.

## Troubleshooting

| Problem | Fix |
|---|---|
| `psql: connection refused` | `brew services start postgresql@17` |
| Scraper returns 403/429 | Wait 5 minutes, try again. stats.wnba.com rate limits aggressively. |
| Off-season: `--auto` exits immediately | Expected behavior Nov-Apr. Use `--season 2025` for manual pulls. |
| Chat page shows "Set ANTHROPIC_API_KEY" | `export ANTHROPIC_API_KEY=sk-ant-...` before running Streamlit |
| Tests fail with "wnba_stats_test does not exist" | `createdb wnba_stats_test` |

## Architecture

```
stats.wnba.com -> Scraper -> PostgreSQL 17 -> Engine (26 functions) -> Viz (Plotly)
                                                                    -> Streamlit UI
                                                                    -> Claude API NLP
```

- **Scraper** (`scraper/`): Pulls from stats.wnba.com JSON endpoints with rate limiting and auto-recovery.
- **Engine** (`engine/`): 26 analysis functions (correlations, splits, matchups, trends) registered via decorators.
- **Viz** (`viz/`): Plotly chart functions translating DataFrames to interactive figures.
- **Streamlit UI** (`app/`): 5 pages -- Team Analysis, Player Analysis, Game Context, Correlation Lab, NLP Chat.
- **NLP Chat** (`nlp/`): Claude API translates natural language to SQL/function calls with full query logging.

See `docs/design/` for detailed architecture and design decisions.

## Tests

```bash
createdb wnba_stats_test  # One-time setup
python3 -m pytest tests/ -v
```
