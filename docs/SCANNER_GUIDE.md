# Scanner configuration and recovery

| Setting | Default | Meaning |
| --- | --- | --- |
| `START_SEASON` | `2021` | First season in a new dataset |
| `SPORT_IDS` | `11,12,13,14,17` | Triple-A, AA, High-A, Single-A, off-season leagues |
| `GAME_TYPES` | `R,F,D,L,W,C,P,A,E` | Regular season, every postseason round the source defines, All-Star games, exhibitions |
| `REFRESH_DAYS` | `7` | Recent completed game dates refreshed once per UTC day |
| `CHECKPOINT_GAMES` | `100` | Successfully parsed games per atomic Hub commit; 1–100 |
| `MAX_GAMES_PER_RUN` | `0` | Attempt limit; zero means no count limit |
| `MAX_RUN_MINUTES` | `150` | Soft stop before fetching another box score |
| `HF_REPO_ID` | required for Hub | Dataset owner/name |
| `HF_TOKEN` | required for Hub | Write token, provided through secrets |
| `HF_PRIVATE` | `true` | Visibility only when creating a repository |

The workflow has a 180-minute hard timeout, leaving time after the 150-minute fetch budget for a final checkpoint. A slow request, retry, or upload can exceed the soft budget; the previous checkpoint remains safe if GitHub ends the job. Limits never mark an unfinished season complete.

A wider scope is adopted in place: more `SPORT_IDS` or `GAME_TYPES`, or an earlier `START_SEASON`. Added levels or game types reopen every stored season (`initialized` and `final_complete` become `false`); per-game progress is kept, so only the games new to the scope are fetched, one season per UTC day from the earliest. A narrower scope is rejected to prevent silently mixing incompatible progress. Use a fresh dataset or local preview directory for that.

`GAME_TYPES` are MLB Stats API codes, stored unchanged in the `game_type` column. Minor-league schedules use `L` and `W` for league playoffs and `C` for the Triple-A title game; `F`, `D` and `P` are accepted so a renamed round is not lost. `A` is an All-Star game and `E` an exhibition; the source lists them only in the off-season leagues. Spring training (`S`) and intrasquad games (`I`) are not supported; the source lists none for these levels.

## Daily selection

1. Select the earliest uninitialized year from 2021 through the current UTC year.
2. Before a new year, finish the previous one. It is refreshed like the current season until 30 days after its last game (off-season leagues end in February), then reconciled once and frozen.
3. Fetch final-game schedules for each selected level and game type. Deduplicate resumed-game schedule entries by game ID.
4. Fetch missing/changed box scores; for the current year also refresh recent games.
5. Commit each batch's team files and state together.
6. Only mark a season initialized/final after every required game succeeds.
7. Advance no more than one backfill/finalization season per UTC day. After catching up, keep refreshing the current year.

The year is based on UTC, not a fixed 2026 setting. At rollover, finalizing the previous year uses that day's season slot; the new year starts on the next run. Whether a past year is still being played is read from its schedule: the last day any of its games is listed under, where days after 1 March of the following year do not count, so a stray entry cannot hold up the next season. In practice a year closes in early March, before the next season's first game. Empty current-year schedules are valid during the off-season. Empty historical coverage for any configured level is treated as an error.

## Data updates

Each refreshed game replaces all its previous player rows in the affected team tables. This removes stale rows from scoring corrections instead of only appending. The row key includes `game_pk`, so two games on the same date remain separate. Transfers appear under the team represented in that game's box score. Historical league IDs/names can differ from today's league names.

Suspended or postponed games are not collected until the schedule reports them as final. Rechecking the complete selected-season schedule catches old dates that become final. Cancelled games have no game-stat rows.

A game the source marks final without a score (cancelled, or postponed and not yet made up) is stored under `excluded_games` with the signature of its schedule entry. It is not fetched again while that entry is unchanged, and it is fetched and removed from the list when the entry changes. Records written by release 2.0 have no signature and are checked once more. An already finalized historical season is not polled indefinitely.

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
