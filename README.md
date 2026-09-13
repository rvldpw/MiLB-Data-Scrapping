# MiLB player game logs

Collect individual game performances into a Hugging Face dataset, organized by season, league, and team. Google Sheets and Apps Script are no longer used.

## Daily behavior

On a fresh dataset, the scheduled run processes **one season per UTC day**:

| Successful daily run | Season |
| --- | --- |
| 1 | 2021 |
| 2 | 2022 |
| 3 | 2023 |
| 4 | 2024 |
| 5 | 2025 |
| 6 | 2026, through the completed games available that day |
| Following days | New, missing, changed, and recent 2026 games |

The example assumes startup during 2026. The ending year is read from the current UTC date, not hardcoded. When 2027 arrives, the scanner reconciles 2026 once, then starts 2027 on the next daily run. It waits for actual completed games during the off-season. The same rollover applies every year.

A slow or failed season can take multiple days. Progress is saved every 100 games. The next run resumes that season; it never skips to the next year because of a timeout or failed API request. Running the workflow again on the same UTC day can resume an unfinished season, but cannot advance a second season after one finishes.

## Coverage

- Regular-season games (`R`) at Double-A (12), High-A (13), and Single-A (14).
- All players with batting or pitching game statistics, including MLB veterans and players who are no longer active. The old current-prospect filter has been removed.
- One row per `(game_pk, team_id, player_id)` in each batting/pitching table. Doubleheaders remain separate games.
- Player name, position, team, opponent, historical league, game date, final team scores, and win/loss/tie.
- Batting: AB, PA, H, HR, RBI, runs, walks, strikeouts, steals, and more.
- Pitching: innings, outs, hits/runs/earned runs allowed, walks, strikeouts, pitches, and decisions when supplied.
- Additional source fields remain available in `raw_stats_json`. Unavailable statistics remain null.

This release replaces the old season-summary workbook and bio/age enrichment with game-log tables. Catchers appear in batting tables with their game position; there is no separate catcher table. It does not collect Triple-A, Rookie, postseason games, or pitch-by-pitch events.

## Dataset layout

```text
README.md                  # Generated viewer configurations and source information
catalog.json               # Season/league/team names and file paths
state/
  index.json               # Backfill queue, scope, season completion
  2021.json                # Successfully committed games for 2021
data/
  season-2021/
    league-113/
      team-402/
        batting.parquet
        pitching.parquet
```

Numeric IDs keep paths stable. League names and affiliations come from the game's season, including the league naming changes in 2021. The team catalog provides readable names. Each team has two tables for each season/league it appears in.

The folders use `season-2021`, `league-113`, and `team-402` naming so standard Parquet readers do not infer conflicting partition-column types. Every row already contains its season, league ID, and team ID.

Hugging Face stores Parquet files and provides dataset viewing; this is not a live SQL database. Batting and pitching have separate dataset configurations because their schemas differ. Each league also has its own configurations, such as `league-113-batting`.

## Setup

See [deployment instructions](docs/DEPLOY.md). In brief:

1. Put this project at the root of your GitHub repository, including `.github/workflows`.
2. Add repository variable `HF_REPO_ID` with `your-username/milb-game-logs`.
3. Add repository secret `HF_TOKEN` with a Hugging Face token allowed to write to that dataset.
4. Open **Actions → MiLB daily game logs → Run workflow**.

The workflow is configured for daily runs at **09:00 UTC / 16:00 WIB**. Hugging Face holds the persistent data and checkpoints; a fresh GitHub runner does not restart the backfill. A newly created dataset is private by default.

## Local preview

Python 3.12 is used in CI.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py --local-dir local-data --max-games 3
```

This makes real public MLB requests, writes local Parquet files, and makes no Hugging Face writes. Repeat to resume. Use a different directory with `--start-season 2024` to preview a different season. Local progress is independent of the deployed dataset. `--max-games` limits attempted box scores, not the number of schedule requests or output rows.

## Download by league or team

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="your-username/milb-game-logs",
    repo_type="dataset",
    allow_patterns=["data/season-2026/league-113/**/*.parquet", "catalog.json"],
    local_dir="eastern-league-2026",
)
```

For one team, use `data/season-2026/league-113/team-402/*.parquet`. For all seasons of a league, use `data/season-*/league-113/**/*.parquet`. Authenticate locally with `hf auth login` to access a private dataset.

To load a league as a table with the optional `datasets` library:

```python
from datasets import load_dataset

batting = load_dataset(
    "your-username/milb-game-logs",
    name="league-113-batting",
    split="train",
    token=True,  # use your saved token for a private dataset
)
```

`train` is only a dataset loading convention here. No machine-learning split has been applied. Do not sum `pitching_IP_str` as decimal numbers: `5.2` means five innings and two outs. Sum `pitching_outs` instead.

## Reliability and limitations

The schedule is rechecked for the selected season, while box scores are fetched only for missing games, changed schedule metadata/scores, and completed games in the last seven days. This catches delayed and resumed games even when their original dates are older. Historical seasons are frozen after successful completion. Corrections outside the refresh window that do not change schedule metadata require a deliberate re-fetch; see [the scanner guide](docs/SCANNER_GUIDE.md).

Data files and checkpoint state are published in the same Hugging Face commit. A concurrent update causes the commit to fail rather than overwrite another writer's progress. Only affected team tables are downloaded and rewritten. Interrupted uploads resume from the last committed batch. Missing final box scores fail visibly instead of silently marking a season complete.

The API is an external dependency; source coverage and future schema changes can affect a run. A final game with unavailable box-score data blocks that season until the source recovers or the issue is investigated. A full production backfill and authenticated Hub upload require your configured repository and token.

## Tests

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
```

Tests cover scheduling, year rollover, resume after failures, duplicate/correction handling, stable Parquet schemas, and a captured real MiLB box score.

The [samples directory](samples/README.md) includes five real 2021 games across all three supported levels. See [validation results](docs/VALIDATION.md) for what has been tested and what still requires deployment credentials.
