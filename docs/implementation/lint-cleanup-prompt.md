# Ruff Lint Cleanup — Implementation Prompt

## ⛔ COMPLETION GATE — Read This First
This task is not complete until EVERY item below is done.
1. ☐ All 6 E402 lines have `# noqa: E402` comments added (do NOT move these imports)
2. ☐ Both bare `except:` clauses replaced with specific exception types
3. ☐ All 3 f-strings without placeholders have `f` prefix removed
4. ☐ All F841 unused variable assignments fixed (8 total)
5. ☐ All F401 unused imports removed (26 total)
6. ☐ Both E401 multi-import lines split
7. ☐ `ruff check .` exits clean [E] — paste full output
8. ☐ `python3 -m pytest tests/ -v` — all 107 tests pass [E] — paste full output

⚠️ DO NOT ask clarifying questions. DO NOT create discovery phases. The spec is complete. Start immediately.

---

## TASK 1: Manual Fixes (E402, E722, F541, F841)

These require human judgment — do NOT let ruff auto-fix these.

### 1A: E402 — Suppress with noqa (6 lines)

These imports are intentionally below `sys.path.insert()` or adapter registration. Add `# noqa: E402` to each line. Do NOT move these imports.

**`app/main.py`** — Line 1 is also E401 (fix in Task 2). After splitting line 1, the E402 lines shift. Add noqa to these import lines that appear after `sys.path.insert`:
- `import streamlit as st` → `import streamlit as st  # noqa: E402`
- `from components.filters import season_selector` → add `# noqa: E402`
- Every `from pages import ...` line inside the page routing block does NOT need noqa — those are inside `if/elif` blocks and ruff won't flag them as E402.

**`engine/utils.py`** — Lines 11–14 are after the numpy/psycopg2 adapter registration block:
```
import logging  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from models.base import get_engine, get_session_factory  # noqa: E402
from models.core import Team, Player  # noqa: E402
```

### 1B: E722 — Bare except → specific exceptions (2 locations)

**`engine/correlation.py` line ~332** — Inside `find_strong_correlations`, the inner try/except wraps `validate_stat()`:
```python
# CURRENT (wrong):
                except:
                    pass

# REPLACE WITH:
                except ValueError:
                    pass
```

**`nlp/schema_prompt.py` line ~39** — Wraps `inspector.get_pk_constraint()`:
```python
# CURRENT (wrong):
            except:
                pass

# REPLACE WITH:
            except Exception:
                pass
```

### 1C: F541 — Remove `f` prefix from f-strings with no placeholders (3 locations)

Find and fix these. Each is an `f"..."` string that contains no `{...}` expressions. Just remove the `f` prefix. The files are:
- `engine/game_context.py` (search for f-strings with no braces)
- `scripts/verify_api.py` (around line 39)
- `scripts/verify_api_fields.py` (around line 87)

### 1D: F841 — Unused variable assignments (8 locations)

**`nlp/schema_prompt.py` line 31** — `nullable_str` is assigned but never used in the `prompt_parts.append` line below it. Delete the assignment line:
```python
# DELETE THIS LINE:
            nullable_str = "nullable" if nullable else "NOT NULL"
```

**`engine/player_trends.py` line 159** — In `player_splits()`, `player_id = resolve_player(player, session)` return value is unused (validation only). Remove variable capture:
```python
# CURRENT:
        player_id = resolve_player(player, session)

# REPLACE WITH:
        resolve_player(player, session)  # validate player exists
```

**`tests/test_engine.py` line ~223** — In `test_registry_contains_expected_modules`, `modules` is assigned but never asserted on. Delete the line:
```python
# DELETE THIS LINE:
        modules = set(f['module'] for f in funcs)
```

**`scripts/health_check.py` line ~130** — In `check_claude_api()`, the response from `client.messages.create(...)` is captured but never used. Remove variable capture:
```python
# CURRENT:
        response = client.messages.create(

# REPLACE WITH — just call without capturing:
        client.messages.create(
```
(Keep the rest of the call arguments the same.)

**`scripts/verify_api_fields.py`** — 5 unused return values from `capture_endpoint_headers()`. Prefix each with `_`:
- Line ~110: `team_headers = capture_endpoint_headers(...)` → `_team_headers = capture_endpoint_headers(...)`
- Line ~124: `player_headers = ...` → `_player_headers = ...`
- Line ~136: `gamelog_headers = ...` → `_gamelog_headers = ...`
- Line ~172: `boxscore_headers = ...` → `_boxscore_headers = ...`
- Line ~184: `summary_headers = ...` → `_summary_headers = ...`

---

## TASK 2: Auto-fixable Issues (F401, E401)

After completing Task 1, run ruff to auto-fix the remaining issues.

### 2A: E401 — Split multi-import lines (2 locations)

**`app/main.py` line 1:**
```python
# CURRENT:
import sys, os

# REPLACE WITH:
import sys
import os
```

**`scripts/check_teams.py` line 2:**
```python
# CURRENT:
import os, sys

# REPLACE WITH:
import os
import sys
```

### 2B: F401 — Remove unused imports (26 locations)

Run `ruff check --fix .` to auto-remove unused imports. Here is the complete list for verification — every one of these should be removed:

| File | Unused Import |
|---|---|
| `app/components/filters.py` | `STAT_COLUMN_MAP` |
| `app/pages/chat.py` | `pandas` (the `pd` alias) |
| `app/pages/game_context.py` | `scatter_correlation` |
| `app/pages/team_analysis.py` | `trend_line` |
| `engine/correlation.py` | `Player`, `Team` |
| `engine/game_context.py` | `Team` |
| `engine/player_trends.py` | `numpy` (the `np` alias), `and_` |
| `models/core.py` | `Boolean`, `Index` |
| `nlp/executor.py` | `inspect` |
| `scraper/runner.py` | `.client` |
| `scripts/health_check.py` | `get_session_factory` |
| `scripts/verify_api_fields.py` | `json` |
| `tests/conftest.py` | `text` |
| `tests/test_engine.py` | `engine_function`, `referee_impact` |
| `tests/test_nlp.py` | `ExecutionResult`, `get_session_factory`, `QueryLog` |
| `tests/test_scraper.py` | `get_max_game_date` |
| `viz/scatter.py` | `scipy.stats` (the `sp_stats` alias), `WNBA_TEAM_COLORS` |
| `viz/trends.py` | `pandas` (the `pd` alias) |

⚠️ After `ruff check --fix .`, run `ruff check .` again to verify zero remaining issues.

---

## TASK 3: Verify

1. Run `ruff check .` — must exit with 0 errors. Paste full output.
2. Run `python3 -m pytest tests/ -v` — all 107 tests must pass. Paste full output.
3. Run `streamlit run app/main.py` briefly to confirm it starts without import errors, then Ctrl+C.

Review the Completion Gate at the top before declaring done.
