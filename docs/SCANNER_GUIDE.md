# Scanner configuration and recovery

| Setting | Default | Meaning |
| --- | --- | --- |
| `START_SEASON` | `2021` | First season in a new dataset |
| `SPORT_IDS` | `12,13,14` | AA, High-A, Single-A |
| `REFRESH_DAYS` | `7` | Recent completed game dates refreshed once per UTC day |
| `CHECKPOINT_GAMES` | `100` | Successfully parsed games per atomic Hub commit; 1–100 |
| `MAX_GAMES_PER_RUN` | `0` | Attempt limit; zero means no count limit |
| `MAX_RUN_MINUTES` | `150` | Soft stop before fetching another box score |
| `HF_REPO_ID` | required for Hub | Dataset owner/name |
| `HF_TOKEN` | required for Hub | Write token, provided through secrets |
| `HF_PRIVATE` | `true` | Visibility only when creating a repository |

The workflow has a 180-minute hard timeout, leaving time after the 150-minute fetch budget for a final checkpoint. A slow request, retry, or upload can exceed the soft budget; the previous checkpoint remains safe if GitHub ends the job. Limits never mark an unfinished season complete.

Changing the stored scope (`START_SEASON`, `SPORT_IDS`, or game types) is rejected to prevent silently mixing incompatible progress. Use a fresh dataset or local preview directory for a different scope.

## Daily selection

1. Select the earliest uninitialized year from 2021 through the current UTC year.
2. Before a new year, reconcile any previously current year that has not been finalized.
3. Fetch final-game schedules for each selected level. Deduplicate resumed-game schedule entries by game ID.
4. Fetch missing/changed box scores; for the current year also refresh recent games.
5. Commit each batch's team files and state together.
6. Only mark a season initialized/final after every required game succeeds.
7. Advance no more than one backfill/finalization season per UTC day. After catching up, keep refreshing the current year.

The year is based on UTC, not a fixed 2026 setting. At rollover, finalizing the previous year uses that day's season slot; the new year starts on the next run. Empty current-year schedules are valid during the off-season. Empty historical coverage for any configured level is treated as an error.

## Data updates

Each refreshed game replaces all its previous player rows in the affected team tables. This removes stale rows from scoring corrections instead of only appending. The row key includes `game_pk`, so two games on the same date remain separate. Transfers appear under the team represented in that game's box score. Historical league IDs/names can differ from today's league names.

Suspended or postponed games are not collected until the schedule reports them as final. Rechecking the complete selected-season schedule catches old dates that become final. Cancelled games have no game-stat rows. An already finalized historical season is not polled indefinitely.

## Recovery

- **Network failure / upload conflict:** rerun unchanged. Hub commits use a pinned revision and reject competing writes.
- **Malformed or unavailable final box score:** inspect the game ID in logs. The scanner keeps successful games but will not advance until the missing data is resolved.
- **Re-fetch an old game deliberately:** stop concurrent jobs; in the dataset, remove only that game's entry from `state/YEAR.json` and set that year's `initialized` and `final_complete` to `false` in `state/index.json`. Wait until the next UTC day if the daily gate was already used. Retain its Parquet rows; the new game rows will replace them. Only do this for a game whose teams/league partitions have not changed; for a partition correction, preserve its old `paths` and instead replace its `signature` with `"force-refresh"`.
- **Re-fetch a finalized season:** stop jobs; set that year's `initialized` and `final_complete` to `false`, and set every game's `signature` in its state file to `"force-refresh"` while retaining `paths`. The next eligible run re-downloads that season. Do not delete data files independently of state.

Dataset README and catalog files are generated. Make persistent documentation changes in `scanner/dataset.py`, not by editing the generated Hub README.

## Modules

- `fetch.py`: retried public schedule/box-score requests; no credentials sent to MLB.
- `game_log.py` / `schema.py`: per-game extraction and typed Parquet columns.
- `state.py`: season selection and per-game refresh decisions.
- `dataset.py`: team table replacement and viewer metadata.
- `storage.py`: local storage or atomic Hugging Face commits.
- `build.py`: orchestration and checkpoints.
