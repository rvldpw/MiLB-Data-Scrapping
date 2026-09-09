# scanner/ module guide

| File | Role |
|---|---|
| `config.py` | Season window, levels, env-var toggles. No network calls — safe to import anywhere. |
| `fetch.py` | All MLB Stats API access. Season totals (`pull_season_level`), bios (`fetch_player_bios`), and per-game logs (`fetch_game_logs`). |
| `metrics.py` | Derived rate stats (AVG/OBP/ERA/WHIP/etc.) computed from the raw counting stats `fetch.py` returns. |
| `sheets_sync.py` | All Google Sheets I/O, via the Apps Script Web App. Push, read-back, and the two independent completion-state helpers (`get_completed_seasons` / `mark_season_complete`, both take a `kind` so different pipelines don't collide). |
| `build.py` | Orchestrates the **season-summary** pipeline: decide what's new → pull → split into Batter/Pitcher/Catcher → sync. |
| `game_log.py` | Orchestrates the **game-by-game** pipeline. Runs after `build.py`'s season sync succeeds, reusing that run's active-player set but reading historical (player, season, level) targets back from the Sheet itself (see the module docstring for why). |

## Env vars this package reads

| Var | Default | Effect |
|---|---|---|
| `APPS_SCRIPT_URL` | *(unset)* | Sheets sync is a no-op entirely if this or the secret below is unset. |
| `APPS_SCRIPT_SECRET` | *(unset)* | Must match the `SHARED_SECRET` script property in the Apps Script project. |
| `ENRICH_WITH_BIO` | `true` | Set `false` to skip the per-player bio/age lookup and speed up a run. |
| `GAME_LOG_ENABLED` | `true` | Set `false` to skip the game-log pipeline entirely and only sync season summaries. |
| `MAX_GAMELOG_SEASONS_PER_RUN` | `1` | How many not-yet-synced *historical* game-log seasons to backfill per run. Current season is always fetched in full regardless of this value. |

## Adding a new derived stat
Add it in `metrics.py`'s `add_batting_rates` / `add_pitching_rates`, guarding any
division against a zero denominator with `np.where(denom > 0, ..., np.nan)` —
`sheets_sync.push_rows` cleans up any stray `NaN`/`inf` before the Sheets push, but
it's still the right place to keep raw box-score counts separate from computed
rates.
