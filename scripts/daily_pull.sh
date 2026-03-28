#!/bin/bash
# WNBA Stats Daily Pull Script
# Invoked by macOS LaunchAgent com.wnba-stats.daily-pull
# Runs the scraper in auto-recovery mode and logs the result.

set -euo pipefail

# Trap infrastructure failures (e.g., mkdir, source, python not found)
trap 'echo "[$TIMESTAMP] FAILURE (infrastructure error on line $LINENO)" >> "${RUN_LOG:-/tmp/wnba-stats-error.log}"' ERR

# Project root
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_DIR"

# Log setup
LOG_DIR="$HOME/Library/Logs/wnba-stats"
mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/daily-pull.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Source .env if it exists (for DATABASE_URL, ANTHROPIC_API_KEY)
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# Use Homebrew Python on Apple Silicon
PYTHON="/opt/homebrew/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON=$(which python3)
fi

# Run the scraper in auto mode
echo "[$TIMESTAMP] Starting daily pull..." >> "$RUN_LOG"

if $PYTHON -m scraper.runner --auto >> "$LOG_DIR/scraper-output.log" 2>&1; then
    echo "[$TIMESTAMP] SUCCESS" >> "$RUN_LOG"
else
    EXIT_CODE=$?
    echo "[$TIMESTAMP] FAILURE (exit code $EXIT_CODE)" >> "$RUN_LOG"
    # macOS notification on failure
    osascript -e 'display notification "WNBA scraper failed. Check ~/Library/Logs/wnba-stats/" with title "WNBA Stats"' 2>/dev/null || true
fi
